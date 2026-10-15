"""Shared SVG helpers for 深度学习/大模型训练 figures.

Style: fireworks-tech-graph Style 6 (Claude Official) — warm cream background,
soft fills, dark-gray 2.5px strokes, 12px corner radius, gray arrows.
Charts are drawn as plain SVG so diagrams and curves share one look.
"""
from __future__ import annotations

import math
from pathlib import Path

BG = "#f8f6f3"
INK = "#1a1a1a"
MUTED = "#6a6a6a"
LABEL = "#5a5a5a"
STROKE = "#4a4a4a"
GRID = "#e2ddd6"

BLUE = "#a8c5e6"
TEAL = "#9dd4c7"
BEIGE = "#f4e4c1"
GRAY = "#e8e6e3"
WHITE = "#ffffff"
CLAY = "#d97757"        # accent: highlight / "this is the part that matters"
CLAY_SOFT = "#f3d3c4"

# curve colors, ordered; muted enough to sit on cream, distinct enough to tell apart
SERIES = ["#d97757", "#4f86c0", "#3f9c86", "#c29a2b", "#8c7c6e"]

FONT = ("<style>text{font-family:-apple-system,'Segoe UI','PingFang SC',"
        "'Microsoft YaHei','SimHei',sans-serif}</style>")
DEFS = (
    '<defs>'
    '<marker id="arr" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
    f'<path d="M0 0L12 6L0 12Z" fill="{LABEL}"/></marker>'
    '<marker id="arr-clay" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
    f'<path d="M0 0L12 6L0 12Z" fill="{CLAY}"/></marker>'
    '<filter id="soft"><feDropShadow dx="0" dy="2" stdDeviation="5" flood-color="#000" '
    'flood-opacity="0.06"/></filter>'
    '</defs>'
)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x: float, y: float, s: str, size: float = 16, fill: str = INK,
         anchor: str = "middle", weight: int | None = None, raw: bool = False,
         italic: bool = False, family: str | None = None) -> str:
    w = f' font-weight="{weight}"' if weight else ""
    it = ' font-style="italic"' if italic else ""
    fam = f' font-family="{family}"' if family else ""
    body = s if raw else esc(s)
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{w}{it}{fam}>{body}</text>')


def mono(x: float, y: float, s: str, size: float = 15, fill: str = INK,
         anchor: str = "middle", weight: int | None = None) -> str:
    return text(x, y, s, size, fill, anchor, weight,
                family="Consolas,'Cascadia Mono','Microsoft YaHei',monospace")


def rect(x: float, y: float, w: float, h: float, fill: str = BLUE, stroke: str = STROKE,
         sw: float = 2.5, rx: float = 12, dash: str | None = None, shadow: bool = False) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    f = ' filter="url(#soft)"' if shadow else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{f}/>')


def node(x: float, y: float, w: float, h: float, title: str, lines: list[str] | None = None,
         fill: str = BLUE, sw: float = 2.5, stroke: str = STROKE, tsize: float = 17) -> str:
    """Box with a bold title and up to a few detail lines, vertically centered."""
    lines = lines or []
    parts = [rect(x, y, w, h, fill, stroke, sw, shadow=True)]
    total = tsize + len(lines) * 22
    top = y + (h - total) / 2 + tsize - 2
    parts.append(text(x + w / 2, top, title, tsize, weight=600))
    for i, ln in enumerate(lines):
        parts.append(text(x + w / 2, top + 24 + i * 22, ln, 14, MUTED))
    return "".join(parts)


def line(x1: float, y1: float, x2: float, y2: float, color: str = LABEL, sw: float = 2,
         dash: str | None = None, arrow: bool = False, clay: bool = False) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = ""
    if arrow:
        m = ' marker-end="url(#arr-clay)"' if clay else ' marker-end="url(#arr)"'
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
            f'stroke-width="{sw}"{d}{m}/>')


def path(d: str, color: str = LABEL, sw: float = 2, fill: str = "none",
         dash: str | None = None, arrow: bool = False, clay: bool = False,
         opacity: float | None = None) -> str:
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    m = ""
    if arrow:
        m = ' marker-end="url(#arr-clay)"' if clay else ' marker-end="url(#arr)"'
    op = f' fill-opacity="{opacity}"' if opacity is not None else ""
    return f'<path d="{d}" fill="{fill}"{op} stroke="{color}" stroke-width="{sw}"{ds}{m}/>'


def circle(cx: float, cy: float, r: float, fill: str, stroke: str = STROKE, sw: float = 2) -> str:
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"/>')


def title(b: list[str], t: str, sub: str | None = None, x: float = 48) -> None:
    b.append(text(x, 50, t, 24, anchor="start", weight=700))
    if sub:
        b.append(text(x, 80, sub, 15, MUTED, "start"))


def svg(w: int, h: int, body: list[str]) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{FONT}{DEFS}<rect width="{w}" height="{h}" fill="{BG}"/>'
            + "".join(body) + "</svg>")


def save(out: Path, name: str, content: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.svg").write_text(content, encoding="utf-8")
    print("wrote", out / f"{name}.svg")


# ---------------------------------------------------------------- charts
class Axes:
    """Maps data coords to pixels; supports log10 axes."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 xlim: tuple[float, float], ylim: tuple[float, float],
                 xlog: bool = False, ylog: bool = False):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.xlim, self.ylim, self.xlog, self.ylog = xlim, ylim, xlog, ylog

    def _t(self, v: float, lim: tuple[float, float], log: bool) -> float:
        if log:
            v, lo, hi = math.log10(v), math.log10(lim[0]), math.log10(lim[1])
        else:
            lo, hi = lim
        return (v - lo) / (hi - lo)

    def px(self, v: float) -> float:
        return self.x + self._t(v, self.xlim, self.xlog) * self.w

    def py(self, v: float) -> float:
        return self.y + self.h - self._t(v, self.ylim, self.ylog) * self.h

    def frame(self, xticks: list[tuple[float, str]], yticks: list[tuple[float, str]],
              xlabel: str = "", ylabel: str = "") -> list[str]:
        b: list[str] = [rect(self.x, self.y, self.w, self.h, WHITE, GRID, 1.5, rx=6)]
        for v, lab in xticks:
            px = self.px(v)
            b.append(line(px, self.y, px, self.y + self.h, GRID, 1))
            b.append(text(px, self.y + self.h + 24, lab, 13, MUTED, raw=True))
        for v, lab in yticks:
            py = self.py(v)
            b.append(line(self.x, py, self.x + self.w, py, GRID, 1))
            b.append(text(self.x - 10, py + 5, lab, 13, MUTED, "end", raw=True))
        if xlabel:
            b.append(text(self.x + self.w / 2, self.y + self.h + 52, xlabel, 14, LABEL))
        if ylabel:
            cx, cy = self.x - 62, self.y + self.h / 2
            b.append(f'<text x="{cx}" y="{cy}" font-size="14" fill="{LABEL}" text-anchor="middle" '
                     f'transform="rotate(-90 {cx} {cy})">{esc(ylabel)}</text>')
        return b

    def curve(self, pts: list[tuple[float, float]], color: str, sw: float = 3,
              dash: str | None = None) -> str:
        d = "M" + " L".join(f"{self.px(a):.1f} {self.py(c):.1f}" for a, c in pts)
        return path(d, color, sw, dash=dash)


def sup10(e: int) -> str:
    return f'10<tspan font-size="10" dy="-7">{e}</tspan>'
