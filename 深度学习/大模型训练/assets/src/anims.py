"""Animated GIFs for the 大模型训练 series, same Claude-style palette as the static figures.

Usage: python anims.py [isoflop|lossmask|beta|grpo ...]   (no args = all)
Contact sheets for checking go to the directory in $SHEET_DIR (default: assets/src/_sheets).
"""
import math
import os
import statistics
import sys
from pathlib import Path

from anim import contact_sheet, make_gif
from claude_style import (BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, SERIES, TEAL,
                          WHITE, Axes, circle, line, mono, node, rect, sup10, svg, text, title)
from figs_pretrain import chin_loss
from figs_rlhf import gauss, reward, tilt
from figs_sft import ASSIST_FROM, SPECIAL, TOKENS

ASSETS = Path(__file__).resolve().parent.parent
SHEETS = Path(os.environ.get("SHEET_DIR", Path(__file__).resolve().parent / "_sheets"))


# ================================================================ IsoFLOP
BUDGETS = [1e19, 1e20, 1e21, 1e22, 1e23, 1e24]
COLS = SERIES + ["#5c5047"]


def _iso_curve(c: float) -> list[tuple[float, float]]:
    pts = []
    for k in range(251):
        n = 10 ** (7 + k / 50)
        d = c / (6 * n)
        if d >= 1e8 and chin_loss(n, d) <= 4.2:
            pts.append((n, chin_loss(n, d)))
    return pts


def _fmt(v: float) -> str:
    for unit, s in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if v >= unit:
            return f"{v / unit:.3g}{s}"
    return f"{v:.3g}"


def iso_frame(done: int, frac: float, show_opt: bool, show_dia: bool) -> str:
    W, H = 1200, 620
    b: list[str] = []
    title(b, "同样的算力，模型该多大？", "每条 U 形曲线是一个算力预算；最低点就是这份算力下最好的模型大小")
    ax = Axes(130, 120, 760, 400, (1e7, 1e12), (1.9, 4.2), True, False)
    b += ax.frame([(10 ** e, sup10(e)) for e in range(7, 13)],
                  [(v, f"{v:.1f}") for v in (2.0, 2.5, 3.0, 3.5, 4.0)], "参数量 N", "预测 loss")
    best = []
    cur = None
    for i, c in enumerate(BUDGETS):
        if i > done:
            break
        pts = _iso_curve(c)
        nb, lb = min(pts, key=lambda p: p[1])
        col = COLS[i]
        if i < done:
            b.append(ax.curve(pts, col, 2.8))
            b.append(circle(ax.px(nb), ax.py(lb), 6, WHITE, col, 3))
            b.append(text(ax.px(nb), ax.py(lb) - 14, sup10(int(math.log10(c))), 14, col, weight=700, raw=True))
            best.append((nb, lb))
        else:
            n_show = max(2, int(len(pts) * frac))
            b.append(ax.curve(pts[:n_show], col, 3.4))
            cur = (c, nb, lb, col)
            if frac >= 1:
                b.append(circle(ax.px(nb), ax.py(lb), 7, WHITE, col, 3.5))
                b.append(text(ax.px(nb), ax.py(lb) - 14, sup10(int(math.log10(c))), 14, col, weight=700, raw=True))
                best.append((nb, lb))
    if show_opt and len(best) > 1:
        d = "M" + " L".join(f"{ax.px(n):.1f} {ax.py(l):.1f}" for n, l in best)
        b.append(f'<path d="{d}" fill="none" stroke="{CLAY}" stroke-width="2.5" stroke-dasharray="6,5"/>')
    if show_dia:
        for (n, dd), col in [((280e9, 300e9), "#5c5047"), ((70e9, 1.4e12), CLAY)]:
            l = chin_loss(n, dd)
            b.append(f'<rect x="{ax.px(n) - 8:.1f}" y="{ax.py(l) - 8:.1f}" width="16" height="16" fill="{col}" '
                     f'transform="rotate(45 {ax.px(n):.1f} {ax.py(l):.1f})"/>')
    # readout
    x = 930
    b.append(rect(x, 130, 230, 330, WHITE, GRID, 1.5, rx=12))
    if show_dia:
        lines_ = [("算力相近的两个模型", INK, 700), ("", None, None),
                  ("◆ Gopher", "#5c5047", 700), ("280B 参数 · 300B token", LABEL, None),
                  ("loss ≈ 2.002", LABEL, None), ("", None, None),
                  ("◆ Chinchilla", CLAY, 700), ("70B 参数 · 1.4T token", LABEL, None),
                  ("loss ≈ 1.977", LABEL, None), ("", None, None),
                  ("小 4 倍，loss 反而更低", CLAY, 700)]
    elif show_opt:
        lines_ = [("把最低点连起来", INK, 700), ("", None, None), ("算力 × 10", LABEL, None),
                  ("最优 N 约 × 3", CLAY, 700), ("最优 D 约 × 3", CLAY, 700), ("", None, None),
                  ("D / N 稳定在 20 左右", LABEL, None)]
    elif cur:
        c, nb, lb, col = cur
        e = int(math.log10(c))
        lines_ = [(f"算力 C = 1e{e} FLOPs", col, 700), ("", None, None)]
        if frac >= 1:
            dopt = c / 6 / nb
            lines_ += [("最低点：", INK, 700), (f"N ≈ {_fmt(nb)} 参数", LABEL, None),
                       (f"D ≈ {_fmt(dopt)} token", LABEL, None), (f"D / N ≈ {dopt / nb:.0f}", LABEL, None),
                       (f"loss ≈ {lb:.3f}", LABEL, None)]
        else:
            lines_ += [("固定算力，扫描 N：", LABEL, None), ("N 变大，D = C / 6N 变小", LABEL, None)]
    else:
        lines_ = []
    for i, (s, col, wt) in enumerate(lines_):
        if s:
            b.append(text(x + 18, 164 + i * 26, s, 15, col, "start", weight=wt))
    b.append(text(510, H - 22, "按 Besiroglu 等 2024 重新拟合的 Chinchilla 公式计算", 13, MUTED))
    return svg(W, H, b)


def anim_isoflop() -> None:
    frames, durs = [], []
    for i in range(len(BUDGETS)):
        for f in (0.2, 0.4, 0.6, 0.8):
            frames.append(iso_frame(i, f, False, False))
            durs.append(70)
        frames.append(iso_frame(i, 1.0, False, False))
        durs.append(1300)
    frames.append(iso_frame(len(BUDGETS), 1.0, True, False))
    durs.append(2200)
    frames.append(iso_frame(len(BUDGETS), 1.0, True, True))
    durs.append(3500)
    dst = ASSETS / "pretrain" / "04-isoflop.gif"
    make_gif(frames, durs, dst)
    contact_sheet(dst, SHEETS / "isoflop.png")


# ================================================================ loss mask
PROBS = {ASSIST_FROM - 1: 0.60, ASSIST_FROM: 0.90, ASSIST_FROM + 1: 0.80, ASSIST_FROM + 2: 0.50}


def mask_frame(step: int) -> str:
    """step = index of the input position currently being processed (0..n-2); n-1 = final."""
    W, H = 1200, 560
    b: list[str] = []
    title(b, "逐个位置看：哪些位置算 loss", "位置 t 预测第 t+1 个 token；目标落在 prompt 里就跳过（标签 -100）")
    n = len(TOKENS)
    x0 = 48
    widths = [64 + (34 if len(t) > 6 else 0) for t in TOKENS]
    total = sum(widths) + 5 * (n - 1)
    sc = (1152 - x0) / total
    xs, x = [], x0
    for w in widths:
        xs.append(x)
        x += (w + 5) * sc
    widths = [w * sc for w in widths]
    final = step >= n - 1
    b.append(text(x0, 128, "输入", 15, MUTED, "start", weight=700))
    b.append(text(x0, 258, "预测目标", 15, MUTED, "start", weight=700))
    for i, t in enumerate(TOKENS):
        fill = TEAL if i >= ASSIST_FROM else (SPECIAL if t.startswith("<|") else GRAY)
        cur = i == step and not final
        b.append(rect(xs[i], 140, widths[i], 46, fill, CLAY if cur else "#4a4a4a", 3.5 if cur else 1.6, rx=6))
        size = (12 if widths[i] > 80 else 10) if len(t) > 6 else 15
        b.append(mono(xs[i] + widths[i] / 2, 169, t, size, CLAY if t.startswith("<|") else INK,
                      weight=700 if t.startswith("<|") else None))
        if i < n - 1 and (i <= step or final):
            hot = i + 1 >= ASSIST_FROM
            lab = TOKENS[i + 1] if hot else "-100"
            b.append(rect(xs[i], 270, widths[i], 46, CLAY_SOFT if hot else WHITE, "#4a4a4a", 1.6, rx=6))
            sz = (12 if widths[i] > 80 else 10) if len(lab) > 6 else 15
            b.append(mono(xs[i] + widths[i] / 2, 299, lab, sz, CLAY if hot else MUTED, weight=700))
    if 0 <= step and not final:
        cx = xs[step] + widths[step] / 2
        b.append(line(cx, 190, cx, 264, CLAY, 2.5, arrow=True, clay=True))
    # running sum
    done = [i for i in PROBS if i <= step or final]
    b.append(rect(48, 350, 1104, 150, WHITE, GRID, 1.5, rx=12))
    if step < 0:
        b.append(text(72, 386, "从第 1 个位置开始，逐个看它的预测目标", 16, MUTED, "start", weight=700))
    elif not final:
        hot = step + 1 >= ASSIST_FROM
        tgt = TOKENS[step + 1]
        if hot:
            p = PROBS[step]
            msg = f"第 {step + 1} 个位置：目标是 {tgt}，模型给它的概率 p = {p:.2f}，−log p = {-math.log(p):.3f}"
            b.append(text(72, 386, msg, 16, CLAY, "start", weight=700))
        else:
            b.append(text(72, 386, f"第 {step + 1} 个位置：目标是 {tgt}，属于 prompt，跳过", 16, MUTED, "start", weight=700))
    terms = [f"{-math.log(PROBS[i]):.3f}" for i in sorted(done)]
    s = " + ".join(terms) if terms else "（还没有计入任何位置）"
    b.append(text(72, 426, f"已计入 {len(terms)} 个位置：{s}", 15, INK, "start"))
    if final:
        tot = sum(-math.log(PROBS[i]) for i in PROBS)
        b.append(text(72, 386, "扫描结束：15 个预测位置里只有 4 个算 loss", 16, CLAY, "start", weight=700))
        b.append(text(72, 466, f"loss = {tot:.3f} / 4 ≈ {tot / 4:.3f}", 18, CLAY, "start", weight=700))
    b.append(text(600, H - 22, "最后一个目标是结束符 <|im_end|>：模型要学会说完就停", 14, LABEL))
    return svg(W, H, b)


def anim_lossmask() -> None:
    n = len(TOKENS)
    frames, durs = [mask_frame(-1)], [900]
    for s in range(n - 1):
        frames.append(mask_frame(s))
        durs.append(1500 if s + 1 >= ASSIST_FROM else 380)
    frames.append(mask_frame(n - 1))
    durs.append(3500)
    dst = ASSETS / "sft" / "02-loss-mask.gif"
    make_gif(frames, durs, dst)
    contact_sheet(dst, SHEETS / "lossmask.png")


# ================================================================ β sweep
XS = [-3 + k * 0.01 for k in range(701)]
REF = [gauss(x, 0, 1) for x in XS]


def beta_frame(beta: float) -> str:
    W, H = 1200, 640
    b: list[str] = []
    title(b, "把 β 慢慢调小", "π*(y) ∝ π_ref(y) · exp(r(y)/β)：β 越小，模型越敢离开 SFT 模型去追高分")
    ax = Axes(130, 120, 700, 150, (-3, 4), (0, 2.5))
    b += ax.frame([(v, str(v)) for v in range(-3, 5)], [(v, str(v)) for v in (0, 1, 2)], "", "奖励 r(y)")
    b.append(ax.curve([(x, reward(x)) for x in XS], "#8c7c6e", 3))
    b.append(text(ax.px(1.0), ax.py(1.2) - 10, "真正更好的回答", 13, LABEL))
    b.append(text(ax.px(3.2) - 10, ax.py(2.2) + 4, "奖励模型的漏洞", 13, CLAY, "end", weight=700))
    p = tilt(beta, XS)
    ymax = 2.4
    ax2 = Axes(130, 330, 700, 220, (-3, 4), (0, ymax))
    b += ax2.frame([(v, str(v)) for v in range(-3, 5)], [(v, f"{v:.1f}") for v in (0, 0.8, 1.6, 2.4)],
                   "回答空间 y（示意）", "概率密度")
    b.append(ax2.curve(list(zip(XS, REF)), "#8c7c6e", 2.5, dash="6,5"))
    b.append(ax2.curve([(x, min(v, ymax)) for x, v in zip(XS, p)], CLAY, 3.4))
    peak = max(p)
    if peak > ymax:
        b.append(text(ax2.px(3.2) - 12, ax2.py(ymax) + 18, f"截顶，峰值约 {peak:.1f}", 12, CLAY, "end", weight=700))
    mass = sum(v for x, v in zip(XS, p) if x > 2.8) * 0.01
    kl = sum(v * math.log(v / r) for v, r in zip(p, REF) if v > 1e-12) * 0.01
    # readout
    x = 870
    b.append(rect(x, 120, 282, 430, WHITE, GRID, 1.5, rx=12))
    b.append(text(x + 20, 162, f"β = {beta:.2f}", 26, CLAY, "start", weight=700))
    # slider
    sx0, sx1 = x + 20, x + 262
    b.append(line(sx0, 192, sx1, 192, GRID, 6))
    t = (math.log(2.0) - math.log(beta)) / (math.log(2.0) - math.log(0.12))
    b.append(circle(sx0 + t * (sx1 - sx0), 192, 9, CLAY, CLAY, 2))
    b.append(text(sx0, 216, "2.0", 12, MUTED, "start"))
    b.append(text(sx1, 216, "0.12", 12, MUTED, "end"))
    b.append(text(x + 20, 262, "落在漏洞区（y > 2.8）", 15, INK, "start", weight=700))
    b.append(text(x + 20, 296, f"{mass * 100:.1f}%", 26, CLAY if mass > 0.05 else INK, "start", weight=700))
    b.append(text(x + 20, 320, f"SFT 模型只有 0.25%", 13, MUTED, "start"))
    b.append(text(x + 20, 364, "离 SFT 模型的距离", 15, INK, "start", weight=700))
    b.append(text(x + 20, 396, f"KL ≈ {kl:.2f}", 22, INK, "start", weight=700))
    b.append(line(x + 20, 412, x + 20 + min(kl / 2.5, 1) * 242, 412, CLAY, 6))
    b.append(text(x + 20, 456, "虚线：π_ref（SFT 模型）", 13, LABEL, "start"))
    b.append(text(x + 20, 478, "实线：当前 β 下的最优策略", 13, CLAY, "start"))
    b.append(text(x + 20, 520, "数值按公式计算，非示意", 12, MUTED, "start"))
    b.append(text(480, H - 18, "β 大：几乎不动；β 适中：往真正好的回答集中；β 太小：开始钻漏洞", 14, LABEL))
    return svg(W, H, b)


def anim_beta() -> None:
    n = 40
    betas = [math.exp(math.log(2.0) + (math.log(0.12) - math.log(2.0)) * k / (n - 1)) for k in range(n)]
    frames = [beta_frame(bt) for bt in betas]
    durs = [1200] + [110] * (n - 2) + [3500]
    dst = ASSETS / "rlhf" / "04-kl-tilt.gif"
    make_gif(frames, durs, dst)
    contact_sheet(dst, SHEETS / "beta.png")
    print("peak density at beta=0.12:", max(tilt(0.12, XS)))


# ================================================================ GRPO
REW = [1, 0, 0, 1, 0, 0, 0, 1]


def grpo_frame(shown: int, stats: int, grow: float) -> str:
    """shown: answers revealed (0-8); stats: 0 none, 1 mean, 2 mean+std; grow: 0..1 advantage bars."""
    W, H = 1200, 600
    b: list[str] = []
    title(b, "GRPO 的一轮", "同一道题采样 8 次 → 程序判对错 → 组内均值和标准差 → 每个回答的优势")
    mu = statistics.fmean(REW)
    sd = statistics.pstdev(REW)
    adv = [(r - mu) / sd for r in REW]
    b.append(node(48, 124, 200, 76, "同一道题", ["采样 G = 8 次"], GRAY))
    x0, cw, zero_y, scale = 300, 100, 440, 70
    for i in range(8):
        cx = x0 + i * cw + cw / 2
        if i < shown:
            ok = REW[i] == 1
            b.append(rect(cx - 40, 126, 80, 52, TEAL if ok else CLAY_SOFT, rx=8, sw=2))
            b.append(text(cx, 150, f"回答 {i + 1}", 13, LABEL))
            b.append(text(cx, 170, "✓ 1" if ok else "✗ 0", 15, INK, weight=700))
        else:
            b.append(rect(cx - 40, 126, 80, 52, "#f1eee9", "#c9c3ba", 1.5, rx=8, dash="4,4"))
    if shown:
        b.append(line(252, 162, 296, 152, LABEL, 2, arrow=True))
    # stats box
    b.append(rect(48, 230, 200, 260, WHITE, GRID, 1.5, rx=12))
    b.append(text(66, 262, "组内统计", 15, INK, "start", weight=700))
    rows = []
    if stats >= 1:
        rows += [f"答对 {sum(REW)} 个，答错 {8 - sum(REW)} 个", f"均值 μ = 3/8 = {mu:.3f}"]
    if stats >= 2:
        rows += [f"标准差 σ = {sd:.3f}", "", "Â = (r − μ) / σ", f"答对：{adv[0]:+.2f}", f"答错：{adv[1]:+.2f}"]
    for i, s in enumerate(rows):
        b.append(text(66, 292 + i * 26, s, 14, CLAY if s.startswith("答对：") or s.startswith("答错：") else LABEL,
                      "start", weight=700 if "：" in s and s[:2] in ("答对", "答错") and "个" not in s else None))
    # zero line, mean marker
    if stats >= 1:
        b.append(text(x0 - 12, 250, "优势", 15, MUTED, "end", weight=700))
        b.append(line(x0 - 6, zero_y, x0 + 8 * cw, zero_y, LABEL, 1.5))
        b.append(text(x0 - 12, zero_y + 5, "0", 13, MUTED, "end"))
    for i, (r, a) in enumerate(zip(REW, adv)):
        if grow <= 0:
            break
        cx = x0 + i * cw + cw / 2
        h = a * scale * grow
        y = zero_y - h if h > 0 else zero_y
        b.append(rect(cx - 26, y, 52, max(abs(h), 1), TEAL if r else CLAY_SOFT, "#4a4a4a", 1.8, rx=4))
        if grow >= 1:
            ty = zero_y - h - 10 if h > 0 else zero_y - h + 22
            b.append(text(cx, ty, f"{a:+.2f}", 14, INK, weight=700))
    if grow >= 1:
        b.append(text(600, H - 46, "高于平均的回答，每个 token 的概率往上推；低于平均的往下压", 15, INK, weight=600))
        b.append(text(600, H - 18, "8 个全对或全错时 σ = 0、优势全为 0，这道题没有梯度", 14, CLAY))
    return svg(W, H, b)


def anim_grpo() -> None:
    frames, durs = [grpo_frame(0, 0, 0)], [800]
    for s in range(1, 9):
        frames.append(grpo_frame(s, 0, 0))
        durs.append(350)
    frames.append(grpo_frame(8, 1, 0))
    durs.append(1600)
    frames.append(grpo_frame(8, 2, 0))
    durs.append(1600)
    for g in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9):
        frames.append(grpo_frame(8, 2, g))
        durs.append(70)
    frames.append(grpo_frame(8, 2, 1.0))
    durs.append(4000)
    dst = ASSETS / "reasoning" / "02-grpo-group.gif"
    make_gif(frames, durs, dst)
    contact_sheet(dst, SHEETS / "grpo.png")


if __name__ == "__main__":
    todo = sys.argv[1:] or ["isoflop", "lossmask", "beta", "grpo"]
    fns = {"isoflop": anim_isoflop, "lossmask": anim_lossmask, "beta": anim_beta, "grpo": anim_grpo}
    SHEETS.mkdir(parents=True, exist_ok=True)
    for name in todo:
        fns[name]()
