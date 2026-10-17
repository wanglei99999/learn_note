"""Figures for 09-子agent与多agent.md.

Usage: python figs_multi.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "multi"


def subagent() -> str:
    W, H = 1240, 650
    b: list[str] = []
    title(b, "子 agent：脏活在别的上下文里干，只把结论带回来",
          "子 agent 可能读了几万 token 的材料，交回主 agent 的通常只有一两千 token 的摘要")
    # main agent context
    b.append(rect(40, 116, 360, 490, WHITE, GRID, 1.5, rx=14))
    b.append(text(60, 148, "主 agent 的上下文", 16, MUTED, "start", weight=700))
    rows = [("任务、计划", GRAY, 60), ("委派：找出鉴权相关代码", BEIGE, 50), ("摘要（约 1,500 token）", TEAL, 60),
            ("委派：查 OAuth 库的用法", BEIGE, 50), ("摘要", TEAL, 60), ("自己写代码、跑测试 …", BLUE, 90)]
    y = 166
    for t, fill, h in rows:
        b.append(rect(60, y, 320, h, fill, rx=8, sw=1.5, stroke=CLAY if fill == TEAL else "#4a4a4a"))
        b.append(text(220, y + h / 2 + 5, t, 14))
        y += h + 10
    # subagents
    for i, (yy, t, sub) in enumerate([(150, "子 agent A", "grep、读 14 个文件，约 4 万 token"),
                                      (370, "子 agent B", "搜文档、读 6 个网页，约 3 万 token")]):
        b.append(rect(620, yy, 560, 170, "#f3efe9", GRID, 1.5, rx=14))
        b.append(text(640, yy + 32, t + " 的上下文（独立、全新）", 15, MUTED, "start", weight=700))
        for j in range(5):
            b.append(rect(640 + j * 104, yy + 52, 92, 56, BLUE, rx=6, sw=1.2))
        b.append(text(900, yy + 140, sub, 14, LABEL))
    b.append(path("M 382 261 C 500 261, 500 210, 616 210", LABEL, 2, arrow=True))
    b.append(path("M 616 290 C 500 290, 500 326, 384 326", CLAY, 2.5, arrow=True, clay=True))
    b.append(path("M 382 391 C 500 391, 500 430, 616 430", LABEL, 2, arrow=True))
    b.append(path("M 616 506 C 500 506, 500 456, 384 456", CLAY, 2.5, arrow=True, clay=True))
    b.append(text(900, 630, "灰线：任务描述　橙线：只回传结论", 14, MUTED))
    return svg(W, H, b)


def flappy() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "Cognition 的 Flappy Bird 例子",
          "两个子 agent 各自做了一个“合理”的决定，但这两个决定互相冲突；拼的人只拿到结果，不知道背后的取舍")
    b.append(node(470, 112, 300, 84, "任务：做一个 Flappy Bird", ["拆成两个子任务"], fill=GRAY))
    b.append(node(110, 270, 360, 120, "子 agent 1：背景和管道", ["做出来像《超级马里奥》", "的横版场景"], fill=BLUE))
    b.append(node(770, 270, 360, 120, "子 agent 2：小鸟", ["小鸟的样子和动作", "和原游戏都不像"], fill=BLUE))
    b.append(path("M 560 198 C 560 240, 290 230, 290 266", LABEL, 2, arrow=True))
    b.append(path("M 680 198 C 680 240, 950 230, 950 266", LABEL, 2, arrow=True))
    b.append(node(420, 430, 400, 96, "最后一个 agent 负责合并", ["两份风格完全不搭的结果"], fill=CLAY_SOFT, stroke=CLAY))
    b.append(path("M 290 392 C 290 470, 380 478, 416 478", CLAY, 2, arrow=True, clay=True))
    b.append(path("M 950 392 C 950 470, 860 478, 824 478", CLAY, 2, arrow=True, clay=True))
    b.append(text(620, 250, "两边都不知道对方选了什么风格", 14, CLAY, weight=600))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-subagent", subagent())
    save(OUT, "02-flappy", flappy())
