"""Static source instantiation, keeping source files immutable."""
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def load_static(path: str | Path, weight: int, italic: bool = False) -> TTFont:
    font = TTFont(path, recalcTimestamp=False)
    try:
        if 'fvar' in font:
            coordinates = {axis.axisTag: axis.defaultValue for axis in font['fvar'].axes}
            for axis in font['fvar'].axes:
                if axis.axisTag == 'wght':
                    value = weight
                elif axis.axisTag == 'ital':
                    value = int(italic)
                else:
                    continue
                if not axis.minValue <= value <= axis.maxValue:
                    raise ValueError(f'{path}: {axis.axisTag}={value} outside supported range')
                coordinates[axis.axisTag] = value
            result = instantiateVariableFont(font, coordinates, inplace=True)
            if 'fvar' in result:
                raise ValueError(f'{path}: static instantiation left variable axes')
            return result
        return font
    except Exception:
        font.close()
        raise


def load_cached_static(path: str | Path, weight: int, italic: bool = False,
                       cache: Path = Path('cache/instances')) -> TTFont:
    """Reuse verified static instances with content and dependency keyed entries."""
    import hashlib
    import json
    import os
    import tempfile

    from fontTools import version

    from .downloader import sha256

    path = Path(path)
    key = hashlib.sha256(json.dumps([sha256(path), weight, italic, version],
                                    separators=(',', ':')).encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / (key + '.ttf')
    checksum = cache / (key + '.sha256')
    if destination.exists() and checksum.exists():
        if sha256(destination) == checksum.read_text(encoding='ascii').strip():
            return TTFont(destination, recalcTimestamp=False)
    font = load_static(path, weight, italic)
    fd, temporary = tempfile.mkstemp(dir=cache, suffix='.ttf')
    os.close(fd)
    try:
        font.save(temporary)
        digest = sha256(Path(temporary))
        os.replace(temporary, destination)
        checksum.write_text(digest + '\n', encoding='ascii')
    finally:
        Path(temporary).unlink(missing_ok=True)
        font.close()
    return TTFont(destination, recalcTimestamp=False)
