"""Figures for 10-模型这一侧.md.

Usage: python figs_model.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "model"


def rollout() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "单轮推理 RL 与 agentic RL 的一次采样",
          "agentic RL 的一条轨迹里交替出现模型写的 token 和环境返回的 token；只有前者参与梯度计算")

    def seq(y: float, label: str, segs: list[tuple[str, float, str, bool]], reward: str) -> None:
        b.append(text(40, y + 30, label, 15, LABEL, "start", weight=700))
        x = 200
        for s, w, fill, loss in segs:
            b.append(rect(x, y, w, 46, fill, CLAY if loss else "#4a4a4a", 2 if loss else 1.5, rx=6))
            b.append(text(x + w / 2, y + 29, s, 13, INK))
            x += w + 6
        b.append(line(x + 4, y + 23, x + 40, y + 23, LABEL, 2, arrow=True))
        b.append(rect(x + 46, y, 120, 46, TEAL, rx=8, sw=2))
        b.append(text(x + 106, y + 29, reward, 13, INK, weight=600))

    seq(130, "单轮推理 RL", [("题目", 120, GRAY, False), ("思考", 280, BEIGE, True), ("答案", 100, BEIGE, True)],
        "答案对不对")
    segs = [("任务", 80, GRAY, False), ("思考+调用", 110, BEIGE, True), ("工具结果", 120, BLUE, False),
            ("思考+调用", 110, BEIGE, True), ("工具结果", 90, BLUE, False), ("…", 40, WHITE, False),
            ("改代码", 90, BEIGE, True), ("测试输出", 90, BLUE, False), ("结束", 60, BEIGE, True)]
    seq(260, "agentic RL", segs, "测试过没过")
    # legend
    b.append(rect(200, 410, 22, 22, BEIGE, CLAY, 2, rx=4))
    b.append(text(232, 427, "模型生成，参与梯度计算", 14, LABEL, "start"))
    b.append(rect(470, 410, 22, 22, BLUE, "#4a4a4a", 1.5, rx=4))
    b.append(text(502, 427, "环境返回，不算 loss（和 SFT 的 loss mask 是同一个道理）", 14, LABEL, "start"))
    b.append(text(200, 480, "难点：轨迹长、环境要真的跑起来（沙箱、测试）、奖励只在最后给一次", 15, CLAY, "start", weight=600))
    return svg(W, H, b)


def coevolve() -> str:
    W, H = 1240, 520
    b: list[str] = []
    title(b, "模型与 harness 的共同演化", "模型在某个 harness 里训练，就会习惯那个 harness 的工具和格式；harness 又会根据模型的长处调整")
    b.append(node(120, 170, 340, 150, "模型", ["在某套工具、某种格式里", "做了大量 RL"], fill=BLUE, tsize=20))
    b.append(node(780, 170, 340, 150, "Harness", ["工具的形状、编辑文件的方式", "system prompt 的写法"], fill=BEIGE, tsize=20))
    b.append(path("M 462 210 C 600 150, 640 150, 776 210", LABEL, 2.5, arrow=True))
    b.append(text(620, 150, "模型擅长什么，harness 就围绕它设计", 14, LABEL))
    b.append(path("M 776 290 C 640 350, 600 350, 462 290", LABEL, 2.5, arrow=True))
    b.append(text(620, 372, "harness 用什么工具，下一代模型就在里面训练", 14, LABEL))
    b.append(rect(220, 420, 800, 60, CLAY_SOFT, CLAY, 1.8, rx=10))
    b.append(text(620, 457, "副作用：换一个工具设计不同的 harness，同一个模型的表现可能明显下降", 15, INK))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 有学习信号的任务占比
def signal() -> str:
    W, H = 1220, 620
    b: list[str] = []
    title(b, "一个任务采样 G 条轨迹，至少有一条成功、一条失败的概率",
          "全对或全错时组内优势全为 0，这个任务不产生梯度；太难和太简单的任务都浪费采样")
    x0, x1, y0, y1 = 130, 1000, 530, 150

    def px(v): return x0 + v * (x1 - x0)

    def py(v): return y0 - v * (y0 - y1)

    for v in (0, 0.25, 0.5, 0.75, 1.0):
        b.append(line(x0, py(v), x1, py(v), GRID, 1.2))
        b.append(mono(x0 - 12, py(v) + 5, f"{v:.2f}", 13, LABEL, "end"))
        b.append(mono(px(v), y0 + 26, f"{v:.2f}", 13, LABEL))
    b.append(text((x0 + x1) / 2, y0 + 58, "模型在这个任务上的成功率 p", 14, MUTED, weight=600))
    b.append(text(48, y1 - 22, "产生学习信号的概率", 14, MUTED, "start", weight=600))
    for G, col in ((4, "#8c7c6e"), (8, "#4f86c0"), (16, CLAY)):
        pts = []
        for i in range(0, 201):
            q = i / 200
            v = 1 - q ** G - (1 - q) ** G
            pts.append(f"{'M' if i == 0 else 'L'} {px(q):.1f} {py(v):.1f}")
        b.append(path(" ".join(pts), col, 3))
    for i, (G, col) in enumerate(((16, CLAY), (8, "#4f86c0"), (4, "#8c7c6e"))):
        b.append(line(1030, 220 + i * 32, 1070, 220 + i * 32, col, 3))
        b.append(text(1080, 225 + i * 32, f"G = {G}", 14, col, "start", weight=700))
    b.append(f'<circle cx="{px(0.05):.1f}" cy="{py(0.337):.1f}" r="6" fill="#4f86c0" stroke="#4a4a4a" stroke-width="1.5"/>')
    b.append(line(px(0.05) + 4, py(0.337) + 6, px(0.11), py(0.17), LABEL, 1.2))
    b.append(mono(px(0.115), py(0.15), "p = 0.05，G = 8：只有 34% 的任务有信号", 13, "#4f86c0", "start", weight=700))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-rollout", rollout())
    save(OUT, "02-coevolve", coevolve())
    save(OUT, "03-signal", signal())
