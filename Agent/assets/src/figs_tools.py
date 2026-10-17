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


# ------------------------------------------------------------- 03 并行调用与 id 配对
def parallel() -> str:
    W, H = 1240, 600
    b: list[str] = []
    title(b, "并行调用：三个 tool_use，三个 tool_result，靠 id 配对",
          "执行可以乱序完成，其中一个失败也要返回一条结果；下一次请求里，每个 id 都必须有对应的结果")
    b.append(rect(40, 110, 560, 440, WHITE, GRID, 1.5, rx=14))
    b.append(text(60, 142, "assistant 消息（模型输出）", 15, MUTED, "start", weight=700))
    calls = [("t1", "上海"), ("t2", "北京"), ("t3", "拉萨")]
    for i, (tid, city) in enumerate(calls):
        y = 166 + i * 70
        b.append(rect(60, y, 520, 54, BLUE, rx=8, sw=1.5))
        b.append(mono(80, y + 33, f'tool_use  id={tid}  get_weather(city="{city}")', 14, INK, "start"))
    b.append(rect(640, 110, 560, 440, WHITE, GRID, 1.5, rx=14))
    b.append(text(660, 142, "下一条 user 消息（harness 组装）", 15, MUTED, "start", weight=700))
    res = [("t2", '{"temp": 9, "sky": "晴"}', TEAL, "先返回"),
           ("t1", '{"temp": 18, "sky": "小雨"}', TEAL, ""),
           ("t3", "is_error: 城市不在支持范围内", CLAY_SOFT, "失败也要回")]
    for i, (tid, body, fill, note) in enumerate(res):
        y = 166 + i * 70
        b.append(rect(660, y, 520, 54, fill, CLAY if fill == CLAY_SOFT else "#4a4a4a", 1.5, rx=8))
        b.append(mono(680, y + 33, f"tool_result  id={tid}  {body}", 13, INK, "start"))
    for (src, dst) in ((0, 1), (1, 0), (2, 2)):
        b.append(line(582, 193 + src * 70, 656, 193 + dst * 70, LABEL, 1.8, arrow=True))
    b.append(text(60, 420, "· 结果的顺序可以和调用不同，模型靠 id 对应", 14, LABEL, "start"))
    b.append(text(60, 448, "· 漏掉任何一个 id，下一次请求会被 API 拒绝", 14, LABEL, "start"))
    b.append(text(60, 476, "· 失败用 is_error 标记，错误信息就是模型下一步的输入", 14, LABEL, "start"))
    b.append(text(60, 504, "· 三个结果放在同一条消息里：少两次往返，少两遍全量重发", 14, LABEL, "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 粒度与 token
def granularity() -> str:
    W, H = 1240, 500
    b: list[str] = []
    title(b, "工具粒度决定 token 消耗（示意）",
          "左：找一个联系人；右：约一个会。上下文按 2 万 token 计，每多一轮调用就要多发一遍全部上下文")
    def bars(x0, items, maxv, unit):
        for i, (lab, v, fill, note) in enumerate(items):
            y = 210 + i * 120
            w = v / maxv * 400
            b.append(text(x0, y - 10, lab, 15, INK, "start", weight=700))
            b.append(rect(x0, y, max(w, 4), 44, fill, "#4a4a4a", 1.5, rx=6))
            b.append(mono(x0 + max(w, 4) + 10, y + 28, f"{v:,} {unit}", 14, INK, "start"))
            b.append(text(x0, y + 72, note, 13, MUTED, "start"))
    b.append(text(60, 140, "返回给模型的 token", 15, MUTED, "start", weight=700))
    bars(60, [("list_contacts：返回全部 2,000 人", 60_000, CLAY, "每人约 30 token，模型自己在里面找"),
              ("search_contacts(name=\"张伟\")：返回 3 人", 100, TEAL, "程序替模型做了筛选")], 60_000, "token")
    b.append(text(660, 140, "完成任务的总输入 token", 15, MUTED, "start", weight=700))
    bars(660, [("list_users → list_events × 2 → create_event", 80_000, CLAY, "4 次调用，每次都带上约 2 万 token 的上下文"),
               ("schedule_event(参会人, 时长, 时间范围)", 20_000, TEAL, "1 次调用，找空档和建会都在工具内部完成")], 80_000, "token")
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-round-trip", round_trip())
    save(OUT, "02-mcp", mcp())
    save(OUT, "03-parallel", parallel())
    save(OUT, "04-granularity", granularity())
