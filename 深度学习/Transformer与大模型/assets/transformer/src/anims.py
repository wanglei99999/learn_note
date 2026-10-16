"""Manim animations for 深度学习/Transformer结构详解.md (Style 6: cream background, soft fills).

Render (1200x600, 20 fps), then convert with
深度学习/生成模型与数据几何/assets/manifold/src/gif_tools.py:
    manim -r 1200,600 --fps 20 anims.py RoPE ResidualStream Generation
    python gif_tools.py <video.mp4> <out.gif> 20 [colors]
Generation needs colors=128; at the default 64 the top probability bar is quantized to gray.
"""
import numpy as np
from manim import *

config.background_color = ManimColor("#F8F6F3")
config.frame_width = 16
config.frame_height = 8

# palette mirrors 大模型训练/assets/src/claude_style.py
INK = ManimColor("#1A1A1A")
MUTED = ManimColor("#6A6A6A")
FAINT = ManimColor("#D6D0C7")
STROKE = ManimColor("#4A4A4A")
BLUE_ = ManimColor("#4F86C0")
BLUE_SOFT = ManimColor("#A8C5E6")
BLUE_MID = ManimColor("#8DB2DD")
ORANGE_ = ManimColor("#D97757")
GREEN_ = ManimColor("#3F9C86")
GREEN_SOFT = ManimColor("#9DD4C7")
FONT = "Microsoft YaHei"


def zh(s: str, size: float = 24, color: ManimColor = INK, weight: str = NORMAL) -> Text:
    return Text(s, font=FONT, font_size=size, color=color, weight=weight)


def tex(s: str, size: float = 34, color: ManimColor = INK) -> MathTex:
    return MathTex(s, font_size=size, color=color)


def header(scene: Scene, title: str, subtitle: str) -> VGroup:
    t = zh(title, 32, weight=BOLD).to_corner(UL, buff=0.6)
    s = zh(subtitle, 20, MUTED).next_to(t, DOWN, aligned_edge=LEFT, buff=0.2)
    scene.add(t, s)
    return VGroup(t, s)


def card(w: float, h: float, fill: ManimColor = BLUE_SOFT, stroke: ManimColor = STROKE,
         width: float = 2.5) -> RoundedRectangle:
    return RoundedRectangle(width=w, height=h, corner_radius=0.12, fill_color=fill,
                            fill_opacity=1, stroke_color=stroke, stroke_width=width)


# ------------------------------------------------------------------ RoPE
class RoPE(Scene):
    """q at position m is rotated by mθ, k at position n by nθ; q·k depends on n - m only."""

    def construct(self) -> None:
        header(self, "RoPE：按位置旋转 q 和 k，点积只取决于相对距离",
               "示意：一对维度上的旋转，每前进一个位置多转 θ；为便于观察，|q| = |k| = 1")
        center = np.array([-3.7, -0.5, 0])
        radius = 2.1
        theta = 0.42
        q_base = 0.35

        self.add(Circle(radius=radius, color=FAINT, stroke_width=2).move_to(center))
        self.add(Line(center + LEFT * (radius + 0.35), center + RIGHT * (radius + 0.35),
                      color=FAINT, stroke_width=2))
        self.add(Line(center + DOWN * (radius + 0.35), center + UP * (radius + 0.35),
                      color=FAINT, stroke_width=2))

        shift = ValueTracker(0.0)
        gap = ValueTracker(2.0)

        def m() -> float:
            return 1 + shift.get_value()

        def n() -> float:
            return m() + gap.get_value()

        def q_ang() -> float:
            return q_base + m() * theta

        def k_ang() -> float:
            return n() * theta

        def unit(a: float) -> np.ndarray:
            return np.array([np.cos(a), np.sin(a), 0])

        def vec(angle_fn, color) -> Arrow:
            return Arrow(center, center + radius * unit(angle_fn()), buff=0, color=color,
                         stroke_width=7, max_tip_length_to_length_ratio=0.12)

        q_vec = always_redraw(lambda: vec(q_ang, BLUE_))
        k_vec = always_redraw(lambda: vec(k_ang, ORANGE_))
        q_lab = always_redraw(lambda: tex(r"\tilde q_m", 36, BLUE_).move_to(center + (radius + 0.5) * unit(q_ang())))
        k_lab = always_redraw(lambda: tex(r"\tilde k_n", 36, ORANGE_).move_to(center + (radius + 0.5) * unit(k_ang())))
        arc = always_redraw(lambda: Arc(radius=0.75, start_angle=q_ang(), angle=k_ang() - q_ang(),
                                        arc_center=center, color=MUTED, stroke_width=4))
        self.add(arc, q_vec, k_vec, q_lab, k_lab)

        def row(label: str, value_fn, places: int = 0, color: ManimColor = INK) -> VGroup:
            name = zh(label, 26, color)
            num = DecimalNumber(value_fn(), num_decimal_places=places, font_size=34, color=color)
            num.add_updater(lambda d: d.set_value(value_fn()))
            return VGroup(name, num)

        rows = [
            row("q 的位置 m", m, 0, BLUE_),
            row("k 的位置 n", n, 0, ORANGE_),
            row("相对距离 n − m", lambda: gap.get_value(), 0),
            row("点积 q · k", lambda: np.cos(k_ang() - q_ang()), 3),
        ]
        x_name, x_num = 1.2, 5.9
        for i, (name, num) in enumerate(rows):
            y = 1.25 - i * 0.85
            name.move_to([x_name, y, 0], aligned_edge=LEFT)
            num.move_to([x_num, y, 0], aligned_edge=RIGHT)
            num.add_updater(lambda d, y=y: d.move_to([x_num, y, 0], aligned_edge=RIGHT))
            self.add(name, num)
        self.add(Line([1.2, -1.75, 0], [6.6, -1.75, 0], color=FAINT, stroke_width=2))
        formula = tex(r"\tilde q_m \cdot \tilde k_n = q^\top R\big((n-m)\theta\big)\, k", 34)
        formula.move_to([1.2, -2.35, 0], aligned_edge=LEFT)
        self.add(formula)

        status = zh("q、k 一起往后移：位置变了，距离不变，点积也不变", 24, BLUE_).move_to([0, -3.45, 0])
        self.add(status)
        self.wait(0.8)
        for step in range(1, 5):
            self.play(shift.animate.set_value(step), run_time=0.9, rate_func=smooth)
            self.wait(0.2)
        self.wait(0.6)

        status2 = zh("只让 k 再往后走：距离变大，夹角和点积才会变化", 24, ORANGE_).move_to(status)
        self.play(FadeTransform(status, status2), run_time=0.5)
        self.play(gap.animate.set_value(4), run_time=1.8, rate_func=smooth)
        self.wait(1.6)


# --------------------------------------------------------- 残差流
def vec_column(values: list[float], high: ManimColor, cell: float = 0.3) -> VGroup:
    cells = [Square(cell, fill_color=interpolate_color(WHITE, high, float(np.clip(v, 0.05, 1))),
                    fill_opacity=1, stroke_color=high, stroke_width=1.5) for v in values]
    return VGroup(*cells).arrange(DOWN, buff=0.04)


class ResidualStream(Scene):
    def construct(self) -> None:
        header(self, "残差流：每个子层读取向量、计算增量，再加回去",
               "示意：一个 token 的向量沿残差流向右流动；方块颜色深浅代表各维数值，为简洁只画两层")
        y_s = -1.05
        xs = [-4.6, -1.55, 1.5, 4.55]
        names = [("Attention", "第 1 层"), ("FFN", "第 1 层"), ("Attention", "第 2 层"), ("FFN", "第 2 层")]
        stream = Arrow([-7.4, y_s, 0], [7.5, y_s, 0], buff=0, color=BLUE_, stroke_width=8,
                       max_tip_length_to_length_ratio=0.02)
        self.add(stream, zh("残差流", 22, BLUE_).move_to([-6.9, y_s - 0.45, 0]))

        blocks = []
        for x, (name, layer) in zip(xs, names):
            box = card(2.3, 1.15).move_to([x, 1.15, 0])
            label = VGroup(zh(name, 26), zh(layer, 18, MUTED)).arrange(DOWN, buff=0.08).move_to(box)
            up = Line([x - 0.7, y_s, 0], [x - 0.7, 0.575, 0], color=BLUE_, stroke_width=3)
            down = Arrow([x + 0.7, 0.575, 0], [x + 0.7, y_s + 0.24, 0], buff=0, color=BLUE_,
                         stroke_width=3, max_tip_length_to_length_ratio=0.12)
            plus = VGroup(Circle(0.22, color=BLUE_, stroke_width=3).set_fill(WHITE, 1),
                          Line(LEFT * 0.12, RIGHT * 0.12, color=BLUE_, stroke_width=3),
                          Line(DOWN * 0.12, UP * 0.12, color=BLUE_, stroke_width=3)).move_to([x + 0.7, y_s, 0])
            norm = zh("Norm", 16, MUTED).next_to(up, LEFT, buff=0.08).shift(UP * 0.3)
            self.add(up, down, plus, box, label, norm)
            blocks.append(box)

        values = np.array([0.25, 0.7, 0.4, 0.15, 0.55, 0.3])
        deltas = [np.array(d) for d in ([0.3, 0.0, 0.25, 0.1, 0.0, 0.2],
                                        [0.0, 0.2, 0.1, 0.35, 0.15, 0.0],
                                        [0.15, 0.0, 0.0, 0.2, 0.25, 0.3],
                                        [0.2, 0.1, 0.2, 0.0, 0.05, 0.15])]
        captions = ["Attention：从上下文其他 token 收集信息，算出增量，加回残差流",
                    "FFN：对这个 token 单独加工，算出增量，加回残差流",
                    "下一层同样：读取当前向量，写入新的增量",
                    "原有内容一直保留，每个子层只往里追加信息"]

        vec = vec_column(values, BLUE_).move_to([-6.05, y_s, 0])
        cap = zh("token 的向量进入残差流", 24).move_to([0, -3.4, 0])
        self.add(vec, cap)
        self.wait(0.6)

        for i, x in enumerate(xs):
            new_cap = zh(captions[i], 24).move_to(cap)
            self.play(vec.animate.move_to([x - 0.7, y_s, 0]), FadeTransform(cap, new_cap), run_time=0.7)
            cap = new_cap
            probe = vec.copy()
            self.play(probe.animate.scale(0.55).move_to([x - 0.7, 0.2, 0]), run_time=0.45)
            self.play(FadeOut(probe, scale=0.6), blocks[i].animate.set_fill(BLUE_MID), run_time=0.35)
            delta = vec_column(deltas[i], GREEN_).scale(0.55).move_to([x + 0.7, 0.2, 0])
            self.play(FadeIn(delta, shift=DOWN * 0.2), blocks[i].animate.set_fill(BLUE_SOFT), run_time=0.35)
            self.play(delta.animate.scale(1 / 0.55).move_to([x + 0.7, y_s, 0]),
                      vec.animate.move_to([x + 0.7, y_s, 0]), run_time=0.6)
            values = np.clip(values + deltas[i], 0, 1)
            updated = vec_column(values, BLUE_).move_to([x + 0.7, y_s, 0])
            self.play(Transform(vec, updated), FadeOut(delta), run_time=0.45)

        self.play(vec.animate.move_to([6.8, y_s, 0]), run_time=0.6)
        self.wait(1.6)


# ------------------------------------------------------- 自回归生成
def token_box(s: str, hot: bool = False) -> VGroup:
    label = zh(s, 26)
    w = max(0.75, label.width + 0.4)
    box = card(w, 0.72, GREEN_SOFT if hot else BLUE_SOFT, STROKE, 2.5)
    return VGroup(box, label.move_to(box))


class Generation(Scene):
    def construct(self) -> None:
        header(self, "自回归生成：预测、采样、追加，再预测",
               "示意：每轮只用最后一个位置的输出；这里每次取概率最高的 token，概率数值仅作示意")
        row_y = 1.45
        row = VGroup(*[token_box(s) for s in ["猫", "吃饱", "了", "，"]])
        row.arrange(RIGHT, buff=0.14).move_to([-6.9, row_y, 0], aligned_edge=LEFT)
        self.add(row)

        model = card(4.4, 1.35).move_to([-4.3, -0.75, 0])
        model_lab = VGroup(zh("Transformer（32 层）", 26), zh("取最后一个位置 → LM head → softmax", 17, MUTED)
                           ).arrange(DOWN, buff=0.12).move_to(model)
        self.add(model, model_lab)
        self.add(Arrow([-4.3, row_y - 0.45, 0], [-4.3, 0.0, 0], buff=0, color=BLUE_, stroke_width=4,
                       max_tip_length_to_length_ratio=0.12))
        self.add(Arrow([-2.05, -0.75, 0], [-0.55, -0.75, 0], buff=0, color=BLUE_, stroke_width=4,
                       max_tip_length_to_length_ratio=0.15))
        self.add(zh("下一个 token 的概率", 22).move_to([0.1, 0.65, 0], aligned_edge=LEFT))

        steps = [
            [("它", 0.46), ("然后", 0.21), ("就", 0.12), ("很", 0.08)],
            [("睡", 0.38), ("就", 0.22), ("很", 0.15), ("开始", 0.09)],
            [("着", 0.52), ("了", 0.27), ("觉", 0.10), ("在", 0.04)],
            [("了", 0.71), ("。", 0.12), ("啦", 0.06), ("吧", 0.03)],
        ]
        cap = zh("前向计算一次，得到整张词表上的概率分布", 24).move_to([0, -3.4, 0])
        self.add(cap)
        x_lab, x_bar, scale = 1.25, 1.45, 6.2
        for k, cands in enumerate(steps):
            self.play(Indicate(model, color=BLUE_MID, scale_factor=1.03), run_time=0.5)
            bars = VGroup()
            for j, (tok, p) in enumerate(cands):
                y = 0.0 - j * 0.62
                lab = zh(tok, 24).move_to([x_lab, y, 0], aligned_edge=RIGHT)
                bar = Rectangle(width=p * scale, height=0.36, stroke_width=0,
                                fill_color=BLUE_ if j == 0 else FAINT, fill_opacity=1)
                bar.move_to([x_bar, y, 0], aligned_edge=LEFT)
                val = zh(f"{p:.2f}", 22, MUTED).next_to(bar, RIGHT, buff=0.15)
                bars.add(VGroup(lab, bar, val))
            self.play(LaggedStart(*[FadeIn(b, shift=RIGHT * 0.2) for b in bars], lag_ratio=0.12), run_time=0.7)
            if k == 0:
                new_cap = zh("选出一个 token，接到输入末尾", 24).move_to(cap)
                self.play(FadeTransform(cap, new_cap), run_time=0.4)
                cap = new_cap
            chosen = token_box(cands[0][0], hot=True)
            chosen.move_to(bars[0][0].get_center())
            target = chosen.copy().next_to(row, RIGHT, buff=0.14)
            self.play(FadeIn(chosen, scale=0.8), run_time=0.3)
            self.play(chosen.animate.move_to(target.get_center()), run_time=0.7)
            row.add(chosen)
            self.play(FadeOut(bars), run_time=0.3)
            if k == 0:
                new_cap = zh("带上新 token 再算一轮，如此循环", 24).move_to(cap)
                self.play(FadeTransform(cap, new_cap), run_time=0.4)
                cap = new_cap

        done = zh("生成结果：猫吃饱了，它睡着了", 26, GREEN_).move_to(cap)
        self.play(FadeTransform(cap, done), run_time=0.5)
        self.wait(1.8)
