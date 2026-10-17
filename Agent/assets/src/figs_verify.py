"""Figures for 04-反馈与验证.md.

Usage: python figs_verify.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, node, path, rect, save, svg, text, title)

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

# ------------------------------------------------------------- 03 检查覆盖矩阵
CLASSES = [("语法 / 类型", 0.30), ("局部逻辑", 0.35), ("集成 / 配置", 0.20), ("需求理解", 0.15)]
CHECKS = [("模型自查", [0.5, 0.3, 0.1, 0.0]),
          ("类型检查", [0.95, 0.0, 0.2, 0.0]),
          ("自己写的单元测试", [0.3, 0.6, 0.1, 0.0]),
          ("端到端测试", [0.6, 0.5, 0.8, 0.4]),
          ("独立上下文的审查", [0.3, 0.4, 0.3, 0.5])]


def coverage() -> str:
    W, H = 1200, 570
    b: list[str] = []
    title(b, "每种检查能看见哪类错误（示意）",
          "格子里是这类错误被这种检查发现的概率；只有端到端测试和独立审查能碰到“需求理解错了”")
    x0, y0, cw, rh = 250, 170, 170, 62
    for j, (name, w) in enumerate(CLASSES):
        b.append(text(x0 + j * cw + cw / 2, y0 - 30, name, 15, INK, weight=700))
        b.append(text(x0 + j * cw + cw / 2, y0 - 8, f"占错误的 {int(w * 100)}%", 12, MUTED))
    for i, (name, rs) in enumerate(CHECKS):
        y = y0 + i * rh
        b.append(text(x0 - 20, y + rh / 2 + 6, name, 15, INK, "end", weight=600))
        for j, r in enumerate(rs):
            x = x0 + j * cw
            a = 0.08 + 0.85 * r
            b.append(f'<rect x="{x + 4}" y="{y + 4}" width="{cw - 8}" height="{rh - 8}" rx="8" '
                     f'fill="{CLAY}" fill-opacity="{a:.2f}" stroke="{GRID}" stroke-width="1"/>')
            b.append(mono(x + cw / 2, y + rh / 2 + 6, f"{r:.2f}", 15, WHITE if r >= 0.6 else INK, weight=700))
    yb = y0 + len(CHECKS) * rh + 36
    b.append(text(x0 - 20, yb, "五种全上：", 15, INK, "end", weight=700))
    for j, v in enumerate([0.995, 0.916, 0.909, 0.70]):
        b.append(mono(x0 + j * cw + cw / 2, yb, f"{v:.2f}", 15, CLAY, weight=700))
    b.append(text(x0 + 4 * cw + 20, yb, "加权 d = 0.91", 15, CLAY, "start", weight=700))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 检查间隔
def interval() -> str:
    W, H = 1200, 620
    b: list[str] = []
    title(b, "每隔几步检查一次（示意）",
          "纵轴是每一步摊到的代价：检查本身 c/k，加上发现得晚而多出的返工 qrk/2；最低点在 k* = √(2c/qr)")
    x0, x1, y0, y1 = 130, 1000, 530, 150
    kmax, vmax = 20, 2.0

    def px(k): return x0 + (k - 1) / (kmax - 1) * (x1 - x0)

    def py(v): return y0 - min(v, vmax) / vmax * (y0 - y1)

    for v in (0, 0.5, 1.0, 1.5, 2.0):
        b.append(line(x0, py(v), x1, py(v), GRID, 1.2))
        b.append(mono(x0 - 12, py(v) + 5, f"{v:.1f}", 13, LABEL, "end"))
    for k in (1, 5, 10, 15, 20):
        b.append(mono(px(k), y0 + 26, str(k), 13, LABEL))
    b.append(text((x0 + x1) / 2, y0 + 58, "检查间隔 k（步）", 14, MUTED, weight=600))
    b.append(text(x0 - 12, y1 - 22, "每步代价（轮）", 14, MUTED, "end", weight=600))
    q, r = 0.1, 1.0
    for (name, c), col in zip([("类型检查 c=0.05", 0.05), ("单元测试 c=0.5", 0.5), ("端到端 c=2", 2.0)],
                              ["#3f9c86", "#4f86c0", CLAY]):
        pts, first = [], True
        k = 1.0
        while k <= kmax + 1e-9:
            v = c / k + q * r * k / 2
            if v <= vmax:
                pts.append(f"{'M' if first else 'L'} {px(k):.1f} {py(v):.1f}")
                first = False
            k += 0.1
        b.append(path(" ".join(pts), col, 3))
        ks = (2 * c / (q * r)) ** 0.5
        vs = c / ks + q * r * ks / 2
        b.append(f'<circle cx="{px(ks):.1f}" cy="{py(vs):.1f}" r="6" fill="{col}" stroke="#4a4a4a" stroke-width="1.5"/>')
        b.append(mono(px(ks) + 4, py(vs) - 14, f"k*={ks:.1f}", 13, col, "start", weight=700))
        li = [0.05, 0.5, 2.0].index(c)
        b.append(line(760, y1 + 10 + li * 30, 800, y1 + 10 + li * 30, col, 3))
        b.append(text(812, y1 + 15 + li * 30, name, 14, col, "start", weight=700))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-signals", signals())
    save(OUT, "02-guardrails", guardrails())
    save(OUT, "03-coverage", coverage())
    save(OUT, "04-interval", interval())
