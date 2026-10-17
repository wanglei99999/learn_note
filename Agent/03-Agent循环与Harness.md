# Agent 循环与 Harness

创建日期：2026-10-17

[上一篇](02-工具调用.md)给了模型一组工具，但伪代码里只有一个 `if`：模型调一次工具，拿到结果，然后回答。查天气这样的问题够用了，修一个 bug 就不够了。你得先搜出相关的文件，读代码，找到问题，改，再跑测试；测试没过，再读，再改。每一步做什么，要看上一步看到了什么。

这一篇把 `if` 换成 `while`。这一改，就得到了 agent。然后我们给“agent”下一个这个系列通用的定义：Agent = 模型 + Harness。后面的每一篇，都是在往 harness 里添一个部件。

## 1. Agent 循环

### 1.1 伪代码

```text
messages = [ {role: "user", content: task} ]
for turn in 1 .. MAX_TURNS:
    r = model.call(system = SYSTEM, messages = messages, tools = TOOLS)
    messages.append({role: "assistant", content: r.content})

    if r.stop_reason == "end_turn":
        return r.text                                  # 模型认为做完了

    if r.stop_reason == "tool_use":
        results = []
        for call in r.tool_uses:                       # 可能有多个并行调用
            try:
                out = execute(call.name, call.input)
                results.append(tool_result(call.id, out))
            except error:
                results.append(tool_result(call.id, describe(error), is_error = true))
        messages.append({role: "user", content: results})

    if r.stop_reason == "max_tokens":
        ...                                            # 输出被截断，要单独处理

return "达到最大轮数，任务没有完成"
```

整个 agent 的核心就是这十几行。和上一篇相比，变化只有两处：`if` 变成了循环，以及循环什么时候结束由模型决定。

![Agent 循环](assets/loop/01-loop.png)

每一轮，模型读到的是全部历史：原始任务，它自己之前的每一次调用，每一次调用的结果。它据此决定下一步：再调一个工具，或者宣布完成。harness 负责执行工具、把结果拼回去、再调一次模型。第 01 篇说过 API 是无状态的，所以这里每一轮都是一次完整的调用，上下文一轮比一轮长。

### 1.2 停止条件

循环结束的方式有几种。

正常的结束是模型不再调用工具，直接给出回答，`stop_reason` 是 `end_turn`。这是由模型自己判断的：它认为任务完成了，或者认为做不下去了需要问用户。

除此之外，harness 还要加几道刹车：最大轮数、token 预算、时间上限、用户随时打断。模型可能陷入死循环，比如反复读同一个文件，或者反复尝试同一个失败的命令。没有刹车，一个出了岔子的 agent 能一直烧钱下去。

刹车设多紧是个权衡。设得太紧，正常的长任务做到一半就被掐断；设得太松，失控的时候损失大。第 08 篇讲长时任务时，会看到另一种思路：不追求一次跑完，而是让 agent 能在中断之后接着干。

### 1.3 错误回填

伪代码里有一个细节：工具执行出错时，harness 不抛异常、不退出循环，而是把错误信息包成一个 `tool_result` 塞回去，标记 `is_error`。

这是 agent 能自我纠错的前提。模型调用 `read_file("src/utlis.py")`，拿到“文件不存在，当前目录下有 src/utils.py”，下一轮它就会改成正确的路径。命令执行失败，它能读到报错，然后换一个写法。上一篇说错误信息要写得能告诉模型下一步怎么做，原因就在这里：错误信息是模型下一轮的输入。

## 2. 一次修 bug 的过程

用文字完整走一遍。任务是：“用户反馈注册接口在邮箱带大写字母时报错，修一下。”

| 轮 | 模型做了什么 | 拿到了什么 |
|---|---|---|
| 1 | `grep -rn "register" src/` | 十几行匹配，定位到 `src/api/auth.py` |
| 2 | 读 `src/api/auth.py` | 注册函数调用了 `validate_email()` |
| 3 | `grep -rn "def validate_email" src/` | 在 `src/utils/validators.py` |
| 4 | 读 `validators.py` | 正则是 `^[a-z0-9._]+@[a-z0-9.]+\.[a-z]+$`，没有大写字母 |
| 5 | 修改正则，加上忽略大小写的标志 | 修改成功 |
| 6 | 运行 `pytest tests/test_validators.py` | 2 个通过，1 个失败：另一个测试期望把邮箱存成小写 |
| 7 | 读这个失败的测试 | 原来系统的约定是校验时忽略大小写、存储时统一转小写 |
| 8 | 在注册函数里加上 `email.lower()` | 修改成功 |
| 9 | 再跑一遍测试 | 全部通过 |
| 10 | 不再调用工具，汇报改了什么 | 结束 |

这张表里有三处可以多看一眼。

前四轮全是在找东西。模型一开始对这个代码库一无所知，只能像一个新来的工程师一样，从搜索开始一点点摸清结构。这个过程能不能高效，很大程度上取决于工具：上一篇讲的 `grep` 返回多少行、截不截断，直接影响这几轮的质量。

第 6 轮的失败是好事。测试告诉了模型一件它不知道的事：存储时要转小写。没有这个测试，模型在第 5 轮就会宣布完成，留下一个隐藏的 bug。下一篇专门讲这个。

每一轮的上下文都比上一轮长。到第 10 轮，上下文里有两个完整的文件、几段搜索结果、两次测试输出，加起来可能有一两万 token。这还只是一个很小的 bug。第 05 篇讲怎么管理这个增长。

## 3. 从 ReAct 到交错思考

### 3.1 ReAct

让模型在推理和行动之间交替，这个想法最早系统地出现在 2022 年的 ReAct 论文里（Yao et al.）。那时候还没有原生的工具调用接口，做法是在 prompt 里规定一个格式：

```text
Thought: 我需要先找到注册函数在哪里
Action: search[register]
Observation: src/api/auth.py 第 42 行 ...
Thought: 它调用了 validate_email，我去看看这个函数
Action: ...
```

模型按这个格式续写，生成到 `Action` 那一行就停下来，程序解析出动作并执行，把结果作为 `Observation` 拼回去，再让模型接着写。这就是一个 agent 循环，只不过协议是靠 prompt 约定的文本格式。论文在 ALFWorld（文字版的家务任务）和 WebShop（模拟网购）上，比模仿学习和强化学习的基线分别高出 34 和 10 个百分点的成功率。

ReAct 里的 `Thought` 很关键。只有 `Action` 和 `Observation`，模型容易走一步看一步，忘了自己要干什么；让它在每次行动前写下想法，相当于逼它维护一个计划，并根据观察更新计划。

### 3.2 交错思考

今天的模型已经不需要靠 prompt 约定格式了。工具调用是训练进模型的原生能力，`Thought` 也变成了推理模型的思考块。

但有一个问题：推理模型最初的设计是“先想，再答”，思考只出现在回答之前。放在 agent 循环里，就是每一轮调用开始时想一次。工具结果回来以后，新的一轮调用开始，模型能不能看到自己上一轮的思考，要看接口怎么处理。

交错思考（interleaved thinking）解决的是这个问题：模型在两次工具调用之间可以继续思考，并且之前的思考块保留在上下文里。Anthropic 在 2025 年 5 月随 Claude 4 推出了这个功能。这样，模型拿到测试失败的输出后，可以先想一想“为什么失败、原来的假设哪里错了”，再决定下一步，而不是直接冲向下一个动作。使用时有一个要求：harness 必须把模型返回的思考块原样放回历史里，不能删改。

从 ReAct 到交错思考，思路是一样的：每次行动之前先想一想，每次看到结果之后再想一想。变化在于，这件事从 prompt 技巧变成了模型训练出来的能力。第 10 篇会讲这种能力是怎么训练出来的。

## 4. Workflow 与 Agent

### 4.1 两者的区别

不是所有用到大模型和工具的系统都要做成 agent。Anthropic 在 2024 年 12 月的《Building effective agents》里做了一个区分，后来被广泛引用：

- **workflow**：模型和工具按照代码里预先写好的路径编排。
- **agent**：模型自己动态地决定流程和工具的使用，自己掌控怎么完成任务。

区别在于谁来决定下一步。workflow 里，执行路径是工程师写死的，模型只负责每一步里的内容；agent 里，路径是模型在运行时自己决定的。

### 4.2 常见的 workflow

这篇文章列了五种常见的 workflow 模式：

![五种 workflow 与 agent](assets/loop/02-workflows.png)

- **提示链**：把任务拆成固定的几步，一步的输出作为下一步的输入，中间可以插入程序化的检查。比如先写大纲、检查大纲是否满足要求、再根据大纲写全文。
- **路由**：先对输入分类，再交给专门的处理流程。比如客服系统把退款、技术问题、一般咨询分开处理，简单问题交给小模型，难问题交给大模型。
- **并行**：把任务拆成独立的子任务同时处理，或者同一个任务跑多次投票。比如一个模型处理用户问题，另一个模型同时检查有没有不当内容。
- **编排者-执行者**：一个模型临时决定怎么拆任务，分派给多个执行者，最后汇总。和并行的区别是子任务不是预先定好的。比如要改多少个文件、改哪些，取决于具体的需求。
- **评估者-优化者**：一个模型生成，另一个模型评估并给出修改意见，循环直到满意。比如翻译，评估者能指出译文里不准确的地方。

编排者-执行者已经很接近 agent 了，区别在于它的结构（一个编排者分派、一组执行者干活、最后汇总）仍然是写死的。

### 4.3 什么时候用 agent

Anthropic 在这篇文章里的建议很朴素：先找最简单的方案，只在必要的时候增加复杂度。很多场景一次调用加上检索和几个示例就够了；需要多步的，优先考虑 workflow；只有当步骤数没法预测、路径没法写死的时候，才用 agent。

原因在于 agent 的代价。它更慢，更贵（每一轮都要重发全部上下文），出错的方式更难预测，出了错也更难排查。workflow 每一步做什么是确定的，可以单独测试；agent 的行为路径每次都可能不同。

适合 agent 的任务有几个特征：开放式的，没法事先列出步骤；有清晰的成功标准，最好能自动验证（比如测试通过）；出错的代价可控，或者有人在旁边看着。编程恰好全部符合，这也是为什么编程 agent 是目前最成熟的一类 agent。

## 5. Agent 的定义

“agent”这个词被用得非常乱。2025 年 3 月 TechCrunch 有一篇文章，标题就叫“没人知道 AI agent 到底是什么”，列举了各家公司对 agent 的不同定义：有的说是能自主完成任务的系统，有的说是带工具的模型，有的把一个预设流程的聊天机器人也叫 agent。

这个系列采用一个比较窄、但比较清楚的定义。Simon Willison 在 2025 年 9 月总结过一句：

> An LLM agent runs tools in a loop to achieve a goal.

一个 LLM agent 在循环里调用工具，以达成一个目标。三个要素：工具、循环、目标。第 1 节的伪代码就是这句话的直接实现。按这个定义，第 4 节里的 workflow 都不算 agent，因为它们的循环（如果有的话）不是由模型控制的。

## 6. Agent = 模型 + Harness

### 6.1 Harness

第 1 节的伪代码里，模型只出现在一行：`model.call(...)`。其余的一切，system prompt 怎么写，提供哪些工具，工具怎么执行，结果怎么拼回去，什么时候停，出错了怎么办，都是模型之外的代码。

LangChain 的 Vivek Trivedy 在 2026 年 3 月的文章里把这部分叫作 harness（原意是马具，套在马身上让它的力气能用来拉车）：

> Agent = Model + Harness. If you're not the model, you're the harness.

harness 包括 system prompt，工具、skills 和 MCP 以及它们的描述，捆绑的基础设施（文件系统、沙箱、浏览器），编排逻辑（启动子 agent、交接、模型路由），以及在固定时机执行的 hooks 和中间件（压缩上下文、自动续写、跑 lint 检查）。

这篇文章的推导方式我很喜欢：从“我们希望 agent 做到什么”出发，看“模型本身做不到什么”，再看“harness 要补什么”。模型不能执行代码，所以要有 Bash 和沙箱；模型没有跨会话的记忆，所以要有文件系统；模型的上下文有限，所以要有压缩和卸载。第 01 篇结尾那张“做不到”的表，就是这个推导的起点。

![Agent = 模型 + Harness](assets/loop/03-harness-map.png)

这张图是这个系列的地图，方框里的数字是讲它的那一篇。中间的模型是第 10 篇的主题，其余全部是 harness。第 13 篇会拿一个真实的产品对照这张图，看每个部件在实际中是什么样子。

### 6.2 Harness 的分量

同一个模型，换一个 harness，表现能差很多。

Trivedy 在文章里举了两个例子。一是 Terminal-Bench 2.0 的排行榜上，同一个 Opus 4.6 模型，在 Claude Code 里的得分明显低于在另一些 harness 里的得分。二是他们自己的编程 agent，只改 harness、不换模型，排名从 30 名开外升到了前 5。

反过来，模型的训练也会适应 harness。模型在后训练时是在某个特定的 harness 里跑任务的，用的是那个 harness 的工具和格式。换到另一个工具设计不同的 harness 里，表现可能会掉。这个“共同演化”的问题留到第 10 篇。

### 6.3 三个阶段

回头看这几年大家关注的重点，大致有一条线：

- **提示词工程**（2022 到 2024 年左右）：怎么写一段 prompt，让模型一次答好。优化的对象是一次调用的输入。
- **上下文工程**（2025 年）：agent 跑起来以后，上下文是一轮轮累积出来的，里面有 system prompt、工具定义、历史、工具结果、检索到的文档。优化的对象变成了“每一轮放进上下文窗口的全部内容”。
- **Harness 工程**（2026 年）：再往外一层，优化的对象变成模型之外的整个系统：工具、循环、验证、权限、环境。OpenAI 在 2026 年 2 月的一篇文章就叫《Harness engineering》，讲他们怎么用 agent 写出一个百万行代码的产品，下一篇会讲到。

这三个阶段是一层包一层的关系，后一个包含前一个。写好 prompt 仍然重要，只是不再够用了。

## 7. 最简单的 agent 还缺什么

第 1 节那十几行伪代码已经是一个能干活的 agent。把它接上 Bash 和文件读写工具，它能修第 2 节那样的 bug。

但它有一个明显的问题，在第 2 节的表格里已经露出来了：模型自己决定什么时候结束。如果那个项目没有测试，或者模型没想到去跑测试，第 5 轮它就会说“修好了”，然后结束。它不是在撒谎，它是真的觉得修好了。

怎么让 agent 知道自己有没有做对，是下一篇的内容。

## 小结

- agent 的核心是一个循环：调用模型，执行它要求的工具，把结果拼回上下文，再调用模型，直到它不再调用工具。
- 循环由模型决定何时结束，harness 要另外加最大轮数、预算、超时等刹车。工具出错时把错误信息当成结果回填，模型才能自己纠错。
- ReAct 在 2022 年用 prompt 格式实现了“想一步、做一步”；今天的模型通过交错思考原生地做到了这一点。
- workflow 的路径由代码决定，agent 的路径由模型决定。能用简单方案就不用 agent。
- 这个系列的定义：agent 是在循环里调用工具以达成目标的模型。Agent = 模型 + Harness，模型之外的一切都是 harness。同一个模型换一个 harness，表现能差很多。

## 参考

- Schluntz, E. & Zhang, B. (Anthropic), 2024. *Building effective agents*. [博客](https://www.anthropic.com/engineering/building-effective-agents)
- Yao et al., 2022. *ReAct: Synergizing Reasoning and Acting in Language Models*. [arXiv:2210.03629](https://arxiv.org/abs/2210.03629)
- Anthropic. *Extended thinking: interleaved thinking*. [文档](https://docs.claude.com/en/docs/build-with-claude/extended-thinking)
- Trivedy, V. (LangChain), 2026. *The Anatomy of an Agent Harness*. [博客](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)
- Willison, S., 2025. *I think "agent" may finally have a widely enough agreed upon definition to be useful jargon now*. [博客](https://simonwillison.net/2025/Sep/18/agents/)
- Wiggers, K. (TechCrunch), 2025. *No one knows what the hell an AI agent is*. [文章](https://techcrunch.com/2025/03/14/no-one-knows-what-the-hell-an-ai-agent-is/)
