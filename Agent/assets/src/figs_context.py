"""Figures for 05-上下文工程.md.

Usage: python figs_context.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, SERIES, TEAL,
                          WHITE, line, mono, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "context"

# (name, tokens, still_needed, fill)
LEDGER = [
    ("system + 工具定义", 4_000, 4_000, GRAY),
    ("CLAUDE.md", 1_200, 1_200, GRAY),
    ("任务与约束（第 1 轮）", 300, 300, CLAY_SOFT),
    ("追加要求（第 12 轮）", 100, 100, CLAY_SOFT),
    ("读过的 8 个文件", 38_000, 11_800, BLUE),
    ("6 次测试输出", 21_000, 2_250, BEIGE),
    ("9 次搜索、列目录、git", 7_500, 300, BEIGE),
    ("2 次失败尝试与报错", 2_000, 200, CLAY_SOFT),
    ("模型自己的输出", 13_500, 800, TEAL),
]


def ledger() -> str:
    W, H = 1240, 690
    b: list[str] = []
    title(b, "第 30 轮的上下文账本（示意）",
          "共 87,600 token。右边一列是下一步还用得到的部分：约 2.1 万，不到四分之一")
    x0, y0, rh, gap = 300, 128, 40, 10
    scale = 640 / 38_000
    b.append(text(x0, y0 - 12, "占用", 14, MUTED, "start", weight=700))
    b.append(text(1180, y0 - 12, "还用得到", 14, MUTED, "end", weight=700))
    for i, (name, tok, need, fill) in enumerate(LEDGER):
        y = y0 + i * (rh + gap)
        b.append(text(x0 - 14, y + 26, name, 15, INK, "end"))
        w = max(tok * scale, 4)
        b.append(rect(x0, y, w, rh, fill, "#4a4a4a", 1.5, rx=5))
        nw = max(need * scale, 3)
        b.append(rect(x0, y, nw, rh, "none", CLAY, 2.5, rx=5))
        b.append(mono(x0 + w + 10, y + 26, f"{tok:,}", 14, LABEL, "start"))
        b.append(mono(1180, y + 26, f"{need:,}", 14, CLAY, "end", weight=700))
    yb = y0 + len(LEDGER) * (rh + gap) + 6
    b.append(line(80, yb, 1180, yb, GRID, 1.5))
    b.append(text(x0 - 14, yb + 28, "合计", 15, INK, "end", weight=700))
    b.append(mono(x0 + 10, yb + 28, "87,600", 15, INK, "start", weight=700))
    b.append(mono(1180, yb + 28, "20,950", 15, CLAY, "end", weight=700))
    b.append(rect(x0, yb + 48, 20, 14, "none", CLAY, 2.5, rx=3))
    b.append(text(x0 + 30, yb + 60, "橙框：下一步还用得到的部分（正在改的两个文件、最新一次测试、各类结论）", 13, LABEL, "start"))
    return svg(W, H, b)


FACTS = ["F1 根因一：worker 吞掉异常，整批丢弃", "F2 根因二：唯一约束冲突导致 500",
         "F3 约束：不能改导入接口的请求和响应格式", "F4 追加：重复的用户跳过，不报错",
         "F5 失败过：改成同步发送会超时", "F6 进度：worker.py 已改好，import.py 改到一半"]
KEEP = {  # 2 kept, 1 vague, 0 lost
    "保留首尾": [0, 0, 2, 0, 2, 2],
    "简单摘要": [1, 2, 0, 1, 0, 2],
    "外存 + 索引": [2, 2, 2, 2, 2, 2],
}


def three_ways() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "三种处理之后，六条关键信息还剩哪些（示意）",
          "“保留首尾”丢了中间的追加要求；“简单摘要”读起来通顺，却丢了原始约束和失败记录")
    b.append(rect(40, 110, 1160, 410, WHITE, GRID, 1.5, rx=14))
    cols = list(KEEP)
    xs = [720, 880, 1060]
    for x, c in zip(xs, cols):
        b.append(text(x, 150, c, 16, INK, weight=700))
    for i, f in enumerate(FACTS):
        y = 190 + i * 52
        if i % 2 == 0:
            b.append(rect(56, y - 22, 1128, 46, "#faf8f5", "none", 0, rx=6))
        b.append(text(76, y + 7, f, 15, INK, "start"))
        for x, c in zip(xs, cols):
            s = KEEP[c][i]
            fill, mark, col = [(CLAY, "✕", WHITE), (BEIGE, "~", INK), (TEAL, "✓", INK)][s]
            b.append(f'<circle cx="{x}" cy="{y + 2}" r="13" fill="{fill}" stroke="#4a4a4a" stroke-width="1.5"/>')
            b.append(text(x, y + 8, mark, 15, col, weight=700))
    b.append(text(76, 548, "✓ 保留　~ 只剩模糊的说法　✕ 丢失", 14, MUTED, "start"))
    return svg(W, H, b)


def prefix_cache() -> str:
    W, H = 1240, 600
    b: list[str] = []
    title(b, "前缀缓存：从第一个不同的 token 开始，后面全部重算",
          "第 k+1 轮只是在第 k 轮末尾追加了新内容，所以前面整段都能命中缓存；中间删一段，后面就全部失效")

    def row(y: float, label: str, segs: list[tuple[str, float, str]], hit_until: float | None,
            note: str, bad: bool = False) -> None:
        b.append(text(40, y + 30, label, 15, LABEL, "start", weight=600))
        x = 200
        for s, w, fill in segs:
            b.append(rect(x, y, w, 46, fill, "#4a4a4a", 1.5, rx=6))
            b.append(text(x + w / 2, y + 29, s, 13, INK))
            x += w
        if hit_until is not None:
            b.append(rect(200, y + 54, hit_until - 200, 10, TEAL, "none", 0, rx=4))
            b.append(rect(hit_until, y + 54, x - hit_until, 10, CLAY, "none", 0, rx=4))
        b.append(text(1200, y + 30, note, 14, CLAY if bad else MUTED, "end", weight=600 if bad else None))

    base = [("system", 160, GRAY), ("工具定义", 150, GRAY), ("任务", 80, BEIGE), ("第 1..k 轮", 300, BLUE)]
    row(130, "第 k 轮", base, None, "")
    row(230, "第 k+1 轮", base + [("新一轮", 110, BLUE)], 890, "前面全部命中，只算新增部分")
    row(330, "删掉最早一轮", [("system", 160, GRAY), ("工具定义", 150, GRAY), ("任务", 80, BEIGE),
                         ("第 2..k 轮*", 270, CLAY_SOFT), ("新一轮", 110, BLUE)], 590, "任务之后全部重算", bad=True)
    row(430, "开头加时间戳", [("system*", 160, CLAY_SOFT), ("工具定义", 150, GRAY), ("任务", 80, BEIGE),
                         ("第 1..k 轮", 300, BLUE), ("新一轮", 110, BLUE)], 200, "全部重算", bad=True)
    b.append(rect(200, 530, 18, 10, TEAL, "none", 0, rx=4))
    b.append(text(228, 540, "命中缓存：约 1/10 的输入价格", 14, LABEL, "start"))
    b.append(rect(500, 530, 18, 10, CLAY, "none", 0, rx=4))
    b.append(text(528, 540, "重新 prefill，按原价或缓存写入价计费", 14, LABEL, "start"))
    b.append(text(900, 540, "* 和上一轮不一样的部分", 14, MUTED, "start"))
    return svg(W, H, b)


def stale() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "消息历史只追加：旧的观察不会因为文件变了而消失",
          "users_import.py 在第 3 轮被完整读入，第 27、29 轮被修改（示意）")
    x0, x1 = 120, 1160
    b.append(line(x0, 200, x1, 200, GRID, 3))
    def px(t): return x0 + (t - 1) / 29 * (x1 - x0)
    for t in (1, 10, 20, 30):
        b.append(text(px(t), 236, f"第 {t} 轮", 13, MUTED))
    ev = [(3, "①", BLUE, "第 3 轮  read：读入全文，此时是版本 A（6,200 token，原样留在历史里）"),
          (27, "②", BEIGE, "第 27 轮  edit 成功：文件变成版本 B，历史里只多了一段修改记录"),
          (28, "③", CLAY_SOFT, "第 28 轮  edit 失败：模型照着版本 A 写 old_str，那段文字在版本 B 里已经不存在"),
          (29, "④", BEIGE, "第 29 轮  edit 成功：文件变成版本 C")]
    for i, (t, mark, fill, lab) in enumerate(ev):
        x = px(t) + (i - 2) * 6 if t >= 27 else px(t)
        b.append(f'<circle cx="{x:.1f}" cy="200" r="14" fill="{fill}" stroke="#4a4a4a" stroke-width="1.5"/>')
        b.append(text(x, 206, mark, 14, INK, weight=700))
        y = 290 + i * 38
        b.append(text(140, y, mark, 15, INK, "start", weight=700))
        b.append(text(170, y, lab, 14, LABEL, "start"))
    b.append(rect(120, 450, 1040, 76, WHITE, GRID, 1.5, rx=10))
    b.append(text(140, 480, "第 30 轮的上下文里，关于这个文件的内容是：版本 A 全文 + 两段修改记录。", 14, INK, "start"))
    b.append(text(140, 506, "磁盘上的真实内容是版本 C，它没有以全文形式出现在上下文的任何位置。", 14, CLAY, "start", weight=600))
    return svg(W, H, b)


def compaction() -> str:
    W, H = 1240, 540
    b: list[str] = []
    title(b, "压缩改动的是 messages，前面的 tools 和 system 保持不变",
          "前缀缓存按 tools → system → messages 的顺序比对；方块宽度不按比例（示意）")
    S = "#4a4a4a"
    def row(y, label, segs):
        b.append(text(40, y + 34, label, 15, LABEL, "start", weight=700))
        x = 150
        for name, tok, w, fill, stroke in segs:
            b.append(rect(x, y, w, 54, fill, stroke, 2 if stroke == CLAY else 1.5, rx=6))
            b.append(text(x + w / 2, y + 24, name, 13, INK))
            b.append(mono(x + w / 2, y + 43, f"{tok:,}", 12, MUTED))
            x += w + 4
        return x
    fixed = [("tools", 1_500, 100, GRAY, S), ("system", 2_500, 110, GRAY, S), ("CLAUDE.md", 1_200, 120, GRAY, S)]
    row(130, "压缩前", fixed + [("任务", 300, 80, CLAY_SOFT, S),
                              ("第 2–30 轮：文件、测试、搜索、模型输出", 82_100, 620, BLUE, S)])
    end = row(270, "压缩后", fixed + [("原始要求", 400, 110, CLAY_SOFT, CLAY), ("状态记录", 4_400, 150, BEIGE, CLAY),
                                    ("最近一次测试", 2_250, 150, BEIGE, CLAY)])
    pre = 150 + 100 + 110 + 120 + 8
    b.append(rect(150, 332, pre - 150, 10, TEAL, "none", 0, rx=4))
    b.append(rect(pre + 4, 332, end - pre - 8, 10, CLAY, "none", 0, rx=4))
    b.append(text(150, 372, "绿色：和压缩前逐 token 相同，命中缓存（5,200 token）", 13, LABEL, "start"))
    b.append(text(150, 394, "橙色：新内容，写入缓存（7,050 token，按 1.25 倍计价）", 13, LABEL, "start"))
    b.append(text(150, 444, "原始要求由 harness 原样复制；状态记录由模型按清单生成；最近一次测试输出保留原文。", 14, INK, "start"))
    b.append(text(150, 470, "其余约 7.8 万 token 移出上下文。它们的原文在产生时已经落盘，状态记录里留有路径和版本。", 14, INK, "start"))
    return svg(W, H, b)

ROWS = [("不处理", 142.7, 1.02, 0, "峰值超过窗口，跑不完"),
        ("滑动窗口", 45.5, 2.57, 0, "每轮缓存失效；丢了追加要求"),
        ("简单摘要", 79.2, 0.82, 6, "违反接口约束，返工 6 轮"),
        ("外存 + 索引", 84.2, 0.89, 2, "多 2 轮回读，信息完整")]


def cost() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "剩余工作的三笔账（示意，开启前缀缓存）",
          "上下文占用、计费、额外轮数并不一起下降：滑动窗口占用最小，却最贵")
    b.append(text(340, 140, "峰值上下文（千 token）", 15, MUTED, "middle", weight=700))
    b.append(text(700, 140, "输入 + 输出计费（美元）", 15, MUTED, "middle", weight=700))
    b.append(text(960, 140, "额外轮数", 15, MUTED, "middle", weight=700))
    for i, (name, peak, usd, extra, note) in enumerate(ROWS):
        y = 170 + i * 84
        b.append(text(156, y + 30, name, 16, INK, "end", weight=700))
        pw = peak * 2.0
        b.append(rect(170, y + 8, pw, 32, SERIES[1] if peak < 128 else CLAY, "#4a4a4a", 1.5, rx=5))
        b.append(mono(176 + pw, y + 30, f"{peak:.1f}", 13, LABEL, "start"))
        uw = usd * 60
        b.append(rect(580, y + 8, uw, 32, SERIES[0] if usd > 2 else SERIES[2], "#4a4a4a", 1.5, rx=5))
        b.append(mono(586 + uw, y + 30, f"{usd:.2f}", 13, LABEL, "start"))
        b.append(mono(960, y + 30, f"+{extra}", 15, INK, weight=700))
        b.append(text(1010, y + 30, note, 13, MUTED, "start"))
    b.append(line(170 + 128 * 2, 160, 170 + 128 * 2, 500, CLAY, 1.5, dash="5 4"))
    b.append(text(170 + 128 * 2, 520, "窗口 12.8 万", 13, CLAY))
    return svg(W, H, b)


if __name__ == "__main__":
    for p in list(OUT.glob("*.svg")) + list(OUT.glob("*.png")):
        p.unlink()
    save(OUT, "01-ledger", ledger())
    save(OUT, "02-stale", stale())
    save(OUT, "03-prefix-cache", prefix_cache())
    save(OUT, "04-three-ways", three_ways())
    save(OUT, "05-compaction", compaction())
    save(OUT, "06-cost", cost())
