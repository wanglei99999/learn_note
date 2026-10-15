"""Figures for 05-LoRA与参数高效微调.md.

Usage: python figs_lora.py
Memory figure counts weights + gradients + Adam states only (no activations), for
Llama-2-7B (6.74B params) with LoRA r=8 on W_q and W_v of all 32 layers.
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, node, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "lora"


# ------------------------------------------------------------- 01 矩阵形状
def shapes() -> str:
    W, H = 1200, 560
    b: list[str] = []
    title(b, "LoRA：冻结 W，只训练两个细长矩阵",
          "h = W·x + (α/r)·B·A·x；以 d = 4096、r = 8 为例")
    # W block
    b.append(rect(80, 130, 280, 280, GRAY, sw=2.5, rx=8))
    b.append(text(220, 262, "W", 34, INK, weight=700))
    b.append(text(220, 296, "4096 × 4096", 15, LABEL))
    b.append(text(220, 320, "冻结", 15, MUTED, weight=600))
    b.append(text(220, 440, "16,777,216 个参数", 16, INK, weight=700))
    b.append(text(410, 280, "+", 40, LABEL, weight=700))
    # B
    b.append(rect(470, 130, 30, 280, CLAY_SOFT, CLAY, 2.5, rx=6))
    b.append(text(485, 116, "B", 22, CLAY, weight=700))
    b.append(text(485, 434, "4096 × 8", 14, LABEL))
    b.append(text(540, 280, "×", 32, LABEL, weight=700))
    # A
    b.append(rect(580, 255, 280, 30, CLAY_SOFT, CLAY, 2.5, rx=6))
    b.append(text(720, 242, "A", 22, CLAY, weight=700))
    b.append(text(720, 310, "8 × 4096", 14, LABEL))
    b.append(text(665, 440, "2 × 4096 × 8 = 65,536 个参数", 16, CLAY, weight=700))
    b.append(text(665, 466, "只有 W 的 0.39%", 15, CLAY))
    # init notes
    x = 910
    b.append(rect(x, 130, 242, 300, WHITE, GRID, 1.5, rx=12))
    b.append(text(x + 18, 162, "初始化", 16, INK, "start", weight=700))
    for i, s in enumerate(["A：随机高斯", "B：全零", "→ 一开始 B·A = 0，", "   模型和原来完全一样", "",
                           "训练后可以合并：", "W' = W + (α/r)·B·A", "推理时没有额外开销"]):
        b.append(text(x + 18, 196 + i * 26, s, 14, LABEL if s and s[0] not in "→W" else INK, "start"))
    b.append(text(600, H - 26, "B·A 的秩最多是 r，所以 LoRA 假设的是：微调需要的改动量 ΔW 是低秩的", 15, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 秩 1 手算
def rank1() -> str:
    W, H = 1200, 520
    b: list[str] = []
    title(b, "手算：4 × 4 的秩 1 矩阵", "16 个数，全部由一列 b 和一行 a 决定：ΔW = b · aᵀ，每个元素 ΔWᵢⱼ = bᵢ · aⱼ")
    bv = [1, 2, 0, -1]
    av = [0.5, 0, 1, 2]
    cell = 70
    # b column
    bx, top = 120, 190
    for i, v in enumerate(bv):
        b.append(rect(bx, top + i * cell, cell, cell, CLAY_SOFT, CLAY, 2, rx=4))
        b.append(mono(bx + cell / 2, top + i * cell + 44, f"{v:g}", 20, INK, weight=700))
    b.append(text(bx + cell / 2, top - 16, "b", 20, CLAY, weight=700))
    b.append(text(240, top + 2 * cell + 10, "×", 30, LABEL, weight=700))
    # a row
    ax0 = 290
    for j, v in enumerate(av):
        b.append(rect(ax0 + j * cell, top - 80, cell, cell, CLAY_SOFT, CLAY, 2, rx=4))
        b.append(mono(ax0 + j * cell + cell / 2, top - 80 + 44, f"{v:g}", 20, INK, weight=700))
    b.append(text(ax0 - 20, top - 36, "aᵀ", 20, CLAY, "end", weight=700))
    # result grid
    for i, bi in enumerate(bv):
        for j, aj in enumerate(av):
            v = bi * aj
            b.append(rect(ax0 + j * cell, top + i * cell, cell, cell, BLUE if v else WHITE, "#4a4a4a", 1.8, rx=4))
            b.append(mono(ax0 + j * cell + cell / 2, top + i * cell + 44, f"{v:g}", 20, INK))
    b.append(text(ax0 + 2 * cell, top + 4 * cell + 36, "ΔW（16 个数）", 16, INK, weight=600))
    # notes
    x = 680
    b.append(rect(x, 140, 472, 290, WHITE, GRID, 1.5, rx=12))
    b.append(text(x + 22, 176, "看几个位置", 16, INK, "start", weight=700))
    for i, s in enumerate(["ΔW₂₄ = b₂ · a₄ = 2 × 2 = 4", "ΔW₄₁ = b₄ · a₁ = −1 × 0.5 = −0.5",
                           "第 3 行全是 0，因为 b₃ = 0", "", "每一行都是 aᵀ 的倍数：行与行线性相关",
                           "", "存储：4 + 4 = 8 个数，而不是 16 个", "d = 4096 时：8,192 对比 16,777,216"]):
        b.append(text(x + 22, 212 + i * 27, s, 15, CLAY if i >= 6 else LABEL, "start",
                      weight=700 if i >= 6 else None))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 显存
def memory() -> str:
    W, H = 1200, 540
    b: list[str] = []
    title(b, "微调 Llama-2-7B，权重相关的显存", "只算权重、梯度、Adam 状态，不含激活值；LoRA 为 r = 8，加在每层的 W_q 和 W_v 上")
    n = 6.74e9
    lora = 32 * 2 * 2 * 4096 * 8   # 4.19M
    rows = [
        ("全参数微调", [("bf16 权重", n * 2, GRAY), ("bf16 梯度", n * 2, BEIGE), ("fp32 主权重", n * 4, BLUE),
                        ("Adam m、v（fp32）", n * 8, TEAL)]),
        ("LoRA", [("bf16 权重", n * 2, GRAY), ("LoRA 参数 + 梯度 + Adam", lora * 16, CLAY_SOFT)]),
        ("QLoRA", [("4-bit 权重（冻结）", n * 0.5 + n / 64 * 0.5, GRAY),
                   ("LoRA 参数 + 梯度 + Adam", lora * 16, CLAY_SOFT)]),
    ]
    x0, scale = 230, 7.0 / 1e9   # px per byte
    for i, (name, parts) in enumerate(rows):
        y = 140 + i * 110
        b.append(text(x0 - 16, y + 36, name, 17, INK, "end", weight=700))
        x = x0
        total = 0.0
        for lab, v, fill in parts:
            w = max(v * scale, 3)
            b.append(rect(x, y, w, 56, fill, "#4a4a4a", 1.8, rx=4))
            if w > 80:
                b.append(text(x + w / 2, y + 34, lab, 13, INK))
            x += w
            total += v
        b.append(text(x + 14, y + 36, f"≈ {total / 1e9:.1f} GB", 17, CLAY if i else INK, "start", weight=700))
        if i == 2:
            b.append(text(x0, y + 82, "4-bit NF4 量化后的基础权重，加上 LoRA 部分（同上）", 13, MUTED, "start"))
        if i == 1:
            b.append(text(x0, y + 82, f"冻结的 bf16 权重；可训练参数 {lora / 1e6:.2f}M，占 {lora / n:.2%}；它们的梯度和优化器状态只有 "
                          f"{lora * 16 / 1e6:.0f} MB", 13, MUTED, "start"))
    b.append(text(x0, 176 + 2 * 110 + 120, "全参数微调按混合精度 + Adam 每参数 16 字节估算；QLoRA 的 4-bit 权重含分块量化常数", 13, MUTED, "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 多 LoRA
def multi_lora() -> str:
    W, H = 1200, 520
    b: list[str] = []
    title(b, "一份基础模型，挂很多个 LoRA", "每个 adapter 只有几 MB 到几十 MB，可以按请求切换")
    b.append(rect(380, 300, 440, 120, GRAY, shadow=True))
    b.append(text(600, 350, "基础模型（7B，bf16 约 13.5 GB）", 18, INK, weight=700))
    b.append(text(600, 380, "在 GPU 上只放一份", 15, LABEL))
    adapters = [("法务问答", TEAL), ("客服话术", BLUE), ("SQL 生成", BEIGE), ("内部代码风格", CLAY_SOFT)]
    for i, (name, fill) in enumerate(adapters):
        x = 70 + i * 275
        b.append(node(x, 130, 230, 76, f"LoRA：{name}", ["r = 16，十几到几十 MB"], fill))
        b.append(line(x + 115, 210, 600 + (i - 1.5) * 90, 294, LABEL, 2, arrow=True))
    b.append(text(600, 466, "请求 A 用“法务问答”，请求 B 用“SQL 生成”，可以放进同一个 batch 一起算", 15, LABEL))
    b.append(text(600, 492, "S-LoRA、vLLM 等推理框架都支持这种部署方式", 14, MUTED))
    return svg(W, H, b)


if __name__ == "__main__":
    for name, fn in [("01-lora-shapes", shapes), ("02-rank1-example", rank1),
                     ("03-memory", memory), ("04-multi-lora", multi_lora)]:
        save(OUT, name, fn())
    lora = 32 * 2 * 2 * 4096 * 8
    print("lora params", lora, "frac", lora / 6.74e9)
