#!/usr/bin/env python3
"""Verify ZIP payload checksums and correspondence to tracked build outputs."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from kumitype.packager import packaged_manifest

parser = argparse.ArgumentParser()
parser.add_argument('--build-dir', type=Path, default=Path('build'))
parser.add_argument('--dist-dir', type=Path, default=Path('dist'))
args = parser.parse_args()
expected = {path.name for path in args.build_dir.rglob('*.ttf') if path.with_suffix('.json').exists()}
observed = set()
archives = sorted(args.dist_dir.glob('*.zip'))
for path in archives:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f'ZIP checksum failure: {path}')
        names = archive.namelist()
        for required in ('README.txt', 'COPYRIGHT.txt', 'VERSION.txt'):
            if required not in names:
                raise ValueError(f'Missing {required}: {path}')
        if not any(name.startswith('licenses/') for name in names):
            raise ValueError(f'Missing licenses: {path}')
        for name in names:
            if not name.endswith('.ttf'):
                continue
            if name in observed:
                raise ValueError(f'Duplicate font: {name}')
            observed.add(name)
            manifest = json.loads(archive.read('manifests/' + Path(name).stem + '.json'))
            matches = list(args.build_dir.rglob(Path(name).stem + '.json'))
            if len(matches) != 1 or packaged_manifest(json.loads(matches[0].read_text(encoding='utf-8'))) != manifest:
                raise ValueError(f'Packaged manifest differs from build manifest: {name}')
            if hashlib.sha256(archive.read(name)).hexdigest() != manifest['sha256']:
                raise ValueError(f'Font hash differs: {name}')
if observed != expected or not archives:
    raise ValueError(f'Package set differs: missing={sorted(expected-observed)}, extra={sorted(observed-expected)}')
print(f'Checked {len(archives)} archives, {len(observed)} fonts')
