"""Figures for 07-记忆.md.

Usage: python figs_memory.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "memory"


def tiers() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "信息可以存在三个地方", "agent 的“记忆”指的主要是第三列：在上下文窗口之外、跨会话保存，并且由 agent 自己读写")
    cols = [
        ("权重", BLUE, ["训练时写入", "部署后不变", "容量大，但改不了", "知道世界，不知道你"]),
        ("上下文", BEIGE, ["每次调用时拼进来", "调用结束就消失", "几十万 token 上限", "越长越贵、越不准"]),
        ("外部存储", TEAL, ["文件、数据库、向量库", "跨会话保存", "容量几乎不限", "要靠工具读写"]),
    ]
    for i, (t, fill, lines_) in enumerate(cols):
        x = 60 + i * 390
        hl = i == 2
        b.append(rect(x, 116, 350, 380, fill, CLAY if hl else "#4a4a4a", 3 if hl else 2.5, rx=14, shadow=True))
        b.append(text(x + 175, 162, t, 22, weight=700))
        for j, s in enumerate(lines_):
            b.append(rect(x + 30, 196 + j * 70, 290, 52, WHITE, GRID, 1.5, rx=10))
            b.append(text(x + 175, 228 + j * 70, s, 15, LABEL))
    b.append(line(802, 300, 836, 300, CLAY, 2.5, arrow=True, clay=True))
    b.append(line(836, 340, 802, 340, CLAY, 2.5, arrow=True, clay=True))
    b.append(text(819, 530, "读进来 / 写出去", 14, CLAY, weight=600))
    return svg(W, H, b)


def lifecycle() -> str:
    W, H = 1240, 580
    b: list[str] = []
    title(b, "记忆的读、写与整理", "写入在会话中发生，读取在会话开始和需要时发生，整理可以放到后台异步做")
    b.append(rect(40, 110, 700, 430, WHITE, GRID, 1.5, rx=14))
    b.append(text(60, 142, "一次会话", 16, MUTED, "start", weight=700))
    b.append(node(70, 170, 200, 90, "会话开始", ["读入索引文件", "（常驻部分）"], fill=GRAY))
    b.append(node(300, 170, 200, 90, "工作中", ["需要时检索", "或按路径读取"], fill=BLUE))
    b.append(node(530, 170, 190, 90, "发生值得记的事", ["用户纠正、做了决定", "踩了坑"], fill=BEIGE))
    b.append(line(272, 215, 296, 215, LABEL, 2, arrow=True))
    b.append(line(502, 215, 526, 215, LABEL, 2, arrow=True))
    b.append(node(530, 330, 190, 90, "写入", ["先查有没有旧的", "有就更新，没有再新建"], fill=CLAY_SOFT, stroke=CLAY))
    b.append(line(625, 262, 625, 326, CLAY, 2.5, arrow=True, clay=True))
    b.append(text(70, 470, "风险：写错、过时、互相矛盾、被注入", 15, CLAY, "start", weight=600))
    b.append(text(70, 500, "写进去的东西，下次会被当成事实读回来", 14, LABEL, "start"))
    # store
    b.append(rect(800, 140, 400, 220, TEAL, rx=14, sw=2.5, shadow=True))
    b.append(text(1000, 178, "外部存储", 18, weight=700))
    for i, s in enumerate(["MEMORY.md：一行一条的索引", "user-偏好.md", "project-约定.md", "…"]):
        b.append(rect(830, 196 + i * 38, 340, 30, WHITE, GRID, 1.5, rx=6))
        b.append(text(846, 216 + i * 38, s, 13, LABEL, "start"))
    b.append(path("M 722 375 C 760 375, 760 300, 796 300", CLAY, 2.5, arrow=True, clay=True))
    b.append(path("M 900 136 C 900 96, 170 96, 170 166", LABEL, 2, arrow=True, dash="6 4"))
    b.append(node(800, 410, 400, 110, "后台整理", ["合并重复、删掉过时的、解决冲突", "可以在没人用的时候异步做"], fill=GRAY))
    b.append(line(1000, 362, 1000, 406, LABEL, 2))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-tiers", tiers())
    save(OUT, "02-lifecycle", lifecycle())
