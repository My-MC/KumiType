"""Pinned source records and explicit source installation."""
import json
import re
import shutil
import tempfile
import tomllib
from pathlib import Path

from .artifacts import write_text
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
        if record.get('font_format', 'ttf') not in ('ttf', 'otf'):
            raise ValueError(f'{identifier}: unsupported font format')
        if record.get('format') not in ('zip', 'ttf', 'otf', 'text'):
            raise ValueError(f'{identifier}: unsupported source format')
    return records


def install_sources(lock: Path, source: Path, cache: Path) -> list[dict]:
    results = []
    for record in load_lock(lock):
        archive = fetch(record['url'], record['sha256'], cache)
        results.append(import_source(lock, record['id'], archive, source, cache))
    return results


def locked_manifests(source: Path, lock: Path, *, identifiers=None) -> list[dict]:
    """Ignore stale installations and verify provenance against the active lock."""
    records = load_lock(lock)
    manifests = []
    for record in records:
        if identifiers is not None and not any(
                record['id'] == identifier or record['id'].startswith(identifier + '-')
                for identifier in identifiers):
            continue
        path = source / record['id'] / record['version'] / 'source-manifest.json'
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        if any(data.get(key) != record.get(key) for key in ('id', 'version', 'sha256', 'url')):
            raise ValueError(f'Source manifest differs from lock: {path}')
        for info in data.get('fonts', []):
            if 'codepoint_ranges' in info:
                info['codepoints'] = [cp for start, end in info['codepoint_ranges']
                                      for cp in range(start, end + 1)]
            info['path'] = str(manifest_font_path(source, info['path']))
        manifests.append(data)
    return manifests


def manifest_font_path(source: Path, path: str) -> Path:
    """Resolve legacy project-relative manifest paths, never against cwd."""
    value = Path(path)
    if value.is_absolute():
        return value
    source = source.resolve()
    # Legacy paths include the entire configured source prefix (data/source,
    # not necessarily just source). Find the ancestor that maps that prefix
    # back onto the active installation without consulting the caller's cwd.
    for parent in source.parents:
        candidate = parent / value
        if candidate.is_relative_to(source):
            return candidate
    return source.parent / value


def update_lock(lock: Path, identifier: str, version: str, url: str, digest: str,
                format: str, filename: str | None = None) -> None:
    """Replace one explicitly pinned record, preserving every other source."""
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


def _file_hashes(destination: Path) -> dict[str, str]:
    return {str(path.relative_to(destination)): sha256(path)
            for path in sorted(destination.rglob('*'))
            if path.is_file() and path.name != 'source-manifest.json'}


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
    manifest = destination / 'source-manifest.json'
    font_format = record.get('font_format', 'otf' if record['format'] == 'otf' else 'ttf')
    try:
        previous = json.loads(manifest.read_text(encoding='utf-8'))
        if (isinstance(previous, dict) and previous.get('manifest_version') == 2
                and {key: value for key, value in previous.items()
                     if key not in ('manifest_version', 'files', 'fonts')} == record
                and isinstance(previous.get('fonts'), list)):
            files = _file_hashes(destination)
            installed_fonts = {str(manifest_font_path(source, info['path']).resolve().relative_to(
                        destination.resolve())): info['sha256'] for info in previous['fonts']}
            expected = {path: digest for path, digest in files.items()
                        if Path(path).suffix.lower() == '.' + font_format}
            if previous.get('files') == files and installed_fonts == expected:
                return previous
    except (OSError, ValueError, TypeError, KeyError):
        pass
    if record['format'] == 'zip':
        extract_zip(cached, destination)
    else:
        filename = record.get('filename', identifier + '.' + record['format'])
        if Path(filename).name != filename:
            raise ValueError('Source filename must be a basename')
        shutil.copyfile(cached, destination / filename)
    fonts = []
    for path in sorted(destination.rglob('*')):
        if path.suffix.lower() == '.' + font_format:
            info = inspect_font(path)
            info['sha256'] = sha256(path)
            ranges: list[list[int]] = []
            for cp in info.pop('codepoints'):
                if ranges and cp == ranges[-1][1] + 1:
                    ranges[-1][1] = cp
                else:
                    ranges.append([cp, cp])
            info['codepoint_ranges'] = ranges
            fonts.append(info)
    result = {**record, 'manifest_version': 2, 'files': _file_hashes(destination), 'fonts': fonts}
    write_text(destination / 'source-manifest.json', json.dumps(result, indent=2, ensure_ascii=False))
    return result


def source_status(lock: Path, source: Path, *, required_paths=None) -> list[dict]:
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
                if record['format'] == 'text':
                    files = [p for p in manifest_path.parent.rglob('*')
                             if p.is_file() and p.name != 'source-manifest.json']
                    if not files or not any(sha256(p) == record['sha256'] for p in files):
                        status['errors'].append('Missing text source or license checksum mismatch')
                for info in data.get('fonts', []):
                    path = manifest_font_path(source, info['path'])
                    if required_paths is not None and path not in required_paths:
                        continue
                    if not path.exists():
                        status['errors'].append(f'Missing input file: {path}')
                    elif sha256(path) != info['sha256']:
                        status['errors'].append(f'Input checksum mismatch: {path}')
            except (ValueError, KeyError, OSError) as exc:
                status['errors'].append(f'Cannot inspect source manifest: {exc}')
        status['ready'] = not status['errors']
        results.append(status)
    return results
