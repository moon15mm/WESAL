"""Generates the WESAL identity as fully outlined SVG files (text converted to paths with
HarfBuzz shaping, so Arabic joining and the kasra are correct without installed fonts).

    python brand/tools/build_brand.py   (needs fontTools + uharfbuzz; fonts from frontend/node_modules/@fontsource)
PNG/ICO/PDF exports are produced by brand/tools/render.mjs (Playwright) and WeasyPrint.
"""
from __future__ import annotations

import pathlib

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
FS = ROOT / "frontend" / "node_modules" / "@fontsource"
OUT = ROOT / "brand"
SVG = OUT / "svg"
SVG.mkdir(parents=True, exist_ok=True)

NAVY, TEAL, MINT, WHITE = "#102B46", "#20B99A", "#55D6B0", "#FFFFFF"
AR_FONT = FS / "ibm-plex-sans-arabic" / "files" / "ibm-plex-sans-arabic-arabic-700-normal.woff"
EN_FONT = FS / "inter" / "files" / "inter-latin-700-normal.woff"
EN_FONT_REG = FS / "inter" / "files" / "inter-latin-500-normal.woff"


def shape_to_path(font_path: pathlib.Path, text: str, size: float, rtl: bool = False, tracking: float = 0.0):
    """Return (svg path d, advance width, ascent) for text at `size` px, baseline at y=0."""
    tt = TTFont(str(font_path))
    upem = tt["head"].unitsPerEm
    # HarfBuzz needs raw sfnt data: decompress woff via fontTools
    import io

    buf = io.BytesIO()
    tt.flavor = None
    tt.save(buf)
    face = hb.Face(buf.getvalue())
    font = hb.Font(face)
    hbuf = hb.Buffer()
    hbuf.add_str(text)
    hbuf.guess_segment_properties()
    if rtl:
        hbuf.direction = "rtl"
    hb.shape(font, hbuf, {"kern": True, "liga": True})
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    scale = size / upem
    x = 0.0
    parts = []
    bpen = BoundsPen(gs)
    for info, pos in zip(hbuf.glyph_infos, hbuf.glyph_positions):
        name = order[info.codepoint]
        pen = SVGPathPen(gs)
        tpen = TransformPen(pen, (scale, 0, 0, -scale, x + pos.x_offset * scale, -pos.y_offset * scale))
        gs[name].draw(tpen)
        gs[name].draw(TransformPen(bpen, (scale, 0, 0, -scale, x + pos.x_offset * scale, -pos.y_offset * scale)))
        d = pen.getCommands()
        if d:
            parts.append(d)
        x += pos.x_advance * scale + tracking
    # bounds in SVG coords (y down): (xmin, ymin, xmax, ymax)
    return " ".join(parts), x - tracking, bpen.bounds


def mark(x: float, y: float, s: float, variant: str = "color") -> str:
    """The WESAL mark in a 64-unit grid, placed at (x, y) with size s."""
    bg = {"color": NAVY, "inverse": WHITE, "mono": NAVY, "mono_white": WHITE, "on_dark": TEAL}[variant]
    fg = {"color": TEAL, "inverse": NAVY, "mono": WHITE, "mono_white": NAVY, "on_dark": WHITE}[variant]
    ac = {"color": MINT, "inverse": TEAL, "mono": WHITE, "mono_white": NAVY, "on_dark": NAVY}[variant]
    k = s / 64
    return (
        f'<g transform="translate({x:.2f} {y:.2f}) scale({k:.5f})">'
        f'<rect width="64" height="64" rx="16" fill="{bg}"/>'
        f'<path d="M17 24 Q32 9 47 24" stroke="{ac}" stroke-width="3" fill="none" stroke-linecap="round" opacity=".8"/>'
        f'<path d="M17 24 Q24 41 32 45 Q40 41 47 24" stroke="{fg}" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="17" cy="24" r="6" fill="{ac}" stroke="{bg}" stroke-width="2.5"/>'
        f'<circle cx="47" cy="24" r="6" fill="{ac}" stroke="{bg}" stroke-width="2.5"/>'
        f'<circle cx="32" cy="45" r="7" fill="{fg}" stroke="{bg}" stroke-width="2.5"/></g>'
    )


def svg(w: float, h: float, body: str, title: str, bg: str | None = None) -> str:
    rect = f'<rect width="100%" height="100%" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" role="img" aria-label="{title}">'
            f"<title>{title}</title>{rect}{body}</svg>\n")


def write(name: str, content: str) -> None:
    (SVG / name).write_text(content, encoding="utf-8")


AR_D, AR_W, AR_B = shape_to_path(AR_FONT, "وِصال", 92, rtl=True)
EN_D, EN_W, EN_B = shape_to_path(EN_FONT, "WESAL", 34, tracking=8)
TAG_AR_D, TAG_AR_W, TAG_AR_B = shape_to_path(AR_FONT, "كل السوق في اتصال واحد", 26, rtl=True)
TAG_EN_D, TAG_EN_W, TAG_EN_B = shape_to_path(EN_FONT_REG, "One Market. Connected.", 24)


def lockup(variant: str, *, ar=True, en=True, tagline=False) -> tuple[str, float, float]:
    text_col = {"color": NAVY, "mono": NAVY, "on_dark": WHITE, "mono_white": WHITE}[variant]
    en_col = {"color": TEAL, "mono": NAVY, "on_dark": MINT, "mono_white": WHITE}[variant]
    pad, m, gap = 24, 132, 30
    x = pad + m + gap
    parts = [mark(pad, pad, m, {"color": "color", "mono": "mono", "on_dark": "on_dark", "mono_white": "mono_white"}[variant])]
    rows = []
    if ar:
        rows.append((AR_D, AR_B, text_col))
    if en:
        rows.append((EN_D, EN_B, en_col))
    heights = [b[3] - b[1] for _, b, _ in rows]
    spacing = 8
    block = sum(heights) + spacing * (len(rows) - 1)
    top = pad + (m - block) / 2
    width = x
    for (d, b, col), h in zip(rows, heights):
        parts.append(f'<path transform="translate({x - b[0]:.1f} {top - b[1]:.1f})" d="{d}" fill="{col}"/>')
        width = max(width, x + (b[2] - b[0]))
        top += h + spacing
    height = pad * 2 + m
    if tagline:
        sep = 28
        width = max(width, pad + TAG_EN_W + sep + TAG_AR_W)
        y = height + 6
        hb_ = max(TAG_EN_B[3] - TAG_EN_B[1], TAG_AR_B[3] - TAG_AR_B[1])
        parts.append(f'<path transform="translate({pad - TAG_EN_B[0]:.1f} {y - TAG_EN_B[1]:.1f})" d="{TAG_EN_D}" fill="{text_col}" opacity=".72"/>')
        parts.append(f'<path transform="translate({width - TAG_AR_B[2]:.1f} {y - TAG_AR_B[1]:.1f})" d="{TAG_AR_D}" fill="{text_col}" opacity=".72"/>')
        height = y + hb_ + pad
    return "".join(parts), width + pad, height


for name, variant, kw, title, bg in [
    ("wesal-logo-primary.svg", "color", {}, "WESAL | وصال", None),
    ("wesal-logo-primary-tagline.svg", "color", {"tagline": True}, "WESAL | وصال — One Market. Connected.", None),
    ("wesal-logo-ar.svg", "color", {"en": False}, "وصال", None),
    ("wesal-logo-en.svg", "color", {"ar": False}, "WESAL", None),
    ("wesal-logo-mono.svg", "mono", {}, "WESAL mono", None),
    ("wesal-logo-mono-white.svg", "mono_white", {}, "WESAL mono white", None),
    ("wesal-logo-on-dark.svg", "on_dark", {}, "WESAL on dark", NAVY),
    ("wesal-logo-on-light.svg", "color", {}, "WESAL on light", "#F5F8FA"),
]:
    body, w, h = lockup(variant, **kw)
    write(name, svg(w, h, body, title, bg))

# app icon (1024) with subtle depth
write("wesal-app-icon.svg", svg(1024, 1024,
      '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#17395A"/><stop offset="1" stop-color="#0B1F33"/></linearGradient></defs>'
      '<rect width="1024" height="1024" rx="228" fill="url(#g)"/>' + mark(112, 112, 800, "color").replace(f'fill="{NAVY}"/>', 'fill="none"/>', 1), "WESAL app icon"))
write("wesal-favicon.svg", svg(64, 64, mark(0, 0, 64, "color"), "WESAL"))
write("wesal-mark.svg", svg(64, 64, mark(0, 0, 64, "color"), "WESAL mark"))

# splash (portrait phone) & social image
body, w, h = lockup("on_dark", tagline=True)
sx, sy = (1242 - w) / 2, 1100
write("wesal-splash.svg", svg(1242, 2688, f'<g transform="translate({sx:.1f} {sy})">{body}</g>', "WESAL splash", NAVY))
body, w, h = lockup("on_dark", tagline=True)
write("wesal-og-image.svg", svg(1200, 630, '<rect width="1200" height="630" fill="#102B46"/>'
      '<circle cx="1080" cy="80" r="260" fill="#20B99A" opacity=".18"/><circle cx="90" cy="600" r="220" fill="#3E6890" opacity=".35"/>'
      f'<g transform="translate({(1200 - w) / 2:.1f} {(630 - h) / 2:.1f})">{body}</g>', "WESAL"))
print("svg written:", sorted(p.name for p in SVG.iterdir()))
