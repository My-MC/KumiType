"""Normalize and center decomposed outlines without donor hint programs."""
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen


def transform_glyph(glyph_set, name: str, scale: float, width: int,
                    baseline: float = 0, reverse_direction: bool = False, horizontal_scale: float = 1):
    recording = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(recording)
    bounds = BoundsPen(None)
    recording.replay(bounds)
    shift = 0
    overflow = False
    if bounds.bounds:
        left, _, right, _ = bounds.bounds
        shift = (width - (right - left) * scale * horizontal_scale) / 2 - left * scale * horizontal_scale
        overflow = (right - left) * scale * horizontal_scale > width
    pen = TTGlyphPen(None)
    conversion = Cu2QuPen(pen, max_err=1.0, reverse_direction=reverse_direction)
    recording.replay(TransformPen(conversion, (scale * horizontal_scale, 0, 0, scale, shift, baseline)))
    glyph = pen.glyph()
    glyph.recalcBounds(None)
    return glyph, getattr(glyph, 'xMin', 0), overflow
