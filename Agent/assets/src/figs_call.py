"""Figures for 01-一次调用.md.

Usage: python figs_call.py
"""
from pathlib import Path

import math

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, SERIES, TEAL,
                          WHITE, line, mono, node, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "call"


# ------------------------------------------------------------- 01 一次调用的数据流
def one_call() -> str:
    W, H = 1240, 520
    b: list[str] = []
    title(b, "一次调用：从请求到响应",
          "左右两端在你的程序里，中间四步在服务端；响应发出后，服务端什么也不留下")
    # server region
    b.append(rect(236, 112, 768, 300, WHITE, GRID, 1.5, rx=14, dash="6 6"))
    b.append(text(256, 140, "服务端", 15, MUTED, "start", weight=700))
    boxes = [
        (40, "请求", ["system", "messages", "max_tokens 等参数"], GRAY),
        (256, "chat 模板", ["消息列表拼成", "一段带特殊标记的文本"], BEIGE),
        (446, "分词", ["文本切成 token id", "（几百到几十万个）"], BEIGE),
        (636, "prefill", ["整段 prompt 并行算一遍", "K、V 存进缓存"], BLUE),
        (826, "decode", ["一次采样一个 token", "直到满足停止条件"], BLUE),
        (1040, "响应", ["content", "stop_reason", "usage"], TEAL),
    ]
    y, h = 186, 150
    for i, (x, t, lines, fill) in enumerate(boxes):
        w = 160 if i in (0, 5) else 168
        b.append(node(x, y, w, h, t, lines, fill=fill, tsize=18))
    xs = [(200, 256), (424, 446), (614, 636), (804, 826), (994, 1040)]
    for x1, x2 in xs:
        b.append(line(x1 + 2, y + h / 2, x2 - 4, y + h / 2, LABEL, 2.5, arrow=True))
    # decode self-loop
    b.append(f'<path d="M 880 {y + h} C 880 {y + h + 50}, 940 {y + h + 50}, 940 {y + h + 4}" '
             f'fill="none" stroke="{LABEL}" stroke-width="2" marker-end="url(#arr)"/>')
    b.append(text(910, y + h + 62, "新 token 追加到末尾", 13, MUTED))
    b.append(rect(236, 432, 768, 52, CLAY_SOFT, CLAY, 1.8, rx=10))
    b.append(text(620, 464, "下一次调用进来时，上面这些全部从头再算一遍（除非命中前缀缓存，见第 05 篇）",
                  15, INK))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 无状态：每轮重发全部历史
def stateless() -> str:
    W, H = 1200, 640
    b: list[str] = []
    title(b, "每一轮都把整段历史重新发一遍",
          "假设 system prompt 1,000 token，每轮用户说 100 token、模型答 300 token")
    x0, y0, rh, gap = 140, 120, 30, 12
    k = 0.17  # px per token
    for t in range(1, 11):
        y = y0 + (t - 1) * (rh + gap)
        b.append(text(x0 - 16, y + 21, f"第 {t} 轮", 15, LABEL, "end"))
        x = x0
        segs = [(1000, GRAY), (400 * (t - 1), BLUE), (100, BEIGE)]
        for n, fill in segs:
            if n == 0:
                continue
            b.append(rect(x, y, n * k, rh, fill, "#4a4a4a", 1.5, rx=4))
            x += n * k
        inp = 1100 + 400 * (t - 1)
        b.append(rect(x + 6, y, 300 * k, rh, TEAL, "#4a4a4a", 1.5, rx=4))
        b.append(mono(x + 6 + 300 * k + 12, y + 21, f"输入 {inp:,}", 14, INK, "start"))
    # legend
    ly = y0 + 10 * (rh + gap) + 22
    items = [(GRAY, "system prompt"), (BLUE, "之前所有轮次"), (BEIGE, "这一轮的用户消息"),
             (TEAL, "这一轮的输出")]
    lx = x0
    for fill, lab in items:
        b.append(rect(lx, ly, 18, 18, fill, "#4a4a4a", 1.5, rx=4))
        b.append(text(lx + 28, ly + 14, lab, 14, LABEL, "start"))
        lx += 210
    b.append(text(x0, ly + 54, "10 轮累计：输入 29,000 token，输出 3,000 token。输入随轮数线性增长，累计量按平方增长。",
                  15, CLAY, "start", weight=600))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 约束解码
def constrained() -> str:
    W, H = 1200, 530
    b: list[str] = []
    title(b, "约束解码：把不合语法的 token 屏蔽掉",
          "schema 规定 temp 是数字。模型本来最想输出引号（准备写字符串），被屏蔽后只能在数字里选")
    # left: state
    b.append(rect(48, 116, 380, 380, WHITE, GRID, 1.5, rx=12))
    b.append(text(70, 150, "schema", 15, MUTED, "start", weight=700))
    for i, s in enumerate(['{ "temp": number,', '  "sky": string }']):
        b.append(mono(70, 184 + i * 26, s, 15, INK, "start"))
    b.append(text(70, 264, "已经生成的文本", 15, MUTED, "start", weight=700))
    b.append(rect(70, 280, 336, 44, GRAY, "#4a4a4a", 1.5, rx=8))
    b.append(mono(86, 308, '{"temp": ', 16, INK, "start"))
    b.append(rect(150, 288, 3, 28, CLAY, CLAY, 0, rx=0))
    b.append(text(70, 364, "语法状态：这里只能出现", 15, MUTED, "start", weight=700))
    b.append(text(70, 390, "数字、负号", 15, INK, "start"))
    b.append(text(70, 440, "每生成一个 token，状态机前进一步，", 14, LABEL, "start"))
    b.append(text(70, 464, "下一步的合法集合随之改变", 14, LABEL, "start"))

    def bars(x0: float, label: str, rows: list[tuple[str, float, bool]], scale: float) -> None:
        b.append(text(x0, 150, label, 16, INK, "start", weight=700))
        for i, (tok, p, ok) in enumerate(rows):
            y = 176 + i * 60
            b.append(rect(x0, y, 64, 40, GRAY if ok else WHITE, "#4a4a4a" if ok else GRID, 1.5, rx=6))
            b.append(mono(x0 + 32, y + 26, tok, 16, INK if ok else MUTED))
            if p > 0:
                b.append(rect(x0 + 78, y + 6, p * scale, 28, BLUE if ok else "#ece9e4",
                              "#4a4a4a" if ok else GRID, 1.5, rx=4))
                b.append(mono(x0 + 86 + p * scale, y + 26, f"{p:.2f}", 14, INK if ok else MUTED, "start"))
            else:
                b.append(text(x0 + 78, y + 26, "−∞，概率 0", 14, CLAY, "start"))

    before = [('"', 0.41, False), ("2", 0.22, True), ("二", 0.18, False), ("1", 0.12, True),
              ("null", 0.07, False)]
    after = [('"', 0, False), ("2", 0.65, True), ("二", 0, False), ("1", 0.35, True),
             ("null", 0, False)]
    bars(470, "原始分布", before, 360)
    b.append(line(788, 320, 836, 320, LABEL, 2.5, arrow=True))
    b.append(text(812, 304, "屏蔽", 14, LABEL))
    bars(852, "屏蔽后重新归一化", after, 360 * 0.6)
    b.append(text(470, 500, "0.22 / (0.22 + 0.12) ≈ 0.65。格式一定合法，但模型原本想写的是 \"25度\" 这样的字符串。",
                  14, LABEL, "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 温度
def temperature() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "同一组 logits，不同温度下的分布",
          "logits = [3.0, 2.0, 1.0, 0.0]；先除以 T 再做 softmax。T 越小越集中，T 越大越平")
    toks = ["巴黎", "Paris", "法国", "伦敦"]
    z = [3.0, 2.0, 1.0, 0.0]
    panels = [(0.5, "T = 0.5"), (1.0, "T = 1"), (2.0, "T = 2")]
    for i, (T, lab) in enumerate(panels):
        x0 = 60 + i * 390
        b.append(rect(x0, 110, 360, 400, WHITE, GRID, 1.5, rx=14))
        b.append(text(x0 + 180, 146, lab, 18, INK, weight=700))
        e = [math.exp(v / T) for v in z]
        sm = sum(e)
        ps = [v / sm for v in e]
        for j, (t, p_) in enumerate(zip(toks, ps)):
            bx = x0 + 40 + j * 78
            h = p_ * 280
            b.append(rect(bx, 470 - h, 56, max(h, 2), SERIES[1] if j == 0 else BLUE, "#4a4a4a", 1.5, rx=4))
            b.append(mono(bx + 28, 462 - h, f"{p_:.3f}", 12, INK))
            b.append(text(bx + 28, 494, t, 13, LABEL))
    return svg(W, H, b)


# ------------------------------------------------------------- 05 prefill 与 decode 的时间线
def latency() -> str:
    W, H = 1240, 470
    b: list[str] = []
    title(b, "一次调用的耗时：prefill 一段，decode 一段（示意）",
          "输入 10,000 token，输出 500 token；假设 prefill 每秒 5,000 token、decode 每秒 50 token")
    x0, scale = 120, 90  # px per second
    b.append(rect(x0, 160, 2 * scale, 60, BEIGE, "#4a4a4a", 2, rx=8))
    b.append(text(x0 + scale, 196, "prefill 2 秒", 15, INK, weight=600))
    b.append(rect(x0 + 2 * scale + 4, 160, 10 * scale, 60, BLUE, "#4a4a4a", 2, rx=8))
    for k in range(1, 10):
        xx = x0 + 2 * scale + 4 + k * scale
        b.append(line(xx, 166, xx, 214, "#7fa3cc", 1))
    b.append(text(x0 + 7 * scale + 4, 196, "decode 10 秒：500 个 token 逐个生成", 15, INK, weight=600))
    b.append(line(x0, 250, x0 + 12 * scale + 4, 250, GRID, 2))
    for sec in range(0, 13, 2):
        xx = x0 + sec * scale + (4 if sec > 2 else 0)
        b.append(line(xx, 244, xx, 256, LABEL, 1.5))
        b.append(text(xx, 278, f"{sec}s", 13, MUTED))
    b.append(line(x0 + 2 * scale, 120, x0 + 2 * scale, 156, CLAY, 2, arrow=True, clay=True))
    b.append(text(x0 + 2 * scale, 112, "首 token（TTFT）", 14, CLAY, weight=600))
    b.append(text(120, 330, "prefill：整段输入并行计算，耗时随输入长度增长，但每个 token 很便宜", 14, LABEL, "start"))
    b.append(text(120, 356, "decode：每步只算一个新 token，要读一遍全部权重和 KV Cache，步与步之间无法并行", 14, LABEL, "start"))
    b.append(text(120, 382, "总耗时 ≈ 输入长度 / prefill 速度 + 输出长度 / decode 速度", 15, INK, "start", weight=600))
    b.append(text(120, 420, "输入翻倍，首 token 晚 2 秒；输出翻倍，整体晚 10 秒。输出 token 的价格通常是输入的 4 到 5 倍，原因同此", 13, MUTED, "start"))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-one-call", one_call())
    save(OUT, "02-stateless", stateless())
    save(OUT, "03-constrained-decoding", constrained())
    save(OUT, "04-temperature", temperature())
    save(OUT, "05-latency", latency())
