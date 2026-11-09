"""Goal runner's public JSON and exit-code contract."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/check-goal.py'


def runner():
    assert SCRIPT.exists(), 'Goal runner is missing'
    spec = importlib.util.spec_from_file_location('check_goal', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_subset_is_exactly_28_paired_targets():
    module = runner()
    matrix = module.subset_targets()
    assert len(matrix) == len(set(matrix)) == 28
    assert {t.base for t in matrix} == {'code-nf', 'mono'}
    assert len({t.japanese for t in matrix}) == 7
    assert {(t.weight, t.style) for t in matrix} == {(400, 'normal'), (700, 'italic')}


def test_g7_missing_subset_is_json_failure_from_external_cwd(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), '--only', 'G7', '--reuse',
                             '--build-dir', str(tmp_path / 'outputs')],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    data = json.loads(result.stdout)['goals']['G7']
    assert data['status'] == 'FAIL'
    assert 'Missing subset' in str(data['evidence'])


@pytest.mark.parametrize('valid', [True, False])
def test_g7_uses_real_runner_result(tmp_path, monkeypatch, valid):
    module = runner()
    monkeypatch.setattr(module, 'run_checks', lambda paths, output, allowlist: {'valid': valid})
    assert module.check_g7([tmp_path / 'font.ttf'], tmp_path)['status'] == ('PASS' if valid else 'FAIL')


def test_unknown_goal_is_rejected():
    assert SCRIPT.exists()
    result = subprocess.run([sys.executable, str(SCRIPT), '--only', 'G9'],
                            capture_output=True, text=True)
    assert result.returncode != 0


def test_empty_existing_build_is_failure_not_vacuous_pass(tmp_path):
    module = runner()
    result = module.check_g2([], module.load(module.ROOT / 'config/build.yaml'))
    assert result['status'] == 'FAIL'


def test_hash_comparison_requires_both_formats_and_same_inventory(tmp_path):
    module = runner()
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    assert module.compare_artifacts(a, b)['status'] == 'FAIL'
    for directory in (a, b):
        (directory / 'font.ttf').write_bytes(b'font')
        (directory / 'package.zip').write_bytes(b'zip')
    assert module.compare_artifacts(a, b)['status'] == 'PASS'
    (b / 'package.zip').write_bytes(b'changed')
    assert module.compare_artifacts(a, b)['status'] == 'FAIL'


def test_g3_synthesizes_each_violation(tmp_path):
    result = runner().check_g3(tmp_path)
    assert result['status'] == 'PASS'
    assert len(result['evidence']) == 4


def test_g4_reads_binary_outlines_instead_of_trusting_manifest(tmp_path):
    module = runner()
    font = module.synthetic_font('0.1.0')
    # The imported glyph is the space glyph with a real oversize outline.
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((900, 0))
    pen.lineTo((900, 700))
    pen.closePath()
    font['glyf']['space'] = pen.glyph()
    path = tmp_path / 'overflow.ttf'
    font.save(path)
    path.with_suffix('.json').write_text(json.dumps({
        'merge': {'added_codepoints': [32], 'overflow_codepoints': []}}))
    result = module.check_g4([path])
    assert result['status'] == 'FAIL'
    assert result['evidence'][0]['overflow_count'] == 1


def test_g4_detects_import_omitted_from_manifest(tmp_path):
    module = runner()
    font = module.synthetic_font('0.1.0')
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((900, 0))
    pen.lineTo((900, 700))
    pen.closePath()
    name = 'kumitype.u003042'
    font['glyf'][name] = pen.glyph()
    font['hmtx'][name] = (500, 0)
    font.setGlyphOrder(list(dict.fromkeys([*font.getGlyphOrder(), name])))
    for table in font['cmap'].tables:
        if table.isUnicode():
            table.cmap[0x3042] = name
    path = tmp_path / 'omitted.ttf'
    font.save(path)
    path.with_suffix('.json').write_text(json.dumps({'merge': {'added_codepoints': []}}))
    result = module.check_g4([path])
    assert result['status'] == 'FAIL'
    assert result['evidence'][0]['overflow_count'] == 1


def test_g6_does_not_pass_when_cache_options_missing(monkeypatch):
    module = runner()
    monkeypatch.setattr(module, 'command', lambda args, cwd: {
        'command': list(map(str, args)), 'returncode': 0, 'stdout': '', 'stderr': ''})
    assert module.check_g6(module.load(module.ROOT / 'config/build.yaml'))['status'] == 'FAIL'


def test_g6_does_not_pass_on_help_only(monkeypatch):
    module = runner()
    monkeypatch.setattr(module, 'command', lambda args, cwd: {
        'command': list(map(str, args)), 'returncode': 0,
        'stdout': '--cache-dir', 'stderr': ''})
    monkeypatch.setattr(module, 'build_one', lambda *args: None)
    assert module.check_g6(module.load(module.ROOT / 'config/build.yaml'))['status'] == 'FAIL'


def test_subset_ignores_unpublished_atomic_temporary(tmp_path, monkeypatch):
    module = runner()
    config = module.load(module.ROOT / 'config/build.yaml')
    target = module.subset_targets()[0]
    monkeypatch.setattr(module, 'subset_targets', lambda: [target])
    path = module.output_path(tmp_path, config, target)
    path.parent.mkdir(parents=True)
    path.write_bytes(b'published')
    from dataclasses import asdict
    import hashlib
    path.with_suffix('.json').write_text(json.dumps({
        'config': config, 'target': asdict(target),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
    (path.parent / '.font-interrupted.ttf').write_bytes(b'')
    assert module.ensure_subset(tmp_path, config, reuse=True) == [path]


def test_g1_requires_type_check_success(monkeypatch):
    module = runner()
    commands = []
    def command(args):
        commands.append(args)
        return {'returncode': 1 if 'mypy' in args else 0}
    monkeypatch.setattr(module, 'command', command)
    assert module.check_g1()['status'] == 'FAIL'
    assert ['uv', 'run', '--locked', 'mypy', 'src'] in commands


def test_g1_failure_is_not_hidden(monkeypatch):
    module = runner()
    monkeypatch.setattr(module, 'command', lambda args: {'returncode': 1})
    assert module.check_g1()['status'] == 'FAIL'


def test_main_emits_json_and_nonzero_on_gate_failure(tmp_path, monkeypatch, capsys):
    module = runner()
    monkeypatch.setattr(module, 'check_g1', lambda: module.outcome(False, ['test failure']))
    assert module.main(['--only', 'G1', '--build-dir', str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)['goals']['G1']['status'] == 'FAIL'


def test_reuse_requires_every_expected_font(tmp_path):
    module = runner()
    with pytest.raises(ValueError, match='Missing subset'):
        module.ensure_subset(tmp_path, module.load(module.ROOT / 'config/build.yaml'), reuse=True)


def test_hash_inventory_mismatch_fails(tmp_path):
    module = runner()
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    for directory in (a, b):
        (directory / 'font.ttf').write_bytes(b'font')
        (directory / 'package.zip').write_bytes(b'zip')
    (b / 'extra.ttf').write_bytes(b'extra')
    assert module.compare_artifacts(a, b)['status'] == 'FAIL'


@pytest.mark.parametrize('value', ['G1,G2', 'G2,G2'])
def test_goal_selection(value):
    module = runner()
    assert module.select_goals(value) == list(dict.fromkeys(value.split(',')))
