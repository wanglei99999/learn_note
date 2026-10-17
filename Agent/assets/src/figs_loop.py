"""Figures for 03-Agent循环与Harness.md.

Usage: python figs_loop.py
"""
from pathlib import Path

from claude_style import (BEIGE, BLUE, CLAY, CLAY_SOFT, GRAY, GRID, INK, LABEL, MUTED, TEAL,
                          WHITE, line, mono, node, path, rect, save, svg, text, title)

OUT = Path(__file__).resolve().parent.parent / "loop"


# ------------------------------------------------------------- 01 agent 循环
def loop() -> str:
    W, H = 1200, 680
    b: list[str] = []
    title(b, "Agent 循环", "模型决定下一步做什么，harness 负责执行并把结果拼回上下文，直到模型说“做完了”")
    b.append(node(90, 310, 220, 120, "上下文", ["system + 工具定义", "+ 全部历史"], fill=GRAY))
    b.append(node(470, 310, 220, 120, "模型", ["读上下文", "决定下一步"], fill=BLUE))
    b.append(node(850, 190, 250, 110, "执行工具", ["harness 运行命令、读文件", "结果作为 tool_result"], fill=BEIGE))
    b.append(node(850, 460, 250, 110, "结束", ["stop_reason = end_turn", "返回最终回答"], fill=TEAL))
    b.append(line(312, 370, 466, 370, LABEL, 2.5, arrow=True))
    b.append(path("M 692 350 C 770 350, 770 245, 846 245", LABEL, 2.5, arrow=True))
    b.append(text(752, 282, "tool_use", 14, LABEL, "end"))
    b.append(path("M 692 390 C 770 390, 770 515, 846 515", LABEL, 2.5, arrow=True))
    b.append(text(752, 470, "end_turn", 14, LABEL, "end"))
    b.append(path("M 975 186 C 975 120, 200 120, 200 306", CLAY, 2.5, arrow=True, clay=True))
    b.append(text(590, 226, "把调用和结果追加进历史，再调一次模型", 15, CLAY, weight=600))
    b.append(rect(90, 508, 600, 120, WHITE, GRID, 1.5, rx=12))
    b.append(text(110, 540, "harness 额外加的刹车", 15, MUTED, "start", weight=700))
    for i, s_ in enumerate(["最大轮数、token 预算、时间上限", "用户随时打断",
                           "工具出错不抛异常，把错误信息当结果回填"]):
        b.append(text(110, 570 + i * 24, "· " + s_, 14, LABEL, "start"))
    return svg(W, H, b)


# ------------------------------------------------------------- 02 workflow 模式
def workflows() -> str:
    W, H = 1240, 780
    b: list[str] = []
    title(b, "五种 workflow 与 agent",
          "前五种的执行路径由代码写死，模型只负责每一格里的内容；agent 的路径由模型自己决定")
    cw, ch = 380, 300
    cells = [(40, 110), (430, 110), (820, 110), (40, 440), (430, 440), (820, 440)]
    names = ["提示链", "路由", "并行", "编排者-执行者", "评估者-优化者", "agent"]
    subs = ["一步的输出是下一步的输入", "先分类，再交给专门的处理流程", "拆成子任务同时做，或多次投票",
            "模型临时拆任务、分派、汇总", "一个生成，一个打分提意见，循环", "模型在循环里自己决定调用什么"]
    for (x, y), n, s in zip(cells, names, subs):
        hl = n == "agent"
        b.append(rect(x, y, cw, ch, CLAY_SOFT if hl else WHITE, CLAY if hl else GRID, 2 if hl else 1.5,
                      rx=14))
        b.append(text(x + 20, y + 34, n, 18, CLAY if hl else INK, "start", weight=700))
        b.append(text(x + 20, y + 60, s, 14, MUTED, "start"))

    def box(x: float, y: float, w: float = 64, h: float = 40, fill: str = BLUE, lab: str = "LLM") -> None:
        b.append(rect(x, y, w, h, fill, rx=8, sw=2))
        b.append(text(x + w / 2, y + h / 2 + 5, lab, 13, weight=600))

    def arr(x1, y1, x2, y2):
        b.append(line(x1, y1, x2, y2, LABEL, 2, arrow=True))

    b.append('<g transform="translate(0,40)">')
    # 1 chain
    y = 190
    xs = [70, 180, 290]
    for i, x in enumerate(xs):
        box(x, y)
        if i:
            arr(xs[i - 1] + 66, y + 20, x - 4, y + 20)
    b.append(rect(220, 260, 64, 34, GRAY, rx=8, sw=1.5))
    b.append(text(252, 282, "检查", 12))
    b.append(line(212, 232, 240, 258, LABEL, 1.5, dash="4 4"))
    # 2 routing
    box(460, 210, 64, 40, BEIGE, "分类")
    for i, yy in enumerate((160, 210, 260)):
        box(640, yy + 0, 80, 36, BLUE, ["退款", "技术", "其他"][i])
        arr(526, 230, 636, yy + 18)
    # 3 parallel
    box(850, 210, 56, 40, GRAY, "拆分")
    for yy in (160, 210, 260):
        box(960, yy, 64, 36)
        arr(908, 230, 956, yy + 18)
        arr(1026, yy + 18, 1086, 230)
    box(1090, 210, 64, 40, GRAY, "汇总")
    b.append('</g><g transform="translate(0,80)">')
    # 4 orchestrator
    box(70, 500, 80, 44, BEIGE, "编排者")
    for yy in (460, 510, 560):
        box(230, yy, 64, 34)
        arr(152, 522, 226, yy + 17)
    box(330, 500, 64, 44, GRAY, "汇总")
    for yy in (460, 510, 560):
        arr(296, yy + 17, 326, 522)
    b.append(text(210, 630, "子任务的数量和内容由模型决定", 13, MUTED))
    # 5 evaluator
    box(480, 510, 80, 44, BLUE, "生成")
    box(660, 510, 80, 44, BEIGE, "评估")
    b.append(path("M 562 522 C 600 490, 620 490, 656 522", LABEL, 2, arrow=True))
    b.append(path("M 658 544 C 620 576, 600 576, 562 544", LABEL, 2, arrow=True))
    b.append(text(610, 600, "意见", 13, MUTED))
    b.append(text(610, 488, "草稿", 13, MUTED))
    # 6 agent
    box(880, 510, 64, 44, BLUE, "LLM")
    box(1060, 510, 80, 44, BEIGE, "工具")
    b.append(path("M 946 524 C 990 490, 1020 490, 1056 524", CLAY, 2, arrow=True, clay=True))
    b.append(path("M 1058 548 C 1020 580, 990 580, 946 548", CLAY, 2, arrow=True, clay=True))
    b.append(text(1010, 615, "循环多少轮、调什么，都由模型决定", 13, CLAY))
    b.append('</g>')
    return svg(W, H, b)


# ------------------------------------------------------------- 03 harness 部件地图
def harness_map() -> str:
    W, H = 1240, 740
    b: list[str] = []
    title(b, "Agent = 模型 + Harness",
          "模型之外的一切都是 harness；方框里的数字是本系列讲它的那一篇")
    b.append(rect(140, 120, 960, 580, "none", CLAY, 2, rx=24, dash="8 6"))
    b.append(text(620, 150, "Harness", 18, CLAY, weight=700))
    b.append(rect(500, 300, 240, 160, BLUE, rx=16, sw=3, shadow=True))
    b.append(text(620, 368, "模型", 24, weight=700))
    b.append(text(620, 402, "权重固定，只会续写", 14, MUTED))
    b.append(text(620, 426, "第 10 篇讲它怎么被训练", 13, MUTED))
    big = [(170, 180, "01", "system prompt", "参数、结构化输出"),
           (475, 180, "02", "工具", "Bash、computer use、MCP"),
           (780, 180, "03", "循环", "停止条件、错误回填"),
           (170, 330, "04", "反馈与护栏", "测试、lint、hooks、git"),
           (780, 330, "05", "上下文管理", "压缩、卸载、缓存"),
           (170, 480, "06", "Skills", "按需加载的能力"),
           (780, 480, "09", "子 agent", "隔离上下文、并行")]
    small = [(170, 600, "07", "记忆", "跨会话的文件与检索", BEIGE),
             (402, 600, "08", "长时任务", "进度文件、交接", BEIGE),
             (634, 600, "11", "权限与沙箱", "审批、隔离", GRAY),
             (866, 600, "12", "评估", "量出好坏", WHITE)]
    def card(x, y, w, num, name, sub, fill):
        b.append(rect(x, y, w, 72, fill, rx=10, sw=2))
        b.append(rect(x + 10, y + 12, 34, 24, CLAY_SOFT, CLAY, 1.5, rx=6))
        b.append(text(x + 27, y + 29, num, 13, CLAY, weight=700))
        b.append(text(x + 54, y + 30, name, 16, INK, "start", weight=700))
        b.append(text(x + 54, y + 56, sub, 13, MUTED, "start"))
    for x, y, n, nm, sub in big:
        card(x, y, 290, n, nm, sub, BEIGE)
    for x, y, n, nm, sub, f in small:
        card(x, y, 220, n, nm, sub, f)
    return svg(W, H, b)


if __name__ == "__main__":
    save(OUT, "01-loop", loop())
    save(OUT, "02-workflows", workflows())
    save(OUT, "03-harness-map", harness_map())
