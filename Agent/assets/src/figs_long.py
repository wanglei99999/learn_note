"""Figures for 08-长时任务.md.

Usage: python figs_long.py
"""
import math
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, Axes, circle, line, mono, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "long"


def relay() -> str:
    W, H = 1240, 640
    b: list[str] = []
    title(b, "多个会话之间的接力",
          "每个会话的上下文都是全新的；接力靠的是磁盘上的文件和 git 历史，不是上下文")
    # sessions
    ses = [(40, "会话 1", "初始化 agent", ["写功能清单（全部 false）", "写 init.sh、进度文件", "第一次提交"], BEIGE),
           (340, "会话 2", "工作 agent", ["读进度和 git log", "跑 init.sh + 冒烟测试", "做一项功能，测试，提交"], BLUE),
           (640, "会话 3", "工作 agent", ["同样的开场流程", "做下一项功能", "更新进度，提交"], BLUE),
           (940, "会话 N", "工作 agent", ["…", "直到清单全部为 true", ""], BLUE)]
    for x, s, role, lines_, fill in ses:
        b.append(rect(x, 116, 260, 230, fill, rx=14, sw=2.5, shadow=True))
        b.append(text(x + 130, 150, s, 18, weight=700))
        b.append(text(x + 130, 176, role, 14, MUTED))
        for j, t in enumerate(lines_):
            if t:
                b.append(text(x + 24, 216 + j * 34, "· " + t, 14, LABEL, "start"))
    for x in (300, 600, 900):
        b.append(line(x + 4, 230, x + 36, 230, LABEL, 2, arrow=True))
    b.append(text(620, 390, "每个会话开场读文件，收尾写文件；上下文不跨会话", 14, MUTED))
    # disk
    b.append(rect(40, 420, 1160, 180, TEAL, rx=14, sw=2.5))
    b.append(text(60, 452, "磁盘：所有会话共享", 16, INK, "start", weight=700))
    files = [("feature_list.json", "200+ 项，只改 passes 字段"), ("claude-progress.txt", "做了什么、做到哪里"),
             ("init.sh", "一条命令启动环境"), ("git 历史", "每项功能一次提交，可回滚")]
    for i, (f, d) in enumerate(files):
        x = 60 + i * 285
        b.append(rect(x, 474, 265, 100, WHITE, GRID, 1.5, rx=10))
        b.append(mono(x + 132, 512, f, 15, INK, weight=700))
        b.append(text(x + 132, 544, d, 13, MUTED))
    for x in (170, 470, 770, 1070):
        b.append(line(x, 348, x, 416, CLAY, 2, dash="5 4"))
        b.append(line(x + 14, 416, x + 14, 350, CLAY, 2, dash="5 4", arrow=True, clay=True))
    return svg(W, H, b)


def horizon() -> str:
    W, H = 1200, 600
    b: list[str] = []
    title(b, "METR 的任务时长指标",
          "纵轴是对数刻度：agent 有 50% 把握完成的任务，换成人类专家需要多久。示意图，只标出论文摘要里给出的一个点")
    ax = Axes(140, 120, 960, 380, (2019, 2027), (1 / 60, 60 * 40), ylog=True)
    yt = [(1 / 60, "1 秒"), (1, "1 分钟"), (10, "10 分钟"), (60, "1 小时"), (480, "8 小时"), (2400, "1 周")]
    b += ax.frame([(y, str(y)) for y in range(2019, 2028)], yt, "", "任务时长（人类所需时间）")
    # trend: 50 min at 2025.15, doubling 7 months
    t0, v0 = 2025.15, 50
    pts = [(t, v0 * 2 ** ((t - t0) * 12 / 7)) for t in [2019 + i * 0.1 for i in range(0, 81)]]
    pts = [(t, v) for t, v in pts if 1 / 60 <= v <= 2400]
    solid = [(t, v) for t, v in pts if t <= t0]
    dashed = [(t, v) for t, v in pts if t >= t0]
    b.append(ax.curve(solid, "#4f86c0", 3))
    b.append(ax.curve(dashed, "#4f86c0", 3, dash="8 6"))
    b.append(circle(ax.px(t0), ax.py(v0), 7, CLAY))
    b.append(text(ax.px(t0) + 14, ax.py(v0) + 26, "Claude 3.7 Sonnet：约 50 分钟", 14, CLAY, "start", weight=600))
    b.append(text(ax.px(2020.6), ax.py(0.07), "2019 年以来约每 7 个月翻一倍", 14, "#4f86c0", "start"))
    b.append(text(ax.px(2026.2), ax.py(500), "按同样速度外推", 13, MUTED, "end"))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-relay", relay())
    save(OUT, "02-horizon", horizon())
