"""Figures for 04-推理模型与强化学习.md.

Usage: python figs_reasoning.py
The pass@k figure uses pass@k = 1 - (1 - p)^k on a toy set of problems; the RL model is a
"sharpened" version of the base model (illustrative, trend after Yue et al. 2025).
"""
import math
import statistics
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, SERIES,
                          TEAL, WHITE, Axes, circle, line, mono, node, path, rect, save, sup10,
                          svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "reasoning"


# ------------------------------------------------------------- 01 RLVR 循环
def rlvr_loop() -> str:
    W, H = 1200, 540
    b: list[str] = []
    title(b, "可验证奖励：让程序来判对错", "奖励不再来自学出来的奖励模型，而是来自答案比对、单元测试这类规则")
    b.append(node(48, 130, 250, 110, "题目", ["求 x² − 5x + 6 = 0", "的较大根"], GRAY))
    b.append(node(400, 130, 250, 110, "策略模型", ["采样多个完整解答", "<think>…</think> + 答案"], BLUE, stroke=CLAY, sw=3))
    b.append(node(752, 130, 400, 110, "验证器", ["数学：抽出最终答案，和标准答案比对",
                                              "代码：跑单元测试，全部通过才算对"], BEIGE))
    b.append(line(302, 185, 394, 185, LABEL, 2.5, arrow=True))
    b.append(line(654, 185, 746, 185, LABEL, 2.5, arrow=True))
    b.append(path("M952 244 V320 H525 V248", LABEL, 2.5, arrow=True))
    b.append(text(738, 310, "奖励：答对 1，答错 0（再加一点格式奖励）", 15, INK, weight=600))
    # contrast box
    b.append(rect(48, 360, 1104, 130, WHITE, GRID, 1.5, rx=12))
    b.append(text(70, 394, "和上一篇的奖励模型比", 16, INK, "start", weight=700))
    rows = [("奖励模型：", "学出来的近似，模型可以钻空子；偏好本身也说不清对错"),
            ("验证器：", "答案对就是对，没法靠写长、写得自信骗分；但只适用于能自动判对错的任务")]
    for i, (k, v) in enumerate(rows):
        b.append(text(70, 430 + i * 30, k, 15, CLAY if i else LABEL, "start", weight=700))
        b.append(text(170, 430 + i * 30, v, 15, LABEL, "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 GRPO
def grpo() -> str:
    W, H = 1200, 600
    b: list[str] = []
    title(b, "GRPO：同一道题采样一组，组内互相比较",
          "不需要价值模型：一组回答的平均分就是基线，高于平均的被鼓励，低于平均的被抑制")
    rewards = [1, 0, 0, 1, 0, 0, 0, 1]
    mu = statistics.fmean(rewards)
    sd = statistics.pstdev(rewards)
    adv = [(r - mu) / sd for r in rewards]
    b.append(node(48, 130, 200, 90, "同一道题", ["采样 G = 8 次"], GRAY))
    x0, cw = 300, 100
    zero_y, scale = 430, 70
    b.append(text(x0 - 12, 300, "优势", 15, MUTED, "end", weight=700))
    b.append(line(x0 - 6, zero_y, x0 + 8 * cw, zero_y, LABEL, 1.5))
    b.append(text(x0 - 12, zero_y + 5, "0", 13, MUTED, "end"))
    for i, (r, a) in enumerate(zip(rewards, adv)):
        cx = x0 + i * cw + cw / 2
        ok = r == 1
        b.append(rect(cx - 40, 132, 80, 52, TEAL if ok else CLAY_SOFT, rx=8, sw=2))
        b.append(text(cx, 156, f"回答 {i + 1}", 13, LABEL))
        b.append(text(cx, 176, "✓ 1" if ok else "✗ 0", 15, INK, weight=700))
        h = a * scale
        y = zero_y - h if h > 0 else zero_y
        b.append(rect(cx - 26, y, 52, abs(h), TEAL if ok else CLAY_SOFT, "#4a4a4a", 1.8, rx=4))
        ty = zero_y - h - 10 if h > 0 else zero_y - h + 22
        b.append(text(cx, ty, f"{a:+.2f}", 14, INK, weight=700))
    b.append(line(250, 175, 296, 160, LABEL, 2, arrow=True))
    # calc
    b.append(rect(48, 260, 200, 230, WHITE, GRID, 1.5, rx=12))
    b.append(text(66, 292, "手算", 15, INK, "start", weight=700))
    for i, s in enumerate([f"均值 μ = {mu:.3f}", f"标准差 σ = {sd:.3f}", "", "答对：", f"(1 − {mu:.3f}) / {sd:.3f}",
                           f"= {adv[0]:+.2f}", "答错：", f"(0 − {mu:.3f}) / {sd:.3f}", f"= {adv[1]:+.2f}"]):
        b.append(text(66, 320 + i * 19, s, 13, LABEL, "start"))
    b.append(text(600, H - 46, "优势 Âᵢ = (rᵢ − mean(r)) / std(r)，这一组回答里的每个 token 都用同一个优势值", 15, INK, weight=600))
    b.append(text(600, H - 18, "如果 8 个全对或全错，所有优势都是 0，这道题提供不了任何梯度", 14, CLAY))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 R1 流程
def r1_pipeline() -> str:
    W, H = 1200, 600
    b: list[str] = []
    title(b, "DeepSeek-R1 的两条路线", "R1-Zero 证明了“只用 RL 也能学会长推理”；R1 补上了可读性和通用能力")
    b.append(text(48, 136, "R1-Zero", 17, INK, "start", weight=700))
    b.append(node(48, 152, 240, 76, "DeepSeek-V3-Base", ["没有任何 SFT"], GRAY))
    b.append(line(292, 190, 352, 190, LABEL, 2.5, arrow=True))
    b.append(node(356, 152, 300, 76, "GRPO + 规则奖励", ["准确率奖励 + 格式奖励"], BLUE, stroke=CLAY, sw=3))
    b.append(line(660, 190, 720, 190, LABEL, 2.5, arrow=True))
    b.append(node(724, 152, 428, 76, "AIME 2024：15.6% → 71.0%", ["但语言混杂、可读性差"], TEAL))

    b.append(text(48, 290, "R1", 17, INK, "start", weight=700))
    steps = [("① 冷启动 SFT", ["数千条长 CoT", "可读格式"], TEAL),
             ("② 推理 RL", ["GRPO", "+ 语言一致性奖励"], BLUE),
             ("③ 拒绝采样 + SFT", ["约 60 万推理样本", "约 20 万通用样本"], TEAL),
             ("④ 全场景 RL", ["推理：规则奖励", "通用：奖励模型"], BLUE)]
    for i, (name, lines_, fill) in enumerate(steps):
        x = 48 + i * 282
        b.append(node(x, 306, 250, 100, name, lines_, fill))
        if i < 3:
            b.append(line(x + 254, 356, x + 278, 356, LABEL, 2.5, arrow=True))
    b.append(text(48 + 2 * 282 + 137, 434, "③ 从 V3-Base 重新训练", 13, MUTED, "start"))
    # distill
    b.append(path("M738 410 V470 H340 V500", LABEL, 2, dash="6,5", arrow=True))
    b.append(node(110, 504, 460, 70, "蒸馏到小模型", ["用 ③ 的约 80 万条数据，直接 SFT Qwen2.5 / Llama"], BEIGE))
    b.append(text(600, 530, "R1-Distill-Qwen-32B 的 AIME 2024 达到 72.6%，", 14, LABEL, "start"))
    b.append(text(600, 554, "比在同一个小模型上直接做 RL 好得多", 14, LABEL, "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 pass@k
def passk() -> str:
    W, H = 1200, 600
    b: list[str] = []
    title(b, "pass@k：采样 k 次，至少对一次的概率",
          "左：单道题，pass@k = 1 − (1 − p)^k。右：一组题上 RL 模型与 base 模型的对比（玩具模型数值计算）")
    ks = [2 ** (e / 4) for e in range(0, 33)]
    ax = Axes(110, 120, 440, 340, (1, 256), (0, 1), True, False)
    b += ax.frame([(2 ** e, str(2 ** e)) for e in range(0, 9, 2)], [(v, f"{v:.0%}") for v in (0, .25, .5, .75, 1)],
                  "采样次数 k", "pass@k")
    for i, p in enumerate([0.01, 0.05, 0.2, 0.5]):
        col = SERIES[[1, 2, 3, 0][i]]
        b.append(ax.curve([(k, 1 - (1 - p) ** k) for k in ks], col, 3))
        k50 = math.log(0.5) / math.log(1 - p)
        b.append(text(ax.px(max(k50, 1)) + 8, ax.py(0.5) + 4, f"p = {p}", 13, col, "start", weight=700))
    # toy model: 40 problems with base solve-rate p_i; RL sharpens solvable ones, drops rare ones
    base = [10 ** (-3 + 3 * i / 39) for i in range(40)]
    rl = [p ** 0.35 if p > 0.03 else p * 0.15 for p in base]

    def mean_pass(ps: list[float], k: float) -> float:
        return sum(1 - (1 - p) ** k for p in ps) / len(ps)

    ax2 = Axes(700, 120, 440, 340, (1, 256), (0, 1), True, False)
    b += ax2.frame([(2 ** e, str(2 ** e)) for e in range(0, 9, 2)], [(v, f"{v:.0%}") for v in (0, .25, .5, .75, 1)],
                   "采样次数 k", "")
    b.append(ax2.curve([(k, mean_pass(base, k)) for k in ks], SERIES[1], 3.5))
    b.append(ax2.curve([(k, mean_pass(rl, k)) for k in ks], CLAY, 3.5))
    b.append(text(ax2.px(1.3), ax2.py(mean_pass(rl, 1)) - 34, "RL 后", 15, CLAY, "start", weight=700))
    b.append(text(ax2.px(1.3), ax2.py(mean_pass(base, 1)) + 24, "base", 15, SERIES[1], "start", weight=700))
    cross = next(k for k in ks if mean_pass(base, k) > mean_pass(rl, k))
    b.append(line(ax2.px(cross), 120, ax2.px(cross), 460, MUTED, 1.5, dash="5,4"))
    b.append(text(ax2.px(cross) + 6, 140, "交叉点", 13, MUTED, "start"))
    b.append(text(600, H - 46, "RL 把“偶尔能做对”的题变成“大多数时候能做对”，pass@1 大涨；", 14, LABEL))
    b.append(text(600, H - 22, "但如果它同时丢掉了 base 模型偶尔能蒙对的冷门解法，k 很大时反而会被 base 追上", 14, LABEL))
    return svg(W, H, b)


if __name__ == "__main__":
    for name, fn in [("01-rlvr-loop", rlvr_loop), ("02-grpo-group", grpo),
                     ("03-r1-pipeline", r1_pipeline), ("04-pass-at-k", passk)]:
        save(OUT, name, fn())
