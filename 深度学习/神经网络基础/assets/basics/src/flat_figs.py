"""Flat-style SVG figures for 深度学习/神经网络基础/*.md.

Usage: python flat_figs.py <output_dir>
Drawn in the old flat palette, then converted to Style 6 (Claude Official) by
大模型训练/assets/src/flat_to_claude.py. Blue/orange carry meaning here
(forward value / backward gradient), so the conversion keeps blue as a data color.
"""
import math
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "大模型训练" / "assets" / "src"))
from flat_to_claude import restyle  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

BLUE = "#2563eb"
ORANGE = "#ea580c"
INK = "#111827"
GRAY = "#6b7280"
LINE = "#d1d5db"
FILL_MAIN = "#eff6ff"
FILL_SOFT = "#f9fafb"
FILL_OUT = "#f0fdf4"
STROKE_SOFT = "#e5e7eb"
STROKE_OUT = "#86efac"

# dataviz reference palette, fixed order
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

FONT = "<style>text{font-family:'Microsoft YaHei','SimHei',sans-serif}</style>"
DEFS = (f'<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" '
        f'orient="auto"><path d="M0 0L10 4L0 8Z" fill="{BLUE}"/></marker>'
        f'<marker id="arrow-o" markerWidth="10" markerHeight="8" refX="9" refY="4" '
        f'orient="auto"><path d="M0 0L10 4L0 8Z" fill="{ORANGE}"/></marker></defs>')


def text(x: float, y: float, content: str, size: float = 20, fill: str = INK,
         anchor: str = "middle") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}">{content}</text>')


def box(x: float, y: float, w: float, h: float, fill: str = FILL_MAIN,
        stroke: str = LINE, sw: float = 2, rx: float = 8) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


def plain(d: str, color: str = BLUE, sw: float = 2.5, dash: str | None = None) -> str:
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{ds}/>'


def arrow(d: str, color: str = BLUE, sw: float = 2.5) -> str:
    marker = "arrow-o" if color == ORANGE else "arrow"
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'marker-end="url(#{marker})"/>')


def polyline(pts: list[tuple[float, float]], color: str, sw: float = 2.5,
             dash: str | None = None) -> str:
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}"{ds}/>'


def svg(w: int, h: int, body: list[str]) -> str:
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{FONT}{DEFS}<rect width="{w}" height="{h}" fill="#ffffff"/>')
    return head + "".join(body) + "</svg>"


def header(b: list[str], title: str, subtitle: str) -> None:
    b.append(text(40, 48, title, 30, anchor="start"))
    b.append(text(40, 82, subtitle, 18, GRAY, "start"))


class Axes:
    """Maps data coordinates into a pixel rectangle and draws a light frame."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 xlim: tuple[float, float], ylim: tuple[float, float]) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h
        self.xlim, self.ylim = xlim, ylim

    def px(self, u: float) -> float:
        return self.x + (u - self.xlim[0]) / (self.xlim[1] - self.xlim[0]) * self.w

    def py(self, v: float) -> float:
        return self.y + (self.ylim[1] - v) / (self.ylim[1] - self.ylim[0]) * self.h

    def frame(self, xticks: list[float], yticks: list[float]) -> list[str]:
        out = []
        for v in yticks:
            out.append(plain(f"M{self.x} {self.py(v):.1f}H{self.x + self.w}",
                             "#1f2937" if v == 0 else STROKE_SOFT, 1.5 if v == 0 else 1))
            out.append(text(self.x - 10, self.py(v) + 5, f"{v:g}", 14, GRAY, "end"))
        for u in xticks:
            if u == 0:
                out.append(plain(f"M{self.px(0):.1f} {self.y}V{self.y + self.h}", "#1f2937", 1.5))
            out.append(text(self.px(u), self.y + self.h + 22, f"{u:g}", 14, GRAY))
        return out

    def curve(self, fn: Callable[[float], float], color: str, dash: str | None = None,
              n: int = 400) -> str:
        lo, hi = self.xlim
        pts = []
        for k in range(n + 1):
            u = lo + (hi - lo) * k / n
            v = max(self.ylim[0], min(self.ylim[1], fn(u)))
            pts.append((self.px(u), self.py(v)))
        return polyline(pts, color, 2.8, dash)


# ------------------------------------------------------------------ 01 激活函数
def sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def gelu(z: float) -> float:
    return 0.5 * z * (1 + math.erf(z / math.sqrt(2)))


def gelu_grad(z: float) -> float:
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    pdf = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    return cdf + z * pdf


def silu(z: float) -> float:
    return z * sigmoid(z)


def silu_grad(z: float) -> float:
    s = sigmoid(z)
    return s * (1 + z * (1 - s))


ACTS = [
    ("sigmoid", lambda z: sigmoid(z), lambda z: sigmoid(z) * (1 - sigmoid(z)), "#9ca3af", "7 5"),
    ("tanh", math.tanh, lambda z: 1 - math.tanh(z) ** 2, SERIES[3], None),
    ("ReLU", lambda z: max(0.0, z), lambda z: 1.0 if z > 0 else 0.0, SERIES[1], None),
    ("GELU", gelu, gelu_grad, SERIES[2], None),
    ("SiLU", silu, silu_grad, SERIES[0], None),
]


def activations() -> str:
    b: list[str] = []
    header(b, "常见激活函数：函数值与导数",
           "左：σ(z)；右：σ′(z)。反向传播时梯度每经过一层，都要乘上这一层的 σ′。")
    lx = 110
    for name, _, _, color, dash in ACTS:
        b.append(plain(f"M{lx} 126H{lx + 30}", color, 3, dash))
        b.append(text(lx + 38, 132, name, 16, INK, "start"))
        lx += 60 + len(name) * 11

    left = Axes(90, 180, 470, 400, (-4, 4), (-1.2, 4.2))
    right = Axes(680, 180, 470, 400, (-4, 4), (-0.2, 1.2))
    b.append(text(left.x, 166, "函数值 σ(z)", 18, INK, "start"))
    b.append(text(right.x, 166, "导数 σ′(z)", 18, INK, "start"))
    b.extend(left.frame([-4, -2, 0, 2, 4], [-1, 0, 1, 2, 3, 4]))
    b.extend(right.frame([-4, -2, 0, 2, 4], [0, 0.25, 0.5, 1]))
    for _, f, df, color, dash in ACTS:
        b.append(left.curve(f, color, dash))
        if df is ACTS[2][2]:
            # ReLU derivative: draw the jump as two flat pieces
            b.append(polyline([(right.px(-4), right.py(0)), (right.px(0), right.py(0))], color, 2.8))
            b.append(polyline([(right.px(0), right.py(1)), (right.px(4), right.py(1))], color, 2.8))
        else:
            b.append(right.curve(df, color, dash))

    # annotations
    b.append(text(right.px(0) + 12, right.py(0.25) - 8, "sigmoid 最大只有 0.25", 14, GRAY, "start"))
    b.append(text(right.px(-3.9), right.py(1) - 10, "ReLU 正半轴恒为 1", 14, GRAY, "start"))
    b.append(text(left.px(-2.4), left.py(-0.6), "SiLU 最小值 ≈ −0.28", 14, GRAY))
    b.append(text(left.x + left.w / 2, left.y + left.h + 48, "z", 15, GRAY))
    b.append(text(right.x + right.w / 2, right.y + right.h + 48, "z", 15, GRAY))
    return svg(1200, 660, b)


# ------------------------------------------------------------------ 02 反向传播
def gnode(cx: float, cy: float, label: str, kind: str = "op") -> str:
    if kind == "op":
        return (f'<circle cx="{cx}" cy="{cy}" r="30" fill="#ffffff" stroke="{BLUE}" stroke-width="2.5"/>'
                + text(cx, cy + 7, label, 19))
    fill, stroke = {"in": (FILL_SOFT, STROKE_SOFT), "param": (FILL_MAIN, LINE),
                    "out": (FILL_OUT, STROKE_OUT)}[kind]
    return box(cx - 50, cy - 26, 100, 52, fill, stroke) + text(cx, cy + 7, label, 19)


def backprop() -> str:
    b: list[str] = []
    header(b, "反向传播：前向算值，反向算梯度",
           "两层网络 ŷ = w₂·ReLU(w₁x)，损失 L = ½(ŷ − y)²。蓝色是前向的值，橙色是反向的梯度 ∂L/∂(·)。")
    row = 330
    xs = {"x": 90, "mul1": 260, "z": 400, "relu": 540, "h": 680, "mul2": 840, "yhat": 980, "L": 1120}
    b.append(gnode(xs["x"], row, "x", "in"))
    b.append(gnode(xs["mul1"], row, "×"))
    b.append(gnode(xs["z"], row, "z", "in"))
    b.append(gnode(xs["relu"], row, "ReLU"))
    b.append(gnode(xs["h"], row, "h", "in"))
    b.append(gnode(xs["mul2"], row, "×"))
    b.append(gnode(xs["yhat"], row, "ŷ", "in"))
    b.append(gnode(xs["L"], row, "L", "out"))
    b.append(gnode(xs["mul1"], 190, "w₁", "param"))
    b.append(gnode(xs["mul2"], 190, "w₂", "param"))
    b.append(gnode(xs["L"], 190, "y", "in"))

    # forward edges
    for a, c in [("x", "mul1"), ("mul1", "z"), ("z", "relu"), ("relu", "h"), ("h", "mul2"),
                 ("mul2", "yhat"), ("yhat", "L")]:
        x0 = xs[a] + (50 if a in ("x", "z", "h", "yhat") else 30)
        x1 = xs[c] - (50 if c in ("z", "h", "yhat", "L") else 30)
        b.append(arrow(f"M{x0} {row - 8}H{x1}"))
    b.append(arrow(f"M{xs['mul1']} 216V298"))
    b.append(arrow(f"M{xs['mul2']} 216V298"))
    b.append(arrow(f"M{xs['L']} 216V302"))

    # forward values
    fv = [("x", "x = 2"), ("z", "z = 1"), ("h", "h = 1"), ("yhat", "ŷ = 3")]
    for k, label in fv:
        b.append(text(xs[k], row - 44, label, 17, BLUE))
    b.append(text(xs["L"], row + 52, "L = 2", 17, BLUE))
    b.append(text(xs["mul1"] + 60, 196, "= 0.5", 17, BLUE, "start"))
    b.append(text(xs["mul2"] + 60, 196, "= 3", 17, BLUE, "start"))
    b.append(text(xs["L"] - 60, 196, "= 1", 17, BLUE, "end"))

    # backward edges and gradients
    by = row + 70
    for a, c in [("L", "yhat"), ("yhat", "h"), ("h", "z")]:
        b.append(arrow(f"M{xs[a] - 20} {by}H{xs[c] + 20}", ORANGE))
    b.append(arrow(f"M{xs['z'] - 20} {by}H{xs['x'] + 70}", ORANGE, 1.6))
    grads = [("yhat", "∂L/∂ŷ = ŷ − y = 2"), ("h", "∂L/∂h = 2 × w₂ = 6"),
             ("z", "∂L/∂z = 6 × 1 = 6")]
    for k, label in grads:
        b.append(text(xs[k], by + 34, label, 16, ORANGE))
    b.append(text(xs["z"], by + 58, "ReLU′(1) = 1", 14, GRAY))
    b.append(text(xs["h"], by + 58, "× 的导数是另一个输入", 14, GRAY))

    # parameter gradients
    gy = 560
    b.append(box(140, gy, 400, 92, "#fff7ed", "#fdba74"))
    b.append(text(160, gy + 36, "∂L/∂w₁ = ∂L/∂z × x = 6 × 2 = 12", 18, INK, "start"))
    b.append(text(160, gy + 68, "w₁ ← 0.5 − 0.01 × 12 = 0.38", 17, GRAY, "start"))
    b.append(box(660, gy, 400, 92, "#fff7ed", "#fdba74"))
    b.append(text(680, gy + 36, "∂L/∂w₂ = ∂L/∂ŷ × h = 2 × 1 = 2", 18, INK, "start"))
    b.append(text(680, gy + 68, "w₂ ← 3 − 0.01 × 2 = 2.98", 17, GRAY, "start"))
    b.append(text(40, 700, "学习率 0.01 更新一步后，重新前向：ŷ ≈ 2.265，L 从 2 降到 0.80。", 18, GRAY, "start"))
    return svg(1200, 740, b)


# ------------------------------------------------------------------ 03 优化器
A1, A2 = 1.0, 20.0  # curvature of the two directions


def grad(p: tuple[float, float]) -> tuple[float, float]:
    return A1 * p[0], A2 * p[1]


def run_sgd(lr: float, steps: int, start: tuple[float, float]) -> list[tuple[float, float]]:
    p, path = start, [start]
    for _ in range(steps):
        g = grad(p)
        p = (p[0] - lr * g[0], p[1] - lr * g[1])
        path.append(p)
    return path


def run_momentum(lr: float, beta: float, steps: int,
                 start: tuple[float, float]) -> list[tuple[float, float]]:
    p, v, path = start, (0.0, 0.0), [start]
    for _ in range(steps):
        g = grad(p)
        v = (beta * v[0] + g[0], beta * v[1] + g[1])
        p = (p[0] - lr * v[0], p[1] - lr * v[1])
        path.append(p)
    return path


def run_adam(lr: float, steps: int, start: tuple[float, float],
             b1: float = 0.9, b2: float = 0.999) -> list[tuple[float, float]]:
    p, m, v, path = start, [0.0, 0.0], [0.0, 0.0], [start]
    for t in range(1, steps + 1):
        g = grad(p)
        nxt = []
        for i in range(2):
            m[i] = b1 * m[i] + (1 - b1) * g[i]
            v[i] = b2 * v[i] + (1 - b2) * g[i] ** 2
            mh, vh = m[i] / (1 - b1 ** t), v[i] / (1 - b2 ** t)
            nxt.append(p[i] - lr * mh / (math.sqrt(vh) + 1e-8))
        p = (nxt[0], nxt[1])
        path.append(p)
    return path


def optimizers() -> str:
    b: list[str] = []
    header(b, "优化器在“狭长山谷”里的轨迹",
           "L = ½(θ₁² + 20θ₂²)：θ₂ 方向陡，θ₁ 方向平。从 (−4.5, 0.9) 出发，各走 40 步，终点是原点。")
    ax = Axes(90, 140, 1060, 400, (-5, 0.6), (-1.15, 1.15))
    # contours: ellipses of constant loss
    for lv in (0.5, 2, 4.5, 8, 12.5):
        r1, r2 = math.sqrt(2 * lv / A1), math.sqrt(2 * lv / A2)
        pts = [(ax.px(r1 * math.cos(t / 100 * 2 * math.pi)), ax.py(r2 * math.sin(t / 100 * 2 * math.pi)))
               for t in range(101)]
        b.append(polyline(pts, STROKE_SOFT, 1.5))
    b.append(f'<circle cx="{ax.px(0):.1f}" cy="{ax.py(0):.1f}" r="6" fill="{INK}"/>')
    b.append(text(ax.px(0) + 12, ax.py(0) - 12, "最低点", 15, INK, "start"))

    start = (-4.5, 0.9)
    runs = [
        ("SGD，η = 0.09：陡的方向来回震荡，平的方向走得慢", run_sgd(0.09, 40, start), SERIES[1]),
        ("动量，η = 0.03，β = 0.7：震荡被抵消，平的方向越走越快", run_momentum(0.03, 0.7, 40, start), SERIES[2]),
        ("Adam，η = 0.15：每个方向按自己的梯度大小缩放步长", run_adam(0.15, 40, start), SERIES[0]),
    ]
    for _, path, color in runs:
        pts = [(ax.px(u), ax.py(max(-1.15, min(1.15, v)))) for u, v in path]
        b.append(polyline(pts, color, 2.2))
        for x, y in pts:
            b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{color}"/>')
    b.append(f'<circle cx="{ax.px(start[0]):.1f}" cy="{ax.py(start[1]):.1f}" r="7" fill="#ffffff" '
             f'stroke="{INK}" stroke-width="2"/>')
    b.append(text(ax.px(start[0]) - 12, ax.py(start[1]) + 5, "起点", 15, INK, "end"))
    ly = 580
    for k, (label, _, color) in enumerate(runs):
        b.append(plain(f"M90 {ly + k * 30 - 6}H120", color, 3))
        b.append(text(130, ly + k * 30, label, 16, INK, "start"))
    return svg(1200, 680, b)


def lr_schedule() -> str:
    b: list[str] = []
    header(b, "学习率调度：线性预热 + 余弦衰减",
           "以 Llama 2 的设置为例：峰值 3×10⁻⁴，预热 2000 步，余弦衰减到峰值的 10%。横轴按总步数约 50 万步示意。")
    total, warm, peak, floor = 500_000, 2000, 3e-4, 3e-5
    ax = Axes(110, 130, 1040, 320, (0, total), (0, 3.3e-4))

    def lr(s: float) -> float:
        if s < warm:
            return peak * s / warm
        prog = (s - warm) / (total - warm)
        return floor + 0.5 * (peak - floor) * (1 + math.cos(math.pi * prog))

    for v in (0, 1e-4, 2e-4, 3e-4):
        b.append(plain(f"M{ax.x} {ax.py(v):.1f}H{ax.x + ax.w}", "#1f2937" if v == 0 else STROKE_SOFT,
                       1.5 if v == 0 else 1))
        b.append(text(ax.x - 10, ax.py(v) + 5, "0" if v == 0 else f"{v * 1e4:g}×10⁻⁴", 14, GRAY, "end"))
    for s in range(0, total + 1, 100_000):
        b.append(text(ax.px(s), ax.y + ax.h + 22, f"{s // 1000}k" if s else "0", 14, GRAY))
    b.append(text(ax.x + ax.w, ax.y + ax.h + 46, "训练步数", 15, GRAY, "end"))
    pts = [(ax.px(s), ax.py(lr(s))) for s in list(range(0, warm, 100)) + list(range(warm, total + 1, 2500))]
    b.append(polyline(pts, BLUE, 3))
    b.append(plain(f"M{ax.px(0):.1f} {ax.py(peak):.1f}V{ax.y + ax.h}", BLUE, 1.2, "4 4"))
    b.append(text(ax.px(warm) + 14, ax.py(0.6e-4), "← 预热 2000 步，在这个尺度下几乎是一条竖线",
                  15, GRAY, "start"))
    b.append(text(ax.px(total) - 4, ax.py(floor) - 14, "终点：3×10⁻⁵", 15, GRAY, "end"))
    return svg(1200, 520, b)


FIGS = {
    "01-activations": activations,
    "02-backprop": backprop,
    "03-optimizers": optimizers,
    "04-lr-schedule": lr_schedule,
}

for name, fn in FIGS.items():
    (OUT / f"{name}.svg").write_text(restyle(fn(), semantic_blue=True), encoding="utf-8")
print("ok")
