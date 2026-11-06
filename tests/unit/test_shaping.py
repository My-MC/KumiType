from pathlib import Path

from kumitype.shaping import compare_shaping


def test_missing_harfbuzz_is_reported_without_claiming_validation():
    result = compare_shaping(Path('base.ttf'), Path('output.ttf'), 'nonexistent-kumitype-hb-shape')
    assert result['status'] == 'unavailable'
    assert result['samples'] == []
