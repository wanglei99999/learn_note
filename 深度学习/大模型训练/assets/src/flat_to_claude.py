"""Restyle the older flat-style SVGs (white bg, #2563eb accent) into Style 6.

Palette comes from claude_style.py so every figure in 深度学习/ shares one look.
Rules key on (fill, stroke) pairs of the flat style:
  light-blue / green / gray nodes -> BLUE / TEAL / GRAY fill, dark 2.5px stroke, soft shadow
  big tinted panels               -> pale tint, GRID border
  blue arrows                     -> gray arrows (thick ones become clay)
  blue text / residual lines      -> clay accent
semantic_blue=True keeps #2563eb as a data color (e.g. "blue = forward, orange = backward").

Usage as a module:  restyle(svg_text, semantic_blue=False) -> str
Usage as a script:  python flat_to_claude.py [--semantic-blue] file.svg ...   (rewrites in place)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_style as cs  # noqa: E402

OLD_BLUE = "#2563eb"
SERIES_BLUE, SERIES_GREEN, SERIES_GOLD = cs.SERIES[1], cs.SERIES[2], cs.SERIES[3]
PALE_BLUE = "#e6eef7"
PALE_TEAL = "#e4f2ee"
PALE_GRAY = "#efebe5"
MASKED = "#ece8e3"
DASH_GRAY = "#9a948c"
AXIS = "#cfc9c0"

# plain color swaps, applied after the structural rules
SIMPLE = {
    "#111827": cs.INK, "#1f2937": cs.STROKE, "#6b7280": cs.MUTED, "#9ca3af": DASH_GRAY,
    "#d1d5db": AXIS, "#e5e7eb": cs.GRID, "#93c5fd": DASH_GRAY,
    "#059669": SERIES_GREEN, "#ea580c": cs.CLAY,
    # dataviz series used by the old charts, mapped hue for hue
    "#2a78d6": SERIES_BLUE, "#eb6834": cs.CLAY, "#1baf7a": SERIES_GREEN, "#eda100": SERIES_GOLD,
}
NODE_FILL = {"#eff6ff": cs.BLUE, "#dbeafe": cs.BLUE, "#f0fdf4": cs.TEAL,
             "#f9fafb": cs.GRAY, "#fff7ed": cs.CLAY_SOFT}
PANEL_FILL = {"#eff6ff": PALE_BLUE, "#dbeafe": PALE_BLUE, "#f0fdf4": PALE_TEAL,
              "#f9fafb": PALE_GRAY, "#fff7ed": cs.CLAY_SOFT}
PANEL_AREA = 50_000  # px²; above this a tinted rect holds content, so keep it pale

FONT_OLD = "<style>text{font-family:'Microsoft YaHei','SimHei',sans-serif}</style>"
SHADOW = ('<filter id="soft"><feDropShadow dx="0" dy="2" stdDeviation="5" flood-color="#000" '
          'flood-opacity="0.06"/></filter>')
CLAY_MARKER = (f'<marker id="arrow-clay" markerWidth="10" markerHeight="8" refX="9" refY="4" '
               f'orient="auto"><path d="M0 0L10 4L0 8Z" fill="{cs.CLAY}"/></marker>')

ATTR = re.compile(r'([\w:-]+)="([^"]*)"')
TAG = re.compile(r'<(rect|circle|line|path|polyline|text|tspan)\b([^>]*?)(/?)>')


def _num(a: dict[str, str], k: str, default: float = 0.0) -> float:
    try:
        return float(a.get(k, default))
    except ValueError:
        return default


def _rect(a: dict[str, str], semantic_blue: bool) -> None:
    fill, stroke = a.get("fill", "").lower(), a.get("stroke", "").lower()
    w, h = _num(a, "width"), _num(a, "height")
    rx = _num(a, "rx")
    if "x" not in a and "y" not in a and fill == "#ffffff" and not stroke:
        a["fill"] = cs.BG  # full-canvas background
        return
    if fill == "#dbeafe" and stroke == OLD_BLUE and rx >= 14:
        a["fill"], a["stroke"] = cs.CLAY_SOFT, cs.CLAY  # "× 32 层" style pill
        return
    if fill == "#f3f4f6":
        a["fill"] = MASKED
        if stroke:
            a["stroke"] = cs.GRID
        return
    if fill in ("#ffffff", "none"):
        if stroke == OLD_BLUE:
            a["stroke"] = cs.CLAY
        return
    if fill in NODE_FILL:
        if stroke and w * h >= PANEL_AREA:
            a["fill"], a["stroke"] = PANEL_FILL[fill], cs.GRID
            return
        if not stroke:
            a["fill"] = PALE_GRAY if fill == "#f9fafb" else PANEL_FILL[fill]
            return
        a["fill"] = NODE_FILL[fill]
        a["stroke"] = cs.CLAY if (stroke == OLD_BLUE and fill == "#eff6ff") else cs.STROKE
        if _num(a, "stroke-width", 1) >= 2:
            a["stroke-width"] = "2.5" if h >= 30 else "1.8"  # thin vector bars stay light
        if h >= 40 and rx >= 8:
            a["rx"] = "12"
            a["filter"] = "url(#soft)"
        return
    if fill == OLD_BLUE:
        a["fill"] = SERIES_BLUE  # data bars


def _stroked(a: dict[str, str], tag: str, semantic_blue: bool) -> None:
    stroke = a.get("stroke", "").lower()
    if tag == "circle":
        fill = a.get("fill", "").lower()
        if fill == "#ffffff" and stroke == OLD_BLUE:
            # op nodes in a computation graph stay neutral; "+"/"×" junctions are accents
            a["stroke"] = cs.STROKE if semantic_blue else cs.CLAY
        elif fill == OLD_BLUE:
            a["fill"] = SERIES_BLUE if semantic_blue else cs.CLAY
        return
    if a.get("fill", "").lower() == OLD_BLUE:
        a["fill"] = SERIES_BLUE  # data bars drawn as paths
    if stroke != OLD_BLUE:
        return
    if semantic_blue:
        a["stroke"] = SERIES_BLUE
        return
    if "marker-end" in a:
        if _num(a, "stroke-width", 2) >= 3:
            a["stroke"], a["marker-end"] = cs.CLAY, "url(#arrow-clay)"
        else:
            a["stroke"] = cs.LABEL
    else:
        a["stroke"] = cs.CLAY  # residual stream and other emphasized lines


def _text(a: dict[str, str], semantic_blue: bool) -> None:
    if a.get("fill", "").lower() == OLD_BLUE:
        a["fill"] = SERIES_BLUE if semantic_blue else cs.CLAY
    # page title of the flat style: 30px at y=48 -> bold 26px
    if a.get("font-size") == "30" and _num(a, "y") < 60:
        a["font-size"], a["font-weight"] = "26", "700"


def _restyle_tag(m: re.Match, semantic_blue: bool) -> str:
    tag, body, close = m.group(1), m.group(2), m.group(3)
    a = dict(ATTR.findall(body))
    if tag == "rect":
        _rect(a, semantic_blue)
    elif tag in ("text", "tspan"):
        _text(a, semantic_blue)
    else:
        _stroked(a, tag, semantic_blue)
    for k in ("fill", "stroke"):
        if a.get(k, "").lower() in SIMPLE:
            a[k] = SIMPLE[a[k].lower()]
    attrs = "".join(f' {k}="{v}"' for k, v in a.items())
    return f"<{tag}{attrs}{close}>"


def _restyle_defs(svg: str, semantic_blue: bool) -> str:
    m = re.search(r"<defs>.*?</defs>", svg, re.S)
    if not m:
        return svg
    defs = m.group(0)
    # marker heads: generic arrows go gray, unless blue carries meaning
    defs = defs.replace(f'fill="{OLD_BLUE}"', f'fill="{SERIES_BLUE if semantic_blue else cs.LABEL}"')
    for old, new in SIMPLE.items():
        defs = defs.replace(f'fill="{old}"', f'fill="{new}"')
    defs = defs.replace("</defs>", CLAY_MARKER + SHADOW + "</defs>")
    return svg[:m.start()] + defs + svg[m.end():]


def restyle(svg: str, semantic_blue: bool = False) -> str:
    if 'id="soft"' in svg:
        return svg  # already converted
    svg = svg.replace(FONT_OLD, cs.FONT)
    svg = _restyle_defs(svg, semantic_blue)
    head, sep, rest = svg.partition("</defs>")
    rest = TAG.sub(lambda m: _restyle_tag(m, semantic_blue), rest)
    return head + sep + rest


def main(argv: list[str]) -> None:
    semantic = "--semantic-blue" in argv
    for p in (Path(x) for x in argv if not x.startswith("--")):
        p.write_text(restyle(p.read_text(encoding="utf-8"), semantic), encoding="utf-8")
        print("restyled", p)


if __name__ == "__main__":
    main(sys.argv[1:])
