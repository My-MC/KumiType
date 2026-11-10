"""Fail-closed policy for the pinned FontBakery JSON format."""
import json

import pytest

from kumitype import fontbakery


@pytest.mark.parametrize('data', [{}, {'result': {}, 'sections': []},
    {'result': {'FAIL': 1}, 'sections': [{'checks': []}]},
    {'result': {'(not finished)': 1}, 'sections': []}])
def test_empty_incomplete_or_inconsistent_report_fails(data):
    with pytest.raises(ValueError):
        fontbakery.classify(data, {})


@pytest.mark.parametrize('status', ['ERROR', 'FATAL'])
def test_errors_cannot_be_allowlisted(status):
    assert not fontbakery.classify(report(status), {('case_mapping', 'known'): '理由'})['valid']


def test_warn_is_recorded_but_does_not_fail():
    result = fontbakery.classify(report('WARN'), {})
    assert result['valid'] and len(result['warnings']) == 1


@pytest.mark.parametrize('entry', [
    {'check_id': 'case_mapping', 'code': 'known', 'reason': ''},
    {'check_id': 'case_mapping', 'code': 'known', 'reason': 'English only'},
    {'check_id': '*', 'code': 'known', 'reason': '日本語の理由'},
])
def test_invalid_policy_rejected(tmp_path, entry):
    path = tmp_path / 'allow.json'
    path.write_text(json.dumps({'schema_version': 1, 'exceptions': [entry]}))
    with pytest.raises(ValueError):
        fontbakery.load_policy(path)


def test_policy_requires_unique_exact_pairs(tmp_path):
    path = tmp_path / 'allow.json'
    entry = {'check_id': 'case_mapping', 'code': 'known', 'reason': '日本語の理由'}
    path.write_text(json.dumps({'schema_version': 1, 'exceptions': [entry]}))
    assert fontbakery.load_policy(path) == {('case_mapping', 'known'): '日本語の理由'}
    path.write_text(json.dumps({'schema_version': 1, 'exceptions': [entry, entry]}))
    with pytest.raises(ValueError):
        fontbakery.load_policy(path)


def report(status='FAIL', code='known', check='case_mapping'):
    return {'result': {status: 1}, 'sections': [{'checks': [{
        'key': ['section', f'<FontBakeryCheck:{check}>', []],
        'result': status, 'logs': [{'status': status, 'message': {
            'code': code, 'message': 'detail'}}]}]}]}


def test_runner_rejects_no_fonts(tmp_path):
    summary = tmp_path / 'summary.json'
    summary.write_text('{"valid": true}')
    with pytest.raises(ValueError, match='No fonts'):
        fontbakery.run_checks([], tmp_path, tmp_path / 'missing.json')
    assert not summary.exists()


def test_runner_records_hashes_and_invokes_universal(tmp_path, monkeypatch):
    import subprocess
    font = tmp_path / 'family/Test.ttf'
    font.parent.mkdir()
    font.write_bytes(b'font')
    policy = tmp_path / 'allow.json'
    policy.write_text(json.dumps({'schema_version': 1, 'exceptions': []}))
    calls = []
    def execute(args, **kwargs):
        calls.append(args)
        assert '--skip-network' in args and 'check-universal' in args
        assert '-x' not in args
        path = args[args.index('--json') + 1]
        Path(path).write_text(json.dumps(report('PASS')))
        return subprocess.CompletedProcess(args, 0, '', '')
    from pathlib import Path
    monkeypatch.setattr(fontbakery.subprocess, 'run', execute)
    result = fontbakery.run_checks([font], tmp_path / 'reports', policy)
    assert result['valid'] and result['font_count'] == 1
    assert result['fonts'][0]['sha256'] == __import__('hashlib').sha256(b'font').hexdigest()
    assert len(calls) == 1


@pytest.mark.parametrize('data', [
    {'result': {'FAIL': 1}, 'sections': [{'checks': [{'key': ['s', '<FontBakeryCheck:x>', []], 'result': 'FAIL', 'logs': []}]}]},
    {'result': {'PASS': 1}, 'sections': [{'checks': [{'key': ['s', '<FontBakeryCheck:x>', []], 'result': 'PASS', 'logs': [{'status': 'MYSTERY', 'message': {'code': 'x', 'message': 'x'}}]}]}]},
])
def test_unexplained_failure_or_unknown_log_fails(data):
    with pytest.raises(ValueError):
        fontbakery.classify(data, {})


def test_cli_empty_is_json_failure(tmp_path, capsys):
    assert fontbakery.main(['--build-dir', str(tmp_path)]) == 1
    assert not json.loads(capsys.readouterr().out)['valid']


@pytest.mark.parametrize('mode', ['no-report', 'crash', 'empty', 'unexplained-exit'])
def test_runner_never_reuses_stale_or_crashed_reports(tmp_path, monkeypatch, mode):
    import subprocess
    from pathlib import Path
    font = tmp_path / 'font.ttf'
    font.write_bytes(b'font')
    policy = tmp_path / 'allow.json'
    policy.write_text(json.dumps({'schema_version': 1, 'exceptions': []}))
    output = tmp_path / 'reports'
    output.mkdir()
    (output / 'universal-000.json').write_text(json.dumps(report('PASS')))
    def execute(args, **kwargs):
        path = Path(args[args.index('--json') + 1])
        assert not path.exists()
        if mode in ('empty', 'unexplained-exit'):
            path.write_text(json.dumps({} if mode == 'empty' else report('PASS')))
        return subprocess.CompletedProcess(args, 2 if mode == 'crash' else 1, '', '')
    monkeypatch.setattr(fontbakery.subprocess, 'run', execute)
    with pytest.raises(ValueError):
        fontbakery.run_checks([font], output, policy)


def test_runner_checks_separate_families_in_parallel_deterministically(tmp_path, monkeypatch):
    import subprocess
    import threading
    from pathlib import Path
    barrier = threading.Barrier(2)
    fonts = [tmp_path / name / 'Test.ttf' for name in ('A', 'B')]
    for font in fonts:
        font.parent.mkdir()
        font.write_bytes(b'font')
    policy = tmp_path / 'allow.json'
    policy.write_text(json.dumps({'schema_version': 1, 'exceptions': []}))
    def execute(args, **kwargs):
        barrier.wait(timeout=5)
        assert len([a for a in args if a.endswith('.ttf')]) == 1
        Path(args[args.index('--json') + 1]).write_text(json.dumps(report('PASS')))
        return subprocess.CompletedProcess(args, 0, '', '')
    monkeypatch.setattr(fontbakery.subprocess, 'run', execute)
    result = fontbakery.run_checks(fonts, tmp_path / 'reports', policy)
    assert result['valid']
    assert [Path(g['directory']).name for g in result['groups']] == ['A', 'B']


def test_exact_message_exception_not_whole_check():
    policy = {('case_mapping', 'known'): '合成ソースの文字集合を保持するため。'}
    assert fontbakery.classify(report(), policy)['valid']
    result = fontbakery.classify(report(code='new-failure'), policy)
    assert not result['valid']
    assert result['failures'][0]['code'] == 'new-failure'
