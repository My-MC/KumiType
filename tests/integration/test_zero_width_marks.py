"""Imported nonspacing/enclosing marks overlay the preceding cell(s)."""
import pytest
from fontTools.ttLib import TTFont

from test_merge import make_font
from kumitype.merger import merge_many
from kumitype.outline_cache import OutlineCache


@pytest.mark.parametrize('cp,width', [(0x030F, 500), (0x20DD, 500), (0x3099, 1000), (0x309A, 1000)])
def test_marks_overlay_without_changing_base_or_nonmarks(tmp_path, cp, width):
    donor = make_font({cp: 'mark', 0x2460: 'circle', 0x3042: 'kana', 0x0301: 'acute'})
    fonts = []
    reports = []
    for _ in range(2):
        base = make_font({65: 'a', 0x0301: 'acute'})
        protected = {n: (base['glyf'][n].compile(base['glyf']), base['hmtx'][n])
                     for n in base.getGlyphOrder()}
        report = merge_many(base, [donor], baseline_offset=37,
                            outline_cache=OutlineCache({'test': cp}, tmp_path / 'cache'))
        assert report['zero_width_mark_codepoints'] == [cp]
        name = base.getBestCmap()[cp]
        glyph = base['glyf'][name]
        # Cached Glyphs are lazily expanded, just like disk-loaded fonts.
        glyph.expand(base['glyf'])
        assert base['hmtx'][name] == (0, glyph.xMin)
        assert -width <= glyph.xMin < glyph.xMax <= 0
        assert (glyph.xMin + glyph.xMax) / 2 == -width / 2
        assert (glyph.yMin, glyph.yMax) == (37, 737)
        assert base['GDEF'].table.GlyphClassDef.classDefs[name] == 3
        for n, expected in protected.items():
            assert (base['glyf'][n].compile(base['glyf']), base['hmtx'][n]) == expected
        circle = base['glyf'][base.getBestCmap()[0x2460]]
        assert (circle.xMin, circle.xMax) == (10, 490)
        kana = base['glyf'][base.getBestCmap()[0x3042]]
        assert (kana.xMin, kana.xMax) == (150, 850)
        path = tmp_path / f'{len(fonts)}.ttf'
        base.save(path)
        with TTFont(path) as loaded:
            assert loaded['GDEF'].table.GlyphClassDef.classDefs[name] == 3
        fonts.append(base)
        reports.append(report)
    assert reports[0] == reports[1]
    assert fonts[0].getTableData('glyf') == fonts[1].getTableData('glyf')


@pytest.mark.parametrize('mutation', ['base-class', 'existing-mark', 'other-subtable', 'extra-nonmark', 'mark-class', 'missing-gdef'])
def test_validator_allows_only_added_mark_classes(tmp_path, mutation):
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from kumitype.config import Target
    from kumitype.metadata import apply_metadata
    from kumitype.validator import validate

    base = make_font({65: 'a', 0x0301: 'acute'})
    addOpenTypeFeaturesFromString(base, 'table GDEF { GlyphClassDef [a], , [acute], ; } GDEF;')
    original = tmp_path / 'base.ttf'
    base.save(original)
    donor = make_font({0x030F: 'mark'})
    merge_many(base, [donor])
    apply_metadata(base, donor, Target('mono', 'biz', 400, 'normal'),
                   {'name': 'KumiType', 'version': '0.1.0'})
    output = tmp_path / 'output.ttf'
    base.save(output)
    assert validate(output, original)['valid']
    if mutation == 'base-class':
        base['GDEF'].table.GlyphClassDef.classDefs['a'] = 3
    elif mutation == 'existing-mark':
        del base['GDEF'].table.GlyphClassDef.classDefs['acute']
    elif mutation == 'other-subtable':
        from fontTools.ttLib.tables import otTables
        base['GDEF'].table.MarkAttachClassDef = otTables.ClassDef()
        base['GDEF'].table.MarkAttachClassDef.classDefs = {'acute': 1}
    elif mutation == 'extra-nonmark':
        base['GDEF'].table.GlyphClassDef.classDefs['space'] = 1
    elif mutation == 'mark-class':
        base['GDEF'].table.GlyphClassDef.classDefs[base.getBestCmap()[0x030F]] = 1
    else:
        del base['GDEF']
    base.save(output)
    assert 'Base layout table changed: GDEF' in validate(output, original)['errors']


def test_validator_rejects_nonzero_imported_mark_advance(tmp_path):
    from kumitype.config import Target
    from kumitype.metadata import apply_metadata
    from kumitype.validator import validate

    base = make_font({65: 'a'})
    donor = make_font({0x030F: 'mark'})
    merge_many(base, [donor])
    apply_metadata(base, donor, Target('mono', 'biz', 400, 'normal'),
                   {'name': 'KumiType', 'version': '0.1.0'})
    output = tmp_path / 'output.ttf'
    base.save(output)
    assert validate(output)['valid']
    name = base.getBestCmap()[0x030F]
    base['hmtx'][name] = (500, base['hmtx'][name][1])
    base.save(output)
    assert 'Nonzero imported mark advance: U+030F' in validate(output)['errors']
