from kumitype.glyph_selector import cell_count, japanese_priority, select_codepoints


def test_pua_protected_even_with_override():
    assert not japanese_priority(0xE0B0, {0xE0B0: 'japanese'})
    assert select_codepoints({}, {0xE0B0: 'icon'}) == []


def test_script_policy_and_explicit_ambiguity():
    assert japanese_priority(ord('漢'))
    assert not japanese_priority(ord('A'))
    assert not japanese_priority(ord('α'))
    assert japanese_priority(ord('α'), {ord('α'): 'japanese'})
    assert not japanese_priority(ord('。'), {ord('。'): 'cascadia'})


def test_terminal_cells():
    assert cell_count(ord('漢')) == cell_count(0x3000) == 2
    assert cell_count(ord('ｱ')) == cell_count(ord('A')) == 1
