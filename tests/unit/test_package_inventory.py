import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path


def test_package_inventory_detects_changed_font_payload(tmp_path):
    build = tmp_path / 'build'
    dist = tmp_path / 'dist'
    build.mkdir()
    dist.mkdir()
    content = b'synthetic font payload'
    manifest = {'sha256': hashlib.sha256(content).hexdigest()}
    (build / 'font.ttf').write_bytes(content)
    (build / 'font.json').write_text(json.dumps(manifest))
    script = Path(__file__).parents[2] / 'scripts/check-packages.py'
    command = [sys.executable, str(script), '--build-dir', str(build), '--dist-dir', str(dist)]
    for payload, packaged_manifest, expected in [
        (content, manifest, 0), (b'changed', manifest, 1),
        (content, {**manifest, 'japanese_weight': 123}, 1),
    ]:
        with zipfile.ZipFile(dist / 'family.zip', 'w') as archive:
            archive.writestr('font.ttf', payload)
            archive.writestr('manifests/font.json', json.dumps(packaged_manifest))
            for name in ('README.txt', 'COPYRIGHT.txt', 'VERSION.txt', 'licenses/source/OFL.txt'):
                archive.writestr(name, 'test')
        result = subprocess.run(command, capture_output=True, text=True)
        assert (result.returncode != 0) == bool(expected)
