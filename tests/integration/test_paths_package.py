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


@pytest.mark.parametrize('command', ['build', 'build-all'])
def test_small_matrix_full_and_scoped_consumers(project, monkeypatch, capsys, command):
    import zipfile

    assert invoke(monkeypatch, project, command, '--jobs', '1') == 0
    report = json.loads((project / 'build/build-report.json').read_text())
    assert report['output_count'] == report['selection']['target_count'] == 1
    capsys.readouterr()
    assert invoke(monkeypatch, project, 'validate', '--all') == 0
    assert len(json.loads(capsys.readouterr().out)) == 1
    assert invoke(monkeypatch, project, 'audit') == 0
    assert json.loads(capsys.readouterr().out)['complete']
    assert invoke(monkeypatch, project, 'package', '--all') == 0
    archive = next((project / 'dist').glob('*.zip'))
    first = archive.read_bytes()
    # Unrelated damaged outputs must not break any scoped consumer.
    unrelated = project / 'build/unrelated.ttf'
    unrelated.write_bytes(b'broken')
    unrelated.with_suffix('.json').write_text('{broken')
    assert invoke(monkeypatch, project, 'validate', '--family', 'mono/biz') == 0
    assert invoke(monkeypatch, project, 'audit', '--family', 'mono/biz') == 0
    assert invoke(monkeypatch, project, 'package', '--family', 'mono/biz') == 0
    assert archive.read_bytes() == first
    with zipfile.ZipFile(archive) as contents:
        assert len([name for name in contents.namelist() if name.endswith('.ttf')]) == 1


def test_selected_validation_rejects_wrong_target_manifest(project, monkeypatch, capsys):
    assert invoke(monkeypatch, project, 'build', '--family', 'mono/biz', '--jobs', '1') == 0
    path = next((project / 'build').rglob('*.ttf')).with_suffix('.json')
    record = json.loads(path.read_text())
    record['target']['base'] = 'code'
    path.write_text(json.dumps(record))
    capsys.readouterr()
    assert invoke(monkeypatch, project, 'validate', '--family', 'mono/biz') == 1
    assert 'Target mismatch' in str(json.loads(capsys.readouterr().out)[0]['errors'])


def test_zip_reproducible_across_project_source_and_cache_locations(project, tmp_path, monkeypatch):
    import shutil
    import zipfile

    (project / 'legal').mkdir()
    (project / 'legal/OFL.txt').write_text('additional license')
    config = yaml.safe_load((project / 'build.yaml').read_text())
    config['font_overrides'] = {'biz': {'subset_files': ['source/biz/1/donor.ttf'],
                                      'subset_licenses': ['legal/OFL.txt']}}
    (project / 'build.yaml').write_text(yaml.safe_dump(config))
    relocated = tmp_path / 'elsewhere' / 'checkout'
    shutil.copytree(project, relocated)
    shutil.move(relocated / 'source', relocated / 'other-inputs')
    config['font_overrides']['biz']['subset_files'] = ['other-inputs/biz/1/donor.ttf']
    (relocated / 'build.yaml').write_text(yaml.safe_dump(config))
    # Include absolute source-manifest paths, not just legacy relative ones.
    for path in (relocated / 'other-inputs').rglob('source-manifest.json'):
        data = json.loads(path.read_text())
        for font in data['fonts']:
            font['path'] = str(relocated / 'other-inputs' / Path(font['path']).relative_to('source'))
        path.write_text(json.dumps(data))
    hashes = []
    for root, args in [(project, []), (relocated, ['--source-dir', 'other-inputs',
                                                  '--cache-dir', 'other-cache'])]:
        assert invoke(monkeypatch, root, 'build', '--base', 'mono', '--jp', 'biz', *args) == 0
        assert invoke(monkeypatch, root, 'package', '--all', *args) == 0
        archive = next((root / 'dist').glob('*.zip'))
        hashes.append(hashlib.sha256(archive.read_bytes()).hexdigest())
        with zipfile.ZipFile(archive) as package:
            for name in package.namelist():
                if name.endswith('.json'):
                    assert str(tmp_path) not in package.read(name).decode()
                    assert '_project_root' not in package.read(name).decode()
    assert hashes[0] == hashes[1]
    # The package auditor must use the same portable projection even though
    # the two local build manifests retain different absolute paths/hashes.
    import subprocess
    import sys

    script = Path(__file__).parents[2] / 'scripts/check-packages.py'
    for root in (project, relocated):
        checked = subprocess.run([sys.executable, str(script), '--build-dir', str(root / 'build'),
                                  '--dist-dir', str(root / 'dist')], capture_output=True, text=True)
        assert checked.returncode == 0, checked.stderr


def test_nested_legacy_source_paths_work_from_external_cwd(project, tmp_path, monkeypatch, capsys):
    import shutil

    (project / 'data').mkdir()
    source = project / 'data/source'
    shutil.move(project / 'source', source)
    for path in source.rglob('source-manifest.json'):
        data = json.loads(path.read_text())
        for font in data['fonts']:
            font['path'] = 'data/' + font['path']
        path.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)
    assert invoke(monkeypatch, project, 'doctor', '--source-dir', 'data/source') == 0
    assert json.loads(capsys.readouterr().out)['sources_ready']
    assert invoke(monkeypatch, project, 'build', '--base', 'mono', '--jp', 'biz',
                  '--source-dir', 'data/source') == 0
    assert invoke(monkeypatch, project, 'validate', '--all') == 0
    assert invoke(monkeypatch, project, 'package', '--all', '--source-dir', 'data/source') == 0


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
    manifest_path = next((project / 'build').rglob('*.ttf')).with_suffix('.json')
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
