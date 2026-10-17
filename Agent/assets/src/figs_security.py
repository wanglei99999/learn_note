"""Figures for 11-安全与权限.md.

Usage: python figs_security.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, Axes, line, mono, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "security"


def trifecta() -> str:
    W, H = 1240, 640
    b: list[str] = []
    title(b, "致命三要素", "三样同时具备，攻击者只要能让 agent 读到一段文字，就可能让它把你的数据发出去")
    circles = [(520, 270, BLUE, "私有数据", ["邮件、代码仓库", "数据库、密钥"]),
               (720, 270, BEIGE, "不可信内容", ["网页、邮件、issue", "第三方文档"]),
               (620, 430, TEAL, "对外通信", ["发请求、发邮件", "提交 PR、渲染图片链接"])]
    for cx, cy, fill, t, sub in circles:
        b.append(f'<circle cx="{cx}" cy="{cy}" r="160" fill="{fill}" fill-opacity="0.55" stroke="#4a4a4a" stroke-width="2.5"/>')
    labels = [(440, 230, "私有数据", ["邮件、代码仓库", "数据库、密钥"]),
              (800, 230, "不可信内容", ["网页、邮件、issue", "第三方文档"]),
              (620, 520, "对外通信", ["发请求、发邮件", "提交 PR"])]
    for x, y, t, sub in labels:
        b.append(text(x, y, t, 18, weight=700))
        for i, s in enumerate(sub):
            b.append(text(x, y + 26 + i * 22, s, 13, MUTED))
    b.append(f'<circle cx="620" cy="330" r="34" fill="{CLAY}" stroke="#4a4a4a" stroke-width="2"/>')
    b.append(text(620, 336, "危险", 15, WHITE, weight=700))
    b.append(rect(940, 150, 270, 200, WHITE, GRID, 1.5, rx=12))
    b.append(text(960, 182, "去掉任意一个", 15, INK, "start", weight=700))
    for i, s in enumerate(["没有私有数据：偷不到东西", "没有不可信内容：没人下指令", "没有对外通信：偷了也发不出去"]):
        b.append(text(960, 216 + i * 34, s, 14, LABEL, "start"))
    return svg(W, H, b)


def sandbox() -> str:
    W, H = 1240, 620
    b: list[str] = []
    title(b, "沙箱的两道边界", "文件系统隔离管“能改哪里”，网络隔离管“能发到哪里”，缺一道都不行；真正的凭据放在沙箱外面")
    b.append(rect(60, 120, 700, 450, CLAY_SOFT, CLAY, 2.5, rx=18, dash="10 6"))
    b.append(text(80, 152, "沙箱", 17, CLAY, "start", weight=700))
    b.append(node(110, 190, 260, 110, "agent", ["模型 + 它执行的命令", "以及命令的子进程"], fill=BLUE))
    b.append(rect(420, 180, 300, 150, WHITE, "#4a4a4a", 2, rx=12))
    b.append(text(570, 212, "文件系统", 16, weight=700))
    b.append(text(570, 244, "项目目录：可读写", 14, LABEL))
    b.append(text(570, 270, "其他目录：只读或不可见", 14, LABEL))
    b.append(text(570, 296, "~/.ssh、密钥：不可见", 14, CLAY))
    b.append(line(372, 245, 416, 245, LABEL, 2, arrow=True))
    b.append(node(110, 380, 260, 110, "网络", ["只能经过一个", "本地代理出去"], fill=GRAY))
    b.append(line(240, 302, 240, 376, LABEL, 2, arrow=True))
    # outside
    b.append(node(860, 150, 320, 120, "网络代理", ["域名白名单", "新域名要用户确认"], fill=BEIGE))
    b.append(path("M 372 420 H 800 V 210 H 854", LABEL, 2, arrow=True))
    b.append(node(860, 320, 320, 120, "git 代理", ["检查请求：只许推到指定分支", "检查通过后才附上真 token"], fill=BEIGE))
    b.append(path("M 372 460 H 820 V 380 H 854", LABEL, 2, arrow=True))
    b.append(node(860, 480, 320, 90, "真正的凭据", ["GitHub token、签名密钥"], fill=TEAL))
    b.append(line(1020, 442, 1020, 476, LABEL, 2))
    b.append(text(410, 540, "即使沙箱里的 agent 被注入，也拿不到凭据，发不出白名单之外的请求", 14, CLAY, weight=600))
    return svg(W, H, b)


# ------------------------------------------------------------- 03 反复尝试
def attempts() -> str:
    W, H = 1220, 620
    b: list[str] = []
    title(b, "单次注入的成功率很低，攻击者可以试很多次（示意）",
          "每次尝试独立地以概率 ε 成功；n 次里至少成功一次的概率是 1 − (1 − ε)ⁿ")
    ax = Axes(150, 140, 860, 380, (1, 10_000), (0, 1), xlog=True)
    b += ax.frame([(1, "1"), (10, "10"), (100, "100"), (1000, "1,000"), (10_000, "10,000")],
                  [(0, "0"), (0.25, "0.25"), (0.5, "0.50"), (0.75, "0.75"), (1, "1.00")],
                  "尝试次数 n（对数刻度）", "至少成功一次的概率")
    for (eps, col) in ((0.05, CLAY), (0.01, "#4f86c0"), (0.001, "#3f9c86")):
        pts = []
        for i in range(0, 401):
            n = 10 ** (i / 100)
            pts.append((n, 1 - (1 - eps) ** n))
        b.append(ax.curve(pts, col, 3))
    for i, (eps, col) in enumerate(((0.05, CLAY), (0.01, "#4f86c0"), (0.001, "#3f9c86"))):
        b.append(line(1040, 200 + i * 32, 1080, 200 + i * 32, col, 3))
        b.append(text(1090, 205 + i * 32, f"ε = {eps}", 14, col, "start", weight=700))
    for n, v, col in ((100, 0.634, "#4f86c0"), (1000, 0.632, "#3f9c86")):
        b.append(f'<circle cx="{ax.px(n):.1f}" cy="{ax.py(v):.1f}" r="6" fill="{col}" stroke="#4a4a4a" stroke-width="1.5"/>')
        b.append(mono(ax.px(n) + 10, ax.py(v) + 22, f"{v:.2f}", 13, col, "start", weight=700))
    return svg(W, H, b)


# ------------------------------------------------------------- 04 上下文的污染
def taint() -> str:
    W, H = 1240, 560
    b: list[str] = []
    title(b, "不可信内容进入上下文之后",
          "消息列表只追加：第 5 轮读进来的网页会一直留在上下文里，之后每一轮的决定都可能受它影响")
    rows = ["用户任务", "读项目文件", "跑测试", "读项目文件", "读一个外部网页", "改代码", "跑测试", "提交"]
    x0, y0, w, h = 60, 150, 132, 70
    for i, r in enumerate(rows):
        x = x0 + i * (w + 8)
        tainted = i >= 4
        fill = CLAY_SOFT if tainted else (BLUE if i else GRAY)
        stroke = CLAY if i == 4 else "#4a4a4a"
        b.append(rect(x, y0, w, h, fill, stroke, 2.5 if i == 4 else 1.5, rx=8))
        b.append(text(x + w / 2, y0 + 30, f"第 {i + 1} 轮", 13, MUTED))
        b.append(text(x + w / 2, y0 + 52, r, 14, INK, weight=600))
    xs = x0 + 4 * (w + 8)
    b.append(line(xs - 4, y0 - 20, xs - 4, y0 + h + 20, CLAY, 2.5, dash="6 4"))
    b.append(text(xs + 4, y0 - 28, "从这里开始，上下文被污染", 14, CLAY, "start", weight=700))
    b.append(rect(60, 290, 540, 220, WHITE, GRID, 1.5, rx=12))
    b.append(text(80, 322, "之前：可以给足能力", 16, INK, "start", weight=700))
    for i, t in enumerate(["读写项目文件", "运行测试和构建", "访问白名单内的网络", "推送到工作分支"]):
        b.append(text(80, 358 + i * 32, "· " + t, 14, LABEL, "start"))
    b.append(rect(640, 290, 540, 220, CLAY_SOFT, CLAY, 2, rx=12))
    b.append(text(660, 322, "之后：收紧有后果的操作", 16, INK, "start", weight=700))
    for i, t in enumerate(["禁止访问新的域名", "推送、发消息、写记忆需要确认", "私有数据的读取需要确认",
                           "或者：交给一个没有工具的隔离模型处理"]):
        b.append(text(660, 358 + i * 32, "· " + t, 14, LABEL, "start"))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-trifecta", trifecta())
    save(OUT, "02-sandbox", sandbox())
    save(OUT, "03-attempts", attempts())
    save(OUT, "04-taint", taint())
