"""Synthetic fonts authored for these tests; no upstream font data required."""
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

from kumitype.merger import merge
from kumitype.validator import validate


def make_font(mapping, upm=1000, layout=False):
    order = ['.notdef', 'space', *dict.fromkeys(mapping.values())]
    builder = FontBuilder(upm, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({32: 'space', **mapping})
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        if name not in ('.notdef', 'space'):
            pen.moveTo((100, 0))
            pen.lineTo((800, 0))
            pen.lineTo((800, 700))
            pen.lineTo((100, 700))
            pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (500, 0) for name in order})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': 'Synthetic', 'styleName': 'Regular',
                            'psName': 'Synthetic-Regular', 'fullName': 'Synthetic Regular'})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    if layout:
        addOpenTypeFeaturesFromString(builder.font, 'feature calt { sub a a by lig; } calt;')
    return builder.font


def test_merge_preserves_layout_and_protected_glyphs(tmp_path):
    base = make_font({65: 'a', 66: 'lig', 0xE0B0: 'icon'}, layout=True)
    donor = make_font({65: 'latin', 0xE0B0: 'badicon', 0x3042: 'kana', 0x20000: 'han'})
    from fontTools.ttLib.tables.ttProgram import Program
    program = Program()
    program.fromBytecode([0xB0, 0x00, 0x21])
    base['glyf']['a'].program = program
    original_order = base.getGlyphOrder()[:]
    original_layout = base.getTableData('GSUB')
    original_glyph = base['glyf']['a'].compile(base['glyf'])
    base_path = tmp_path / 'base.ttf'
    base.save(base_path)
    result = merge(base, donor)
    path = tmp_path / 'merged.ttf'
    base.save(path)
    assert result['added_codepoints'] == [0x3042, 0x20000]
    with TTFont(path) as output:
        assert output.getGlyphOrder()[:len(original_order)] == original_order
        assert output.getTableData('GSUB') == original_layout
        assert output['glyf']['a'].compile(output['glyf']) == original_glyph
        cmap = output.getBestCmap()
        assert cmap[65] == 'a' and cmap[0xE0B0] == 'icon'
        assert output['hmtx'][cmap[0x3042]][0] == 1000
        assert output['hmtx'][cmap[0x20000]][0] == 1000
        glyph = output['glyf'][cmap[0x3042]]
        assert glyph.xMin == 150 and glyph.xMax == 850
    from kumitype.config import Target
    from kumitype.metadata import apply_metadata
    apply_metadata(base, donor, Target('mono', 'biz', 400, 'normal'),
                   {'name': 'KumiType', 'version': '0.1.0'})
    base.save(path)
    assert validate(path, base_path)['valid']


def test_overflow_is_fitted_horizontally_without_changing_other_outlines():
    from kumitype.merger import merge_many

    donor = make_font({0x2460: 'circle', 0x3042: 'kana'})
    before = make_font({65: 'a'})
    after = make_font({65: 'a'})
    original = after['glyf']['a'].compile(after['glyf'])
    merge(before, donor, fit_overflow=False)
    report = merge_many(after, [donor])
    cmap = after.getBestCmap()
    fitted = after['glyf'][cmap[0x2460]]
    assert (fitted.xMin, fitted.xMax, fitted.yMin, fitted.yMax) == (10, 490, 0, 700)
    assert report['fitted_codepoints'] == [0x2460]
    assert report['overflow_codepoints'] == []
    assert after['glyf']['a'].compile(after['glyf']) == original
    name = cmap[0x3042]
    assert after['glyf'][name].compile(after['glyf']) == before['glyf'][name].compile(before['glyf'])


def test_fit_applies_to_two_cells_and_respects_margin_and_disable(tmp_path):
    from kumitype.outline_cache import OutlineCache

    donor = make_font({0x2460: 'circle', 0x3042: 'kana', 0x30A2: 'katakana'})
    disabled = make_font({65: 'a'})
    report = merge(disabled, donor, jp_scale=2, baseline_offset=37, fit_overflow=False)
    assert report['fitted_codepoints'] == []
    assert 0x3042 in report['overflow_codepoints']
    first = make_font({65: 'a'})
    options = dict(jp_scale=2, baseline_offset=37, fit_margin=0.1)
    identity = {**options, 'fit_overflow': True}
    report = merge(first, donor, outline_cache=OutlineCache(identity, tmp_path), **options)
    assert {0x2460, 0x3042, 0xFF71} <= set(report['fitted_codepoints'])
    assert report['overflow_codepoints'] == []
    cmap = first.getBestCmap()
    for cp in report['fitted_codepoints']:
        glyph = first['glyf'][cmap[cp]]
        width = first['hmtx'][cmap[cp]][0]
        assert (glyph.xMin, glyph.xMax) == (width * 0.1, width * 0.9)
        assert (glyph.yMin, glyph.yMax) == (37, 1437)
    second = make_font({65: 'a'})
    cached = merge(second, donor, outline_cache=OutlineCache(identity, tmp_path), **options)
    assert cached == report
    assert first.getTableData('glyf') == second.getTableData('glyf')
    assert first.getTableData('hmtx') == second.getTableData('hmtx')
    cache = OutlineCache(identity, tmp_path)
    assert cache.path != OutlineCache({**identity, 'fit_margin': 0}, tmp_path).path
    assert cache.path != OutlineCache({**identity, 'fit_overflow': False}, tmp_path).path


def test_cubic_fitting_preserves_converted_vertical_coordinates():
    from kumitype.glyph_transform import transform_glyph

    class Curve:
        def draw(self, pen):
            pen.moveTo((0, 0))
            pen.curveTo((1841, 1434), (2668, 1054), (859, -116))
            pen.lineTo((0, 0))
            pen.closePath()

    original, _, _ = transform_glyph({'curve': Curve()}, 'curve', 1, 500)
    fitted, _, overflow = transform_glyph({'curve': Curve()}, 'curve', 1, 500,
                                         fit_overflow=True, fit_margin=0)
    assert [y for _, y in fitted.coordinates] == [y for _, y in original.coordinates]
    assert (fitted.xMin, fitted.xMax) == (0, 500)
    assert not overflow


def test_cubic_outline_conversion():
    from kumitype.glyph_transform import transform_glyph

    class CubicGlyph:
        def draw(self, pen):
            pen.moveTo((0, 0))
            pen.curveTo((0, 700), (700, 700), (700, 0))
            pen.lineTo((0, 0))
            pen.closePath()

    glyph, _, overflow = transform_glyph({'curve': CubicGlyph()}, 'curve', 1, 1000)
    assert glyph.numberOfContours == 1
    assert glyph.xMin == 150 and glyph.xMax == 850
    assert not overflow


def test_all_metadata_names_unique_and_style_links():
    from kumitype.config import load, targets
    from kumitype.metadata import apply_metadata

    matrix = targets(load('config/build.yaml'))
    names = set()
    for target in matrix:
        base = make_font({65: 'a'})
        donor = make_font({0x3042: 'kana'})
        base['name'].setName('Base Copyright', 0, 3, 1, 0x409)
        donor['name'].setName('Donor Copyright', 0, 3, 1, 0x409)
        result = apply_metadata(base, donor, target, {'name': 'KumiType', 'version': '0.1.0'})
        assert result['postscript_name'] not in names
        names.add(result['postscript_name'])
        assert 'Base Copyright' in base['name'].getDebugName(0)
        assert 'Donor Copyright' in base['name'].getDebugName(0)
        assert base['OS/2'].usWeightClass == target.weight
        assert bool(base['head'].macStyle & 2) == (target.style == 'italic')
        assert bool(base['head'].macStyle & 1) == (target.weight == 700)
        if target.weight not in (400, 700):
            assert base['name'].getDebugName(1) != result['family']
    assert len(names) == 504


def test_instance_cache_checks_integrity(tmp_path):
    from kumitype.font_converter import load_cached_static

    source = tmp_path / 'source.ttf'
    make_font({0x3042: 'kana'}).save(source)
    cache = tmp_path / 'cache'
    first = load_cached_static(source, 400, cache=cache)
    first.close()
    cached = next(cache.glob('*.ttf'))
    good = cached.read_bytes()
    cached.write_bytes(b'corrupt')
    rebuilt = load_cached_static(source, 400, cache=cache)
    assert ord('あ') in rebuilt.getBestCmap()
    rebuilt.close()
    assert cached.read_bytes() == good


def test_packaging_rejects_modified_output(tmp_path):
    import hashlib
    import json

    import pytest

    from kumitype.packager import package_all

    root = tmp_path / 'build'
    root.mkdir()
    path = root / 'font.ttf'
    make_font({65: 'a'}).save(path)
    manifest = {'validation': {'valid': True},
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_suffix('.json').write_text(json.dumps(manifest))
    path.write_bytes(path.read_bytes() + b'modified')
    with pytest.raises(ValueError, match='modified output'):
        package_all(root=root, source=tmp_path / 'source', output=tmp_path / 'dist')


def test_packaging_refuses_missing_license(tmp_path):
    from kumitype.config import Target
    from kumitype.metadata import apply_metadata
    import hashlib
    import json

    import pytest

    from kumitype.packager import package_all

    root = tmp_path / 'build'
    root.mkdir()
    path = root / 'font.ttf'
    font = make_font({65: 'a'})
    apply_metadata(font, font, Target('mono', 'biz', 400, 'normal'),
                   {'name': 'KumiType', 'version': '2.3.4'})
    font.save(path)
    manifest = {'validation': {'valid': True},
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'sources': [{'path': str(path)}],
                'identity': {'family': 'KumiType BIZ Mono', 'style': 'Regular',
                             'postscript_name': 'KumiTypeBIZMono-Regular'},
                'config': {'project': {'name': 'KumiType', 'version': '2.3.4'}},
                'target': {'base': 'mono', 'japanese': 'biz', 'weight': 400, 'style': 'normal'}}
    path.with_suffix('.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Missing Cascadia license'):
        package_all(root=root, source=tmp_path / 'source', output=tmp_path / 'dist')


def test_split_sources_union_without_duplicate_import():
    from kumitype.merger import merge_many

    base = make_font({65: 'a'})
    first = make_font({0x3042: 'kana'})
    second = make_font({0x3042: 'overlap', 0x20000: 'han'})
    original_count = len(base.getGlyphOrder())
    result = merge_many(base, [first, second])
    assert result['added_codepoints'] == [0x3042, 0x20000]
    assert len(base.getGlyphOrder()) == original_count + 2


def test_packaging_rejects_obsolete_reserved_name(tmp_path):
    import hashlib
    import json

    import pytest

    from kumitype.packager import package_all

    root = tmp_path / 'build'
    root.mkdir()
    path = root / 'old.ttf'
    make_font({65: 'a'}).save(path)
    manifest = {'validation': {'valid': True},
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'target': {'base': 'mono', 'japanese': 'plex', 'weight': 400, 'style': 'normal'},
                'config': {'project': {'name': 'KumiType'}},
                'identity': {'family': 'KumiType Plex Mono', 'style': 'Regular',
                             'postscript_name': 'KumiTypePlexMono-Regular'}}
    path.with_suffix('.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Obsolete font naming'):
        package_all(root=root, source=tmp_path / 'source', output=tmp_path / 'dist')


def test_validation_detects_empty_names_and_bad_weight(tmp_path):
    font = make_font({65: 'a'})
    font['OS/2'].usWeightClass = 0
    font['name'].names = [record for record in font['name'].names if record.nameID != 6]
    path = tmp_path / 'invalid.ttf'
    font.save(path)
    result = validate(path)
    assert not result['valid']
    assert 'Invalid weight class' in result['errors']
    assert 'Missing font name ID 6' in result['errors']


def test_offline_build_orchestration(tmp_path, monkeypatch):
    import hashlib
    import json

    from kumitype.builder import build_one
    from kumitype.config import Target

    source = tmp_path / 'source'
    base_path = source / 'cascadia/1/ttf/static/CascadiaMono-Regular.ttf'
    base_path.parent.mkdir(parents=True)
    make_font({65: 'a'}).save(base_path)
    donor_path = source / 'biz/1/donor.ttf'
    donor_path.parent.mkdir(parents=True)
    make_font({0x3042: 'kana', 0x030F: 'mark'}).save(donor_path)
    records = []
    for identifier, path in [('cascadia', base_path), ('biz', donor_path)]:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record = {'id': identifier, 'version': '1', 'url': 'https://example.org/' + identifier,
                  'sha256': digest, 'format': 'ttf'}
        records.append(record)
        from kumitype.font_inspector import inspect_font
        info = inspect_font(path)
        info['sha256'] = digest
        manifest = {**record, 'fonts': [info]}
        (source / identifier / '1/source-manifest.json').write_text(json.dumps(manifest))
    lock = tmp_path / 'lock.toml'
    lock.write_text('\n'.join('[[sources]]\n' + '\n'.join(
        f'{key}={json.dumps(value)}' for key, value in record.items()) for record in records))
    license_file = tmp_path / 'subset-OFL.txt'
    license_file.write_text('Additional source license')
    config = {'project': {'name': 'KumiType', 'version': '0.1.0'},
              'sources': {'cascadia': {'version': '1'}, 'lock': str(lock)}}
    config['font_overrides'] = {'biz': {'subset_licenses': [str(license_file)]}}
    def no_network(*args, **kwargs):
        raise AssertionError('offline build used network')
    monkeypatch.setattr('urllib.request.urlopen', no_network)
    monkeypatch.chdir(tmp_path)
    path = build_one(config, Target('mono', 'biz', 400, 'normal'), source, tmp_path / 'build')
    manifest = json.loads(path.with_suffix('.json').read_text())
    assert manifest['validation']['valid']
    assert manifest['coverage']['coverage_ratio'] == 1
    assert manifest['additional_licenses'] == [{'path': str(license_file),
        'sha256': hashlib.sha256(license_file.read_bytes()).hexdigest()}]
    assert manifest['identity']['family'] == 'KumiType BIZ Mono'
    assert manifest['config_sha256'] == hashlib.sha256(json.dumps(
        config, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert manifest['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    from kumitype.validator import validate_all
    assert manifest['merge']['zero_width_mark_codepoints'] == [0x030F]
    manifest['merge']['zero_width_mark_codepoints'] = []
    path.with_suffix('.json').write_text(json.dumps(manifest))
    checked = validate_all(path.parent, harfbuzz='nonexistent-kumitype-hb-shape')
    assert 'Zero-width mark inventory differs from binary' in checked[0]['errors']
    manifest['config']['project']['version'] = 'tampered'
    path.with_suffix('.json').write_text(json.dumps(manifest))
    checked = validate_all(path.parent, harfbuzz='nonexistent-kumitype-hb-shape')
    assert not checked[0]['valid']
    assert 'Configuration checksum differs from manifest' in checked[0]['errors']


def test_outline_cache_matches_uncached_merge(tmp_path):
    from kumitype.outline_cache import OutlineCache

    first = make_font({65: 'a'})
    second = make_font({65: 'a'})
    donor = make_font({0x3042: 'kana'})
    cache = OutlineCache({'source': 'synthetic', 'scale': 1}, tmp_path)
    merge(first, donor, outline_cache=cache)
    reloaded = OutlineCache({'source': 'synthetic', 'scale': 1}, tmp_path)
    merge(second, donor, outline_cache=reloaded)
    assert first.getTableData('glyf') == second.getTableData('glyf')
    assert first.getTableData('hmtx') == second.getTableData('hmtx')


def test_corrupted_outline_cache_is_discarded(tmp_path):
    import json

    from kumitype.outline_cache import OutlineCache

    cache = OutlineCache({'source': 'synthetic'}, tmp_path)
    cache.path.write_text(json.dumps({'payload': '{}', 'sha256': 'wrong'}))
    reloaded = OutlineCache({'source': 'synthetic'}, tmp_path)
    assert reloaded.get(0x3042) is None
    cache.path.write_text('truncated JSON')
    assert OutlineCache({'source': 'synthetic'}, tmp_path).get(0x3042) is None


def test_additional_donor_copyright_and_license_are_preserved():
    from kumitype.config import Target
    from kumitype.metadata import apply_metadata

    base = make_font({65: 'a'})
    donor = make_font({0x3042: 'kana'})
    subset = make_font({0x20000: 'han'})
    subset['name'].setName('Subset Copyright', 0, 3, 1, 0x409)
    subset['name'].setName('Subset license text', 13, 3, 1, 0x409)
    apply_metadata(base, donor, Target('mono', 'biz', 400, 'normal'),
                   {'name': 'KumiType', 'version': '0.1.0'}, [subset])
    assert 'Subset Copyright' in base['name'].getDebugName(0)
    assert 'Subset license text' in base['name'].getDebugName(13)


def test_validation_rejects_changed_base_advance(tmp_path):
    base = make_font({65: 'a'})
    original = tmp_path / 'base.ttf'
    base.save(original)
    base['hmtx'].metrics['a'] = (600, 0)
    changed = tmp_path / 'changed.ttf'
    base.save(changed)
    result = validate(changed, original)
    assert not result['valid']
    assert 'Base horizontal metric changed: a' in result['errors']


def test_halfwidth_kana_scale_does_not_change_fullwidth_or_advance():
    base = make_font({65: 'a'})
    donor = make_font({0xFF71: 'halfkana', 0x3042: 'kana'})
    report = merge(base, donor, halfwidth_kana_scale=0.5)
    cmap = base.getBestCmap()
    half = base['glyf'][cmap[0xFF71]]
    full = base['glyf'][cmap[0x3042]]
    assert half.xMax - half.xMin == 350
    assert full.xMax - full.xMin == 700
    assert base['hmtx'][cmap[0xFF71]][0] == 500
    assert base['hmtx'][cmap[0x3042]][0] == 1000
    assert 0xFF71 not in report['overflow_codepoints']


def test_validation_rejects_extra_private_use_mapping(tmp_path):
    base = make_font({65: 'a'})
    original = tmp_path / 'base.ttf'
    base.save(original)
    for table in base['cmap'].tables:
        if table.isUnicode():
            table.cmap[0xE123] = 'a'
    changed = tmp_path / 'changed.ttf'
    base.save(changed)
    result = validate(changed, original)
    assert not result['valid']
    assert 'Unexpected PUA character added: U+E123' in result['errors']


def test_missing_halfwidth_kana_derived_from_selected_source():
    base = make_font({65: 'a'})
    donor = make_font({0x30A2: 'katakanaA'})
    report = merge(base, donor)
    cmap = base.getBestCmap()
    assert 0xFF71 in report['derived_halfwidth_codepoints']
    assert base['hmtx'][cmap[0xFF71]][0] == 500
    glyph = base['glyf'][cmap[0xFF71]]
    assert glyph.xMax - glyph.xMin == 350
    assert glyph.yMax == 700


def test_derived_kana_cache_retains_geometry_and_provenance(tmp_path):
    from kumitype.outline_cache import OutlineCache

    donor = make_font({0x30A2: 'katakanaA', 0xFF72: 'existingHalfwidth'})
    first = make_font({65: 'a'})
    report = merge(first, donor, outline_cache=OutlineCache({'source': 'synthetic'}, tmp_path))
    second = make_font({65: 'a'})
    cached_report = merge(second, donor, outline_cache=OutlineCache({'source': 'synthetic'}, tmp_path))
    assert report == cached_report
    assert 0xFF71 in report['derived_halfwidth_codepoints']
    assert 0xFF72 not in report['derived_halfwidth_codepoints']
    assert first.getTableData('glyf') == second.getTableData('glyf')
    assert first.getTableData('hmtx') == second.getTableData('hmtx')
