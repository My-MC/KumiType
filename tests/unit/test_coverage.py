from kumitype.coverage import coverage_report


def test_source_coverage_reports_missing_supplementary_kanji():
    report = coverage_report({0x3042: 'kana'}, [{0x3042: 'kana', 0x20000: 'han', 65: 'latin'}])
    assert report['source_japanese_count'] == 2
    assert report['covered_japanese_count'] == 1
    assert report['missing_source_codepoints'] == [0x20000]
    assert report['coverage_ratio'] == 0.5
    assert ord('漢') in report['missing_sample_codepoints']
