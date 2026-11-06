from kumitype.validator import check_halfwidth_kana


def test_halfwidth_kana_requires_full_range_and_one_cell():
    cmap = {cp: f'kana{cp}' for cp in range(0xFF61, 0xFFA0)}
    metrics = {name: (500, 0) for name in cmap.values()}
    assert check_halfwidth_kana(cmap, metrics, 500) == []
    del cmap[0xFF71]
    metrics[cmap[0xFF72]] = (1000, 0)
    errors = check_halfwidth_kana(cmap, metrics, 500)
    assert 'Missing halfwidth kana: U+FF71' in errors
    assert 'Incorrect halfwidth kana cell: U+FF72' in errors
