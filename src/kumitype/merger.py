"""Append donor outlines while retaining all base glyph IDs and layout tables."""
import unicodedata

from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

from .glyph_selector import cell_count, select_codepoints
from .glyph_transform import fit_glyph, transform_glyph


def merge(base, donor, *, jp_scale=1.0, baseline_offset=0, overrides=None, outline_cache=None, halfwidth_kana_scale=1.0, fit_overflow=True, fit_margin=0.02) -> dict:
    if 'glyf' not in base or 'fvar' in base or 'fvar' in donor:
        raise ValueError('Merge requires a static TrueType base and static donor')
    cmap = base.getBestCmap() or {}
    donor_cmap = donor.getBestCmap() or {}
    donor_cmap = dict(donor_cmap)
    derived_halfwidth = []
    for cp in range(0xFF61, 0xFFA0):
        if cp in donor_cmap or cp in cmap:
            continue
        normalized = unicodedata.normalize('NFKC', chr(cp))
        if len(normalized) == 1 and ord(normalized) in donor_cmap:
            donor_cmap[cp] = donor_cmap[ord(normalized)]
            derived_halfwidth.append(cp)
    selected = select_codepoints(cmap, donor_cmap, overrides)
    order = base.getGlyphOrder()[:]
    if len(order) + len(selected) > 65535:
        raise ValueError('Merged glyph count exceeds TrueType limit (65535)')
    if ord(' ') not in cmap:
        raise ValueError('Base font has no space metric')
    cell = base['hmtx'].metrics[cmap[ord(' ')]][0]
    scale = base['head'].unitsPerEm / donor['head'].unitsPerEm * jp_scale
    glyph_set = donor.getGlyphSet()
    added = {}
    overflow = []
    fitted = []
    for cp in selected:
        name = f'kumitype.u{cp:06X}'
        while name in base['glyf'].glyphs:
            name += '_'
        width = cell * cell_count(cp)
        cached = outline_cache.get(cp) if outline_cache else None
        if cached is None:
            glyph, lsb, exceeds = transform_glyph(
                glyph_set, donor_cmap[cp],
                scale * (halfwidth_kana_scale if 0xFF61 <= cp <= 0xFF9F else 1),
                width, baseline_offset,
                reverse_direction='glyf' not in donor,
                horizontal_scale=0.5 if cp in derived_halfwidth else 1)
            was_fitted = exceeds and fit_overflow
            if was_fitted:
                glyph, lsb, exceeds = fit_glyph(glyph, width, fit_margin)
            if outline_cache:
                outline_cache.put(cp, glyph, lsb, exceeds, was_fitted)
        else:
            glyph, lsb, exceeds, was_fitted = cached
        if was_fitted:
            fitted.append(cp)
        base['glyf'].glyphs[name] = glyph
        base['hmtx'].metrics[name] = (width, lsb)
        order.append(name)
        added[cp] = name
        if exceeds:
            overflow.append(cp)
    if outline_cache:
        outline_cache.save()
    base.setGlyphOrder(order)
    for table in base['cmap'].tables:
        if table.isUnicode() and table.format in (4, 12):
            table.cmap.update({cp: name for cp, name in added.items()
                               if cp <= 0xFFFF or table.format == 12})
    if any(cp > 0xFFFF for cp in added) and not any(
            t.format == 12 and t.isUnicode() for t in base['cmap'].tables):
        table = CmapSubtable.newSubtable(12)
        table.platformID, table.platEncID, table.language = 3, 10, 0
        table.cmap = {**cmap, **added}
        base['cmap'].tables.append(table)
    base['maxp'].numGlyphs = len(order)
    base['OS/2'].recalcUnicodeRanges(base)
    return {'derived_halfwidth_codepoints': derived_halfwidth, 'added_codepoints': selected, 'overflow_codepoints': overflow, 'fitted_codepoints': fitted,
            'ivs_inherited': False, 'cell_width': cell}


def merge_many(base, donors, **options) -> dict:
    """Merge ordered subset sources, importing each Unicode scalar once."""
    combined = {'derived_halfwidth_codepoints': [], 'added_codepoints': [], 'overflow_codepoints': [], 'fitted_codepoints': [], 'ivs_inherited': False}
    imported = set()
    for donor in donors:
        # Earlier subsets win if their coverage overlaps.
        overrides = {**options.get('overrides', {}), **{cp: 'cascadia' for cp in imported}}
        result = merge(base, donor, **{**options, 'overrides': overrides})
        imported.update(result['added_codepoints'])
        combined['derived_halfwidth_codepoints'].extend(result['derived_halfwidth_codepoints'])
        combined['added_codepoints'].extend(result['added_codepoints'])
        combined['overflow_codepoints'].extend(result['overflow_codepoints'])
        combined['fitted_codepoints'].extend(result['fitted_codepoints'])
        combined['cell_width'] = result['cell_width']
    combined['added_codepoints'].sort()
    combined['overflow_codepoints'].sort()
    combined['fitted_codepoints'].sort()
    return combined
