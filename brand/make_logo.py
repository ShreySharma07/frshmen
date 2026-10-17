"""Outline 'kario' in Instrument Serif into SVG paths (the wordmark becomes a logo, not a font)."""
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

font = TTFont(sys.argv[1]); out = sys.argv[2]
gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
upm = font["head"].unitsPerEm
TRACK = -0.02 * upm  # matches the prototype's tight tracking

def outline(text, x0=0.0, y0=0.0, scale=1.0):
    """Paths for text with the baseline at y0 (SVG y grows downward)."""
    pen, bounds, x = SVGPathPen(gs), BoundsPen(gs), x0
    for ch in text:
        g = cmap[ord(ch)]
        t = (scale, 0, 0, -scale, x, y0)
        gs[g].draw(TransformPen(pen, t)); gs[g].draw(TransformPen(bounds, t))
        x += (hmtx[g][0] + TRACK) * scale
    return pen.getCommands(), bounds.bounds

# Wordmark: tight viewBox around the ink, fill = currentColor so it follows the text colour.
d, (x1, y1, x2, y2) = outline("kario", y0=upm)
pad = 0.02 * upm
vb = f"{x1 - pad:.0f} {y1 - pad:.0f} {x2 - x1 + 2 * pad:.0f} {y2 - y1 + 2 * pad:.0f}"
open(f"{out}/kario-wordmark.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="kario">'
    f'<path fill="currentColor" d="{d}"/></svg>\n')

# Mark: a lowercase 'k' centred in a rounded square, for the favicon and app icon.
S = 512
k_d, (a1, b1, a2, b2) = outline("k", scale=1.0, y0=0)
sc = 0.62 * S / (b2 - b1)
k_d, (a1, b1, a2, b2) = outline("k", scale=sc, y0=0)
dx, dy = (S - (a2 - a1)) / 2 - a1, (S - (b2 - b1)) / 2 - b1
open(f"{out}/kario-mark.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="kario">'
    f'<rect width="{S}" height="{S}" rx="{S * 0.22:.0f}" fill="#0A0A12"/>'
    f'<g transform="translate({dx:.1f} {dy:.1f})"><path fill="#FFFFFF" d="{k_d}"/></g></svg>\n')
print("viewBox", vb)
