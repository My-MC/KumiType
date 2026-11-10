"""Portable environment diagnostics."""
import importlib.metadata
import json
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import write_text
from .config import targets
from .downloader import sha256
from .metadata import WEIGHT_NAMES
from .source_registry import locked_manifests, source_status


def doctor(source=Path('source'), output=Path('build'), lock=Path('config/sources.lock.toml'),
           config=None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    sources = source_status(lock, source)
    required_errors = []
    required_ids = {row['id'] for row in sources}
    if config is not None:
        from .builder import choose_donor

        required_ids = {'cascadia', 'cascadia-license'}
        required_paths = set()
        manifests = locked_manifests(source, lock, identifiers=('cascadia', *config['japanese_fonts']))
        for japanese in config['japanese_fonts']:
            for weight in config['weights']:
                try:
                    donor, info = choose_donor(source, japanese, weight, lock)
                    required_paths.update([donor, *map(Path, info['subset_paths'])])
                except (OSError, ValueError) as exc:
                    required_errors.append(str(exc))
        for target in targets(config):
            variant = target.base.replace('-pl', 'PL').replace('-nf', 'NF')
            variant = variant[0].upper() + variant[1:]
            style = WEIGHT_NAMES[target.weight]
            if target.style == 'italic':
                style = 'Italic' if target.weight == 400 else style + 'Italic'
            required_paths.add(source / 'cascadia' / config['sources']['cascadia']['version'] /
                               'ttf/static' / f'Cascadia{variant}-{style}.ttf')
        for record in manifests:
            if any(Path(info['path']) in required_paths for info in record.get('fonts', [])):
                required_ids.add(record['id'])
        for japanese in config['japanese_fonts']:
            license_id = japanese + '-license'
            if any(row['id'] == license_id for row in sources):
                required_ids.add(license_id)
            else:
                embedded = [source / record['id'] / record['version']
                            for record in manifests if record['id'] == japanese]
                if not any(path.name.lower() in ('license', 'license.txt', 'ofl.txt')
                           for folder in embedded for path in folder.rglob('*') if path.is_file()):
                    required_errors.append(f'Missing Japanese license: {japanese}')
        known = {Path(info['path']): info for record in manifests for info in record.get('fonts', [])}
        for path in required_paths:
            if path not in known or not path.exists() or sha256(path) != known[path]['sha256']:
                required_errors.append(f'Missing or modified required font: {path}')
        # Unselected files in an installed font record are informational only.
        selected_status = source_status(lock, source, required_paths=required_paths)
        by_id = {row['id']: row for row in selected_status}
        sources = [by_id[row['id']] if row['id'] in required_ids else row for row in sources]
        for identifier in required_ids - {row['id'] for row in sources}:
            required_errors.append(f'Missing required lock record: {identifier}')
    for row in sources:
        row['required'] = row['id'] in required_ids
    return {
        'python': platform.python_version(),
        'packages': {name: importlib.metadata.version(name) for name in ('fonttools', 'PyYAML')},
        'tools': {name: shutil.which(name) for name in ('hb-shape', 'fc-scan', 'docker', 'podman')},
        'sources': sources,
        'sources_ready': not required_errors and all(record['ready'] for record in sources if record['required']),
        'required_errors': required_errors,
        'source_manifests': len(list(source.rglob('source-manifest.json'))),
        'free_disk_bytes': shutil.disk_usage(output).free,
        'output_writable': os.access(output, os.W_OK),
        'notes': ['Optional validation tools may be absent without preventing font synthesis.'],
    }


def write_build_report(outputs: list[str], errors: list[dict], root=Path('build'),
                       selection=None) -> None:
    """Emit machine-readable and reviewable summaries of completed work."""
    records = [json.loads(Path(path).with_suffix('.json').read_text(encoding='utf-8'))
               for path in outputs]
    report: dict[str, Any] = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'output_count': len(outputs), 'outputs': outputs, 'errors': errors,
              'warnings': [warning for record in records for warning in record['warnings']],
              'records': records, 'selection': selection}
    root.mkdir(parents=True, exist_ok=True)

    write_text(root / 'build-report.json', json.dumps(report, indent=2))
    lines = ['# KumiType build report', '', f"Generated: {report['generated_at']}",
             f'Output files: {len(outputs)}', f'Errors: {len(errors)}', '',
             '| Font | Imported characters | Overflow | Valid |', '| --- | ---: | ---: | --- |']
    for record in records:
        lines.append(f"| {record['identity']['postscript_name']} | "
                     f"{len(record['merge']['added_codepoints'])} | "
                     f"{len(record['merge']['overflow_codepoints'])} | "
                     f"{record['validation']['valid']} |")
    lines.extend(['', '## Selection', '', json.dumps(selection, ensure_ascii=False),
                  '', '## Warnings', ''] + report['warnings'])
    lines.extend(['', '## Errors', ''] + [str(error) for error in errors])
    write_text(root / 'build-report.md', '\n'.join(lines) + '\n')


def write_validation_report(results: list[dict], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / 'validation-report.json', json.dumps(results, indent=2))
    lines = ['# KumiType validation report', '', '| File | Binary checks | Shaping |',
             '| --- | --- | --- |']
    for result in results:
        lines.append(f"| {result['path']} | {'passed' if result['valid'] else 'failed'} | "
                     f"{result.get('shaping', {}).get('status', 'not checked')} |")
    for result in results:
        if result['errors']:
            lines.extend(['', result['path'], *['- ' + str(error) for error in result['errors']]])
    write_text(root / 'validation-report.md', '\n'.join(lines) + '\n')
