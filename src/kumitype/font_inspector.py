"""Read source identity without modifying source fonts."""
from pathlib import Path

from fontTools.ttLib import TTFont


def inspect_font(path: str | Path) -> dict:
    with TTFont(path, lazy=True) as font:
        axes = []
        if 'fvar' in font:
            axes = [{'tag': a.axisTag, 'min': a.minValue,
                     'default': a.defaultValue, 'max': a.maxValue}
                    for a in font['fvar'].axes]
        return {
            'path': str(path),
            'family': font['name'].getDebugName(16) or font['name'].getDebugName(1),
            'style': font['name'].getDebugName(17) or font['name'].getDebugName(2),
            'weight': font['OS/2'].usWeightClass,
            'italic': bool(font['OS/2'].fsSelection & 1),
            'axes': axes,
            'outline': 'truetype' if 'glyf' in font else 'cff',
            'glyph_count': font['maxp'].numGlyphs,
            'codepoints': sorted((font.getBestCmap() or {}).keys()),
            'license': font['name'].getDebugName(13),
            'copyright': font['name'].getDebugName(0),
        }
