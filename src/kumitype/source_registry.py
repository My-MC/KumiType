"""Pinned source records and explicit source installation."""
import json
import re
import shutil
import tomllib
from pathlib import Path

from .downloader import extract_zip, fetch, sha256
from .font_inspector import inspect_font


def load_lock(path: Path) -> list[dict]:
    with path.open('rb') as stream:
        data = tomllib.load(stream)
    records = data.get('sources', [])
    if not records:
        raise ValueError(f'{path}: source lock contains no sources')
    seen = set()
    for record in records:
        identifier = record.get('id', '')
        if not re.fullmatch(r'[a-z0-9-]+', identifier) or identifier in seen:
            raise ValueError(f'Invalid or duplicate source ID: {identifier}')
        seen.add(identifier)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', str(record.get('version', ''))) or record['version'] == 'latest':
            raise ValueError(f'{identifier}: an explicit pinned version is required')
        if not re.fullmatch(r'[a-f0-9]{64}', record.get('sha256', '')):
            raise ValueError(f'{identifier}: missing SHA-256')
        if record.get('format') not in ('zip', 'ttf', 'otf', 'text'):
            raise ValueError(f'{identifier}: unsupported source format')
    return records


def install_sources(lock: Path, source: Path, cache: Path) -> list[dict]:
    results = []
    for record in load_lock(lock):
        archive = fetch(record['url'], record['sha256'], cache)
        results.append(import_source(lock, record['id'], archive, source, cache))
    return results


def locked_manifests(source: Path, lock: Path) -> list[dict]:
    """Ignore stale installations and verify provenance against the active lock."""
    records = load_lock(lock)
    manifests = []
    for record in records:
        path = source / record['id'] / record['version'] / 'source-manifest.json'
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        if any(data.get(key) != record.get(key) for key in ('id', 'version', 'sha256', 'url')):
            raise ValueError(f'Source manifest differs from lock: {path}')
        manifests.append(data)
    return manifests


def update_lock(lock: Path, identifier: str, version: str, url: str, digest: str,
                format: str, filename: str | None = None) -> None:
    """Replace one explicitly pinned record, preserving every other source."""
    import tempfile

    from .artifacts import write_text

    records = load_lock(lock)
    record = {'id': identifier, 'version': version, 'url': url,
              'sha256': digest, 'format': format}
    if filename:
        if Path(filename).name != filename:
            raise ValueError('Source filename must be a basename')
        record['filename'] = filename
    if not url.startswith('https://'):
        raise ValueError('Source URL must use HTTPS')
    records = [item for item in records if item['id'] != identifier] + [record]
    lines = ['lock_version = 1', '']
    for item in records:
        lines.append('[[sources]]')
        lines.extend(f'{key} = {json.dumps(value, ensure_ascii=False)}' for key, value in item.items())
        lines.append('')
    text = '\n'.join(lines)
    with tempfile.TemporaryDirectory() as temporary:
        candidate = Path(temporary) / 'sources.lock.toml'
        candidate.write_text(text, encoding='utf-8')
        load_lock(candidate)
    write_text(lock, text)


def import_source(lock: Path, identifier: str, artifact: Path,
                  source: Path = Path('source'), cache: Path = Path('cache')) -> dict:
    """Import an official locked archive or font without network access."""
    record = next((item for item in load_lock(lock) if item['id'] == identifier), None)
    if record is None:
        raise ValueError(f'Source not present in lock: {identifier}')
    if sha256(artifact) != record['sha256']:
        raise ValueError(f'SHA-256 mismatch for manually placed source: {identifier}')
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / record['sha256']
    if artifact.resolve() != cached.resolve():
        shutil.copyfile(artifact, cached)
    destination = source / record['id'] / record['version']
    destination.mkdir(parents=True, exist_ok=True)
    if record['format'] == 'zip':
        extract_zip(cached, destination)
    else:
        filename = record.get('filename', identifier + '.' + record['format'])
        if Path(filename).name != filename:
            raise ValueError('Source filename must be a basename')
        shutil.copyfile(cached, destination / filename)
    fonts = []
    for path in sorted(destination.rglob('*')):
        if path.suffix.lower() in ('.ttf', '.otf'):
            info = inspect_font(path)
            info['sha256'] = sha256(path)
            fonts.append(info)
    result = {**record, 'fonts': fonts}
    from .artifacts import write_text
    write_text(destination / 'source-manifest.json', json.dumps(result, indent=2, ensure_ascii=False))
    return result


def source_status(lock: Path, source: Path) -> list[dict]:
    """Describe missing pinned inputs without fetching or stopping at the first one."""
    results = []
    for record in load_lock(lock):
        manifest_path = source / record['id'] / record['version'] / 'source-manifest.json'
        status = {'id': record['id'], 'required_version': record['version'],
                  'manifest': str(manifest_path), 'errors': []}
        if not manifest_path.exists():
            status['errors'].append('Source is not installed; fetch or import-source is required')
        else:
            try:
                data = json.loads(manifest_path.read_text(encoding='utf-8'))
                if any(data.get(key) != record.get(key) for key in ('id', 'version', 'url', 'sha256')):
                    status['errors'].append('Manifest provenance differs from lock')
                for info in data.get('fonts', []):
                    path = Path(info['path'])
                    if not path.exists():
                        status['errors'].append(f'Missing input file: {path}')
                    elif sha256(path) != info['sha256']:
                        status['errors'].append(f'Input checksum mismatch: {path}')
            except (ValueError, KeyError, OSError) as exc:
                status['errors'].append(f'Cannot inspect source manifest: {exc}')
        status['ready'] = not status['errors']
        results.append(status)
    return results
