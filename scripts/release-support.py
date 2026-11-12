#!/usr/bin/env python3
"""Offline release metadata and artifact checks used by GitHub Actions."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import tomllib
import zipfile

from kumitype.config import load, targets
from kumitype.selection import target_path


def release_matrix(config: dict) -> dict:
    ids = list(config['_font_registry'])
    if set(ids) != set(config['japanese_fonts']):
        raise ValueError('Release matrix must cover the complete font registry')
    return {'jp': ids}


def assemble(config: dict, artifacts: Path, output: Path) -> dict:
    """Restore fonts from ZIPs beside original build manifests for independent audit.

    Keep shard reports isolated, and never extract arbitrary archive paths.
    """
    paths = [target_path(output / 'build', config, target) for target in targets(config)]
    expected = {path.name: path for path in paths}
    families = {(target.base, target.japanese) for target in targets(config)}
    archives = sorted(artifacts.glob('*/dist/*.zip'))
    if len(archives) != len(families) or len({p.name for p in archives}) != len(archives):
        raise ValueError('Archive inventory differs from configured families')
    observed = set()
    dist = output / 'dist'
    dist.mkdir(parents=True, exist_ok=True)
    sums = []
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not name.endswith('.ttf'):
                    continue
                if name not in expected or name in observed:
                    raise ValueError(f'Font inventory contains unexpected/duplicate entry: {name}')
                observed.add(name)
                destination = expected[name]
                manifests = list((archive.parent.parent / 'build').rglob(destination.stem + '.json'))
                if len(manifests) != 1:
                    raise ValueError(f'Missing/ambiguous original build manifest: {name}')
                payload = z.read(name)
                if hashlib.sha256(payload).hexdigest() != json.loads(manifests[0].read_text())['sha256']:
                    raise ValueError(f'Font hash differs from original build manifest: {name}')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
                shutil.copyfile(manifests[0], destination.with_suffix('.json'))
        shutil.copyfile(archive, dist / archive.name)
        sums.append(f'{hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()}  {archive.name}\n')
    if observed != expected.keys():
        raise ValueError(f'Font inventory incomplete: missing={sorted(expected.keys() - observed)}')
    (dist / 'SHA256SUMS').write_text(''.join(sums), encoding='utf-8')
    result = {'archives': len(archives), 'fonts': len(observed)}
    (dist / 'release-inventory.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def changelog_notes(text: str, version: str, *, dry_run: bool = False) -> str:
    headings = list(re.finditer(r'^## (.+)$', text, re.MULTILINE))
    candidates = [i for i, item in enumerate(headings) if item[1].startswith(f'[{version}]')]
    if not candidates and dry_run:
        candidates = [i for i, item in enumerate(headings) if item[1] == '[Unreleased]']
    if len(candidates) != 1:
        raise ValueError(f'CHANGELOG requires exactly one section for {version}')
    index = candidates[0]
    heading = headings[index]
    if heading[1] != '[Unreleased]':
        match = re.fullmatch(rf'\[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})', heading[1])
        try:
            if match is None:
                raise ValueError('Missing release date')
            date.fromisoformat(match[1])
        except ValueError as exc:
            raise ValueError(f'Invalid CHANGELOG release heading: {heading[1]}') from exc
    end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
    body = text[heading.end():end]
    body = re.sub(r'^\[[^\]]+\]:.*$', '', body, flags=re.MULTILINE).strip()
    if not body:
        raise ValueError('Empty CHANGELOG release section')
    return body + '\n'


def check_version(tag: str, build_version: str, package_version: str) -> str:
    number = r'(?:0|[1-9][0-9]*)'
    identifier = r'(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)'
    match = re.fullmatch(rf'v({number}\.{number}\.{number})(?:-{identifier}(?:\.{identifier})*)?', tag)
    if match is None:
        raise ValueError(f'Invalid release tag: {tag!r}')
    version = match[1]
    if version != build_version or version != package_version:
        raise ValueError(f'Release version mismatch: tag={version}, build={build_version}, package={package_version}')
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'assemble'])
    parser.add_argument('--config', type=Path, default=Path('config/build.yaml'))
    parser.add_argument('--tag')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('.'))
    parser.add_argument('--artifacts', type=Path, default=Path('artifacts'))
    args = parser.parse_args()
    config = load(args.config)
    if args.command == 'assemble':
        result = assemble(config, args.artifacts, args.output)
        if result != {'archives': 42, 'fonts': 504}:
            raise ValueError(f'Release requires 42 ZIP / 504 TTF: {result}')
        print(json.dumps(result))
        return
    with Path('pyproject.toml').open('rb') as stream:
        package_version = tomllib.load(stream)['project']['version']
    if not args.tag and not args.dry_run:
        parser.error('--tag is required outside dry-run')
    version = check_version(args.tag or f'v{package_version}', config['project']['version'], package_version)
    notes = changelog_notes(Path('CHANGELOG.md').read_text(encoding='utf-8'), version, dry_run=args.dry_run)
    result = {'version': version, 'matrix': release_matrix(config)}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'release-notes.md').write_text(notes, encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
