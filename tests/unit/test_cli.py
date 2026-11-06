import json

from kumitype.cli import main


def test_cli_audit_reports_missing_targets(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['kumitype', 'audit', '--build-dir', str(tmp_path)])
    assert main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report['expected_count'] == 504
    assert len(report['missing']) == 504


def test_cli_validation_empty_directory_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['kumitype', 'validate', '--all', '--build-dir', str(tmp_path)])
    assert main() == 1
    assert json.loads(capsys.readouterr().out) == []


def test_cli_validation_reports_corrupt_files_and_continues(tmp_path, monkeypatch, capsys):
    for name in ('first', 'second'):
        (tmp_path / (name + '.ttf')).write_bytes(b'bad font')
        (tmp_path / (name + '.json')).write_text('{broken')
    monkeypatch.setattr('sys.argv', ['kumitype', 'validate', '--all', '--build-dir', str(tmp_path)])
    assert main() == 1
    results = json.loads(capsys.readouterr().out)
    assert len(results) == 2
    assert all(not result['valid'] and result['errors'] for result in results)


def test_require_harfbuzz_rejects_unavailable_shaping(tmp_path, monkeypatch, capsys):
    import kumitype.cli as cli

    monkeypatch.setattr(cli, 'validate_all', lambda **kwargs: [{
        'path': 'example.ttf', 'valid': True, 'errors': [],
        'shaping': {'status': 'unavailable'}}])
    monkeypatch.setattr('sys.argv', ['kumitype', 'validate', '--all', '--require-harfbuzz',
                                   '--build-dir', str(tmp_path)])
    assert main() == 1
    result = json.loads(capsys.readouterr().out)[0]
    assert not result['valid']
    assert 'Required HarfBuzz' in result['errors'][0]
