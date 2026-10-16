"""Flat-style SVG figures for 深度学习/Transformer结构详解.md.

Usage: python flat_figs.py <output_dir>
Layouts are drawn in the old flat palette, then converted to Style 6 (Claude Official)
by 大模型训练/assets/src/flat_to_claude.py, which shares claude_style.py's colors.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "大模型训练" / "assets" / "src"))
from flat_to_claude import restyle  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

BLUE = "#2563eb"
INK = "#111827"
GRAY = "#6b7280"
LINE = "#d1d5db"
FILL_MAIN = "#eff6ff"
FILL_SOFT = "#f9fafb"
FILL_OUT = "#f0fdf4"
STROKE_MAIN = "#93c5fd"
STROKE_SOFT = "#e5e7eb"
STROKE_OUT = "#86efac"

# dataviz reference palette, fixed order (validated: scripts/validate_palette.js)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

FONT = "<style>text{font-family:'Microsoft YaHei','SimHei',sans-serif}</style>"
DEFS = (f'<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" '
        f'orient="auto"><path d="M0 0L10 4L0 8Z" fill="{BLUE}"/></marker></defs>')


def sub(base: str, s: str, size: float) -> str:
    small = round(size * 0.68)
    return f'{base}<tspan font-size="{small}" baseline-shift="sub">{s}</tspan>'


def text(x: float, y: float, content: str, size: float = 20, fill: str = INK,
         anchor: str = "middle", weight: str | None = None) -> str:
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{w}>{content}</text>')


def box(x: float, y: float, w: float, h: float, fill: str = FILL_MAIN,
        stroke: str = LINE, sw: float = 2, dash: str | None = None, rx: float = 8) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')


def node(cx: float, y: float, w: float, h: float, title: str, note: str | None = None,
         fill: str = FILL_MAIN, stroke: str = LINE, sw: float = 2) -> str:
    parts = [box(cx - w / 2, y, w, h, fill, stroke, sw)]
    if note:
        parts.append(text(cx, y + h / 2 - 4, title, 20))
        parts.append(text(cx, y + h / 2 + 20, note, 15, GRAY))
    else:
        parts.append(text(cx, y + h / 2 + 7, title, 20))
    return "".join(parts)


def arrow(d: str, color: str = BLUE, sw: float = 2.5) -> str:
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'marker-end="url(#arrow)"/>')


def plain(d: str, color: str = BLUE, sw: float = 2.5, dash: str | None = None) -> str:
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{ds}/>'


def plus_circle(cx: float, cy: float, r: float = 17) -> str:
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" stroke="{BLUE}" stroke-width="2.5"/>'
            f'<path d="M{cx - 8} {cy}H{cx + 8}M{cx} {cy - 8}V{cy + 8}" stroke="{BLUE}" stroke-width="2.5"/>')


def times_circle(cx: float, cy: float, r: float = 17) -> str:
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" stroke="{BLUE}" stroke-width="2.5"/>'
            f'<circle cx="{cx}" cy="{cy}" r="3.5" fill="{BLUE}"/>')


def svg(w: int, h: int, body: list[str]) -> str:
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{FONT}{DEFS}<rect width="{w}" height="{h}" fill="#ffffff"/>')
    return head + "".join(body) + "</svg>"


def header(b: list[str], title: str, subtitle: str) -> None:
    b.append(text(40, 48, title, 30, anchor="start"))
    b.append(text(40, 82, subtitle, 18, GRAY, "start"))


# ------------------------------------------------------------------ 01 总览
def overview() -> str:
    b: list[str] = []
    header(b, "decoder-only Transformer：从一段文字到下一个 token",
           "以 Llama-2-7B 为例；右侧是每一步输出的张量形状，S 为输入的 token 数。")
    cx, w, h = 430, 300, 52
    ann_x = 760
    b.append(text(ann_x, 124, "输出形状", 17, GRAY, "start"))

    steps_top = [
        (140, "输入文字", "“猫吃饱了，它”", FILL_SOFT, STROKE_SOFT),
        (220, "Tokenizer", "token id：[S]", FILL_MAIN, LINE),
        (300, "Embedding 查表", "[S, 4096]", FILL_MAIN, LINE),
    ]
    for y, title, ann, fill, stroke in steps_top:
        b.append(node(cx, y, w, h, title, fill=fill, stroke=stroke))
        b.append(text(ann_x, y + 33, ann, 18, INK, "start"))
    for y in (192, 272):
        b.append(arrow(f"M{cx} {y}V{y + 28}"))
    b.append(arrow(f"M{cx} 352V380"))

    # block container
    b.append(box(150, 380, 560, 250, "none", "#9ca3af", 2, "6,4"))
    b.append(text(170, 412, "Transformer block", 20, INK, "start"))
    b.append(box(590, 392, 104, 30, "#dbeafe", BLUE, 2, rx=15))
    b.append(text(642, 413, "× 32 层", 16, BLUE))
    b.append(node(cx, 432, 480, 70, "注意力子层", "RMSNorm → 多头因果注意力（RoPE）→ 残差相加"))
    b.append(arrow(f"M{cx} 502V530"))
    b.append(node(cx, 530, 480, 70, "FFN 子层", "RMSNorm → SwiGLU FFN → 残差相加"))
    b.append(text(ann_x, 512, "[S, 4096]，每层形状不变", 18, INK, "start"))
    b.append(text(ann_x, 538, "attention：token 之间交换信息", 16, GRAY, "start"))
    b.append(text(ann_x, 562, "FFN：每个 token 单独加工", 16, GRAY, "start"))
    b.append(arrow(f"M{cx} 630V660"))

    steps_bottom = [
        (660, "最终 RMSNorm", "[S, 4096]"),
        (740, "LM head", "logits：[S, 32000]"),
        (820, "softmax（取最后一个位置）", "概率分布：[32000]"),
    ]
    for y, title, ann in steps_bottom:
        b.append(node(cx, y, w, h, title))
        b.append(text(ann_x, y + 33, ann, 18, INK, "start"))
    for y in (712, 792, 872):
        b.append(arrow(f"M{cx} {y}V{y + 28}"))
    b.append(node(cx, 900, w, h, "采样得到下一个 token：“睡”", fill=FILL_OUT, stroke=STROKE_OUT))
    b.append(text(ann_x, 933, "接到输入末尾，开始下一轮", 18, INK, "start"))

    # autoregressive loop on the left
    b.append(arrow(f"M{cx - w / 2} 926H96V166H{cx - w / 2}", "#9ca3af", 2))
    b.append(f'<text x="80" y="546" font-size="16" fill="{GRAY}" text-anchor="middle" '
             f'transform="rotate(-90 80 546)">自回归：追加后重复整个过程</text>')
    return svg(1200, 990, b)


# ------------------------------------------------------------------ 03 block
def block() -> str:
    b: list[str] = []
    header(b, "一个 Pre-Norm Transformer block（Llama 风格）",
           "两个子层，各自先归一化、再计算，结果作为增量加回残差流。")
    rx = 330          # residual stream x
    sx = 640          # sublayer column center
    sw_ = 320

    b.append(node(rx, 110, 260, 52, "输入 x（来自上一层）", fill=FILL_SOFT, stroke=STROKE_SOFT))
    # residual stream segments
    b.append(plain(f"M{rx} 162V433", BLUE, 4))
    b.append(plain(f"M{rx} 467V733", BLUE, 4))
    b.append(arrow(f"M{rx} 767V800", BLUE, 2.5))
    b.append(text(rx - 26, 300, "残差直通", 17, BLUE, "end"))
    b.append(text(rx - 26, 324, "x 原样保留", 15, GRAY, "end"))
    b.append(text(rx - 26, 600, "残差直通", 17, BLUE, "end"))
    b.append(text(rx - 26, 624, "h 原样保留", 15, GRAY, "end"))

    # sublayer 1
    b.append(arrow(f"M{rx} 192H{sx}V220"))
    b.append(node(sx, 220, sw_, 48, "RMSNorm"))
    b.append(arrow(f"M{sx} 268V296"))
    b.append(node(sx, 296, sw_, 84, "多头因果自注意力", "RoPE 旋转 q、k · 因果 mask · W_O"))
    b.append(arrow(f"M{sx} 380V450H{rx + 19}"))
    b.append(plus_circle(rx, 450))
    b.append(text(rx - 30, 457, "h", 18, INK, "end"))

    # sublayer 2
    b.append(arrow(f"M{rx} 490H{sx}V518"))
    b.append(node(sx, 518, sw_, 48, "RMSNorm"))
    b.append(arrow(f"M{sx} 566V594"))
    b.append(node(sx, 594, sw_, 84, "FFN（SwiGLU）", "4096 → 11008 → 4096 · 逐位置独立"))
    b.append(arrow(f"M{sx} 678V750H{rx + 19}"))
    b.append(plus_circle(rx, 750))

    b.append(node(rx, 800, 260, 52, "输出（送入下一层）", fill=FILL_OUT, stroke=STROKE_OUT))

    # right annotations
    ax = 840
    b.append(text(ax, 330, "token 之间交换信息", 18, INK, "start"))
    b.append(text(ax, 356, "每个位置只看自己和前面", 16, GRAY, "start"))
    b.append(text(ax, 628, "每个 token 单独加工", 18, INK, "start"))
    b.append(text(ax, 654, "提供主要的非线性变换", 16, GRAY, "start"))
    b.append(text(ax, 790, "h = x + Attention(RMSNorm(x))", 18, INK, "start"))
    b.append(text(ax, 822, "out = h + FFN(RMSNorm(h))", 18, INK, "start"))
    return svg(1200, 890, b)


# ------------------------------------------------------------------ 05 FFN
def vec_bar(cx: float, y: float, dim: int, label: str, color: str = STROKE_MAIN,
            fill: str = FILL_MAIN, unit: float = 80 / 4096) -> str:
    w = dim * unit
    return (box(cx - w / 2, y, w, 26, fill, color, 2, rx=6)
            + text(cx + w / 2 + 12, y + 19, label, 16, GRAY, "start"))


def ffn() -> str:
    b: list[str] = []
    header(b, "FFN：先升维，做非线性变换，再降回原维度",
           "条的长度按向量维度等比例绘制；d = 4096。两种结构的参数量都约为 8d²。")

    # left panel: standard FFN
    b.append(box(40, 110, 520, 620, "#ffffff", STROKE_SOFT))
    b.append(text(64, 150, "标准 FFN（原始 Transformer）", 22, INK, "start"))
    lx = 255
    b.append(vec_bar(lx, 200, 4096, "x：4096"))
    b.append(arrow(f"M{lx} 226V286"))
    b.append(text(lx + 14, 262, sub("× W", "1", 17), 17, BLUE, "start"))
    b.append(vec_bar(lx, 290, 16384, "4d = 16384"))
    b.append(arrow(f"M{lx} 316V356"))
    b.append(node(lx, 360, 200, 44, "ReLU / GELU"))
    b.append(arrow(f"M{lx} 404V444"))
    b.append(vec_bar(lx, 448, 16384, "16384"))
    b.append(arrow(f"M{lx} 474V534"))
    b.append(text(lx + 14, 510, sub("× W", "2", 17), 17, BLUE, "start"))
    b.append(vec_bar(lx, 538, 4096, "输出：4096", STROKE_OUT, FILL_OUT))
    b.append(text(64, 640, "参数：2 × d × 4d = 8d²", 18, INK, "start"))
    b.append(text(64, 672, "两个矩阵，激活函数作用在升维后的向量上", 16, GRAY, "start"))

    # right panel: SwiGLU
    b.append(box(600, 110, 560, 620, "#ffffff", BLUE, 2))
    b.append(text(624, 150, "SwiGLU FFN（Llama、Qwen 等）", 22, INK, "start"))
    cx, gx, ux = 880, 760, 1000
    b.append(vec_bar(cx, 200, 4096, "x：4096"))
    b.append(arrow(f"M{cx - 20} 226V250H{gx}V286"))
    b.append(arrow(f"M{cx + 20} 226V250H{ux}V376"))
    b.append(text(gx - 12, 274, sub("× W", "gate", 17), 17, BLUE, "end"))
    b.append(text(ux + 12, 274, sub("× W", "up", 17), 17, BLUE, "start"))
    b.append(box(gx - 108, 290, 216, 26, FILL_MAIN, STROKE_MAIN, 2, rx=6))
    b.append(text(gx, 309, "11008", 15, GRAY))
    b.append(arrow(f"M{gx} 316V336"))
    b.append(node(gx, 336, 120, 40, "SiLU"))
    b.append(arrow(f"M{gx} 376V396"))
    b.append(box(gx - 108, 400, 216, 26, FILL_MAIN, STROKE_MAIN, 2, rx=6))
    b.append(text(gx, 419, "门：每个维度放行多少", 14, GRAY))
    b.append(box(ux - 108, 380, 216, 26, FILL_MAIN, STROKE_MAIN, 2, rx=6))
    b.append(text(ux, 399, "11008：候选内容", 14, GRAY))
    b.append(arrow(f"M{gx} 426V470H{cx - 19}"))
    b.append(arrow(f"M{ux} 406V470H{cx + 19}"))
    b.append(times_circle(cx, 470))
    b.append(text(cx, 508, "逐元素相乘 ⊙", 15, GRAY))
    b.append(arrow(f"M{cx} 516V540", BLUE))
    b.append(box(cx - 108, 544, 216, 26, FILL_MAIN, STROKE_MAIN, 2, rx=6))
    b.append(text(cx, 563, "11008", 15, GRAY))
    b.append(arrow(f"M{cx} 570V600"))
    b.append(text(cx + 14, 590, sub("× W", "down", 17), 17, BLUE, "start"))
    b.append(vec_bar(cx, 604, 4096, "输出：4096", STROKE_OUT, FILL_OUT))
    b.append(text(624, 672, "参数：3 × d × (8d/3) = 8d²；8/3 × 4096 ≈ 10923，取整为 11008", 16, INK, "start"))
    b.append(text(624, 700, "多一个矩阵，隐藏层就缩小到 8d/3，参数量保持不变", 16, GRAY, "start"))
    return svg(1200, 770, b)


# ------------------------------------------------------------------ 07 架构
def mask_grid(x0: float, y0: float, n: int, cell: float, rule: str) -> str:
    parts = []
    for i in range(n):
        for j in range(n):
            on = rule == "full" or (rule == "causal" and j <= i)
            fill, stroke = (("#dbeafe", BLUE) if on else ("#f3f4f6", STROKE_SOFT))
            parts.append(box(x0 + j * (cell + 4), y0 + i * (cell + 4), cell, cell, fill, stroke, 1.5, rx=4))
    return "".join(parts)


def architectures() -> str:
    b: list[str] = []
    header(b, "三种 Transformer 架构：区别在于每个位置能看到谁",
           "方格表示注意力范围：第 i 行是提问的 token，第 j 列是被关注的 token，蓝色表示可见。")
    panels = [
        ("Encoder-only", "双向：每个 token 能看整句", "BERT、RoBERTa", "理解：分类、抽取、检索向量", "#e5e7eb"),
        ("Encoder-decoder", "编码器双向，解码器因果 + 交叉注意力", "原始 Transformer、T5", "翻译、摘要等输入输出分开的任务", "#e5e7eb"),
        ("Decoder-only", "因果：只能看自己和前面", "GPT、Llama、Qwen、DeepSeek", "生成，以及能写成续写的几乎所有任务", BLUE),
    ]
    for p, (name, rule_desc, models, use, border) in enumerate(panels):
        px = 40 + p * 380
        b.append(box(px, 110, 360, 500, "#ffffff", border, 2))
        b.append(text(px + 24, 150, name, 23, INK, "start"))
        b.append(text(px + 24, 178, rule_desc, 15, GRAY, "start"))
        if p == 0:
            b.append(mask_grid(px + 95, 210, 5, 30, "full"))
        elif p == 2:
            b.append(mask_grid(px + 95, 210, 5, 30, "causal"))
        else:
            b.append(text(px + 90, 214, "编码器自注意力", 14, GRAY))
            b.append(mask_grid(px + 30, 226, 4, 26, "full"))
            b.append(text(px + 270, 214, "解码器自注意力", 14, GRAY))
            b.append(mask_grid(px + 210, 226, 4, 26, "causal"))
            b.append(text(px + 180, 382, "交叉注意力：Q 来自解码器，", 14, GRAY))
            b.append(text(px + 180, 402, "K、V 来自编码器输出（全部可见）", 14, GRAY))
        b.append(f'<line x1="{px + 24}" y1="440" x2="{px + 336}" y2="440" stroke="{STROKE_SOFT}" stroke-width="1.5"/>')
        b.append(text(px + 24, 478, "代表模型", 15, GRAY, "start"))
        b.append(text(px + 24, 506, models, 17, INK, "start"))
        b.append(text(px + 24, 546, "擅长", 15, GRAY, "start"))
        b.append(text(px + 24, 574, use, 17, INK, "start"))
    b.append(text(40, 652, "今天的大语言模型几乎都是 decoder-only：一个“预测下一个 token”的目标覆盖所有任务，"
                  "结构简单，也天然适合 KV Cache。", 18, GRAY, "start"))
    return svg(1200, 690, b)


# ------------------------------------------------------------------ 08 参数
def stacked_bar(y: float, parts: list[tuple[float, str, str, str]], x0: float = 40,
                width: float = 1120, h: float = 52) -> list[str]:
    """parts: (fraction, color, label, value_text). Labels sit below each segment."""
    out, x = [], x0
    gap = 2
    for k, (frac, color, label, value) in enumerate(parts):
        w = width * frac - (gap if k < len(parts) - 1 else 0)
        first, last = k == 0, k == len(parts) - 1
        rx = 4
        # rounded only at the bar's outer ends
        if first:
            out.append(f'<path d="M{x + rx} {y}H{x + w}V{y + h}H{x + rx}Q{x} {y + h} {x} {y + h - rx}'
                       f'V{y + rx}Q{x} {y} {x + rx} {y}Z" fill="{color}"/>')
        elif last:
            out.append(f'<path d="M{x} {y}H{x + w - rx}Q{x + w} {y} {x + w} {y + rx}V{y + h - rx}'
                       f'Q{x + w} {y + h} {x + w - rx} {y + h}H{x}Z" fill="{color}"/>')
        else:
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}"/>')
        x += w + gap
    return out


def params() -> str:
    b: list[str] = []
    header(b, "Llama-2-7B 的参数：FFN 约占三分之二",
           "合计 6,738,415,616 个参数；归一化层共 26.6 万个，在图中不可见。")
    legend = [("FFN", SERIES[0]), ("attention", SERIES[1]), ("embedding", SERIES[2]), ("LM head", SERIES[3])]
    lx = 40
    for name, color in legend:
        b.append(f'<rect x="{lx}" y="112" width="18" height="18" rx="4" fill="{color}"/>')
        b.append(text(lx + 28, 127, name, 17, INK, "start"))
        lx += 60 + len(name) * 10

    # whole model
    b.append(text(40, 186, "整个模型", 20, INK, "start"))
    total = 6_738_415_616
    whole = [(4_328_521_728 / total, SERIES[0], "FFN", ""),
             (2_147_483_648 / total, SERIES[1], "attention", ""),
             (131_072_000 / total, SERIES[2], "embedding", ""),
             (131_072_000 / total, SERIES[3], "LM head", "")]
    b.extend(stacked_bar(200, whole))
    ffn_end = 40 + 1120 * whole[0][0]
    attn_end = ffn_end + 1120 * whole[1][0]
    b.append(text((40 + ffn_end) / 2, 284, "FFN 64.2%", 18, INK))
    b.append(text((40 + ffn_end) / 2, 308, "43.3 亿", 16, GRAY))
    b.append(text((ffn_end + attn_end) / 2, 284, "attention 31.9%", 18, INK))
    b.append(text((ffn_end + attn_end) / 2, 308, "21.5 亿", 16, GRAY))
    b.append(f'<path d="M{attn_end + 22} 197V186" fill="none" stroke="{GRAY}" stroke-width="1.5"/>')
    b.append(text(1160, 180, "embedding + LM head 3.9%（各 1.31 亿）", 16, INK, "end"))

    # one block
    b.append(text(40, 386, "单个 block（共 32 个）", 20, INK, "start"))
    blk = 202_383_360
    one = [(135_266_304 / blk, SERIES[0], "FFN", ""),
           (67_108_864 / blk, SERIES[1], "attention", "")]
    b.extend(stacked_bar(400, one))
    f_end = 40 + 1120 * one[0][0]
    b.append(text((40 + f_end) / 2, 484, "FFN 66.8%", 18, INK))
    b.append(text((40 + f_end) / 2, 508, "1.35 亿：3 个 4096 × 11008 矩阵", 16, GRAY))
    b.append(text((f_end + 1160) / 2, 484, "attention 33.2%", 18, INK))
    b.append(text((f_end + 1160) / 2, 508, "0.67 亿：4 个 4096 × 4096 矩阵", 16, GRAY))

    b.append(text(40, 566, "FFN 是参数的大头，所以 MoE 选择把 FFN 换成多个专家：在参数最多的地方做稀疏化，收益最大。",
                  18, GRAY, "start"))
    return svg(1200, 600, b)


# ------------------------------------------------------------------ 02 正弦位置编码
def sinusoidal_pe() -> str:
    import math
    b: list[str] = []
    header(b, "正弦位置编码：每对维度是一个频率不同的波",
           "d = 6 时的三组频率，圆点是位置 t = 0…7 的 sin 取值，对应正文表格。")

    x0, x1, t_max = 250, 1160, 24
    sx = (x1 - x0) / t_max
    b.append(f'<rect x="{x0}" y="120" width="{7 * sx}" height="330" fill="{FILL_SOFT}"/>')
    b.append(text(x0 + 3.5 * sx, 140, "表中的 8 个位置", 15, GRAY))
    lx = 860
    b.append(plain(f"M{lx} 132H{lx + 30}", SERIES[0], 3))
    b.append(text(lx + 38, 138, "sin（偶数维）", 15, INK, "start"))
    b.append(plain(f"M{lx + 150} 132H{lx + 180}", SERIES[1], 3, "6 5"))
    b.append(text(lx + 188, 138, "cos（奇数维）", 15, INK, "start"))

    rows = [(0, "dim0 / dim1", "ω = 1，周期 ≈ 6.3"),
            (2, "dim2 / dim3", "ω ≈ 0.046，周期 ≈ 135"),
            (4, "dim4 / dim5", "ω ≈ 0.0022，周期 ≈ 2916")]
    for r, (i, label, note) in enumerate(rows):
        cy, amp = 205 + r * 100, 34
        w = 1 / 10000 ** (i / 6)
        b.append(text(40, cy - 4, label, 18, INK, "start"))
        b.append(text(40, cy + 20, note, 14, GRAY, "start"))
        b.append(plain(f"M{x0} {cy}H{x1}", STROKE_SOFT, 1.5))
        for fn, color, dash in [(math.sin, SERIES[0], None), (math.cos, SERIES[1], "6 5")]:
            pts = " ".join(f"{x0 + t / 10 * sx:.1f},{cy - amp * fn(w * t / 10):.1f}"
                           for t in range(t_max * 10 + 1))
            ds = f' stroke-dasharray="{dash}"' if dash else ""
            b.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"{ds}/>')
        for t in range(8):
            b.append(f'<circle cx="{x0 + t * sx:.1f}" cy="{cy - amp * math.sin(w * t):.1f}" r="4.5" '
                     f'fill="{SERIES[0]}" stroke="#ffffff" stroke-width="1.5"/>')
    for t in range(0, t_max + 1, 4):
        b.append(text(x0 + t * sx, 474, str(t), 14, GRAY))
    b.append(text(x1, 496, "位置 t", 15, GRAY, "end"))
    return svg(1200, 520, b)


# ------------------------------------------------------------------ 09 encoder-decoder
def encoder_decoder() -> str:
    b: list[str] = []
    header(b, "Encoder-decoder：编码器读一次原文，解码器边生成边查原文",
           "以翻译“我爱猫 → I love cats”为例，解码器正在预测第 3 个词。")
    ex, dx, w = 300, 820, 340

    # encoder column
    b.append(text(ex, 132, "编码器（Encoder）", 22))
    b.append(node(ex, 150, w, 52, "源语言：我 爱 猫", fill=FILL_SOFT, stroke=STROKE_SOFT))
    b.append(arrow(f"M{ex} 202V230"))
    b.append(node(ex, 230, w, 52, "Embedding + 位置编码"))
    b.append(arrow(f"M{ex} 282V316"))
    b.append(box(ex - w / 2 - 20, 316, w + 40, 240, "none", "#9ca3af", 2, "6,4"))
    b.append(box(ex + w / 2 - 70, 326, 80, 28, "#dbeafe", BLUE, 2, rx=14))
    b.append(text(ex + w / 2 - 30, 346, "× N", 15, BLUE))
    b.append(node(ex, 366, w, 70, "双向自注意力", "每个词看整句，没有因果 mask"))
    b.append(arrow(f"M{ex} 436V464"))
    b.append(node(ex, 464, w, 70, "FFN", "逐位置加工"))
    b.append(arrow(f"M{ex} 556V590"))
    b.append(node(ex, 590, w, 70, "编码器输出 H", "[3, d]：每个源词一个向量，只算一次",
                  fill=FILL_OUT, stroke=STROKE_OUT))

    # decoder column
    b.append(text(dx, 132, "解码器（Decoder）", 22))
    b.append(node(dx, 150, w, 52, "已生成：&lt;s&gt; I love", fill=FILL_SOFT, stroke=STROKE_SOFT))
    b.append(arrow(f"M{dx} 202V230"))
    b.append(node(dx, 230, w, 52, "Embedding + 位置编码"))
    b.append(arrow(f"M{dx} 282V316"))
    b.append(box(dx - w / 2 - 20, 316, w + 40, 330, "none", "#9ca3af", 2, "6,4"))
    b.append(box(dx + w / 2 - 70, 326, 80, 28, "#dbeafe", BLUE, 2, rx=14))
    b.append(text(dx + w / 2 - 30, 346, "× N", 15, BLUE))
    b.append(node(dx, 366, w, 70, "因果自注意力", "只看已生成的部分"))
    b.append(arrow(f"M{dx} 436V460"))
    b.append(node(dx, 460, w, 70, "交叉注意力", "Q 来自解码器，K、V 来自 H", stroke=BLUE, sw=2.5))
    b.append(arrow(f"M{dx} 530V554"))
    b.append(node(dx, 554, w, 70, "FFN", "逐位置加工"))
    b.append(arrow(f"M{dx} 646V680"))
    b.append(node(dx, 680, w, 52, "LM head + softmax"))
    b.append(arrow(f"M{dx} 732V760"))
    b.append(node(dx, 760, w, 52, "下一个词：cats", fill=FILL_OUT, stroke=STROKE_OUT))

    # H feeds every decoder layer's cross-attention
    turn = dx - w / 2 - 40
    b.append(arrow(f"M{ex + w / 2} 625H{turn}V495H{dx - w / 2 - 2}", BLUE, 3))
    b.append(text(ex + w / 2 + 12, 652, "K、V", 18, BLUE, "start"))
    b.append(text(ex + w / 2 + 12, 676, "每层共用 H", 15, GRAY, "start"))

    # autoregressive loop on the right
    b.append(arrow(f"M{dx + w / 2} 786H{dx + w / 2 + 50}V176H{dx + w / 2 + 2}", "#9ca3af", 2))
    b.append(f'<text x="{dx + w / 2 + 72}" y="480" font-size="15" fill="{GRAY}" text-anchor="middle" '
             f'transform="rotate(90 {dx + w / 2 + 72} 480)">追加到已生成序列，再预测下一个</text>')
    b.append(text(40, 852, "编码器只在开始时跑一次；解码器每生成一个词跑一次，"
                  "交叉注意力的 K、V 由 H 算出，整个生成过程中都不变。", 17, GRAY, "start"))
    return svg(1200, 880, b)


FIGS = {
    "01-overview": overview,
    "02-sinusoidal-pe": sinusoidal_pe,
    "03-block": block,
    "05-ffn": ffn,
    "07-architectures": architectures,
    "08-params": params,
    "09-encoder-decoder": encoder_decoder,
}

for name, fn in FIGS.items():
    (OUT / f"{name}.svg").write_text(restyle(fn()), encoding="utf-8")
print("ok")
