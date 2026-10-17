"""Figures for 05-上下文工程.md.

Usage: python figs_context.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, Axes, line, mono, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "context"


# ------------------------------------------------------------- 01 前缀缓存
def prefix_cache() -> str:
    W, H = 1240, 600
    b: list[str] = []
    title(b, "前缀缓存：从第一个不同的 token 开始，后面全部重算",
          "第 k+1 轮只是在第 k 轮末尾追加了新内容，所以前面整段都能命中缓存；开头改一个字，就全部失效")

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

    base = [("system", 160, GRAY), ("工具定义", 150, GRAY), ("任务", 80, BEIGE),
            ("第 1..k 轮", 300, BLUE)]
    row(130, "第 k 轮", base, None, "")
    row(230, "第 k+1 轮", base + [("新一轮", 110, BLUE)], 890, "前面全部命中，只算新增部分")
    bad = [("system*", 160, CLAY_SOFT), ("工具定义", 150, GRAY), ("任务", 80, BEIGE),
           ("第 1..k 轮", 300, BLUE), ("新一轮", 110, BLUE)]
    row(330, "开头加时间戳", bad, 200, "全部重算", bad=True)
    bad2 = [("system", 160, GRAY), ("工具定义*", 150, CLAY_SOFT), ("任务", 80, BEIGE),
            ("第 1..k 轮", 300, BLUE), ("新一轮", 110, BLUE)]
    row(430, "中途删一个工具", bad2, 360, "工具之后全部重算", bad=True)
    b.append(rect(200, 530, 18, 10, TEAL, "none", 0, rx=4))
    b.append(text(228, 540, "命中缓存：按约 1/10 的价格计费", 14, LABEL, "start"))
    b.append(rect(520, 530, 18, 10, CLAY, "none", 0, rx=4))
    b.append(text(548, 540, "需要重新 prefill", 14, LABEL, "start"))
    b.append(text(760, 540, "* 表示和上一轮不一样的部分", 14, MUTED, "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 上下文随轮次增长与压缩
def growth() -> str:
    W, H = 1200, 620
    b: list[str] = []
    title(b, "上下文随轮次增长，以及两种减负手段",
          "示意图：每轮工具输出约 2,000 token；第 30 轮附近接近上限，触发压缩")
    ax = Axes(130, 120, 960, 380, (0, 60), (0, 100_000))
    b += ax.frame([(i, str(i)) for i in range(0, 61, 10)],
                  [(v, f"{v // 1000}k") for v in range(0, 100_001, 20_000)], "轮次", "上下文 token 数")
    limit = 80_000
    b.append(line(ax.px(0), ax.py(limit), ax.px(60), ax.py(limit), CLAY, 2, dash="8 6"))
    b.append(text(ax.px(60) - 8, ax.py(limit) - 10, "上下文上限前的警戒线", 13, CLAY, "end"))
    # offload: smaller slope
    off = [(t, 6000 + 1100 * t) for t in range(0, 61)]
    b.append(ax.curve(off, "#4f86c0", 3))
    b.append(text(ax.px(13), ax.py(11_000), "大输出写进文件，只留路径", 14, "#4f86c0", "start"))
    # compaction sawtooth
    pts = []
    v = 6000
    for t in range(0, 61):
        if v > 76_000:
            pts.append((t, v))
            v = 14_000
        pts.append((t, v))
        v += 2600
    b.append(ax.curve(pts, CLAY, 3))
    b.append(text(ax.px(31) + 8, ax.py(18_000), "压缩：总结成摘要后从头开始", 14, CLAY, "start"))
    # naive
    naive = [(t, 6000 + 2600 * t) for t in range(0, 31)]
    b.append(ax.curve(naive, "#5a5a5a", 3, dash="10 8"))
    b.append(text(ax.px(27) - 10, ax.py(83_000), "什么都不做", 14, "#8c7c6e", "end"))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-prefix-cache", prefix_cache())
    save(OUT, "02-growth", growth())
