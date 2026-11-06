"""Independent family naming and legacy four-style links."""
import re

WEIGHT_NAMES = {200: 'ExtraLight', 300: 'Light', 350: 'SemiLight',
                400: 'Regular', 600: 'SemiBold', 700: 'Bold'}
JP_NAMES = {'plex': 'IBMJP', 'biz': 'BIZ', 'noto': 'Noto', 'line-seed': 'LINESeed',
            'mplus1': 'MPlus1', 'mplus2': 'MPlus2', 'zen-kaku': 'ZenKaku'}


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
    font['OS/2'].usWeightClass = target.weight
    selection = font['OS/2'].fsSelection & ~((1 << 0) | (1 << 5) | (1 << 6))
    selection |= int(italic) | (int(bold) << 5) | (int(not bold and not italic) << 6)
    font['OS/2'].fsSelection = selection
    font['head'].macStyle = (font['head'].macStyle & ~3) | int(bold) | (int(italic) << 1)
    return {'family': family, 'style': style, 'postscript_name': ps}


def expected_identity(target, project: dict) -> dict:
    variant = target.base.replace('-pl', ' PL').replace('-nf', ' NF')
    variant = variant[0].upper() + variant[1:]
    family = f"{project['name']} {project.get('font_names', JP_NAMES)[target.japanese]} {variant}"
    style = WEIGHT_NAMES[target.weight] + (' Italic' if target.style == 'italic' else '')
    ps = re.sub(r'[^A-Za-z0-9-]', '', family) + '-' + style.replace(' ', '')
    return {'family': family, 'style': style, 'postscript_name': ps}
