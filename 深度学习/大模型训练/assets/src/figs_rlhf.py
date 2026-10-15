"""Figures for 03-RLHF与DPO.md.

Usage: python figs_rlhf.py
The KL-tilt figure is computed from pi*(y) ∝ pi_ref(y) exp(r(y)/beta) on a 1-D toy space.
The over-optimization figure uses the functional form from Gao et al. 2022
(R_RL(d) = d(a - b log d), d = sqrt(KL)) with illustrative coefficients.
"""
import math
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, SERIES,
                          TEAL, WHITE, Axes, circle, line, mono, node, path, rect, save, svg,
                          text, title)

OUT = Path(__file__).resolve().parent.parent / "rlhf"


# ------------------------------------------------------------- 01 InstructGPT 三步
def three_steps() -> str:
    W, H = 1200, 520
    b: list[str] = []
    title(b, "InstructGPT 的三步", "SFT 之后，先训练一个给回答打分的奖励模型，再用强化学习让模型去拿高分")
    cols = [
        ("① SFT", TEAL, ["约 1.3 万条 prompt", "标注员写示范回答", "", "监督学习"],
         "得到 π_SFT"),
        ("② 训练奖励模型", BEIGE, ["约 3.3 万条 prompt", "每题采样 4~9 个回答", "标注员从好到差排序", "两两比较的 loss"],
         "得到 r(x, y)"),
        ("③ PPO", BLUE, ["约 3.1 万条 prompt", "模型自己生成回答", "奖励模型打分", "加 KL 惩罚"],
         "得到 π_RL"),
    ]
    bw, gap = 330, 57
    for i, (name, fill, lines_, out) in enumerate(cols):
        x = 48 + i * (bw + gap)
        b.append(rect(x, 112, bw, 300, fill, shadow=True))
        b.append(text(x + bw / 2, 152, name, 20, INK, weight=700))
        for k, s in enumerate(lines_):
            b.append(text(x + bw / 2, 198 + k * 32, s, 16, LABEL))
        b.append(rect(x + 60, 352, bw - 120, 40, WHITE, CLAY if i == 2 else "#4a4a4a", 2, rx=20))
        b.append(text(x + bw / 2, 378, out, 16, CLAY if i == 2 else INK, weight=700))
        if i < 2:
            b.append(line(x + bw + 8, 262, x + bw + gap - 8, 262, LABEL, 2.5, arrow=True))
    b.append(text(600, 456, "结果：1.3B 的 InstructGPT，在人工评估里比 175B 的 GPT-3 更受偏好", 16, INK, weight=600))
    b.append(text(600, 486, "数字来自 Ouyang 等 2022", 13, MUTED))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 奖励模型
def reward_model() -> str:
    W, H = 1200, 560
    b: list[str] = []
    title(b, "奖励模型：只学“哪个更好”", "Bradley–Terry 模型：两个分数之差过 sigmoid，就是“A 比 B 好”的概率")
    # schematic
    b.append(node(48, 130, 230, 64, "prompt x", [], GRAY))
    b.append(node(48, 220, 230, 64, "回答 y_w（更好）", [], TEAL))
    b.append(node(48, 310, 230, 64, "回答 y_l（更差）", [], CLAY_SOFT, stroke="#4a4a4a"))
    b.append(node(340, 200, 170, 104, "奖励模型", ["LLM + 标量头"], BEIGE))
    for y in (162, 252, 342):
        b.append(line(282, y, 334, 252, LABEL, 2, arrow=True))
    b.append(line(514, 230, 580, 200, LABEL, 2, arrow=True))
    b.append(line(514, 276, 580, 306, LABEL, 2, arrow=True))
    b.append(text(590, 205, "r_w = 1.2", 17, INK, "start", weight=700))
    b.append(text(590, 312, "r_l = 0.4", 17, INK, "start", weight=700))
    b.append(rect(48, 410, 520, 110, WHITE, GRID, 1.5, rx=12))
    b.append(text(70, 444, "loss = −log σ(r_w − r_l)", 17, INK, "start", weight=700))
    b.append(text(70, 474, "= −log σ(0.8) = −log 0.690 ≈ 0.371", 15, LABEL, "start"))
    b.append(text(70, 500, "梯度把 r_w 往上推、r_l 往下压，直到差距足够大", 14, MUTED, "start"))
    # curve
    ax = Axes(790, 130, 340, 300, (-4, 4), (0, 4.2))
    b += ax.frame([(v, str(v)) for v in (-4, -2, 0, 2, 4)], [(v, str(v)) for v in (0, 1, 2, 3, 4)],
                  "分数差 r_w − r_l", "loss")
    pts = [(-4 + k * 0.08, math.log1p(math.exp(-(-4 + k * 0.08)))) for k in range(101)]
    b.append(ax.curve(pts, CLAY, 3.5))
    b.append(circle(ax.px(0.8), ax.py(0.371), 7, WHITE, CLAY, 3))
    b.append(text(ax.px(0.8) + 12, ax.py(0.371) - 12, "(0.8, 0.371)", 14, CLAY, "start", weight=700))
    b.append(circle(ax.px(0), ax.py(math.log(2)), 5, WHITE, LABEL, 2))
    b.append(text(ax.px(0) - 12, ax.py(math.log(2)) + 22, "0.693", 13, LABEL, "end"))
    b.append(text(960, 520, "排错（差 < 0）时 loss 很大；排对后 loss 迅速变小", 14, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 PPO 四个模型
def ppo_models() -> str:
    W, H = 1200, 560
    b: list[str] = []
    title(b, "PPO 训练时，显存里有四个模型", "只有策略模型和价值模型在更新；参考模型和奖励模型冻结")
    b.append(node(60, 140, 260, 96, "prompt", ["从 prompt 池采样"], GRAY))
    b.append(node(470, 140, 260, 96, "策略模型 π_θ", ["生成回答 · 更新"], BLUE, stroke=CLAY, sw=3))
    b.append(line(324, 188, 464, 188, LABEL, 2.5, arrow=True))
    b.append(node(880, 110, 260, 80, "奖励模型 r", ["冻结 · 给整段回答打分"], BEIGE))
    b.append(node(880, 220, 260, 80, "参考模型 π_ref", ["冻结 · 就是 SFT 模型"], GRAY))
    b.append(node(880, 330, 260, 80, "价值模型 V", ["更新 · 估计每一步的预期得分"], TEAL))
    for y in (150, 260, 370):
        b.append(line(734, 188, 874, y, LABEL, 2, arrow=True))
    b.append(text(790, 150, "回答 y", 14, LABEL))
    # reward composition
    b.append(rect(140, 300, 640, 150, WHITE, GRID, 1.5, rx=12))
    b.append(text(164, 336, "每条回答拿到的奖励", 16, INK, "start", weight=700))
    b.append(mono(164, 374, "R = r(x, y) − β · [log π_θ(y|x) − log π_ref(y|x)]", 16, INK, "start"))
    b.append(text(164, 410, "第一项：奖励模型的打分；第二项：偏离 SFT 模型越远，扣得越多", 14, LABEL, "start"))
    b.append(text(164, 434, "价值模型用来把整段奖励分摊到每个 token，降低梯度的方差", 14, LABEL, "start"))
    b.append(text(600, H - 30, "7B 规模就要同时放下 4 份 7B 模型，外加生成回答的推理开销，这是 PPO 难用的主要原因", 14, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 KL 约束
def gauss(x: float, m: float, s: float) -> float:
    return math.exp(-0.5 * ((x - m) / s) ** 2) / (s * math.sqrt(2 * math.pi))


def reward(x: float) -> float:
    # broad hill around x=1 (genuinely better answers) + narrow spike at x=3.2 (RM loophole)
    return 1.2 * math.exp(-0.5 * ((x - 1.0) / 0.9) ** 2) + 2.2 * math.exp(-0.5 * ((x - 3.2) / 0.12) ** 2)


def tilt(beta: float, xs: list[float]) -> list[float]:
    w = [gauss(x, 0, 1) * math.exp(reward(x) / beta) for x in xs]
    z = sum(w) * (xs[1] - xs[0])
    return [v / z for v in w]


def kl_tilt() -> str:
    W, H = 1200, 706
    b: list[str] = []
    title(b, "β 控制模型能离 SFT 多远",
          "最优策略 π*(y) ∝ π_ref(y) · exp(r(y)/β)。横轴是一维化的“回答空间”，按公式数值计算")
    xs = [-3 + k * 0.01 for k in range(701)]
    ax = Axes(130, 130, 700, 200, (-3, 4), (0, 2.5))
    b += ax.frame([(v, str(v)) for v in range(-3, 5)], [(v, str(v)) for v in (0, 1, 2)], "", "奖励 r(y)")
    b.append(ax.curve([(x, reward(x)) for x in xs], "#8c7c6e", 3))
    b.append(text(ax.px(1.0), ax.py(1.2) - 12, "真正更好的回答", 14, LABEL))
    b.append(text(ax.px(3.2) - 8, ax.py(2.2) - 6, "奖励模型的漏洞", 14, CLAY, "end", weight=700))

    ax2 = Axes(130, 380, 700, 220, (-3, 4), (0, 1.6))
    b += ax2.frame([(v, str(v)) for v in range(-3, 5)], [(v, f"{v:.1f}") for v in (0, 0.5, 1.0, 1.5)],
                   "回答空间 y（示意）", "概率密度")
    ref = [gauss(x, 0, 1) for x in xs]
    b.append(ax2.curve(list(zip(xs, ref)), "#8c7c6e", 2.5, dash="6,5"))
    series = [(1.0, SERIES[1]), (0.4, SERIES[2]), (0.2, CLAY)]
    for beta, col in series:
        p = tilt(beta, xs)
        b.append(ax2.curve(list(zip(xs, p)), col, 3))
    # legend + mass on spike
    lx = 870
    b.append(rect(lx, 130, 282, 470, WHITE, GRID, 1.5, rx=12))
    b.append(text(lx + 20, 164, "下图曲线", 16, INK, "start", weight=700))
    items = [("π_ref（SFT 模型）", "#8c7c6e", True)] + [(f"β = {bt}", c, False) for bt, c in series]
    for i, (lab, col, dash) in enumerate(items):
        y = 196 + i * 30
        b.append(line(lx + 20, y - 5, lx + 56, y - 5, col, 3, dash="6,5" if dash else None))
        b.append(text(lx + 66, y, lab, 14, LABEL, "start"))
    b.append(text(lx + 20, 344, "落在漏洞区（y > 2.8）的概率", 14, INK, "start", weight=700))
    for i, (beta, col) in enumerate(series):
        p = tilt(beta, xs)
        mass = sum(v for x, v in zip(xs, p) if x > 2.8) * 0.01
        b.append(text(lx + 20, 376 + i * 28, f"β = {beta}：{mass * 100:.1f}%", 14, col, "start", weight=700))
    ref_mass = sum(v for x, v in zip(xs, ref) if x > 2.8) * 0.01
    b.append(text(lx + 20, 376 + 3 * 28, f"π_ref：{ref_mass * 100:.2f}%", 14, LABEL, "start"))
    b.append(text(lx + 20, 506, "β 越小，越敢为了分数", 14, LABEL, "start"))
    b.append(text(lx + 20, 528, "跑到 SFT 模型很少去的地方", 14, LABEL, "start"))
    b.append(text(600, H - 18, "KL 约束的作用：奖励模型只在 SFT 模型常去的区域打分可靠，不让策略跑出这片区域", 14, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 05 过度优化
def overopt() -> str:
    W, H = 1200, 560
    b: list[str] = []
    title(b, "奖励模型的分数越刷越高，真实质量先升后降",
          "曲线形状按 Gao 等 2022 的拟合形式 d(a − b·log d) 绘制，d = √KL；系数为示意")
    ax = Axes(130, 120, 760, 320, (0, 9), (0, 6))
    b += ax.frame([(v, str(v)) for v in range(0, 10, 3)], [(v, str(v)) for v in range(0, 7, 2)],
                  "√KL(π ‖ π_ref)：离 SFT 模型的距离", "奖励")
    ds = [0.01 + k * 0.09 for k in range(100)]
    proxy = [(d, 0.62 * d) for d in ds]
    gold = [(d, d * (1.0 - 0.45 * math.log(d))) for d in ds]
    b.append(ax.curve(proxy, SERIES[1], 3.5))
    b.append(ax.curve(gold, CLAY, 3.5))
    peak = max(gold, key=lambda p: p[1])
    b.append(line(ax.px(peak[0]), ax.py(0), ax.px(peak[0]), ax.py(peak[1]), CLAY, 1.5, dash="5,4"))
    b.append(text(ax.px(peak[0]) + 10, ax.py(peak[1]) + 40, "该停在这里", 14, CLAY, "start", weight=700))
    b.append(text(ax.px(6.2), ax.py(0.62 * 6.2) - 16, "奖励模型给的分", 15, SERIES[1], "end", weight=700))
    b.append(text(ax.px(8.6), ax.py(gold[-1][1]) - 40, "真实偏好（gold）", 15, CLAY, "end", weight=700))
    x = 930
    b.append(rect(x, 130, 222, 300, WHITE, GRID, 1.5, rx=12))
    b.append(text(x + 18, 162, "常见的刷分方式", 16, INK, "start", weight=700))
    for i, s in enumerate(["· 回答越写越长", "· 堆砌列表和加粗", "· 顺着用户说（谄媚）",
                           "· 自信地给出答案，", "  不说“我不确定”", "· 过度道歉和免责声明"]):
        b.append(text(x + 18, 198 + i * 30, s, 14, LABEL, "start"))
    b.append(text(600, H - 26, "奖励模型只是人类偏好的近似；优化得越狠，越会钻近似里的空子", 14, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 06 PPO vs DPO
def ppo_vs_dpo() -> str:
    W, H = 1200, 560
    b: list[str] = []
    title(b, "DPO 把“训练奖励模型 + 强化学习”压成一步", "同样的偏好数据，DPO 直接在策略模型上算一个分类式的 loss")
    # PPO lane
    b.append(text(48, 140, "RLHF (PPO)", 17, INK, "start", weight=700))
    lane = [("偏好数据", GRAY), ("训练奖励模型", BEIGE), ("采样生成回答", BLUE), ("打分 + KL", BEIGE), ("PPO 更新", BLUE)]
    for i, (s, fill) in enumerate(lane):
        x = 48 + i * 224
        b.append(rect(x, 160, 196, 64, fill, shadow=True))
        b.append(text(x + 98, 198, s, 16, INK, weight=600))
        if i < 4:
            b.append(line(x + 200, 192, x + 220, 192, LABEL, 2, arrow=True))
    b.append(path("M942 228 C 942 270, 488 270, 488 230", LABEL, 2, dash="5,4", arrow=True))
    b.append(text(715, 282, "循环：在线采样，每轮都要生成", 13, MUTED))
    # DPO lane
    b.append(text(48, 340, "DPO", 17, INK, "start", weight=700))
    b.append(rect(48, 360, 196, 64, GRAY, shadow=True))
    b.append(text(146, 398, "偏好数据", 16, INK, weight=600))
    b.append(line(248, 392, 300, 392, LABEL, 2, arrow=True))
    b.append(rect(304, 360, 848, 64, TEAL, CLAY, 3, shadow=True))
    b.append(text(728, 398, "直接用 DPO loss 更新策略模型（参考模型只做前向）", 16, INK, weight=600))
    b.append(rect(48, 448, 1104, 64, WHITE, GRID, 1.5, rx=12))
    b.append(text(70, 486, "需要的模型：", 15, INK, "start", weight=700))
    b.append(text(170, 486, "PPO = 策略 + 参考 + 奖励 + 价值 4 个，还要在线生成；"
                  "DPO = 策略 + 参考 2 个，数据是静态的", 15, LABEL, "start"))
    return svg(W, H, b)


if __name__ == "__main__":
    for name, fn in [("01-instructgpt-steps", three_steps), ("02-reward-model", reward_model),
                     ("03-ppo-four-models", ppo_models), ("04-kl-tilt", kl_tilt),
                     ("05-overoptimization", overopt), ("06-ppo-vs-dpo", ppo_vs_dpo)]:
        save(OUT, name, fn())
