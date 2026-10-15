"""Figures for 01-预训练与Scaling-Law.md.

Usage: python figs_pretrain.py
Numbers come from the cited papers: LLaMA (Touvron 2023a) Table 1, Kaplan et al. 2020
eq. 1.1/1.2, and the Chinchilla parametric loss as refit by Besiroglu et al. 2024
(the coefficients printed in Hoffmann et al. 2022 imply ~50-100 tokens/param, inconsistent
with the paper's own ~20; the refit agrees with it).
"""
import math
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, SERIES,
                          TEAL, WHITE, Axes, circle, line, mono, node, rect, save, sup10, svg,
                          text, title)

OUT = Path(__file__).resolve().parent.parent / "pretrain"


# ------------------------------------------------------------- 01 数据清洗
def funnel() -> str:
    W, H = 1200, 640
    b: list[str] = []
    title(b, "从网页到训练语料", "以 Common Crawl 为起点的典型清洗流程（宽度只表示“越筛越少”，不按比例）")
    steps = [
        ("Common Crawl 原始抓取", "几十亿个网页，HTML、导航栏、广告全在", BLUE),
        ("URL 过滤", "按黑名单去掉成人、赌博、垃圾站点", BLUE),
        ("正文抽取", "从 HTML 里抠出正文，丢掉模板和菜单", BLUE),
        ("语言识别", "fastText 分类器判断语种，按阈值保留", TEAL),
        ("质量过滤", "启发式规则 + 质量分类器：太短、重复行多、符号比例异常的去掉", TEAL),
        ("去重", "MinHash 找近似重复文档，只留一份", TEAL),
        ("训练语料", "例：FineWeb 从 96 个快照中得到约 15T token", BEIGE),
    ]
    top, rowh, maxw, minw, cx = 108, 70, 560, 220, 340
    for i, (name, note, fill) in enumerate(steps):
        w = maxw - (maxw - minw) * i / (len(steps) - 1)
        y = top + i * rowh
        b.append(rect(cx - w / 2, y, w, 50, fill, shadow=True))
        b.append(text(cx, y + 31, name, 17, weight=600))
        b.append(line(cx + w / 2 + 12, y + 25, 676, y + 25, GRID, 1.5, dash="4,4"))
        b.append(text(690, y + 31, note, 15, LABEL, "start"))
        if i < len(steps) - 1:
            b.append(line(cx, y + 50, cx, y + rowh - 2, LABEL, 2, arrow=True))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 LLaMA 数据配比
def data_mix() -> str:
    W, H = 1200, 560
    b: list[str] = []
    title(b, "LLaMA 的预训练数据配比（共 1.4T token）",
          "左：每个来源占采样的比例；右：训练过程中这份数据被重复了几遍（epoch）")
    rows = [("CommonCrawl", 67.0, 1.10, "3.3 TB"), ("C4", 15.0, 1.06, "783 GB"),
            ("GitHub", 4.5, 0.64, "328 GB"), ("Wikipedia", 4.5, 2.45, "83 GB"),
            ("Books", 4.5, 2.23, "85 GB"), ("ArXiv", 2.5, 1.06, "92 GB"),
            ("StackExchange", 2.0, 1.03, "78 GB")]
    x0, y0, rh, scale = 230, 130, 52, 6.2   # 6.2 px per %
    ex0, escale = 820, 120                 # epochs panel
    b.append(text(x0, y0 - 18, "采样比例", 14, MUTED, "start", weight=600))
    b.append(text(ex0, y0 - 18, "epoch", 14, MUTED, "start", weight=600))
    b.append(line(ex0 + escale, y0 - 6, ex0 + escale, y0 + rh * len(rows) - 10, GRID, 1.5, dash="4,4"))
    b.append(text(ex0 + escale, y0 + rh * len(rows) + 10, "1 遍", 13, MUTED))
    for i, (name, pct, ep, disk) in enumerate(rows):
        y = y0 + i * rh
        hot = ep > 2
        b.append(text(x0 - 14, y + 24, name, 15, INK, "end", weight=600))
        b.append(rect(x0, y + 4, max(pct * scale, 4), 30, BLUE, rx=6, sw=2))
        b.append(text(x0 + pct * scale + 10, y + 25, f"{pct:.1f}%  ·  {disk}", 14, LABEL, "start"))
        b.append(rect(ex0, y + 4, ep * escale, 30, CLAY_SOFT if hot else GRAY,
                      CLAY if hot else "#4a4a4a", 2, rx=6))
        b.append(text(ex0 + ep * escale + 10, y + 25, f"{ep:.2f}", 14,
                      CLAY if hot else LABEL, "start", weight=700 if hot else None))
    b.append(text(600, H - 26, "Wikipedia 和 Books 只有几十 GB，但质量高，被刻意重复了两遍多；"
                  "GitHub 不到一遍", 15, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 Kaplan 幂律
def kaplan() -> str:
    W, H = 1200, 560
    b: list[str] = []
    title(b, "Kaplan 等人（2020）：loss 随规模按幂律下降",
          "双对数坐标下是一条直线。左：数据足够时只看参数量 N；右：模型足够大时只看数据量 D")
    yt = [(v, f"{v:g}") for v in (2, 2.5, 3, 4, 5)]
    a1 = Axes(130, 120, 420, 330, (1e5, 1e10), (1.8, 5.2), True, True)
    b += a1.frame([(10 ** e, sup10(e)) for e in range(5, 11)], yt, "参数量 N（不含 embedding）", "测试 loss")
    pts = [(10 ** (5 + k / 20), (8.8e13 / 10 ** (5 + k / 20)) ** 0.076) for k in range(101)]
    b.append(a1.curve(pts, SERIES[0], 3.5))
    b.append(text(a1.x + 30, a1.y + 300, "L(N) = (8.8×10¹³ / N)^0.076", 15, SERIES[0], "start", weight=600))

    a2 = Axes(700, 120, 420, 330, (1e7, 1e11), (1.8, 5.2), True, True)
    b += a2.frame([(10 ** e, sup10(e)) for e in range(7, 12)], yt, "数据量 D（token）", "")
    pts = [(10 ** (7 + k / 25), (5.4e13 / 10 ** (7 + k / 25)) ** 0.095) for k in range(101)]
    b.append(a2.curve(pts, SERIES[1], 3.5))
    b.append(text(a2.x + 30, a2.y + 300, "L(D) = (5.4×10¹³ / D)^0.095", 15, SERIES[1], "start", weight=600))
    b.append(text(600, H - 22, "参数量每翻 10 倍，loss 乘以 10^-0.076 ≈ 0.84；曲线不会突然拐弯，所以可以用小模型的结果外推大模型",
                  14, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 IsoFLOP
E, A, B, ALPHA, BETA = 1.82, 482.01, 2085.43, 0.3478, 0.3658


def chin_loss(n: float, d: float) -> float:
    return E + A / n ** ALPHA + B / d ** BETA


def isoflop() -> str:
    W, H = 1200, 620
    b: list[str] = []
    title(b, "同样的算力，模型该多大？",
          "L(N, D) = 1.82 + 482/N^0.348 + 2085/D^0.366（Besiroglu 等 2024 重新拟合），固定 C ≈ 6ND 后扫描 N")
    ax = Axes(130, 120, 760, 400, (1e7, 1e12), (1.9, 4.2), True, False)
    b += ax.frame([(10 ** e, sup10(e)) for e in range(7, 13)],
                  [(v, f"{v:.1f}") for v in (2.0, 2.5, 3.0, 3.5, 4.0)],
                  "参数量 N", "预测 loss")
    budgets = [1e19, 1e20, 1e21, 1e22, 1e23, 1e24]
    best = []
    for i, c in enumerate(budgets):
        pts = []
        for k in range(0, 251):
            n = 10 ** (7 + k / 50)
            d = c / (6 * n)
            if d < 1e8:
                continue
            l = chin_loss(n, d)
            if l <= 4.2:
                pts.append((n, l))
        col = SERIES[i % len(SERIES)] if i < 5 else "#5c5047"
        b.append(ax.curve(pts, col, 2.8))
        nb, lb = min(pts, key=lambda p: p[1])
        best.append((nb, lb))
        b.append(circle(ax.px(nb), ax.py(lb), 6, WHITE, col, 3))
        exp = int(math.log10(c))
        b.append(text(ax.px(nb), ax.py(lb) - 14, sup10(exp), 14, col, weight=700, raw=True))
    d = "M" + " L".join(f"{ax.px(n):.1f} {ax.py(l):.1f}" for n, l in best)
    b.append(f'<path d="{d}" fill="none" stroke="{CLAY}" stroke-width="2" stroke-dasharray="6,5"/>')

    # Gopher vs Chinchilla, both ~5.8e23 FLOPs
    gop, chi = (280e9, 300e9), (70e9, 1.4e12)
    for (n, dd), name, col in [(gop, "Gopher 280B / 300B token", "#5c5047"),
                               (chi, "Chinchilla 70B / 1.4T token", CLAY)]:
        l = chin_loss(n, dd)
        b.append(f'<rect x="{ax.px(n) - 7:.1f}" y="{ax.py(l) - 7:.1f}" width="14" height="14" '
                 f'fill="{col}" transform="rotate(45 {ax.px(n):.1f} {ax.py(l):.1f})"/>')
    # side notes
    x = 930
    b.append(rect(x, 130, 230, 330, WHITE, GRID, 1.5, rx=10))
    b.append(text(x + 18, 162, "怎么读这张图", 16, INK, "start", weight=700))
    notes = ["每条 U 形曲线是一个算力", "预算（FLOPs，标在最低点", "上方）。左端模型太小，学", "不动；右端模型太大，数据", "不够喂。",
             "", "圆点是每条曲线的最低点，", "虚线把它们连起来，就是", "“算力最优”的模型大小。",
             "", "◆ 两个菱形算力相近，", "小 4 倍的 Chinchilla 反而", "loss 更低。"]
    for i, s in enumerate(notes):
        b.append(text(x + 18, 192 + i * 20, s, 14, LABEL, "start"))
    b.append(text(510, H - 22, "算力每增加 10 倍，最优参数量和最优数据量各增加约 3 倍，两者之比稳定在 20 左右",
                  14, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 05 token/参数
def tokens_per_param() -> str:
    W, H = 1200, 520
    b: list[str] = []
    title(b, "每个参数“喂”了多少 token", "对数坐标。Chinchilla 之后，大家反而越训越多")
    rows = [("GPT-3 175B", 300e9 / 175e9, "2020 · 300B token"),
            ("Gopher 280B", 300e9 / 280e9, "2021 · 300B token"),
            ("Chinchilla 70B", 1.4e12 / 70e9, "2022 · 1.4T token"),
            ("Llama 2 7B", 2e12 / 7e9, "2023 · 2T token"),
            ("Llama 3 8B", 15e12 / 8e9, "2024 · 15T token")]
    ax = Axes(260, 110, 760, 330, (0.5, 3000), (0, 5), True, False)
    for e, lab in [(1, "1"), (10, "10"), (100, "100"), (1000, "1000")]:
        px = ax.px(e)
        b.append(line(px, 110, px, 440, GRID, 1))
        b.append(text(px, 466, lab, 13, MUTED))
    for i, (name, r, note) in enumerate(rows):
        y = 124 + i * 64
        hot = name.startswith("Chinchilla")
        b.append(text(244, y + 25, name, 15, INK, "end", weight=600))
        b.append(rect(ax.px(0.5), y, ax.px(r) - ax.px(0.5), 36, CLAY_SOFT if hot else BLUE,
                      CLAY if hot else "#4a4a4a", 2, rx=6))
        b.append(text(ax.px(r) + 10, y + 24, f"{r:,.0f}" if r >= 10 else f"{r:.1f}", 15,
                      CLAY if hot else INK, "start", weight=700))
        b.append(text(ax.px(r) + 70 if r < 100 else ax.px(r) + 64, y + 24, note, 13, MUTED, "start"))
    px = ax.px(20)
    b.append(line(px, 104, px, 446, CLAY, 2, dash="6,5"))
    b.append(text(px, 98, "≈ 20：Chinchilla 算力最优", 14, CLAY, weight=600))
    b.append(text(600, H - 14, "小模型训练远超 20 倍，是拿更多训练算力换更便宜的推理", 14, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 06 base vs chat
def base_vs_chat() -> str:
    W, H = 1200, 470
    b: list[str] = []
    title(b, "同一个输入，两种模型", "示意：方框里是模型接在输入后面生成的内容")
    b.append(rect(48, 110, 1104, 56, WHITE, GRID, 1.5, rx=10))
    b.append(text(70, 145, "输入：", 16, MUTED, "start", weight=600))
    b.append(mono(130, 145, "法国的首都是哪里？", 17, INK, "start"))
    cols = [("base 模型", BLUE, ["德国的首都是哪里？", "意大利的首都是哪里？",
                                 "西班牙的首都是哪里？", "（以上每题 2 分）", ""],
             "它见过大量“题目列表”式网页，觉得接着出题最像原文"),
            ("chat 模型", TEAL, ["法国的首都是巴黎。", "", "", "", ""],
             "经过后训练，学会了“用户提问 → 助手回答”这种格式")]
    for i, (name, fill, lines_, why) in enumerate(cols):
        x = 48 + i * 568
        b.append(rect(x, 196, 536, 210, fill, shadow=True))
        b.append(text(x + 22, 230, name, 18, INK, "start", weight=700))
        for k, s in enumerate(lines_):
            if s:
                b.append(mono(x + 22, 266 + k * 26, s, 15, INK, "start"))
        b.append(text(x + 22, 392, why, 14, LABEL, "start"))
    b.append(text(600, H - 18, "知道“巴黎”这个事实的，其实是 base 模型；后训练只是教会它按问答的方式说出来",
                  14, LABEL))
    return svg(W, H, b)


if __name__ == "__main__":
    for name, fn in [("01-data-funnel", funnel), ("02-llama-data-mix", data_mix),
                     ("03-kaplan-power-law", kaplan), ("04-isoflop", isoflop),
                     ("05-tokens-per-param", tokens_per_param), ("06-base-vs-chat", base_vs_chat)]:
        save(OUT, name, fn())
    # print numbers quoted in the note
    for c in (1e21, 1e22, 1e23, 1e24):
        nb = min((10 ** (7 + k / 500) for k in range(2500)),
                 key=lambda n: chin_loss(n, c / (6 * n)))
        print(f"C={c:.0e}  N_opt={nb:.3g}  D_opt={c / 6 / nb:.3g}  tok/param={c / 6 / nb / nb:.1f}"
              f"  L={chin_loss(nb, c / 6 / nb):.3f}")
    print("Gopher L", chin_loss(280e9, 300e9), "Chinchilla L", chin_loss(70e9, 1.4e12))
