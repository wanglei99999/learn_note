"""Figures for 11-安全与权限.md.

Usage: python figs_security.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, node, path, rect, save, svg, text, title)

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


if __name__ == "__main__":
    save(OUT, "01-trifecta", trifecta())
    save(OUT, "02-sandbox", sandbox())
