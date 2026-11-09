"""Binary integrity and protected-source invariants."""
import hashlib
import json
from dataclasses import asdict
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

from fontTools.ttLib import TTFont

from .config import Target, targets
from .downloader import sha256
from .glyph_selector import cell_count, private_use
from .metadata import metadata_errors
from .shaping import compare_shaping


def validate(path: str | Path, base_path: str | Path | None = None, *,
             project_version: str | None = None) -> dict:
    if project_version is None:
        project_version = version('KumiType')
    errors: list[str] = []
    with TTFont(path, recalcTimestamp=False) as font:
        required = {'head', 'hhea', 'hmtx', 'maxp', 'OS/2', 'name', 'cmap', 'post', 'glyf', 'loca'}
        errors.extend(f'Missing table: {tag}' for tag in sorted(required - set(font.keys())))
        if errors:
            return {'valid': False, 'errors': errors}
        errors.extend(metadata_errors(font, project_version))
        order = font.getGlyphOrder()
        cmap = font.getBestCmap() or {}
        if 'fvar' in font:
            errors.append('Output is variable')
        if not 0 < len(order) <= 65535:
            errors.append('Invalid glyph count')
        if font['maxp'].numGlyphs != len(order):
            errors.append('maxp glyph count differs from glyph order')
        if not 16 <= font['head'].unitsPerEm <= 16384:
            errors.append('Invalid unitsPerEm')
        if not 1 <= font['OS/2'].usWeightClass <= 1000:
            errors.append('Invalid weight class')
        if not cmap:
            errors.append('Empty Unicode cmap')
        for identifier in (1, 2, 4, 6):
            if not font['name'].getDebugName(identifier):
                errors.append(f'Missing font name ID {identifier}')
        for name in order:
            metric = font['hmtx'].metrics.get(name)
            if metric is None or not 0 <= metric[0] <= 65535 or not -32768 <= metric[1] <= 32767:
                errors.append(f'Invalid horizontal metric: {name}')
        for cp, name in cmap.items():
            if name not in font['hmtx'].metrics or name not in font['glyf'].glyphs:
                errors.append(f'Invalid cmap reference: U+{cp:04X}')
        for name in order:
            glyph = font['glyf'][name]
            if glyph.isComposite():
                for component in glyph.components:
                    if component.glyphName not in font['glyf'].glyphs:
                        errors.append(f'Invalid component in {name}')
        if base_path:
            with TTFont(base_path) as base:
                original_order = base.getGlyphOrder()
                if order[:len(original_order)] != original_order:
                    errors.append('Base glyph IDs changed')
                for name in original_order:
                    if font['hmtx'].metrics.get(name) != base['hmtx'].metrics.get(name):
                        errors.append(f'Base horizontal metric changed: {name}')
                original = base.getBestCmap() or {}
                extra_pua = {cp for cp in cmap if private_use(cp)} - {cp for cp in original if private_use(cp)}
                for cp in sorted(extra_pua):
                    errors.append(f'Unexpected PUA character added: U+{cp:04X}')
                for cp, name in original.items():
                    if private_use(cp) and cmap.get(cp) != name:
                        errors.append(f'Protected PUA changed: U+{cp:04X}')
                for tag in ('GSUB', 'GPOS', 'GDEF'):
                    if tag in base and (tag not in font or base.getTableData(tag) != font.getTableData(tag)):
                        errors.append(f'Base layout table changed: {tag}')
        buffer = BytesIO()
        font.save(buffer)
        buffer.seek(0)
        with TTFont(buffer) as roundtrip:
            roundtrip.ensureDecompiled()
    return {'valid': not errors, 'errors': errors}


def validate_all(root: Path = Path('build'), *, harfbuzz='hb-shape') -> list[dict]:
    """Revalidate tracked outputs, including manifest hashes and source invariants."""
    results = []
    names = {}
    for path in sorted(root.rglob('*.ttf')):
        try:
            manifest_path = path.with_suffix('.json')
            if not manifest_path.exists():
                results.append({'path': str(path), 'valid': False, 'errors': ['Missing manifest']})
                continue
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            base = manifest['sources'][0]['path']
            result = validate(path, base,
                              project_version=manifest.get('config', {}).get('project', {}).get('version'))
            if 'config_sha256' in manifest:
                config_digest = hashlib.sha256(json.dumps(manifest['config'], sort_keys=True,
                    separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
                if config_digest != manifest['config_sha256']:
                    result['errors'].append('Configuration checksum differs from manifest')
            if sha256(path) != manifest['sha256']:
                result['errors'].append('Output checksum differs from manifest')
            with TTFont(path) as font:
                ps = font['name'].getDebugName(6)
                if ps != manifest['identity']['postscript_name']:
                    result['errors'].append('PostScript name differs from manifest')
                if font['name'].getDebugName(16) != manifest['identity']['family']:
                    result['errors'].append('Typographic family differs from manifest')
                if font['OS/2'].usWeightClass != manifest['target']['weight']:
                    result['errors'].append('Weight differs from target')
                if ps in names:
                    result['errors'].append(f'Duplicate PostScript name: {ps}')
                names[ps] = str(path)
                cmap = font.getBestCmap() or {}
                cell = manifest['merge']['cell_width']
                result['errors'].extend(check_halfwidth_kana(cmap, font['hmtx'].metrics, cell))
                for cp in manifest['merge']['added_codepoints']:
                    if cp not in cmap:
                        result['errors'].append(f'Missing imported character: U+{cp:04X}')
                    elif font['hmtx'].metrics[cmap[cp]][0] != cell * cell_count(cp):
                        result['errors'].append(f'Incorrect cell width: U+{cp:04X}')
            result['shaping'] = compare_shaping(Path(base), path, harfbuzz)
            result['errors'].extend(result['shaping']['errors'])
            result['valid'] = not result['errors']
            results.append({'path': str(path), **result})
        except Exception as exc:
            results.append({'path': str(path), 'valid': False,
                            'errors': [f'{type(exc).__name__}: {exc}']})
    return results


def audit_matrix(config: dict, root=Path('build')) -> dict:
    """Check the complete requested matrix, rather than merely counting files."""
    expected = set(targets(config))
    observed = {}
    errors = []
    for path in sorted(root.rglob('*.json')):
        font = path.with_suffix('.ttf')
        if not font.exists():
            continue
        record = json.loads(path.read_text(encoding='utf-8'))
        try:
            target = Target(**record['target'])
        except (KeyError, TypeError) as exc:
            errors.append(f'Invalid target manifest: {path}: {exc}')
            continue
        if target in observed:
            errors.append(f'Duplicate target: {target}')
        observed[target] = str(font)
        if not record.get('validation', {}).get('valid'):
            errors.append(f'Unvalidated target: {target}')
    missing = expected - observed.keys()
    unexpected = observed.keys() - expected
    def key(t):
        return (t.base, t.japanese, t.weight, t.style)
    return {'complete': not missing and not unexpected and not errors,
            'expected_count': len(expected), 'observed_count': len(observed),
            'missing': [asdict(t) for t in sorted(missing, key=key)],
            'unexpected': [asdict(t) for t in sorted(unexpected, key=key)], 'errors': errors}


def check_halfwidth_kana(cmap: dict, metrics: dict, cell: int) -> list[str]:
    errors = []
    for cp in range(0xFF61, 0xFFA0):
        name = cmap.get(cp)
        if name is None:
            errors.append(f'Missing halfwidth kana: U+{cp:04X}')
        elif metrics.get(name, (None,))[0] != cell:
            errors.append(f'Incorrect halfwidth kana cell: U+{cp:04X}')
    return errors
