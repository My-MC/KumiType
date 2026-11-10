"""Independent family naming and legacy four-style links."""
import re

from fontTools.misc.fixedTools import floatToFixedToFloat
from fontTools.otlLib.builder import buildStatTable

WEIGHT_NAMES = {200: 'ExtraLight', 300: 'Light', 350: 'SemiLight',
                400: 'Regular', 600: 'SemiBold', 700: 'Bold'}
JP_NAMES = {'plex': 'IBMJP', 'biz': 'BIZ', 'noto': 'Noto', 'line-seed': 'LINESeed',
            'mplus1': 'MPlus1', 'mplus2': 'MPlus2', 'zen-kaku': 'ZenKaku'}


def font_revision(version: str) -> float:
    """Encode major.minor.patch as major.minorPP in OpenType 16.16.

    Patch uses two decimal places (0.1.0 -> 0.100); reject unrepresentable
    versions rather than silently dropping a release component.
    """
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d{1,2})', version)
    if not match:
        raise ValueError(f'Unsupported font version: {version}')
    major, minor, patch = match.groups()
    if len(minor) != 1:
        raise ValueError(f'Unsupported font version (minor must be 0-9): {version}')
    value = float(f'{major}.{minor}{int(patch):02d}')
    if value >= 32768:
        raise ValueError(f'Font version exceeds 16.16 range: {version}')
    return floatToFixedToFloat(value, 16)


def metadata_errors(font, version: str) -> list[str]:
    """Return independent errors for the generated-font metadata contract."""
    errors = []
    if 'DSIG' in font:
        errors.append('DSIG must be absent after modification')
    if not font['OS/2'].ulCodePageRange1 & (1 << 17):
        errors.append('OS/2.ulCodePageRange1 bit17 (JIS/Japan) is not set')
    if font['OS/2'].achVendID != 'NONE':
        errors.append("OS/2.achVendID must be NONE")
    try:
        expected = font_revision(version)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        if font['head'].fontRevision != expected:
            errors.append(f'head.fontRevision differs from project.version {version}')
    return errors


def apply_metadata(font, donor, target, project: dict, additional_donors=()) -> dict:
    weight_name = WEIGHT_NAMES[target.weight]
    italic = target.style == 'italic'
    bold = target.weight == 700
    variant = target.base.replace('-pl', ' PL').replace('-nf', ' NF')
    variant = variant[0].upper() + variant[1:]
    family = f"{project['name']} {project.get('font_names', JP_NAMES)[target.japanese]} {variant}"
    style = weight_name + (' Italic' if italic else '')
    legacy_family = family if target.weight in (400, 700) else f'{family} {weight_name}'
    legacy_style = ('Bold Italic' if bold and italic else 'Bold' if bold else
                    'Italic' if italic else 'Regular')
    ps = re.sub(r'[^A-Za-z0-9-]', '', family) + '-' + style.replace(' ', '')
    if len(ps) > 63:
        raise ValueError('PostScript name exceeds 63 characters')
    names = font['name']
    values = {1: legacy_family, 2: legacy_style, 3: f"{project['version']};{ps}",
              4: f'{family} {style}', 5: f"Version {project['version']}",
              6: ps, 16: family, 17: style}
    for identifier in (0, 13, 14):
        texts = [source['name'].getDebugName(identifier) for source in (font, donor, *additional_donors)]
        values[identifier] = '\n'.join(dict.fromkeys(t for t in texts if t))
    names.names = [n for n in names.names if n.nameID not in values and n.nameID not in (18, 21, 22)]
    for identifier, text in values.items():
        if text:
            names.setName(text, identifier, 3, 1, 0x409)
    if 'DSIG' in font:
        del font['DSIG']
    font['OS/2'].ulCodePageRange1 |= 1 << 17
    font['OS/2'].achVendID = 'NONE'
    font['head'].fontRevision = font_revision(project['version'])
    font['OS/2'].usWeightClass = target.weight
    selection = font['OS/2'].fsSelection & ~((1 << 0) | (1 << 5) | (1 << 6))
    selection |= int(italic) | (int(bold) << 5) | (int(not bold and not italic) << 6)
    font['OS/2'].fsSelection = selection
    font['head'].macStyle = (font['head'].macStyle & ~3) | int(bold) | (int(italic) << 1)
    font['head'].flags |= 1 << 3  # Preserve Cascadia hinting with integer PPEM.
    font['OS/2'].panose.bFamilyType = 2  # Latin text; CJK keeps two-cell metrics.
    font['OS/2'].panose.bProportion = 9
    buildStatTable(font, [
        {'tag': 'wght', 'name': 'Weight', 'values': [
            {'value': target.weight, 'name': weight_name, 'flags': 2 if target.weight == 400 else 0}]},
        {'tag': 'ital', 'name': 'Italic', 'values': [
            {'value': int(italic), 'name': 'Italic' if italic else 'Roman',
             'flags': 0 if italic else 2, **({} if italic else {'linkedValue': 1.0})}]},
    ], macNames=False)
    return {'family': family, 'style': style, 'postscript_name': ps}


def expected_identity(target, project: dict) -> dict:
    variant = target.base.replace('-pl', ' PL').replace('-nf', ' NF')
    variant = variant[0].upper() + variant[1:]
    family = f"{project['name']} {project.get('font_names', JP_NAMES)[target.japanese]} {variant}"
    style = WEIGHT_NAMES[target.weight] + (' Italic' if target.style == 'italic' else '')
    ps = re.sub(r'[^A-Za-z0-9-]', '', family) + '-' + style.replace(' ', '')
    return {'family': family, 'style': style, 'postscript_name': ps}
