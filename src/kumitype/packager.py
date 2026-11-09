"""Family archives with verified fonts, provenance and upstream licenses."""
import json
import zipfile
from pathlib import Path

from fontTools.ttLib import TTFont

from .downloader import sha256
from .artifacts import atomic_output
from .validator import validate
from .config import Target
from .metadata import expected_identity
from .source_registry import locked_manifests


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
        with atomic_output(destination) as temporary:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for path, manifest in fonts:
                    archive.write(path, path.name)
                    archive.write(path.with_suffix('.json'), 'manifests/' + path.stem + '.json')
                    with TTFont(path) as font:
                        copyright_text.append(font['name'].getDebugName(0) or '')
                for identifier, path in licenses:
                    archive.write(path, 'licenses/' + identifier + '/' + path.name)
                    provenance = path.parent / 'source-manifest.json'
                    if not provenance.exists():
                        provenance = next((parent / 'source-manifest.json' for parent in path.parents
                                           if (parent / 'source-manifest.json').exists()), None)
                    if provenance is not None and provenance.exists():
                        archive.write(provenance, 'sources/' + identifier + '.json')
                for digest, path in sorted(extra_licenses.items()):
                    archive.write(path, 'licenses/additional/' + digest[:16] + '-' + path.name)
                versions = sorted({manifest['config']['project'].get('version', 'unknown')
                                   for _, manifest in fonts})
                archive.writestr('VERSION.txt', '\n'.join(versions) + '\n')
                archive.writestr('COPYRIGHT.txt', '\n\n'.join(dict.fromkeys(copyright_text)))
                archive.writestr('README.txt', family + '\nModified composite font built by KumiType.\n'
                                 'Cascadia layout preserved; Japanese outlines added without donor hinting.\n'
                                 'See manifests for versions, source URLs, settings and checksums.\n')
        archives.append(destination)
    if not archives:
        raise ValueError('No validated generated fonts found')
    return archives
