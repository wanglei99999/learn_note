"""Figures for 06-Skills.md.

Usage: python figs_skills.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "skills"


def levels() -> str:
    W, H = 1240, 640
    b: list[str] = []
    title(b, "Skill 的三级加载",
          "只有第一级常驻上下文；第二级在模型判断用得上时才读；第三级按需读，脚本直接执行、不进上下文")
    # context window column
    b.append(rect(40, 110, 380, 490, WHITE, GRID, 1.5, rx=14))
    b.append(text(60, 142, "上下文窗口", 16, MUTED, "start", weight=700))
    b.append(rect(60, 160, 340, 60, GRAY, rx=8, sw=1.5))
    b.append(text(230, 196, "system prompt + 工具定义", 14))
    b.append(rect(60, 230, 340, 96, BEIGE, CLAY, 2, rx=8))
    for i, s in enumerate(["pdf：读取、填写 PDF 表单时使用", "pptx：制作或修改幻灯片时使用", "… 共 50 个，每个几十 token"]):
        b.append(mono(76, 256 + i * 26, s, 13, INK, "start"))
    b.append(rect(60, 336, 340, 80, BLUE, rx=8, sw=1.5, dash="6 4"))
    b.append(text(230, 370, "pdf/SKILL.md 正文", 14, weight=600))
    b.append(text(230, 394, "命中后才读进来", 13, MUTED))
    b.append(rect(60, 426, 340, 56, TEAL, rx=8, sw=1.5, dash="6 4"))
    b.append(text(230, 460, "forms.md（需要填表时）", 14))
    b.append(rect(60, 492, 340, 92, "#f3efe9", GRID, 1.5, rx=8))
    b.append(text(230, 530, "对话历史 …", 14, MUTED))
    # right: levels
    rows = [(230, "第 1 级 · 元数据", "name + description，启动时全部加载", "常驻", BEIGE),
            (346, "第 2 级 · SKILL.md 正文", "流程、规范、注意事项", "用到才读", BLUE),
            (436, "第 3 级 · 附带文件", "参考文档、模板、子流程", "按需读", TEAL),
            (520, "脚本", "extract_fields.py 直接运行，只有输出进上下文", "不进上下文", GRAY)]
    for y, t, sub, tag, fill in rows:
        if tag != "不进上下文":
            b.append(line(404, y + 24, 520, y + 24, LABEL, 2, dash="4 4"))
        b.append(rect(520, y, 520, 56, fill, rx=10, sw=2, shadow=True))
        b.append(text(540, y + 24, t, 16, INK, "start", weight=700))
        b.append(text(540, y + 46, sub, 13, MUTED, "start"))
        b.append(rect(1060, y + 12, 140, 32, CLAY_SOFT if tag == "常驻" else WHITE, CLAY if tag == "常驻" else GRID,
                      1.5, rx=16))
        b.append(text(1130, y + 33, tag, 14, CLAY if tag == "常驻" else LABEL, weight=600))
    b.append(text(520, 152, "pdf/", 16, INK, "start", weight=700))
    b.append(mono(520, 180, "SKILL.md · forms.md · reference.md", 14, LABEL, "start"))
    b.append(mono(520, 204, "scripts/extract_fields.py", 14, LABEL, "start"))
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-levels", levels())
