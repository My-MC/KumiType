"""Family archives with verified fonts, provenance and upstream licenses."""
import json
import os
from datetime import datetime, timezone
import zipfile
from pathlib import Path
from typing import Any

from fontTools.ttLib import TTFont

from .downloader import sha256
from .artifacts import atomic_output
from .validator import validate
from .config import Target
from .metadata import expected_identity
from .source_registry import locked_manifests


RUNTIME_FIELDS = frozenset(('generated_at', 'duration_seconds', 'process_peak_rss_kib'))


def packaged_manifest(manifest: dict) -> dict:
    """Project provenance onto portable content, never local storage locations.

    Source/license hashes retain input identity. Storage paths, the lock filename
    and subset filenames are execution details; actual subset inputs are also
    recorded by hash in sources/additional_licenses. Build JSON stays untouched.
    """
    excluded = RUNTIME_FIELDS | {'_project_root', 'paths', 'path', 'lock',
                                 'subset_files', 'subset_licenses'}

    def portable(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: portable(item) for key, item in value.items() if key not in excluded}
        if isinstance(value, list):
            return [portable(item) for item in value]
        return value

    result = portable(manifest)
    if 'config_sha256' in result:
        import hashlib

        result['config_sha256'] = hashlib.sha256(json.dumps(
            result['config'], sort_keys=True, separators=(',', ':'),
            ensure_ascii=False).encode()).hexdigest()
    return result


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def zip_datetime() -> tuple:
    """Use UTC, clamped to the DOS range, rounded down to two seconds."""
    raw = os.environ.get('SOURCE_DATE_EPOCH', '315532800')
    try:
        epoch = int(raw)
    except ValueError as exc:
        raise ValueError('SOURCE_DATE_EPOCH must be an integer') from exc
    epoch = min(max(epoch, 315532800), 4354819198)
    value = datetime.fromtimestamp(epoch - epoch % 2, timezone.utc)
    return value.timetuple()[:6]


def package_all(root=Path('build'), source=Path('source'), output=Path('dist'),
                lock=Path('config/sources.lock.toml')) -> list[Path]:
    groups = {}
    for path in sorted(root.rglob('*.ttf')):
        manifest_path = path.with_suffix('.json')
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not manifest['validation']['valid'] or sha256(path) != manifest['sha256']:
            raise ValueError(f'Unvalidated or modified output: {path}')
        identity = expected_identity(Target(**manifest['target']), manifest['config']['project'])
        if manifest['identity'] != identity:
            raise ValueError(f'Obsolete font naming; rebuild required: {path}')
        checked = validate(path, manifest['sources'][0]['path'],
                           project_version=manifest['config']['project'].get('version'))
        if not checked['valid']:
            raise ValueError(f'Font failed current validation: {path}: {checked["errors"]}')
        groups.setdefault(manifest['identity']['family'], []).append((path, manifest))
    output.mkdir(parents=True, exist_ok=True)
    archives = []
    for family, fonts in groups.items():
        japanese = fonts[0][1]['target']['japanese']
        licenses = []
        for record in locked_manifests(source, lock):
            manifest_path = source / record['id'] / record['version'] / 'source-manifest.json'
            if record['id'] not in ('cascadia-license', japanese, japanese + '-license'):
                continue
            for path in manifest_path.parent.rglob('*'):
                if path.is_file() and path.name.lower() in ('license', 'license.txt', 'ofl.txt'):
                    if record['format'] == 'text' and sha256(path) != record['sha256']:
                        raise ValueError(f'License checksum mismatch: {path}')
                    licenses.append((record['id'], path))
        if not any(identifier == 'cascadia-license' for identifier, _ in licenses):
            raise ValueError('Missing Cascadia license; run kumitype fetch')
        if not any(identifier.startswith(japanese) for identifier, _ in licenses):
            raise ValueError(f'Missing Japanese license: {japanese}')
        extra_licenses = {}
        for _, manifest in fonts:
            for entry in manifest.get('additional_licenses', []):
                path = Path(entry['path'])
                if sha256(path) != entry['sha256']:
                    raise ValueError(f'Additional license checksum mismatch: {path}')
                extra_licenses[entry['sha256']] = path
        destination = output / (family.replace(' ', '-') + '.zip')
        copyright_text = []
        entries = {}
        for path, manifest in fonts:
            entries[path.name] = path.read_bytes()
            entries['manifests/' + path.stem + '.json'] = json_bytes(packaged_manifest(manifest))
            with TTFont(path) as font:
                copyright_text.append(font['name'].getDebugName(0) or '')
        for identifier, path in sorted(licenses):
            entries['licenses/' + identifier + '/' + path.name] = path.read_bytes()
            provenance = next((parent / 'source-manifest.json' for parent in path.parents
                               if (parent / 'source-manifest.json').exists()), None)
            if provenance is not None:
                entries['sources/' + identifier + '.json'] = json_bytes(
                    packaged_manifest(json.loads(provenance.read_text(encoding='utf-8'))))
        for digest, path in sorted(extra_licenses.items()):
            entries['licenses/additional/' + digest[:16] + '-' + path.name] = path.read_bytes()
        versions = sorted({manifest['config']['project'].get('version', 'unknown')
                           for _, manifest in fonts})
        entries['VERSION.txt'] = ('\n'.join(versions) + '\n').encode('utf-8')
        entries['COPYRIGHT.txt'] = '\n\n'.join(sorted(set(copyright_text))).encode('utf-8')
        entries['README.txt'] = (family + '\nModified composite font built by KumiType.\n'
                               'Cascadia layout preserved; Japanese outlines added without donor hinting.\n'
                               'See manifests for versions, source URLs, settings and checksums.\n').encode('utf-8')
        timestamp = zip_datetime()
        with atomic_output(destination) as temporary:
            with zipfile.ZipFile(temporary, 'w') as archive:
                for name, payload in sorted(entries.items()):
                    info = zipfile.ZipInfo(name, date_time=timestamp)
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, payload, compresslevel=9)
        archives.append(destination)
    if not archives:
        raise ValueError('No validated generated fonts found')
    return archives
