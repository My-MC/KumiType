import json
import sys
from dataclasses import asdict

import pytest

from kumitype.cli import main
from kumitype.config import Target, load
from kumitype.selection import target_path


def test_list_selects_repeated_and_csv_dimensions(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'list', '--base', 'code,mono',
                                    '--base', 'mono', '--jp', 'plex,noto',
                                    '--weight', '400,700', '--json'])
    assert main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data['target_count'] == 16
    assert data['family_count'] == 4
    assert {t['weight'] for t in data['targets']} == {400, 700}


def test_scoped_validate_reports_all_missing_and_ignores_unrelated(tmp_path, monkeypatch, capsys):
    (tmp_path / 'broken.ttf').write_bytes(b'broken')
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'validate', '--family', 'mono-nf/biz',
                                    '--build-dir', str(tmp_path)])
    assert main() == 1
    results = json.loads(capsys.readouterr().out)
    assert len(results) == 12
    assert all('Missing font' in r['errors'][0] for r in results)


def test_scoped_audit_ignores_other_targets(tmp_path, monkeypatch, capsys):
    config = load('config/build.yaml')
    for target in (Target('mono', 'biz', 400, 'normal'), Target('code', 'biz', 400, 'normal')):
        path = target_path(tmp_path, config, target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'font')
        path.with_suffix('.json').write_text(json.dumps({
            'target': asdict(target), 'validation': {'valid': True}}))
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'audit', '--family', 'mono/biz',
                                    '--weight', '400', '--style', 'normal',
                                    '--build-dir', str(tmp_path)])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report['expected_count'] == report['observed_count'] == 1


@pytest.mark.parametrize('options,message', [
    (['--family', 'mono/biz'], 'Missing family outputs'),
    (['--family', 'mono/biz', '--weight', '400'], 'Partial packages'),
    (['--style', 'normal'], 'Partial packages'),
])
def test_package_rejects_incomplete_or_partial(tmp_path, monkeypatch, capsys, options, message):
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'package', '--build-dir', str(tmp_path), *options])
    assert main() == 1
    assert message in capsys.readouterr().err


@pytest.mark.parametrize('family', ['mono-nf/biz', 'KumiType BIZ Mono NF',
                                  ' kumitype-biz  MONO-nf ', 'MONO-NF/BIZ'])
def test_family_aliases(family, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'list', '--family', family, '--json'])
    assert main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data['target_count'] == 12
    assert [f['id'] for f in data['families']] == ['mono-nf/biz']


def test_family_union_intersects_dimensions(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'list', '--family', 'mono/biz,code/noto',
                                    '--family', 'mono/plex', '--base', 'mono',
                                    '--jp', 'biz,plex', '--weight', '400',
                                    '--style', 'normal', '--style', 'italic', '--json'])
    assert main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data['target_count'] == 4
    assert {f['id'] for f in data['families']} == {'mono/biz', 'mono/plex'}


@pytest.mark.parametrize('options', [
    ['--base', 'invalid'], ['--jp', 'invalid'], ['--weight', '500'],
    ['--style', 'oblique'], ['--family', 'mono/invalid'], ['--family', 'Unknown Font'],
    ['--family', 'mono/biz', '--base', 'code'], ['--jp', ''], ['--base', 'mono,'],
])
def test_invalid_selection_lists_choices(options, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'list', *options])
    assert main() == 1
    err = capsys.readouterr().err
    assert 'Selectable values' in err
    assert all(option in err for option in ('--base:', '--jp:', '--weight:', '--style:', '--family:'))


def test_list_text_shows_family_and_total(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'list', '--family', 'mono/biz'])
    assert main() == 0
    text = capsys.readouterr().out
    assert 'mono/biz: KumiType BIZ Mono (12 TTF)' in text
    assert '1 families; 12 static TTF targets' in text


@pytest.mark.parametrize('command', ['build', 'build-all'])
def test_build_uses_shared_scheduler_and_records_selection(command, monkeypatch, capsys):
    import kumitype.cli as cli
    calls = []
    monkeypatch.setattr(cli, 'build_all', lambda *args, **kwargs: calls.append((args, kwargs)))
    options = [] if command == 'build-all' else ['--base', 'mono', '--jp', 'biz',
                                               '--all-weights', '--all-styles']
    monkeypatch.setattr(sys, 'argv', ['kumitype', command, '--jobs', '3', *options])
    assert main() == 0
    args, kwargs = calls[0]
    assert args[1] == '3'
    assert len(kwargs['selected']) == (504 if command == 'build-all' else 12)
    assert kwargs['selection']['target_count'] == len(kwargs['selected'])
    if command == 'build':
        err = capsys.readouterr().err
        assert '--all-weights is deprecated and ignored' in err
        assert '--all-styles is deprecated and ignored' in err


def test_selector_uses_configured_matrix_not_global_values(monkeypatch, capsys, tmp_path):
    import yaml
    config = yaml.safe_load(__import__('pathlib').Path('config/build.yaml').read_text())
    config.update(variants=['mono'], japanese_fonts=['biz'], weights=[400], styles=['normal'])
    path = tmp_path / 'build.yaml'
    path.write_text(yaml.safe_dump(config))
    monkeypatch.setattr(sys, 'argv', ['kumitype', '--config', str(path), 'list', '--weight', '700'])
    assert main() == 1
    assert '--weight: 400\n' in capsys.readouterr().err


def test_scoped_package_rejects_wrong_target_at_expected_path(tmp_path, monkeypatch, capsys):
    config = load('config/build.yaml')
    from kumitype.config import targets
    for target in targets(config):
        if target.base != 'mono' or target.japanese != 'biz':
            continue
        path = target_path(tmp_path, config, target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'font')
        path.with_suffix('.json').write_text(json.dumps({'target': asdict(
            Target('code', 'biz', target.weight, target.style))}))
    monkeypatch.setattr(sys, 'argv', ['kumitype', 'package', '--family', 'mono/biz',
                                    '--build-dir', str(tmp_path)])
    assert main() == 1
    assert 'Target mismatch' in capsys.readouterr().err
