"""Figures for 02-工具调用.md.

Usage: python figs_tools.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, node, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "tools"


# ------------------------------------------------------------- 01 一次工具调用的往返
def round_trip() -> str:
    W, H = 1240, 760
    b: list[str] = []
    title(b, "一次工具调用的往返",
          "模型只负责写出“想调用什么”，真正去调用的是你的程序；一来一回是两次独立的 API 调用")
    lanes = [(200, "模型 API", BLUE), (620, "你的程序", BEIGE), (1040, "天气服务", TEAL)]
    for x, name, fill in lanes:
        b.append(rect(x - 110, 108, 220, 52, fill, rx=12, shadow=True))
        b.append(text(x, 141, name, 18, weight=700))
        b.append(line(x, 160, x, 730, GRID, 2, dash="6 6"))

    def msg(y: float, x1: float, x2: float, label: str, sub: str | None = None,
            clay: bool = False) -> None:
        col = CLAY if clay else LABEL
        d = 1 if x2 > x1 else -1
        b.append(line(x1 + d * 6, y, x2 - d * 8, y, col, 2.5, arrow=True, clay=clay))
        cx = (x1 + x2) / 2
        b.append(text(cx, y - 12, label, 15, INK, weight=600))
        if sub:
            b.append(mono(cx, y + 24, sub, 13, MUTED))

    msg(214, 620, 200, "① 消息 + 工具定义", "tools: [get_weather(city)]")
    msg(300, 200, 620, "② 不直接回答，返回一个调用请求", 'tool_use{id: t1, input:{city:"上海"}}', clay=True)
    b.append(text(410, 352, "stop_reason = tool_use，这次调用结束", 13, CLAY))
    msg(410, 620, 1040, "③ 程序解析参数，真正去调用", "GET /weather?city=上海")
    msg(490, 1040, 620, "④ 返回结果", '{"temp": 18, "sky": "小雨"}')
    msg(576, 620, 200, "⑤ 全部历史 + 工具结果", "tool_result{tool_use_id: t1, ...}")
    msg(662, 200, 620, "⑥ 根据结果作答", "“上海 18 度，小雨，带把伞。”")
    b.append(text(410, 714, "stop_reason = end_turn", 13, MUTED))
    # brace showing two calls
    for y0, lab in ((190, "第 1 次 API 调用"), (552, "第 2 次 API 调用")):
        b.append(rect(36, y0, 34, 170, CLAY_SOFT, CLAY, 1.5, rx=6))
        cy = y0 + 85
        b.append(f'<text x="53" y="{cy}" font-size="14" fill="{CLAY}" font-weight="700" '
                 f'text-anchor="middle" dominant-baseline="central" '
                 f'transform="rotate(-90 53 {cy})">{lab}</text>')
    return svg(W, H, b)


# ------------------------------------------------------------- 02 M×N 与 M+N
def mcp() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "MCP 把 M×N 的对接变成 M+N",
          "左边每个应用都要为每个服务单独写一套集成；右边双方各自实现一次协议")
    apps = ["Claude Code", "Cursor", "自己的 agent"]
    svcs = ["GitHub", "Slack", "Postgres", "浏览器"]

    def column(x: float, names: list[str], fill: str, w: float = 150) -> list[float]:
        n = len(names)
        top = 120 + (380 - n * 60 - (n - 1) * 22) / 2
        ys = []
        for i, nm in enumerate(names):
            y = top + i * 82
            b.append(rect(x, y, w, 60, fill, rx=10, sw=2, shadow=True))
            b.append(text(x + w / 2, y + 36, nm, 15, weight=600))
            ys.append(y + 30)
        return ys

    # left panel
    b.append(rect(40, 104, 560, 420, WHITE, GRID, 1.5, rx=14))
    ay = column(70, apps, BLUE)
    sy = column(420, svcs, TEAL)
    for a in ay:
        for s in sy:
            b.append(line(222, a, 418, s, CLAY, 1.6))
    b.append(text(320, 500, "3 × 4 = 12 套集成", 16, CLAY, weight=700))
    # right panel
    b.append(rect(640, 104, 560, 420, WHITE, GRID, 1.5, rx=14))
    ay = column(664, apps, BLUE, 140)
    sy = column(1036, svcs, TEAL, 140)
    b.append(rect(870, 150, 100, 320, BEIGE, rx=12, sw=2.5, shadow=True))
    b.append(text(920, 300, "MCP", 18, weight=700))
    b.append(text(920, 324, "协议", 14, MUTED))
    for a in ay:
        b.append(line(806, a, 868, a, LABEL, 2))
    for s in sy:
        b.append(line(972, s, 1034, s, LABEL, 2))
    b.append(text(920, 500, "3 个客户端 + 4 个服务器 = 7 份实现", 16, INK, weight=700))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-round-trip", round_trip())
    save(OUT, "02-mcp", mcp())
