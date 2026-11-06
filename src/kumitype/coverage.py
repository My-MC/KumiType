"""Compare Japanese source coverage and required rendering samples."""
from .glyph_selector import japanese_priority

SAMPLE = ('あいうえおアイウエオ漢字日本語こんにちは世界プログラミング設定ファイル'
          '括弧「」『』句読点。、・全角文字１２３半角文字123ｱｲｳｴｵ')


def coverage_report(output_cmap: dict, donor_cmaps: list[dict]) -> dict:
    expected = {cp for cmap in donor_cmaps for cp in cmap if japanese_priority(cp)}
    missing = sorted(expected - output_cmap.keys())
    sample_missing = sorted({ord(c) for c in SAMPLE} - output_cmap.keys())
    return {'source_japanese_count': len(expected),
            'covered_japanese_count': len(expected) - len(missing),
            'coverage_ratio': (len(expected) - len(missing)) / len(expected) if expected else 1.0,
            'missing_source_codepoints': missing, 'missing_sample_codepoints': sample_missing}
