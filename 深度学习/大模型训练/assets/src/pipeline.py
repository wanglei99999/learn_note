"""Series overview: pretrain -> SFT -> preference -> reasoning RL, one stage highlighted.

Usage: python pipeline.py   (writes assets/<topic>/00-pipeline.svg for the four topics)
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, LABEL, MUTED, TEAL, line, node,
                          rect, save, svg, text, title)

ASSETS = Path(__file__).resolve().parent.parent

STAGES = [
    ("预训练", "海量网页、书、代码", "每个 token 都算 loss", "学会语言和知识", BLUE),
    ("SFT", "指令-回答对话", "只算回答部分的 loss", "学会格式和听指令", TEAL),
    ("RLHF / DPO", "同题两个回答，标出好坏", "拉开好坏回答的差距", "学会人更喜欢的回答", BEIGE),
    ("推理 RL", "有标准答案的题", "答对给奖励", "学会长链条推理", GRAY),
]
TOPICS = ["pretrain", "sft", "rlhf", "reasoning"]


def pipeline(active: int) -> str:
    W, H = 1200, 330
    b: list[str] = []
    title(b, "从 base 模型到助手：四个训练阶段", "模型结构始终不变，每一步换的是数据和 loss")
    bw, bh, gap, x0, y0 = 245, 170, 52, 48, 118
    for i, (name, data, loss, gain, fill) in enumerate(STAGES):
        x = x0 + i * (bw + gap)
        on = i == active
        b.append(node(x, y0, bw, bh, name, [data, loss, ""], fill=fill if on else "#f1eee9",
                      sw=3.5 if on else 2, stroke=CLAY if on else "#9a948c", tsize=19))
        b.append(text(x + bw / 2, y0 + bh - 22, gain, 14, CLAY if on else MUTED, weight=600))
        if on:
            b.append(rect(x + bw / 2 - 34, y0 - 16, 68, 28, CLAY_SOFT, CLAY, 2, rx=14))
            b.append(text(x + bw / 2, y0 + 3, "本篇", 14, CLAY, weight=700))
        if i < 3:
            ax = x + bw + 8
            b.append(line(ax, y0 + bh / 2, ax + gap - 16, y0 + bh / 2, LABEL, 2.5, arrow=True))
    b.append(text(600, H - 14, "预训练消耗绝大部分算力；后面三步的数据量小几个数量级，但决定了模型怎么说话",
                  14, MUTED))
    return svg(W, H, b)


if __name__ == "__main__":
    for i, t in enumerate(TOPICS):
        save(ASSETS / t, "00-pipeline", pipeline(i))
