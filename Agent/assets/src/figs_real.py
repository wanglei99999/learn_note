"""Figures for 13-拆解一个真实的harness.md.

Usage: python figs_real.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "real"


def architecture() -> str:
    W, H = 1240, 780
    b: list[str] = []
    title(b, "Claude Code 的各个部件，对应本系列的哪一篇",
          "根据公开文档整理（2026 年 10 月）；红色小标签是篇号")

    def card(x, y, w, h, name, lines_, num, fill=BEIGE):
        b.append(rect(x, y, w, h, fill, rx=12, sw=2, shadow=True))
        b.append(text(x + 16, y + 30, name, 16, INK, "start", weight=700))
        bw = 18 + len(num) * 8.5
        b.append(rect(x + w - 12 - bw, y + 12, bw, 24, CLAY_SOFT, CLAY, 1.5, rx=6))
        b.append(text(x + w - 12 - bw / 2, y + 29, num, 13, CLAY, weight=700))
        for i, s in enumerate(lines_):
            b.append(mono(x + 16, y + 58 + i * 22, s, 13, LABEL, "start"))

    # top row: context in
    card(40, 110, 370, 150, "启动时进上下文", ["system prompt、工具定义", "CLAUDE.md（多层）", "skills 的 name + description"], "01·06·07")
    card(435, 110, 370, 150, "工具", ["Read / Edit / Write", "Bash（或 PowerShell）", "Glob / Grep、WebFetch / WebSearch"], "02")
    card(830, 110, 370, 150, "MCP 与 ToolSearch", ["外部服务的工具", "工具很多时延迟加载定义", "用到再取 schema"], "02·06")
    # center loop
    b.append(rect(330, 300, 580, 170, BLUE, rx=16, sw=3, shadow=True))
    b.append(text(620, 340, "主循环", 20, weight=700))
    b.append(text(620, 372, "模型决定调用什么 → harness 执行 → 结果拼回上下文", 14, LABEL))
    b.append(text(620, 398, "交错思考；工具出错时把错误回填", 14, LABEL))
    b.append(rect(860, 312, 38, 24, CLAY_SOFT, CLAY, 1.5, rx=6))
    b.append(text(879, 329, "03", 13, CLAY, weight=700))
    b.append(text(620, 440, "plan 模式：先只读探索、写计划，批准后再改", 14, MUTED))
    # left / right of loop
    card(40, 300, 260, 170, "上下文管理", ["自动压缩 /compact", "大输出截断", "PreCompact hook"], "05", GRAY)
    card(940, 300, 260, 170, "子 agent", ["Agent 工具", "独立上下文", "只回传结论"], "09", GRAY)
    # bottom row
    card(40, 510, 280, 160, "反馈与护栏", ["hooks：PreToolUse、", "PostToolUse、Stop …", "exit 2 可以拦截"], "04")
    card(340, 510, 280, 160, "任务清单", ["TaskCreate / TaskUpdate", "（早期是 TodoWrite）", "目标反复出现在末尾"], "05·08")
    card(640, 510, 280, 160, "权限", ["default / acceptEdits", "plan / auto / dontAsk", "allow / deny 规则"], "11")
    card(940, 510, 260, 160, "沙箱", ["文件系统 + 网络", "两道边界", "网页版凭据在沙箱外"], "11")
    for x in (180, 480, 780, 1070):
        b.append(line(x, 472, x, 506, GRID, 2))
    b.append(text(620, 720, "第 12 篇的评估在这张图之外：同一个模型放进这套 harness 里，整体是好是坏，要靠评估来回答", 14, CLAY, weight=600))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 一次会话
def trace() -> str:
    W, H = 1240, 620
    b: list[str] = []
    title(b, "修一个 bug 的会话里，各个部件在什么时候起作用",
          "上面一行是模型做的决定，下面是 harness 在同一时刻做的事；数字是本系列讲它的那一篇")
    steps = ["会话开始", "派子 agent 定位", "读文件", "编辑", "跑测试", "想要结束"]
    model = ["读任务", "写委派说明", "决定读哪几个", "写 old/new 字符串", "决定跑哪些测试", "end_turn"]
    harness = [["加载 CLAUDE.md", "skill 描述", "工具定义（部分延迟）"], ["新上下文", "只回传摘要"], ["记下读取时的版本"],
               ["文件改过则拒绝", "PostToolUse：lint"], ["权限规则放行", "沙箱内执行"], ["Stop hook 跑测试", "不过则继续"]]
    nums = [["07", "06", "02"], ["09", "09"], ["05"], ["05", "04"], ["11", "11"], ["04", "04"]]
    x0, cw, gap = 40, 186, 8
    b.append(text(x0, 150, "模型", 14, MUTED, "start", weight=700))
    b.append(text(x0, 290, "harness", 14, MUTED, "start", weight=700))
    for i, st in enumerate(steps):
        x = x0 + i * (cw + gap)
        b.append(rect(x, 160, cw, 90, BLUE, rx=10, sw=2))
        b.append(text(x + cw / 2, 190, st, 15, INK, weight=700))
        b.append(text(x + cw / 2, 220, model[i], 13, LABEL))
        b.append(line(x + cw / 2, 252, x + cw / 2, 296, GRID, 2))
        for j, (h, n) in enumerate(zip(harness[i], nums[i])):
            y = 300 + j * 82
            b.append(rect(x, y, cw, 70, BEIGE, rx=10, sw=1.8))
            b.append(text(x + 12, y + 42, h, 13, INK, "start"))
            b.append(rect(x + cw - 42, y + 8, 32, 20, CLAY_SOFT, CLAY, 1.2, rx=5))
            b.append(text(x + cw - 26, y + 23, n, 12, CLAY, weight=700))
    b.append(line(x0, 268, x0 + 6 * (cw + gap) - gap, 268, CLAY, 2, arrow=True, clay=True))
    b.append(text(620, 590, "判断留给模型：读什么、改什么、何时结束；边界交给程序：版本校验、lint、权限、沙箱、结束前的测试", 14, CLAY, weight=600))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-architecture", architecture())
    save(OUT, "02-trace", trace())
