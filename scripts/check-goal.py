#!/usr/bin/env python3
"""Evidence-based acceptance gates. Only stdout contains the final JSON document."""
import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from fontTools.ttLib import TTFont, newTable

from kumitype.builder import build_one
from kumitype.config import JAPANESE_FONTS, Target, load
from kumitype.metadata import JP_NAMES, expected_identity, font_revision, metadata_errors
from kumitype.packager import package_all
from kumitype.validator import validate

ROOT = Path(__file__).resolve().parents[1]
GOALS = tuple(f'G{i}' for i in range(1, 8))


def outcome(ok, evidence):
    return {'status': 'PASS' if ok else 'FAIL', 'evidence': evidence}


def select_goals(value):
    selected = list(dict.fromkeys(value.split(',')))
    if not selected or any(item not in GOALS for item in selected):
        raise argparse.ArgumentTypeError('Expected comma-separated G1 through G7')
    return selected


def subset_targets():
    return [Target(base, jp, weight, style)
            for base in ('code-nf', 'mono') for jp in JAPANESE_FONTS
            for weight, style in ((400, 'normal'), (700, 'italic'))]


def command(args, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=3600)
    return {'command': list(map(str, args)), 'returncode': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def check_g1():
    evidence = [command(['uv', 'run', '--locked', 'pytest']),
                command(['uv', 'run', '--locked', 'ruff', 'check', 'src', 'tests', 'scripts'])]
    return outcome(all(item['returncode'] == 0 for item in evidence), evidence)


def output_path(root, config, target):
    variant = target.base.replace('-nf', 'NF')
    variant = variant[0].upper() + variant[1:]
    return (root / config['project'].get('font_names', JP_NAMES)[target.japanese] / variant /
            (expected_identity(target, config['project'])['postscript_name'] + '.ttf'))


def ensure_subset(root, config, reuse=False):
    paths = []
    for target in subset_targets():
        path = output_path(root, config, target)
        if not reuse and not (path.is_file() and path.with_suffix('.json').is_file()):
            # Run each build with a repository cwd so existing source manifests stay valid.
            import os
            previous = Path.cwd()
            try:
                os.chdir(ROOT)
                with redirect_stdout(sys.stderr):
                    path = build_one(config, target, Path('source'), root)
            finally:
                os.chdir(previous)
        if not path.is_file() or not path.with_suffix('.json').is_file():
            raise ValueError(f'Missing subset output/manifest: {path}')
        manifest = json.loads(path.with_suffix('.json').read_text())
        if manifest['target'] != asdict(target):
            raise ValueError(f'Subset target mismatch: {path}')
        if manifest['config'] != config:
            raise ValueError(f'Stale configuration in output: {path}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sha256']:
            raise ValueError(f'Output checksum mismatch: {path}')
        paths.append(path)
    # Inspect extra outputs too: G2 must not silently ignore a bad font in build-dir.
    return sorted(set(paths) | {p for p in root.rglob('*.ttf')
                                if not p.name.startswith('.font-')})


def check_g2(paths, config):
    evidence = []
    ok = bool(paths)
    for path in paths:
        with TTFont(path, recalcTimestamp=False) as font:
            errors = metadata_errors(font, config['project']['version'])
            evidence.append({'path': str(path), 'DSIG': 'DSIG' in font,
                             'ulCodePageRange1': font['OS/2'].ulCodePageRange1,
                             'jis_bit17': bool(font['OS/2'].ulCodePageRange1 & (1 << 17)),
                             'fontRevision': font['head'].fontRevision,
                             'expectedRevision': font_revision(config['project']['version']),
                             'achVendID': font['OS/2'].achVendID, 'errors': errors})
            ok &= not errors
    return outcome(ok, evidence or ['No generated fonts'])


def synthetic_font(version):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from kumitype.metadata import apply_metadata

    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(['.notdef', 'space'])
    builder.setupCharacterMap({32: 'space'})
    builder.setupGlyf({name: TTGlyphPen(None).glyph() for name in ('.notdef', 'space')})
    builder.setupHorizontalMetrics({name: (500, 0) for name in ('.notdef', 'space')})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': 'Synthetic', 'styleName': 'Regular',
                            'psName': 'Synthetic-Regular', 'fullName': 'Synthetic Regular'})
    builder.setupOS2()
    builder.setupPost()
    builder.setupMaxp()
    font = builder.font
    apply_metadata(font, font, Target('mono', 'biz', 400, 'normal'),
                   {'name': 'KumiType', 'version': version})
    return font


def check_g3(directory, version='0.1.0'):
    evidence = []
    for violation in ('DSIG', 'ulCodePageRange1', 'fontRevision', 'achVendID'):
        font = synthetic_font(version)
        path = directory / f'{violation}.ttf'
        font.save(path)
        control = validate(path, project_version=version)
        if violation == 'DSIG':
            font['DSIG'] = newTable('DSIG')
            font['DSIG'].ulVersion, font['DSIG'].usFlag = 1, 0
            font['DSIG'].usNumSigs, font['DSIG'].signatureRecords = 0, []
        elif violation == 'ulCodePageRange1':
            font['OS/2'].ulCodePageRange1 &= ~(1 << 17)
        elif violation == 'fontRevision':
            font['head'].fontRevision += 1
        else:
            font['OS/2'].achVendID = 'TEST'
        font.save(path)
        font.close()
        result = validate(path, project_version=version)
        detected = control['valid'] and not result['valid'] and any(
            violation in error for error in result['errors'])
        evidence.append({'violation': violation, 'control_valid': control['valid'],
                         'detected': detected, 'errors': result['errors']})
    return outcome(all(item['detected'] for item in evidence), evidence)


def check_g4(paths):
    evidence = []
    for path in paths:
        manifest = json.loads(path.with_suffix('.json').read_text())
        overflow, errors = [], []
        with TTFont(path) as font:
            cmap = font.getBestCmap() or {}
            declared = set(manifest['merge']['added_codepoints'])
            # Imported glyphs have a reserved prefix assigned by merger.merge().
            imported_names = {name for name in font.getGlyphOrder() if name.startswith('kumitype.u')}
            binary_cps = {cp for cp, name in cmap.items() if name in imported_names}
            if binary_cps - declared:
                errors.append('Imported binary codepoints missing from manifest')
            for cp in sorted(declared):
                if cp not in cmap:
                    errors.append(f'Missing imported character U+{cp:04X}')
            names = imported_names | {cmap[cp] for cp in declared if cp in cmap}
            if not names:
                errors.append('No imported glyphs to inspect')
            for name in sorted(names):
                glyph = font['glyf'][name]
                glyph.recalcBounds(font['glyf'])
                width = getattr(glyph, 'xMax', 0) - getattr(glyph, 'xMin', 0)
                advance = font['hmtx'][name][0]
                if width > advance:
                    overflow.append({'glyph': name, 'width': width, 'advance': advance})
        evidence.append({'path': str(path), 'imported': len(names), 'errors': errors,
                         'overflow_count': len(overflow), 'overflow': overflow})
    return outcome(bool(paths) and not any(e['overflow_count'] or e['errors'] for e in evidence), evidence)


def compare_artifacts(first, second):
    def inventory(root):
        return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.suffix in ('.ttf', '.zip')}
    a, b = inventory(first), inventory(second)
    both_formats = all(any(Path(p).suffix == ext for p in a) for ext in ('.ttf', '.zip'))
    differences = {p: {'first': a.get(p), 'second': b.get(p)}
                   for p in sorted(a.keys() | b.keys()) if a.get(p) != b.get(p)}
    return outcome(both_formats and a == b,
                   {'first': a, 'second': b, 'differences': differences,
                    'both_formats': both_formats})


def check_g5(config):
    import os

    with tempfile.TemporaryDirectory(prefix='kumitype-repro-') as temporary:
        root = Path(temporary)
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            # Identical output paths in both runs; snapshots contain only deliverables.
            work = root / 'work'
            snapshots = []
            for run in range(2):
                import shutil
                if work.exists():
                    shutil.rmtree(work)
                fonts = work / 'fonts'
                ensure_subset(fonts, config)
                package_all(root=fonts, source=Path('source'), output=work / 'packages')
                snapshot = root / str(run)
                shutil.copytree(work, snapshot)
                snapshots.append(snapshot)
                time.sleep(2)  # Expose wall-clock timestamps, including ZIP's two-second granularity.
            return compare_artifacts(*snapshots)
        finally:
            os.chdir(previous)


def check_g6(config):
    """Probe CLI contracts from an unrelated cwd without touching installed sources."""
    import copy
    import yaml

    with tempfile.TemporaryDirectory(prefix='kumitype-cli-') as temporary:
        root = Path(temporary)
        custom = copy.deepcopy(config)
        custom.update(variants=['mono'], japanese_fonts=['biz'], weights=[400], styles=['normal'])
        custom['sources']['lock'] = str(root / 'canary-missing-lock.toml')
        cfg = root / 'build.yaml'
        cfg.write_text(yaml.safe_dump(custom))
        cache = root / 'custom-cache'
        evidence = []
        # All public commands must accept cache-dir (including inspection commands).
        commands = ('list', 'doctor', 'fetch', 'build', 'build-all', 'validate',
                    'package', 'audit', 'import-source', 'update-source')
        for name in commands:
            probe = command([sys.executable, '-m', 'kumitype.cli', '--config', str(cfg),
                             name, '--help'], cwd=root)
            probe['cache_option'] = '--cache-dir' in probe['stdout']
            evidence.append(probe)
        if all(e['cache_option'] for e in evidence):
            # Supply one real, validated family for package's lock lookup. An
            # empty build-dir would fail before the configured lock is touched.
            import os
            previous = Path.cwd()
            try:
                os.chdir(ROOT)
                with redirect_stdout(sys.stderr):
                    build_one(config, Target('mono', 'biz', 400, 'normal'),
                              Path('source'), root / 'real-input')
            finally:
                os.chdir(previous)
        # Canary must come from configuration, not a default/CLI lock; doctor may
        # report errors in JSON without a failing exit status.
        for args in (['doctor'], ['fetch', '--source-dir', str(root / 'source'),
                                   '--cache-dir', str(cache)],
                     ['build', '--base', 'mono', '--jp', 'biz',
                      '--source-dir', str(ROOT / 'source'), '--output-dir', str(root / 'fonts'),
                      '--cache-dir', str(cache)],
                     ['build-all', '--jobs', '1', '--source-dir', str(ROOT / 'source'),
                      '--output-dir', str(root / 'fonts'), '--cache-dir', str(cache)],
                     ['package', '--all', '--source-dir', str(ROOT / 'source'),
                      '--build-dir', str(root / 'real-input'), '--output-dir', str(root / 'packages'),
                      '--cache-dir', str(cache)],
                     ['import-source', '--id', 'canary', '--file', str(cfg), '--cache-dir', str(cache)],
                     ['update-source', '--id', 'canary', '--version', '1',
                      '--url', 'https://example.invalid/canary', '--sha256', '0' * 64,
                      '--format', 'text', '--cache-dir', str(cache)]):
            probe = command([sys.executable, '-m', 'kumitype.cli', '--config', str(cfg), *args], root)
            report = root / 'fonts/build-report.json'
            report_text = report.read_text() if report.is_file() and args[0] == 'build-all' else ''
            probe['configured_lock_observed'] = 'canary-missing-lock.toml' in (
                probe['stdout'] + probe['stderr'] + report_text)
            evidence.append(probe)
        listing = command([sys.executable, '-m', 'kumitype.cli', '--config',
                           str(ROOT / 'config/build.yaml'), 'list', '--json'], root)
        listing['external_cwd_ok'] = listing['returncode'] == 0
        evidence.append(listing)
        options = all(e.get('cache_option', True) for e in evidence)
        locks = all(e.get('configured_lock_observed', True) for e in evidence)
        # Do not claim cache routing is proven by argparse alone. Once options
        # and canary work, exercise a real build into an initially empty cache.
        if options and locks:
            probe = command([sys.executable, '-m', 'kumitype.cli', '--config',
                             str(ROOT / 'config/build.yaml'), 'build', '--base', 'mono',
                             '--jp', 'biz', '--source-dir', str(ROOT / 'source'),
                             '--output-dir', str(root / 'real'), '--cache-dir', str(cache)], root)
            probe['custom_cache_populated'] = cache.exists() and any(cache.rglob('*'))
            evidence.append(probe)
            cache_ok = probe['returncode'] == 0 and probe['custom_cache_populated']
        else:
            cache_ok = False
        return outcome(options and locks and listing['external_cwd_ok'] and cache_ok, evidence)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', type=select_goals, default=list(GOALS))
    parser.add_argument('--build-dir', type=Path, default=ROOT / 'build-check')
    parser.add_argument('--reuse', action='store_true', help='Require existing complete subset; do not rebuild')
    args = parser.parse_args(argv)
    root = args.build_dir.resolve()
    config = load(ROOT / 'config/build.yaml')
    results = {}
    paths, build_error = None, None
    for goal in args.only:
        try:
            if goal in ('G2', 'G4') and paths is None and build_error is None:
                try:
                    paths = ensure_subset(root, config, args.reuse)
                except Exception as exc:
                    build_error = f'{type(exc).__name__}: {exc}'
            if goal == 'G1':
                result = check_g1()
            elif goal in ('G2', 'G4'):
                result = (outcome(False, [build_error]) if build_error else
                          check_g2(paths, config) if goal == 'G2' else check_g4(paths))
            elif goal == 'G3':
                with tempfile.TemporaryDirectory(prefix='kumitype-invalid-') as temporary:
                    result = check_g3(Path(temporary), config['project']['version'])
            elif goal == 'G5':
                result = check_g5(config)
            elif goal == 'G6':
                result = check_g6(config)
            else:
                result = {'status': 'PENDING', 'evidence': ['fontbakery gate is not implemented yet']}
        except Exception as exc:
            result = outcome(False, [f'{type(exc).__name__}: {exc}'])
        results[goal] = result
    report = {'schema_version': 1, 'build_dir': str(root), 'subset_expected': len(subset_targets()),
              'goals': results}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(any(result['status'] == 'FAIL' for result in results.values()))


if __name__ == '__main__':
    raise SystemExit(main())
