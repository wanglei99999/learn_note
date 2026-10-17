"""Figures for 04-反馈与验证.md.

Usage: python figs_verify.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "verify"


# ------------------------------------------------------------- 01 反馈信号的强弱
def signals() -> str:
    W, H = 1200, 600
    b: list[str] = []
    title(b, "agent 能拿到的反馈", "越往右越接近“真的能用”，也越慢、越贵；好的 harness 把便宜的检查放在每一轮，贵的放在宣布完成之前")
    items = [("自己读一遍", "模型看自己的 diff", "几乎不花时间", GRAY),
             ("编译 / 类型检查", "语法、类型、引用", "秒级", BEIGE),
             ("lint", "风格和架构规则", "秒级", BEIGE),
             ("单元测试", "函数的行为", "秒到分钟", BLUE),
             ("端到端测试", "浏览器里点一遍", "分钟级", BLUE),
             ("日志 / 指标", "运行时真实表现", "分钟级", TEAL)]
    x0, w, gap = 40, 176, 12
    for i, (t, sub, cost, fill) in enumerate(items):
        x = x0 + i * (w + gap)
        hgt = 150 + i * 36
        y = 470 - hgt
        b.append(rect(x, y, w, hgt, fill, rx=12, sw=2, shadow=True))
        b.append(text(x + w / 2, y + 36, t, 16, weight=700))
        b.append(text(x + w / 2, y + 62, sub, 13, MUTED))
        b.append(text(x + w / 2, y + 88, cost, 13, LABEL))
    b.append(line(60, 510, 1140, 510, CLAY, 2.5, arrow=True, clay=True))
    b.append(text(60, 540, "便宜、快，但只能查出表面问题", 15, CLAY, "start", weight=600))
    b.append(text(1140, 540, "离真实使用越近，反馈越可信", 15, CLAY, "end", weight=600))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 护栏的分层
def guardrails() -> str:
    W, H = 1200, 660
    b: list[str] = []
    title(b, "护栏的分层", "上面几层靠模型自觉，下面几层由程序强制执行；越往下越确定，越难被绕过")
    layers = [
        ("提示里的规则", "“不要修改测试文件”“提交前先跑测试”", "模型多数时候会照做", WHITE),
        ("工具设计", "只给需要的工具；参数用 schema 约束", "做不到的事就不会去做", GRAY),
        ("hooks", "每次编辑后自动格式化；拦截危险命令", "在固定时机必然执行", BEIGE),
        ("lint 与类型检查", "依赖方向、命名、文件大小", "报错信息直接告诉模型怎么改", BEIGE),
        ("测试与 CI", "不过就不能合并", "结果不由模型说了算", BLUE),
        ("权限与沙箱", "文件和网络访问的边界", "第 11 篇", TEAL),
    ]
    for i, (t, ex, note, fill) in enumerate(layers):
        y = 112 + i * 86
        inset = i * 14
        b.append(rect(80 + inset, y, 1040 - 2 * inset, 72, fill, rx=12, sw=2, shadow=True))
        b.append(text(110 + inset, y + 44, t, 17, INK, "start", weight=700))
        b.append(text(330, y + 44, ex, 14, LABEL, "start"))
        b.append(text(1090 - inset, y + 44, note, 14, MUTED, "end"))
    b.append(line(50, 120, 50, 620, CLAY, 2.5, arrow=True, clay=True))
    b.append(f'<text x="34" y="370" font-size="14" fill="{CLAY}" font-weight="700" text-anchor="middle" '
             f'transform="rotate(90 34 370)">越来越硬</text>')
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-signals", signals())
    save(OUT, "02-guardrails", guardrails())
