"""Metadata contract on synthetic binary fonts."""
import pytest
from fontTools.ttLib import newTable

from test_merge import make_font
from kumitype.config import Target
from kumitype.metadata import apply_metadata
from kumitype.validator import validate


def prepared():
    font = make_font({65: 'a'})
    apply_metadata(font, make_font({0x3042: 'kana'}), Target('mono', 'biz', 400, 'normal'),
                   {'name': 'KumiType', 'version': '0.1.0'})
    return font


@pytest.mark.parametrize('version', ['1.2', '1.2.100', '1.10.0', '32768.0.0'])
def test_unrepresentable_font_version_is_rejected(version):
    from kumitype.metadata import font_revision
    with pytest.raises(ValueError):
        font_revision(version)


def test_output_metadata_contract(tmp_path):
    font = make_font({65: 'a'})
    font['DSIG'] = newTable('DSIG')
    font['DSIG'].ulVersion, font['DSIG'].usFlag = 1, 0
    font['DSIG'].usNumSigs, font['DSIG'].signatureRecords = 0, []
    apply_metadata(font, make_font({0x3042: 'kana'}), Target('mono', 'biz', 700, 'italic'),
                   {'name': 'KumiType', 'version': '0.1.0'})
    assert 'DSIG' not in font
    assert font['OS/2'].ulCodePageRange1 & (1 << 17)
    assert font['OS/2'].achVendID == 'NONE'
    assert font['head'].fontRevision == pytest.approx(0.1, abs=1 / 65536)
    path = tmp_path / 'valid.ttf'
    font.save(path)
    assert validate(path)['valid']


@pytest.mark.parametrize('weight,style', [(400, 'normal'), (700, 'italic'), (350, 'normal')])
def test_quality_metadata(tmp_path, weight, style):
    from fontTools.ttLib import TTFont
    font = make_font({65: 'a'})
    font['head'].flags &= ~8
    apply_metadata(font, make_font({0x3042: 'kana'}), Target('mono', 'biz', weight, style),
                   {'name': 'KumiType', 'version': '0.1.0'})
    path = tmp_path / 'quality.ttf'
    font.save(path)
    with TTFont(path) as loaded:
        assert loaded['head'].flags & 8
        assert not any(n.platformID == 1 for n in loaded['name'].names)
        assert loaded['OS/2'].panose.bFamilyType == 2
        assert loaded['OS/2'].panose.bProportion == 9
        stat = loaded['STAT'].table
        assert [a.AxisTag for a in stat.DesignAxisRecord.Axis] == ['wght', 'ital']
        assert [v.Value for v in stat.AxisValueArray.AxisValue] == [weight, int(style == 'italic')]
        ital = stat.AxisValueArray.AxisValue[1]
        if style != 'italic':
            assert ital.Format == 3
            assert ital.LinkedValue == 1.0
        else:
            assert ital.Format == 1


def test_validate_all_uses_manifest_project_version(tmp_path):
    import hashlib
    import json
    from kumitype.validator import validate_all

    font = prepared()
    font['head'].fontRevision = 2.0
    path = tmp_path / 'custom.ttf'
    font.save(path)
    path.with_suffix('.json').write_text(json.dumps({
        'sources': [{'path': str(path)}], 'config': {'project': {'version': '2.0.0'}},
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'identity': {'postscript_name': font['name'].getDebugName(6),
                     'family': font['name'].getDebugName(16)},
        'target': {'weight': 400}, 'merge': {'cell_width': 500, 'added_codepoints': []}}))
    result = validate_all(tmp_path, harfbuzz='missing-hb-shape')[0]
    assert not any('fontRevision' in error for error in result['errors'])


@pytest.mark.parametrize('violation,message', [
    ('DSIG', 'DSIG'), ('codepage', 'ulCodePageRange1'),
    ('vendor', 'achVendID'), ('revision', 'fontRevision')])
def test_validator_rejects_metadata_violation(tmp_path, violation, message):
    font = prepared()
    if violation == 'DSIG':
        font['DSIG'] = newTable('DSIG')
        font['DSIG'].ulVersion, font['DSIG'].usFlag = 1, 0
        font['DSIG'].usNumSigs, font['DSIG'].signatureRecords = 0, []
    elif violation == 'codepage':
        font['OS/2'].ulCodePageRange1 &= ~(1 << 17)
    elif violation == 'vendor':
        font['OS/2'].achVendID = 'TEST'
    else:
        font['head'].fontRevision = 1.0
    path = tmp_path / 'invalid.ttf'
    font.save(path)
    result = validate(path)
    assert not result['valid']
    assert any(message in error for error in result['errors'])
