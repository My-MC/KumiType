import json

from kumitype.validator import audit_matrix


def test_matrix_detects_missing_and_duplicate_targets(tmp_path):
    config = {'variants': ['mono'], 'japanese_fonts': ['biz'], 'weights': [400],
              'styles': ['normal', 'italic']}
    record = {'target': {'base': 'mono', 'japanese': 'biz', 'weight': 400, 'style': 'normal'},
              'validation': {'valid': True}}
    for name in ('one', 'duplicate'):
        (tmp_path / (name + '.ttf')).write_bytes(b'font')
        (tmp_path / (name + '.json')).write_text(json.dumps(record))
    report = audit_matrix(config, tmp_path)
    assert not report['complete']
    assert report['missing'][0]['style'] == 'italic'
    assert report['errors']


def test_exact_matrix_is_complete(tmp_path):
    config = {'variants': ['mono'], 'japanese_fonts': ['biz'], 'weights': [400], 'styles': ['normal']}
    (tmp_path / 'one.ttf').write_bytes(b'font')
    (tmp_path / 'one.json').write_text(json.dumps({'target': {
        'base': 'mono', 'japanese': 'biz', 'weight': 400, 'style': 'normal'},
        'validation': {'valid': True}}))
    assert audit_matrix(config, tmp_path)['complete']
