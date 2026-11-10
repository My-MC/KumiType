"""Offline single-target build orchestration."""
import hashlib
import json
import resource
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import save_font, write_text
from .config import resolve_path, targets
from .coverage import coverage_report
from .downloader import sha256
from .font_converter import load_cached_static, load_static
from .merger import merge_many
from .metadata import JP_NAMES, WEIGHT_NAMES, apply_metadata
from .outline_cache import OutlineCache
from .provenance import WORKER_PROVENANCE
from .report import write_build_report
from .resources import worker_count
from .source_registry import locked_manifests
from .validator import validate


def choose_donor(source: Path, identifier: str, weight: int, lock=Path('config/sources.lock.toml')) -> tuple[Path, dict]:
    candidates = []
    for data in locked_manifests(source, lock, identifiers=(identifier,)):
        if data['id'] != identifier and not data['id'].startswith(identifier + '-'):
            continue
        for info in data['fonts']:
            if info['italic']:
                continue
            axes = {axis['tag']: axis for axis in info['axes']}
            variable = 'wght' in axes and axes['wght']['min'] <= weight <= axes['wght']['max']
            rank = 0 if not axes and info['weight'] == weight else 1 if variable else 2
            candidates.append((rank, abs(info['weight'] - weight), info['path'], info))
    if not candidates:
        raise ValueError(f'Missing Japanese source: {identifier}; run kumitype fetch or install sources')
    _, _, path, info = min(candidates, key=lambda item: item[:3])
    info = dict(info)
    covered = set(info['codepoints'])
    subset_paths = []
    chosen_rank = min(candidates, key=lambda item: item[:3])[:2]
    for rank, distance, candidate_path, candidate in sorted(candidates, key=lambda item: item[:3]):
        if (rank, distance) != chosen_rank or candidate_path == path:
            continue
        if candidate['family'] != info['family'] or candidate['weight'] != info['weight']:
            continue
        additional = set(candidate['codepoints']) - covered
        if additional:
            if sha256(Path(candidate_path)) != candidate['sha256']:
                raise ValueError(f'Subset checksum mismatch: {candidate_path}')
            subset_paths.append(candidate_path)
            covered.update(additional)
    info['subset_paths'] = subset_paths
    if sha256(Path(path)) != info['sha256']:
        raise ValueError(f'Source checksum mismatch: {path}')
    return Path(path), info


def build_one(config: dict, target, source=None, output=None) -> Path:
    started = time.monotonic()
    paths = config.get('paths', {})
    source = resolve_path(config, source or paths.get('source', 'source'))
    output = resolve_path(config, output or paths.get('build', 'build'))
    cache = resolve_path(config, paths.get('cache', 'cache'))
    version = config['sources']['cascadia']['version']
    variant = target.base.replace('-pl', 'PL').replace('-nf', 'NF')
    variant = variant[0].upper() + variant[1:]
    style = WEIGHT_NAMES[target.weight]
    if target.style == 'italic':
        style = 'Italic' if target.weight == 400 else style + 'Italic'
    base_path = source / 'cascadia' / version / 'ttf/static' / f'Cascadia{variant}-{style}.ttf'
    if not base_path.exists():
        raise ValueError(f'Missing Cascadia {version} source: {base_path}')
    lock = resolve_path(config, config.get('sources', {}).get('lock', 'config/sources.lock.toml'))
    manifests = locked_manifests(source, lock)
    base_record = next((record for record in manifests
                        if record['id'] == 'cascadia' and record['version'] == version), None)
    base_info = next((entry for entry in base_record['fonts']
                      if Path(entry['path']) == base_path), None) if base_record else None
    if base_info is None or sha256(base_path) != base_info['sha256']:
        raise ValueError(f'Cascadia source missing or differs from locked manifest: {base_path}')
    donor_path, info = choose_donor(source, target.japanese, target.weight, lock)
    rendering = {**config.get('rendering', {}),
                 **config.get('font_overrides', {}).get(target.japanese, {})}
    if rendering.get('width_ratio', '1:2') != '1:2':
        raise ValueError('Only consistent 1:2 width rendering is currently implemented')
    if rendering.get('japanese_italic', 'upright') != 'upright':
        raise ValueError('Synthetic Japanese italic is not yet implemented')
    base = load_static(base_path, target.weight, target.style == 'italic')
    donor = load_cached_static(donor_path, target.weight, cache=cache / 'instances')
    extra_donors = []
    extra_paths = list(dict.fromkeys(Path(path) for path in [
        *info.get('subset_paths', []),
        *config.get('font_overrides', {}).get(target.japanese, {}).get('subset_files', [])]))
    try:
        unicode_overrides = {int(str(cp), 16): preference for cp, preference in
                             config.get('unicode_overrides', {}).items()}
        for path in extra_paths:
            extra_donors.append(load_cached_static(path, target.weight, cache=cache / 'instances'))
        outline_cache = None
        if not extra_donors:
            outline_cache = OutlineCache({
                'donor': sha256(donor_path), 'weight': target.weight,
                'upm': base['head'].unitsPerEm,
                'cell': base['hmtx'].metrics[base.getBestCmap()[32]][0],
                'scale': rendering.get('jp_scale', 1),
                'halfwidth_kana_scale': rendering.get('halfwidth_kana_scale', 1),
                'baseline': rendering.get('baseline_offset', 0),
                'fit_overflow': rendering.get('fit_overflow', True),
                'fit_margin': rendering.get('fit_margin', 0.02)}, root=cache / 'outlines')
        report = merge_many(base, [donor, *extra_donors],
                            halfwidth_kana_scale=rendering.get('halfwidth_kana_scale', 1), outline_cache=outline_cache, overrides=unicode_overrides, jp_scale=rendering.get('jp_scale', 1),
                       baseline_offset=rendering.get('baseline_offset', 0),
                       fit_overflow=rendering.get('fit_overflow', True),
                       fit_margin=rendering.get('fit_margin', 0.02))
        coverage = coverage_report(base.getBestCmap() or {},
                                   [font.getBestCmap() or {} for font in [donor, *extra_donors]])
        identity = apply_metadata(base, donor, target, config['project'], extra_donors)
        directory = output / config['project'].get('font_names', JP_NAMES)[target.japanese] / variant
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / (identity['postscript_name'] + '.ttf')
        validation = save_font(base, destination, lambda path: validate(path, base_path, project_version=config['project']['version']))
    finally:
        base.close()
        donor.close()
        for extra in extra_donors:
            extra.close()
    warnings = []
    if not info['axes'] and info['weight'] != target.weight:
        warnings.append(f"Nearest Japanese weight used: {info['weight']} for {target.weight}")

    if coverage['missing_sample_codepoints']:
        warnings.append(f"Missing sample characters: {coverage['missing_sample_codepoints']}")
    if report['overflow_codepoints']:
        warnings.append(f"Glyph outlines exceed cell: {len(report['overflow_codepoints'])} characters")
    if report.get('derived_halfwidth_codepoints'):
        warnings.append(f"Halfwidth kana derived from fullwidth outlines: {len(report['derived_halfwidth_codepoints'])} characters")
    warnings.append('Japanese donor hinting and IVS are not inherited')
    additional_licenses = []
    for license_path in config.get('font_overrides', {}).get(target.japanese, {}).get('subset_licenses', []):
        license_file = Path(license_path)
        additional_licenses.append({'path': str(license_file), 'sha256': sha256(license_file)})
    manifest = {'config_sha256': hashlib.sha256(json.dumps(
                    config, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
                'builder': WORKER_PROVENANCE, 'target': asdict(target), 'identity': identity, 'config': config,
                'sources': [{'path': str(p), 'sha256': sha256(p)} for p in (base_path, donor_path, *extra_paths)],
                'japanese_weight': target.weight if any(axis['tag'] == 'wght' for axis in info['axes']) else info['weight'],
                'warnings': warnings,
                'additional_licenses': additional_licenses,
                'merge': report, 'validation': validation, 'sha256': sha256(destination),
                'duration_seconds': time.monotonic() - started,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'coverage': coverage, 'output_bytes': destination.stat().st_size,
                'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    write_text(destination.with_suffix('.json'), json.dumps(manifest, indent=2))
    if not validation['valid']:
        raise ValueError(f'Generated font failed validation: {validation["errors"]}')
    return destination


def build_all(config: dict, jobs=None, source=None, output=None) -> list[str]:
    """Execute the configured matrix, never silently omitting failed targets."""
    source = resolve_path(config, source or config.get('paths', {}).get('source', 'source'))
    output = resolve_path(config, output or config.get('paths', {}).get('build', 'build'))
    settings = config.get('build', {})
    jobs = worker_count(jobs if jobs is not None else settings.get('jobs', 'auto'),
                        worker_memory_mb=settings.get('worker_memory_mb', 2048),
                        max_jobs=settings.get('max_jobs'))
    matrix = targets(config)
    results = []
    errors = []
    remaining = iter(matrix)
    stopped = False
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        pending = {}
        def submit_next():
            target = next(remaining, None)
            if target is not None:
                pending[pool.submit(build_one, config, target, source, output)] = target
        for _ in range(jobs):
            submit_next()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                target = pending.pop(future)
                try:
                    path = str(future.result())
                    results.append(path)
                    print(path, flush=True)
                except Exception as exc:
                    errors.append({'target': asdict(target), 'error': str(exc)})
                    if settings.get('fail_on_error', True):
                        stopped = True
            if not stopped:
                for _ in done:
                    submit_next()
        if stopped:
            for target in remaining:
                errors.append({'target': asdict(target), 'error': 'Not started after earlier failure'})

    write_build_report(results, errors, root=output)
    if errors:
        raise ValueError(f'{len(errors)} build errors; see {output / "build-report.json"}')
    return results
