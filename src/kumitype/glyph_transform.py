"""Normalize and center decomposed outlines without donor hint programs."""
from fontTools.misc.roundTools import otRound
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen


def transform_glyph(glyph_set, name: str, scale: float, width: int,
                    baseline: float = 0, reverse_direction: bool = False, horizontal_scale: float = 1,
                    fit_overflow: bool = False, fit_margin: float = 0.02):
    recording = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(recording)
    bounds = BoundsPen(None)
    recording.replay(bounds)
    shift = 0
    if bounds.bounds:
        left, _, right, _ = bounds.bounds
        shift = (width - (right - left) * scale * horizontal_scale) / 2 - left * scale * horizontal_scale
    pen = TTGlyphPen(None)
    conversion = Cu2QuPen(pen, max_err=1.0, reverse_direction=reverse_direction)
    recording.replay(TransformPen(conversion, (scale * horizontal_scale, 0, 0, scale, shift, baseline)))
    glyph = pen.glyph()
    glyph.recalcBounds(None)
    if fit_overflow:
        return fit_glyph(glyph, width, fit_margin)
    return glyph, getattr(glyph, 'xMin', 0), glyph_overflows(glyph, width)


def glyph_overflows(glyph, width):
    return getattr(glyph, 'xMax', 0) - getattr(glyph, 'xMin', 0) > width


def fit_glyph(glyph, width, margin):
    """Fit finalized quadratic coordinates, retaining every y coordinate."""
    if glyph_overflows(glyph, width):
        left = glyph.xMin
        factor = width * (1 - 2 * margin) / (glyph.xMax - left)
        for index, (x, y) in enumerate(glyph.coordinates):
            glyph.coordinates[index] = (otRound((x - left) * factor + width * margin), y)
        glyph.recalcBounds(None)
    return glyph, getattr(glyph, 'xMin', 0), glyph_overflows(glyph, width)
