from pathlib import Path

import pytest
import yaml

from kumitype.cli import main
from kumitype.config import load


def config_file(tmp_path):
    data = yaml.safe_load(Path('config/build.yaml').read_text())
    data['sources']['lock'] = 'pins.toml'
    data['paths'] = {'source': 'inputs', 'cache': 'intermediates', 'build': 'outputs'}
    folder = tmp_path / 'project'
    folder.mkdir()
    path = folder / 'build.yaml'
    path.write_text(yaml.safe_dump(data))
    return path


def test_config_paths_are_anchored_to_configuration(tmp_path, monkeypatch):
    path = config_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    config = load(path)
    assert config['sources']['lock'] == str(path.parent / 'pins.toml')
    assert config['paths']['cache'] == str(path.parent / 'intermediates')


def test_config_directory_uses_project_root_and_resolves_subsets(tmp_path):
    path = config_file(tmp_path)
    data = yaml.safe_load(path.read_text())
    data['font_overrides'] = {'biz': {'subset_files': ['extra.ttf'], 'subset_licenses': ['OFL.txt']}}
    folder = path.parent / 'config'
    folder.mkdir()
    nested = folder / 'build.yaml'
    nested.write_text(yaml.safe_dump(data))
    config = load(nested)
    assert config['sources']['lock'] == str(path.parent / 'pins.toml')
    assert config['font_overrides']['biz']['subset_files'] == [str(path.parent / 'extra.ttf')]
    assert config['font_overrides']['biz']['subset_licenses'] == [str(path.parent / 'OFL.txt')]


def test_import_and_fetch_share_configured_source_cache_and_lock(tmp_path, monkeypatch):
    import hashlib
    import json

    path = config_file(tmp_path)
    artifact = path.parent / 'LICENSE'
    artifact.write_bytes(b'Offline license')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (path.parent / 'pins.toml').write_text('[[sources]]\nid="test-license"\nversion="1"\n'
        'url="https://example.invalid/LICENSE"\nformat="text"\nfilename="LICENSE"\nsha256="' + digest + '"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv', ['kumitype', '--config', str(path), 'import-source',
                                   '--id', 'test-license', '--file', 'LICENSE'])
    assert main() == 0
    installed = path.parent / 'inputs/test-license/1/LICENSE'
    assert installed.read_bytes() == artifact.read_bytes()
    assert (path.parent / 'intermediates' / digest).read_bytes() == artifact.read_bytes()
    installed.unlink()
    monkeypatch.setattr('sys.argv', ['kumitype', '--config', str(path), 'fetch'])
    assert main() == 0
    assert installed.read_bytes() == artifact.read_bytes()
    manifest = json.loads(installed.with_name('source-manifest.json').read_text())
    assert manifest['sha256'] == digest


@pytest.mark.parametrize('args', [
    ['fetch'], ['doctor'], ['import-source', '--id', 'test', '--file', 'artifact'],
    ['update-source', '--id', 'test', '--version', '1', '--url', 'https://example.org/a',
     '--sha256', '0' * 64, '--format', 'text'],
])
def test_cli_uses_configured_lock_from_external_cwd(tmp_path, monkeypatch, capsys, args):
    path = config_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv', ['kumitype', '--config', str(path), *args])
    assert main() == 1
    assert str(path.parent / 'pins.toml') in capsys.readouterr().err


def test_explicit_lock_overrides_configuration(tmp_path, monkeypatch, capsys):
    path = config_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv', ['kumitype', '--config', str(path), 'fetch', '--lock', 'override.toml'])
    assert main() == 1
    assert str(path.parent / 'override.toml') in capsys.readouterr().err


def test_container_config_environment_uses_mounted_project(tmp_path, monkeypatch, capsys):
    path = config_file(tmp_path)
    data = yaml.safe_load(path.read_text())
    data.update(variants=['mono'], japanese_fonts=['biz'], weights=[400], styles=['normal'])
    path.write_text(yaml.safe_dump(data))
    monkeypatch.setenv('KUMITYPE_CONFIG', str(path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv', ['kumitype', 'list', '--json'])
    assert main() == 0
    assert __import__('json').loads(capsys.readouterr().out)['targets'] == [
        {'base': 'mono', 'japanese': 'biz', 'weight': 400, 'style': 'normal'}]
    # An explicit --config remains authoritative over the container default.
    monkeypatch.setenv('KUMITYPE_CONFIG', str(tmp_path / 'missing.yaml'))
    monkeypatch.setattr('sys.argv', ['kumitype', '--config', str(path), 'list', '--json'])
    assert main() == 0


def test_all_commands_accept_cache_dir(monkeypatch, capsys):
    for name in ('list', 'doctor', 'fetch', 'build', 'build-all', 'validate',
                 'package', 'audit', 'import-source', 'update-source'):
        monkeypatch.setattr('sys.argv', ['kumitype', name, '--help'])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        assert '--cache-dir' in capsys.readouterr().out
