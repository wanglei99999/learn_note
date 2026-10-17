"""Figures for 12-评估.md.

Usage: python figs_eval.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, SERIES, TEAL,
                          WHITE, Axes, circle, line, mono, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "eval"


def anatomy() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "一次 agent 评估由哪些部分组成", "同一个任务跑多次（trial），每次留下完整的运行记录（transcript）和环境的最终状态（outcome），再由评分器打分")
    b.append(node(40, 200, 200, 130, "任务 task", ["输入 + 成功标准", "+ 参考解"], fill=GRAY))
    for i in range(3):
        y = 130 + i * 120
        b.append(rect(320, y, 400, 100, BLUE, rx=12, sw=2, shadow=True))
        b.append(text(340, y + 30, f"trial {i + 1}：模型 + harness 在干净的环境里跑一遍", 14, INK, "start", weight=600))
        b.append(rect(340, y + 46, 170, 40, WHITE, GRID, 1.5, rx=8))
        b.append(text(425, y + 72, "transcript", 13, LABEL))
        b.append(rect(530, y + 46, 170, 40, TEAL, GRID, 1.5, rx=8))
        b.append(text(615, y + 72, "outcome", 13, LABEL))
        b.append(line(242, 265, 316, y + 50, LABEL, 1.8, arrow=True))
        b.append(line(722, y + 50, 796, 265, LABEL, 1.8, arrow=True))
    b.append(node(800, 170, 200, 190, "评分器 grader", ["代码：测试、比对", "模型：按评分标准打分", "人：抽查、校准"], fill=BEIGE))
    b.append(line(1002, 265, 1050, 265, LABEL, 2, arrow=True))
    b.append(node(1054, 205, 160, 120, "指标", ["通过率", "pass@k / pass^k"], fill=GRAY))
    b.append(text(620, 520, "评估“agent”，评的是模型和 harness 的组合，换掉任何一个，结果都可能变", 15, CLAY, weight=600))
    return svg(W, H, b)


def passk() -> str:
    W, H = 1200, 600
    b: list[str] = []
    title(b, "pass@k 与 pass^k", "单次成功率 p = 0.75。k 次里至少成功一次的概率越来越高，k 次全部成功的概率越来越低")
    ax = Axes(130, 120, 960, 380, (1, 10), (0, 1))
    b += ax.frame([(k, str(k)) for k in range(1, 11)], [(v / 10, f"{v * 10}%") for v in range(0, 11, 2)],
                  "尝试次数 k", "概率")
    p = 0.75
    at = [(k, 1 - (1 - p) ** k) for k in range(1, 11)]
    all_ = [(k, p ** k) for k in range(1, 11)]
    b.append(ax.curve(at, SERIES[1], 3))
    b.append(ax.curve(all_, SERIES[0], 3))
    for k, v in at:
        b.append(circle(ax.px(k), ax.py(v), 5, SERIES[1], SERIES[1], 1))
    for k, v in all_:
        b.append(circle(ax.px(k), ax.py(v), 5, SERIES[0], SERIES[0], 1))
    b.append(text(ax.px(6), ax.py(0.90), "pass@k：至少成功一次", 15, SERIES[1], "start", weight=600))
    b.append(text(ax.px(5.6), ax.py(0.32), "pass^k：每次都成功", 15, SERIES[0], "start", weight=600))
    b.append(text(ax.px(3) + 10, ax.py(p ** 3) - 12, "0.75³ ≈ 42%", 14, SERIES[0], "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 需要多少个任务
def sample_size() -> str:
    W, H = 1220, 640
    b: list[str] = []
    title(b, "要看出一次改动的效果，需要多少个任务（示意）",
          "显著性 0.05、检出把握 80%；独立比较以 50% 为基线，成对比较假设每次改动让 2% 的任务变差")
    ax = Axes(150, 130, 860, 400, (0.03, 0.3), (10, 5000), xlog=True, ylog=True)
    b += ax.frame([(0.03, "3"), (0.05, "5"), (0.1, "10"), (0.2, "20"), (0.3, "30")],
                  [(10, "10"), (50, "50"), (100, "100"), (500, "500"), (1000, "1,000"), (5000, "5,000")],
                  "改动带来的成功率提升（百分点，对数刻度）", "需要的任务数（对数刻度）")
    z2 = (1.96 + 0.8416) ** 2
    un, pa = [], []
    d = 0.03
    while d <= 0.3001:
        p1, p2 = 0.5, min(0.5 + d, 0.999)
        un.append((d, min(5000, z2 * (p1 * (1 - p1) + p2 * (1 - p2)) / d ** 2)))
        p10, p01 = 0.02, 0.02 + d
        pa.append((d, max(10, min(5000, z2 * (p01 + p10) / d ** 2))))
        d *= 1.03
    b.append(ax.curve(un, CLAY, 3))
    b.append(ax.curve(pa, "#4f86c0", 3))
    b.append(line(1030, 200, 1070, 200, CLAY, 3))
    b.append(text(1080, 205, "独立比较", 14, CLAY, "start", weight=700))
    b.append(line(1030, 232, 1070, 232, "#4f86c0", 3))
    b.append(text(1080, 237, "成对比较", 14, "#4f86c0", "start", weight=700))
    b.append(line(ax.px(0.05), ax.py(10), ax.px(0.05), ax.py(5000), LABEL, 1.2, dash="4 4"))
    b.append(mono(ax.px(0.05) + 8, ax.py(1560) - 8, "≈1,560", 13, CLAY, "start", weight=700))
    b.append(mono(ax.px(0.05) + 8, ax.py(280) + 20, "≈280", 13, "#4f86c0", "start", weight=700))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-anatomy", anatomy())
    save(OUT, "02-passk", passk())
    save(OUT, "03-sample-size", sample_size())
