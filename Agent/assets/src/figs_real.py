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


if __name__ == "__main__":
    save(OUT, "01-architecture", architecture())
