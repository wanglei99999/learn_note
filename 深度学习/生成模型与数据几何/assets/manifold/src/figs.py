"""Manim figures for 深度学习/从流形假说到深度学习.md (Style 6: cream background)."""
import numpy as np
from manim import *

BG = ManimColor("#F8F6F3")
config.background_color = BG
config.frame_width = 16
config.frame_height = 8

# palette mirrors 大模型训练/assets/src/claude_style.py
INK = ManimColor("#1A1A1A")
MUTED = ManimColor("#6A6A6A")
FAINT = ManimColor("#D6D0C7")
BLUE_ = ManimColor("#4F86C0")
ORANGE_ = ManimColor("#D97757")
GREEN_ = ManimColor("#3F9C86")
FONT = "Microsoft YaHei"


def zh(s, size=24, color=INK, weight=NORMAL):
    return Text(s, font=FONT, font_size=size, color=color, weight=weight)


def tex(s, size=34, color=INK):
    return MathTex(s, font_size=size, color=color)


def header(scene, title, subtitle):
    t = zh(title, 32, weight=BOLD).to_corner(UL, buff=0.6)
    s = zh(subtitle, 20, MUTED).next_to(t, DOWN, aligned_edge=LEFT, buff=0.2)
    scene.add(t, s)
    return VGroup(t, s)


# ------------------------------------------------------------------ 螺旋展开
R = 2.6


def spiral_points(w, phase, n=240):
    """w=1: 1.5 圈螺旋；w=0: 一条射线。两类在同一半径处始终相差 π，永不相交。"""
    t = np.linspace(0, 1, n)
    r = R * (0.10 + 0.90 * t)
    ang = PI / 2 + phase + w * 3 * PI * t
    return np.stack([r * np.cos(ang), r * np.sin(ang), np.zeros(n)], 1)


def spiral_pair(w, center=ORIGIN, scale=1.0, width=7):
    a = VMobject().set_points_smoothly(spiral_points(w, 0.0) * scale).set_stroke(BLUE_, width)
    b = VMobject().set_points_smoothly(spiral_points(w, PI) * scale).set_stroke(ORANGE_, width)
    return VGroup(a, b).shift(center)


def separator(center=ORIGIN, half=3.0):
    return DashedLine(center + LEFT * half, center + RIGHT * half, color=MUTED,
                      stroke_width=3, dash_length=0.14)


class SpiralUnfold(Scene):
    def construct(self):
        header(self, "网络逐层把缠绕的流形展开",
               "示意：每一层对空间做一次连续变形，不撕裂、不交叉；最后一条直线就能分开两类")
        center = DOWN * 0.35
        w = ValueTracker(1.0)
        curves = always_redraw(lambda: spiral_pair(w.get_value(), center, 0.84))
        legend = VGroup(
            VGroup(Line(ORIGIN, RIGHT * 0.5, color=BLUE_, stroke_width=7), zh("类别 A", 22)).arrange(RIGHT, buff=0.18),
            VGroup(Line(ORIGIN, RIGHT * 0.5, color=ORANGE_, stroke_width=7), zh("类别 B", 22)).arrange(RIGHT, buff=0.18),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.2).to_corner(DR, buff=0.6)

        stages = ["输入空间：两类缠绕在一起，任何直线都分不开",
                  "中间层：空间被连续拉伸，螺旋逐渐松开",
                  "最后一层：一条直线即可分开"]
        labels = [zh(s, 26).to_corner(DL, buff=0.6) for s in stages]

        self.add(curves, legend, labels[0])
        self.wait(1.0)
        self.play(w.animate.set_value(0.45), run_time=2.4, rate_func=smooth)
        self.play(FadeTransform(labels[0], labels[1]), run_time=0.5)
        self.play(w.animate.set_value(0.0), run_time=2.4, rate_func=smooth)
        sep = separator(center, 3.2)
        sep_label = zh("线性分类边界", 20, MUTED).next_to(sep, RIGHT, buff=0.2)
        self.play(FadeTransform(labels[1], labels[2]), Create(sep), FadeIn(sep_label), run_time=0.8)
        self.wait(2.0)


class SpiralStages(Scene):
    def construct(self):
        header(self, "网络逐层把缠绕的流形展开",
               "示意：每一层对空间做一次连续变形，不撕裂、不交叉；最后一条直线就能分开两类")
        xs = [-5.2, 0.0, 5.2]
        cy = -0.75
        names = ["输入空间", "中间层", "最后一层"]
        notes = ["两类缠绕，直线分不开", "螺旋逐渐松开", "一条直线即可分开"]
        for x, wv, name, note in zip(xs, [1.0, 0.42, 0.0], names, notes):
            c = np.array([x, cy, 0])
            self.add(spiral_pair(wv, c, 0.72, 6))
            cap = VGroup(zh(name, 26), zh(note, 20, MUTED)).arrange(DOWN, buff=0.12)
            cap.move_to([x, -3.45, 0])
            self.add(cap)
        sep = separator(np.array([xs[2], cy, 0]), 1.3)
        self.add(sep)
        for x0, x1 in [(xs[0], xs[1]), (xs[1], xs[2])]:
            self.add(Arrow([x0 + 2.0, cy, 0], [x1 - 2.0, cy, 0], color=FAINT, stroke_width=5,
                           max_tip_length_to_length_ratio=0.35, buff=0))


# ------------------------------------------------------------- 平行线与 JS
def js_gauss(theta, sigma):
    """JS(N(0,σ²), N(θ,σ²))，自然对数，数值积分。"""
    if abs(theta) < 1e-12:
        return 0.0
    x = np.linspace(-8 * sigma - abs(theta), 8 * sigma + abs(theta), 4001)
    dx = x[1] - x[0]
    p = np.exp(-x**2 / (2 * sigma**2))
    q = np.exp(-(x - theta) ** 2 / (2 * sigma**2))
    p, q = p / (p.sum() * dx), q / (q.sum() * dx)
    m = 0.5 * (p + q)
    mask_p, mask_q = p > 1e-300, q > 1e-300
    kl_pm = np.sum(p[mask_p] * np.log(p[mask_p] / m[mask_p])) * dx
    kl_qm = np.sum(q[mask_q] * np.log(q[mask_q] / m[mask_q])) * dx
    return 0.5 * (kl_pm + kl_qm)


def muted_axes(x_range, y_range, x_len, y_len, x_dec=0, y_dec=1, y_numbers=True):
    ax = Axes(
        x_range=x_range, y_range=y_range, x_length=x_len, y_length=y_len,
        tips=False,
        axis_config={"color": MUTED, "stroke_width": 2, "include_ticks": True, "tick_size": 0.06},
        x_axis_config={"include_numbers": True, "font_size": 24,
                       "decimal_number_config": {"num_decimal_places": x_dec, "color": MUTED}},
        y_axis_config={"include_numbers": y_numbers, "font_size": 24,
                       "decimal_number_config": {"num_decimal_places": y_dec, "color": MUTED}},
    )
    for axis in (ax.x_axis, ax.y_axis):
        if hasattr(axis, "numbers"):
            axis.numbers.set_color(MUTED)
    return ax


class ParallelLines(Scene):
    def construct(self):
        header(self, "两个分布越来越近，JS 却纹丝不动",
               "真实数据在一条线上，生成数据在旁边一条平行线上：只要两条线不完全重合，支撑就没有交集")

        # 左：平行线
        unit, x0, y0, y1 = 1.5, -6.9, -2.9, 0.4
        self.add(zh("两条平行线上的均匀分布", 24).move_to([-5.3, 1.75, 0]))
        self.add(Line([x0, y0, 0], [x0, y1, 0], color=BLUE_, stroke_width=9))
        self.add(tex("P", 36, BLUE_).move_to([x0, y0 - 0.42, 0]))
        for th, op in [(1.6, 0.25), (0.8, 0.5), (0.25, 1.0)]:
            x = x0 + th * unit
            self.add(Line([x, y0, 0], [x, y1, 0], color=ORANGE_, stroke_width=9, stroke_opacity=op))
        self.add(tex(r"Q_\theta", 36, ORANGE_).move_to([x0 + 0.8 * unit, y0 - 0.42, 0]))
        ay = y1 + 0.32
        self.add(Arrow([x0 + 1.6 * unit + 0.1, ay, 0], [x0 + 0.25 * unit - 0.05, ay, 0], color=MUTED,
                       stroke_width=4, max_tip_length_to_length_ratio=0.12, buff=0))
        self.add(tex(r"\theta:\ 1.6\to0.8\to0.25", 26, MUTED).move_to([x0 + 1.0 * unit, ay + 0.38, 0]))

        # 中：三条曲线
        ax = muted_axes([-2, 2, 1], [0, 1.6, 0.8], 5.4, 4.1).move_to([0.2, -0.95, 0])
        self.add(zh("各种度量随 θ 的变化", 24).move_to([0.2, 1.75, 0]))
        self.add(ax, tex(r"\theta", 32, MUTED).next_to(ax.x_axis, RIGHT, buff=0.15))

        w1 = ax.plot(lambda t: abs(t), x_range=[-1.6, 1.6, 0.01], color=BLUE_, stroke_width=6)
        ln2 = np.log(2)
        js_l = Line(ax.c2p(-2, ln2), ax.c2p(0, ln2), color=ORANGE_, stroke_width=6)
        js_r = Line(ax.c2p(0, ln2), ax.c2p(2, ln2), color=ORANGE_, stroke_width=6)
        hollow = Circle(radius=0.08, color=ORANGE_, stroke_width=4).set_fill(BG, 1).move_to(ax.c2p(0, ln2))
        filled = Dot(ax.c2p(0, 0), radius=0.08, color=ORANGE_)
        sig = 0.5
        noisy = DashedVMobject(
            ax.plot(lambda t: js_gauss(t, sig), x_range=[-2, 2, 0.02], color=GREEN_, stroke_width=6),
            num_dashes=46, dashed_ratio=0.6)
        self.add(noisy, w1, js_l, js_r, hollow, filled)

        # 右：图例
        def item(mark, title, note):
            words = VGroup(title, note).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
            return VGroup(mark, words).arrange(RIGHT, buff=0.25, aligned_edge=UP)

        seg = lambda c: Line(ORIGIN, RIGHT * 0.6, color=c, stroke_width=6)
        legend = VGroup(
            item(seg(BLUE_), tex(r"W_1(P,Q_\theta)=|\theta|", 30, BLUE_),
                 zh("随距离线性下降，始终有方向", 18, MUTED)),
            item(seg(ORANGE_), tex(r"\mathrm{JS}(P,Q_\theta)", 30, ORANGE_),
                 zh("θ ≠ 0 时恒为 log 2，梯度为 0", 18, MUTED)),
            item(DashedLine(ORIGIN, RIGHT * 0.6, color=GREEN_, stroke_width=6, dash_length=0.12),
                 VGroup(zh("加噪后的 JS", 22, GREEN_), tex(r"(\sigma=0.5)", 28, GREEN_)).arrange(RIGHT, buff=0.1),
                 zh("重新变得平滑，第 8 节再讲", 18, MUTED)),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.45).move_to([5.75, -0.7, 0], aligned_edge=ORIGIN)
        legend.align_to([3.55, 0, 0], LEFT)
        self.add(legend)


# ------------------------------------------------------------------ 加噪
def band_image(thetas_colors, sigma, length, xlim, ylim, unit_px=120):
    from math import erf, sqrt
    w = int((xlim[1] - xlim[0]) * unit_px)
    h = int((ylim[1] - ylim[0]) * unit_px)
    xs = np.linspace(xlim[0], xlim[1], w)
    ys = np.linspace(ylim[1], ylim[0], h)  # 图片第一行在上
    X, Y = np.meshgrid(xs, ys)
    verf = np.vectorize(erf)
    gy = 0.5 * (verf(Y / (sqrt(2) * sigma)) - verf((Y - length) / (sqrt(2) * sigma)))
    # RGBA with a transparent base, so the bands sit on the page background without a visible box
    premul = np.zeros((h, w, 3))
    alpha = np.zeros((h, w))
    for x0, color in thetas_colors:
        a = (np.exp(-(X - x0) ** 2 / (2 * sigma**2)) * gy)
        a = 0.62 * a / a.max()
        rgb = np.array(color.to_rgb())
        premul = rgb * a[..., None] + premul * (1 - a[..., None])
        alpha = a + alpha * (1 - a)
    straight = premul / np.maximum(alpha, 1e-6)[..., None]
    return (np.dstack([straight, alpha]) * 255).astype(np.uint8)


class NoiseSmoothing(Scene):
    def construct(self):
        header(self, "加噪：让两个低维分布在整个空间里重叠",
               "给两个分布都加上高斯噪声：细线变成模糊的带子，处处有正密度，两者开始重叠")
        theta, sigma, length, unit = 0.6, 0.22, 2.4, 1.45
        cy0 = -2.35  # 线段底部的 y

        # 左：加噪前
        lx = -6.0
        self.add(zh("加噪前：两条不相交的线", 24).move_to([-5.55, 1.75, 0]))
        self.add(Line([lx, cy0, 0], [lx, cy0 + length * unit, 0], color=BLUE_, stroke_width=9))
        self.add(Line([lx + theta * unit, cy0, 0], [lx + theta * unit, cy0 + length * unit, 0],
                      color=ORANGE_, stroke_width=9))
        self.add(tex("P", 34, BLUE_).move_to([lx, cy0 - 0.4, 0]),
                 tex(r"Q_\theta", 34, ORANGE_).move_to([lx + theta * unit, cy0 - 0.4, 0]))

        # 中：加噪后
        xlim, ylim = (-0.9, theta + 0.9), (-0.6, length + 0.6)
        img = ImageMobject(band_image([(0, BLUE_), (theta, ORANGE_)], sigma, length, xlim, ylim))
        img.height = (ylim[1] - ylim[0]) * unit
        mx = -0.85
        img.move_to([mx + (xlim[0] + xlim[1]) / 2 * unit, cy0 + (ylim[0] + ylim[1]) / 2 * unit, 0])
        self.add(img, zh("加噪后：两条带子重叠", 24).move_to([mx + 0.45, 1.75, 0]))
        cut_y = cy0 + length / 2 * unit
        cut = DashedLine([img.get_left()[0] - 0.3, cut_y, 0], [img.get_right()[0] + 0.3, cut_y, 0],
                         color=MUTED, stroke_width=2.5, dash_length=0.08)
        self.add(cut, zh("截面", 18, MUTED).next_to(cut, RIGHT, buff=0.12))
        self.add(Arrow([-4.75, cut_y, 0], [img.get_left()[0] - 0.4, cut_y, 0], color=FAINT,
                       stroke_width=5, max_tip_length_to_length_ratio=0.3, buff=0))
        self.add(tex(r"+\,\sigma\epsilon", 30, MUTED).move_to([-3.75, cut_y + 0.4, 0]))

        # 右：截面密度
        ax = muted_axes([-1.2, 2.0, 1], [0, 1.15, 0.5], 4.6, 3.4, y_numbers=False).move_to([4.75, -0.95, 0])
        ax.y_axis.set_opacity(0)
        self.add(zh("截面：密度曲线有了交集", 24).move_to([4.75, 1.75, 0]))
        self.add(ax, tex("x", 30, MUTED).next_to(ax.x_axis, RIGHT, buff=0.12))
        g = lambda c: (lambda t: np.exp(-(t - c) ** 2 / (2 * sigma**2)))
        p_curve = ax.plot(g(0), x_range=[-1.2, 2.0, 0.01], color=BLUE_, stroke_width=6)
        q_curve = ax.plot(g(theta), x_range=[-1.2, 2.0, 0.01], color=ORANGE_, stroke_width=6)
        ts = np.linspace(-1.2, 2.0, 300)
        overlap = Polygon(*[ax.c2p(t, min(g(0)(t), g(theta)(t))) for t in ts],
                          ax.c2p(2.0, 0), ax.c2p(-1.2, 0),
                          stroke_width=0, fill_color=GREEN_, fill_opacity=0.22)
        self.add(overlap, p_curve, q_curve)
        self.add(tex(r"P_\sigma", 30, BLUE_).next_to(ax.c2p(-0.35, 0.85), LEFT, buff=0.05),
                 tex(r"Q_{\theta,\sigma}", 30, ORANGE_).next_to(ax.c2p(0.95, 0.85), RIGHT, buff=0.05),
                 )
        note = zh("重叠部分", 20, GREEN_).move_to(ax.c2p(1.55, 0.42))
        self.add(note, Arrow(note.get_bottom() + DOWN * 0.05 + LEFT * 0.2, ax.c2p(0.38, 0.1),
                             color=GREEN_, stroke_width=3, max_tip_length_to_length_ratio=0.12, buff=0.05))
