"""Portable environment diagnostics."""
import importlib.metadata
import os
import platform
import shutil
from pathlib import Path


def doctor(source=Path('source'), output=Path('build'), lock=Path('config/sources.lock.toml')) -> dict:
    from .source_registry import source_status

    output.mkdir(parents=True, exist_ok=True)
    sources = source_status(lock, source)
    return {
        'python': platform.python_version(),
        'packages': {name: importlib.metadata.version(name) for name in ('fonttools', 'PyYAML')},
        'tools': {name: shutil.which(name) for name in ('hb-shape', 'fc-scan', 'docker', 'podman')},
        'sources': sources,
        'sources_ready': all(record['ready'] for record in sources),
        'source_manifests': len(list(source.rglob('source-manifest.json'))),
        'free_disk_bytes': shutil.disk_usage(output).free,
        'output_writable': os.access(output, os.W_OK),
        'notes': ['Optional validation tools may be absent without preventing font synthesis.'],
    }


def write_build_report(outputs: list[str], errors: list[dict], root=Path('build')) -> None:
    """Emit machine-readable and reviewable summaries of completed work."""
    import json
    from datetime import datetime, timezone

    records = [json.loads(Path(path).with_suffix('.json').read_text(encoding='utf-8'))
               for path in outputs]
    report = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'output_count': len(outputs), 'outputs': outputs, 'errors': errors,
              'warnings': [warning for record in records for warning in record['warnings']],
              'records': records}
    root.mkdir(parents=True, exist_ok=True)
    from .artifacts import write_text

    write_text(root / 'build-report.json', json.dumps(report, indent=2))
    lines = ['# KumiType build report', '', f"Generated: {report['generated_at']}",
             f'Output files: {len(outputs)}', f'Errors: {len(errors)}', '',
             '| Font | Imported characters | Overflow | Valid |', '| --- | ---: | ---: | --- |']
    for record in records:
        lines.append(f"| {record['identity']['postscript_name']} | "
                     f"{len(record['merge']['added_codepoints'])} | "
                     f"{len(record['merge']['overflow_codepoints'])} | "
                     f"{record['validation']['valid']} |")
    lines.extend(['', '## Warnings', ''] + report['warnings'])
    lines.extend(['', '## Errors', ''] + [str(error) for error in errors])
    write_text(root / 'build-report.md', '\n'.join(lines) + '\n')


def write_validation_report(results: list[dict], root: Path) -> None:
    import json

    from .artifacts import write_text

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
