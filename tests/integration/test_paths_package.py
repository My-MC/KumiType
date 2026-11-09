"""Exercise public commands with synthetic, pinned fonts outside project cwd."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from test_merge import make_font
from kumitype.cli import main
from kumitype.font_inspector import inspect_font


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    records = []
    for identifier, filename, mapping in [
        ('cascadia', 'ttf/static/CascadiaMono-Regular.ttf', {65: 'a'}),
        ('biz', 'donor.ttf', {0x3042: 'kana', **{cp: f'half{cp}' for cp in range(0xFF61, 0xFFA0)}}),
        ('cascadia-license', 'LICENSE', None), ('biz-license', 'OFL.txt', None),
    ]:
        path = root / 'source' / identifier / '1' / filename
        path.parent.mkdir(parents=True)
        if mapping is None:
            path.write_text(identifier + ' license')
        else:
            with make_font(mapping) as font:
                font.save(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record = dict(id=identifier, version='1', url='https://example.org/' + identifier,
                      sha256=digest, format='text' if mapping is None else 'ttf')
        records.append(record)
        fonts = []
        if mapping is not None:
            info = inspect_font(path)
            # Legacy installations used project-relative paths.
            info['path'] = str(path.relative_to(root))
            fonts = [{**info, 'sha256': digest}]
        (root / 'source' / identifier / '1/source-manifest.json').write_text(
            json.dumps({**record, 'fonts': fonts}))
    (root / 'pins.toml').write_text('\n'.join('[[sources]]\n' + '\n'.join(
        f'{key}={json.dumps(value)}' for key, value in record.items()) for record in records))
    config = dict(project=dict(name='KumiType', version='0.1.0'),
                  sources=dict(cascadia=dict(version='1'), lock='pins.toml'),
                  variants=['mono'], japanese_fonts=['biz'], weights=[400], styles=['normal'],
                  paths=dict(cache='configured-cache'))
    (root / 'build.yaml').write_text(yaml.safe_dump(config))
    return root


def invoke(monkeypatch, project, *args):
    monkeypatch.setattr('sys.argv', ['kumitype', '--config', str(project / 'build.yaml'), *args])
    return main()


def test_external_cwd_build_validate_package_routes_cache(project, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert invoke(monkeypatch, project, 'build', '--base', 'mono', '--jp', 'biz',
                  '--cache-dir', 'chosen-cache') == 0
    assert list((project / 'chosen-cache/instances').glob('*.ttf'))
    assert list((project / 'chosen-cache/outlines').glob('*.json'))
    assert not (tmp_path / 'cache').exists()
    assert not (project / 'configured-cache').exists()
    assert invoke(monkeypatch, project, 'validate', '--all') == 0
    assert invoke(monkeypatch, project, 'package', '--all') == 0
    assert list((project / 'dist').glob('*.zip'))
    assert invoke(monkeypatch, project, 'build-all', '--jobs', '1') == 0
    assert list((project / 'configured-cache/instances').glob('*.ttf'))
    assert list((project / 'configured-cache/outlines').glob('*.json'))


def test_doctor_only_requires_selected_fonts_and_licenses(project, monkeypatch, capsys):
    lock = project / 'pins.toml'
    lock.write_text(lock.read_text() + '\n[[sources]]\nid="unused"\nversion="1"\n'
                    'url="https://example.org/unused"\nsha256="' + 'a' * 64 + '"\nformat="ttf"\n')
    assert invoke(monkeypatch, project, 'doctor') == 0
    result = json.loads(capsys.readouterr().out)
    assert result['sources_ready']
    unused = next(row for row in result['sources'] if row['id'] == 'unused')
    assert not unused['required'] and not unused['ready']
    stale = project / 'source/unused/1/source-manifest.json'
    stale.parent.mkdir(parents=True)
    stale.write_text('{}')
    assert invoke(monkeypatch, project, 'doctor') == 0
    assert json.loads(capsys.readouterr().out)['sources_ready']
    (project / 'source/biz-license/1/OFL.txt').write_text('tampered')
    assert invoke(monkeypatch, project, 'doctor') == 0
    result = json.loads(capsys.readouterr().out)
    assert not result['sources_ready']
    assert any('checksum' in error.lower() for row in result['sources'] for error in row['errors'])


@pytest.mark.parametrize('epoch, expected', [(None, (1980, 1, 1, 0, 0, 0)),
                                           ('1700000001', (2023, 11, 14, 22, 13, 20)),
                                           ('0', (1980, 1, 1, 0, 0, 0))])
def test_zip_reproducible_despite_mtime_permissions_and_runtime_fields(
        project, monkeypatch, epoch, expected):
    import os
    import zipfile

    if epoch is None:
        monkeypatch.delenv('SOURCE_DATE_EPOCH', raising=False)
    else:
        monkeypatch.setenv('SOURCE_DATE_EPOCH', epoch)
    assert invoke(monkeypatch, project, 'build', '--base', 'mono', '--jp', 'biz') == 0
    assert invoke(monkeypatch, project, 'package', '--all') == 0
    archive = next((project / 'dist').glob('*.zip'))
    first = archive.read_bytes()
    manifest_path = next((project / 'build').rglob('*.json'))
    manifest = json.loads(manifest_path.read_text())
    manifest.update(generated_at='different time', duration_seconds=999, process_peak_rss_kib=123)
    manifest_path.write_text(json.dumps(manifest))
    for folder in ('build', 'source'):
        for path in (project / folder).rglob('*'):
            if path.is_file():
                os.utime(path, (1800000000, 1800000000))
                path.chmod(0o600)
    assert invoke(monkeypatch, project, 'package', '--all') == 0
    assert archive.read_bytes() == first
    with zipfile.ZipFile(archive) as package:
        assert package.namelist() == sorted(package.namelist())
        assert len(set(package.namelist())) == len(package.namelist())
        assert all(item.date_time == expected for item in package.infolist())
        assert all(item.external_attr >> 16 == 0o100644 for item in package.infolist())
        packaged = json.loads(package.read('manifests/' + manifest_path.name))
        assert not {'generated_at', 'duration_seconds', 'process_peak_rss_kib'} & packaged.keys()
    assert json.loads(manifest_path.read_text())['duration_seconds'] == 999
    import subprocess
    import sys
    script = Path(__file__).parents[2] / 'scripts/check-packages.py'
    checked = subprocess.run([sys.executable, str(script), '--build-dir', str(project / 'build'),
                              '--dist-dir', str(project / 'dist')], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
