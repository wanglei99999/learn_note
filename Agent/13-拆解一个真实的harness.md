# 拆解一个真实的 harness：Claude Code

创建日期：2026-10-17

前面十二篇，从一次 API 调用开始，一层一层往外加：工具、循环、验证、上下文管理、skill、记忆、长任务、子 agent，再到模型的训练、安全和评估。每一篇讲一个部件，讲的时候难免是孤立的。

这一篇拿一个真实的产品，看这些部件放在一起是什么样子。选 Claude Code，一是因为它是目前用得最广的编程 agent 之一，二是因为它的公开文档写得很细，很多设计可以直接对上前面的内容。

先说明两点。这里只用公开的文档和 Anthropic 发表的文章，不涉及任何内部实现。Claude Code 更新很快，下面的内容以 2026 年 10 月的文档为准，具体的工具名、配置项以后可能会变，但背后的设计思路变化不会太快。

## 1. 总览

![Claude Code 的各个部件，对应本系列的哪一篇](assets/real/01-architecture.png)

把第 03 篇那张 harness 地图里的方框，换成 Claude Code 里具体的东西，大致就是这张图。下面按启动、干活、收尾的顺序走一遍。

## 2. 启动时进入上下文的东西

一个会话开始时，上下文里先放进几样固定的东西。

**system prompt 和工具定义。** 这是第 01 篇和第 02 篇的内容，每次调用都会带上。

**CLAUDE.md。** 第 07 篇讲过的项目说明文件。Claude Code 的 CLAUDE.md 可以有好几层：组织统一下发的，用户自己的（放在 `~/.claude/` 下，对所有项目生效），项目的（提交进仓库，团队共享），以及只在本地生效、不提交的。子目录里也可以放 CLAUDE.md，agent 处理那个目录里的文件时才加载。这正好对应第 07 篇说的“目录而不是百科全书”：根目录的说明保持简短，细节分散到相关的位置。

**skill 的元数据。** 第 06 篇讲的三级加载的第一级：每个 skill 只有名字和描述进入上下文，正文要等模型通过 `Skill` 工具调用时才加载。

配置文件也是分层的。从高到低是：组织的托管配置，命令行参数，项目本地配置（`.claude/settings.local.json`），项目共享配置（`.claude/settings.json`），用户配置（`~/.claude/settings.json`）。高层的设置覆盖低层的。这让组织可以统一锁定某些安全策略，团队可以共享项目约定，个人还能保留自己的偏好。

## 3. 工具

### 3.1 工具集

Claude Code 的内置工具大致分几类：

- **读写文件**：`Read` 读文件，`Edit` 做局部修改，`Write` 写整个文件。
- **执行命令**：`Bash`（Windows 上还有 `PowerShell`）。
- **搜索**：`Glob` 按文件名找，`Grep` 按内容找。文档里写着，在 macOS、Linux 和 WSL 上这两个工具默认不提供，搜索直接在 `Bash` 里完成。
- **网络**：`WebFetch` 取网页，`WebSearch` 搜索。
- **编排**：`Agent` 启动子 agent，`Skill` 调用 skill，一组 `Task` 工具管理任务清单，`EnterPlanMode` 和 `ExitPlanMode` 进出计划模式。

第 02 篇讲过，Bash 是通用工具，什么都能做。Claude Code 的工具集就是以 Bash 为核心，再加上少数专用工具。专用工具的意义在第 02 篇也说过：更省 token，权限更好控制，用法更明确。比如 `Read` 不需要权限确认，`Bash` 需要；但文档也写了，`Bash` 里一些只读的命令（`ls`、`cat` 这类）会自动放行。

### 3.2 Edit 用的是字符串替换

`Edit` 工具的用法是：给出文件里一段原有的文字，和要替换成的新文字。原文必须在文件里唯一出现，否则报错。

这正是第 10 篇讲的“模型与 harness 共同演化”的例子。Anthropic 训练 Claude 时大量使用这种字符串替换的编辑方式，Claude Code 也就用它。如果你自己给 Claude 写 harness，照着这个形状设计编辑工具会比较稳。

### 3.3 工具定义的延迟加载

第 02 篇说，MCP 接多了，工具定义会堆满上下文。Claude Code 的做法是 `ToolSearch`：工具很多时，一部分工具只把名字放进上下文，完整的定义（参数的 schema）先不加载。模型需要用某个工具时，先调用 `ToolSearch` 把它的定义取回来，再去调用它。

这就是第 06 篇的三级加载，用在了工具上：名字常驻，定义按需加载。

## 4. 主循环

### 4.1 循环本身

主循环就是第 03 篇那十几行伪代码：模型输出工具调用，harness 执行，结果拼回去，再调用模型，直到模型不再调用工具。交错思考让模型在每次拿到工具结果后都能接着想（第 03 篇、第 10 篇）。工具出错时，错误信息作为工具结果回填，模型自己调整。

### 4.2 计划模式

第 08 篇提到的“先探索、再计划、再执行”，在 Claude Code 里是 plan 模式。进入这个模式后，agent 只能读，不能改，它把相关代码摸清楚，写出一份计划，通过 `ExitPlanMode` 交给用户。用户批准了，才开始修改。

这把“理解问题”和“解决问题”分开了。人在成本最低的时候介入：改一份计划，比回滚一堆代码修改便宜得多。

### 4.3 任务清单

Claude Code 用一组 `Task` 工具（早期版本是一个叫 `TodoWrite` 的工具）维护任务清单：开始时列出要做的步骤，做完一项更新一项。第 05 篇讲过 Manus 的 `todo.md`，原理相同：清单每次更新都出现在上下文的末尾，帮模型记住整体目标；同时用户也能实时看到 agent 打算做什么、做到哪里了。

## 5. 上下文管理

### 5.1 压缩

上下文快满时，Claude Code 会自动压缩：把之前的对话总结成摘要，用摘要开一个新的上下文继续。用户也可以手动执行 `/compact`，还可以附带说明，告诉它压缩时重点保留什么。

第 05 篇引用过 Anthropic 对这个过程的描述：保留架构决定、未解决的 bug、实现细节，丢掉重复的工具输出，压缩后再重新读入最近访问的几个文件。有一个 `PreCompact` hook 可以在压缩前执行自定义的逻辑，比如把当前状态先存进文件。

### 5.2 用 grep，不建索引

Claude Code 一个很有代表性的设计选择，是不给代码库建向量索引，而是让 agent 用 `grep`、`glob` 这样的命令现场搜索。第 05 篇讲过这个取舍：Anthropic 的文章把它描述为一种混合策略，CLAUDE.md 预先加载，具体的代码按需搜索。Claude Code 的开发者在公开访谈里也提到过，他们试过基于向量检索的方案，最后发现让 agent 自己搜索效果更好。

背后有几个原因。代码一直在变，索引很容易过时，而 `grep` 每次查到的都是当前的真实内容。`grep` 是精确匹配，搜函数名、变量名、报错信息这类代码里最常见的查询，比语义检索更准。不需要维护一套索引系统，也就少了一个需要同步、需要保护的东西。代价是 agent 要多花几轮去找，但随着模型越来越会搜索，这个代价越来越小。

这个选择体现了整个 Claude Code 的风格：尽量用简单、通用、透明的原语（文件、shell、文本搜索），把判断交给模型。

## 6. 子 agent

`Agent` 工具启动一个子 agent，它有自己独立的上下文窗口，完成后把结果交回主 agent（第 09 篇）。用户还可以在 `.claude/agents/` 下用 Markdown 文件自定义子 agent：给它单独的 system prompt，限定它能用哪些工具，甚至指定用哪个模型。

第 09 篇引用过 Cognition 对 Claude Code 子 agent 的评价：子 agent 通常只负责回答一个定义清楚的问题，不和主 agent 并行写代码。这是一种保守但稳妥的分工：主 agent 掌握全部上下文，负责所有的决定和修改；子 agent 去做那些读得多、结论短的调查工作，避免把主上下文撑满。

## 7. 护栏：hooks

第 04 篇讲护栏时说过，hooks 是在固定时机必然执行的程序。Claude Code 的 hooks 覆盖了 agent 生命周期里的几十个时机，常用的有：

- `SessionStart`：会话开始时，比如注入一些动态的背景信息。
- `UserPromptSubmit`：用户提交消息后、模型处理前。
- `PreToolUse`：工具执行前。可以检查参数，决定放行、拒绝或者转为询问用户。
- `PostToolUse`：工具执行后。比如每次编辑文件后自动格式化、跑 lint。
- `Stop`：模型准备结束时。比如检查测试是否全部通过，没通过就不让它结束。
- `PreCompact`：压缩前。

hook 是一段普通的脚本。它以退出码 2 退出，或者输出一段带拒绝决定的 JSON，就能拦下对应的动作，并把理由反馈给模型。第 04 篇讲的“每次编辑后自动检查”“没过测试不准结束”，都可以用 hooks 实现。

文档里也写了一句提醒：不要把 hooks 当作硬性的安全边界。hooks 适合守住流程和质量，真正的安全边界在下一节。

## 8. 权限与沙箱

### 8.1 权限模式

Claude Code 有几种权限模式，在便利和监督之间做不同的取舍：

| 模式 | 不用询问就能做的事 | 适合 |
|---|---|---|
| `default` | 只能读 | 每一步都要自己审查的敏感工作 |
| `acceptEdits` | 读、编辑文件、常见的文件系统命令 | 边改边看 |
| `plan` | 只读探索 | 动手之前先想清楚 |
| `auto` | 全部，但有后台的安全检查 | 长任务，减少审批疲劳 |
| `dontAsk` | 只有预先批准的工具，其他一律拒绝 | 锁定的 CI 和脚本 |
| `bypassPermissions` | 全部 | 只在隔离的容器或虚拟机里用 |

`auto` 模式值得多说一句。第 11 篇讲过审批疲劳：确认框太多，人就不看了。`auto` 模式的做法是让另一个模型（文档里叫分类器）代替人去审查 agent 的动作，只有它判断有风险的才拦下来。这是用模型来做一部分安全把关，但它本身也可能出错，所以还要配合下面的沙箱。

除了模式，还可以在配置里写允许和禁止的规则，比如允许 `Bash(npm test)`、禁止读 `.env` 文件。

### 8.2 沙箱

第 11 篇讲的沙箱就来自 Claude Code。文件系统隔离加网络隔离两道边界，用操作系统的机制（Linux 的 bubblewrap、macOS 的 seatbelt）实现，约束 agent 和它启动的所有子进程。网络请求经过沙箱外的代理，按域名白名单放行。网页版的 Claude Code 在云端沙箱里运行，真正的 git 凭据放在沙箱外的代理里，检查请求后才附加上去。

Anthropic 内部的数据是，开启沙箱后，需要用户确认的次数减少了 84%。边界清楚了，边界之内就可以放手。

## 9. 几个设计取舍

把 Claude Code 的这些设计放在一起看，能看出几条一贯的思路。

**用简单的原语。** 文件存记忆，`grep` 搜代码，Bash 执行一切，Markdown 写配置和 skill。这些东西人能直接读、直接改，出了问题容易排查，也不需要额外维护一套系统。

**把判断交给模型，把边界交给程序。** 怎么搜、搜到什么程度、怎么改、什么时候停，都由模型决定。但能碰哪些文件、能连哪些服务器、什么命令绝对不能执行，由操作系统、代理、hooks、权限规则来保证。这正是第 04 篇和第 11 篇反复讲的：重要的约束不靠模型自觉。

**按需加载。** CLAUDE.md 分层、skill 三级加载、工具定义延迟加载、子 agent 隔离上下文，都是在省上下文。第 05 篇说上下文是有限的预算，Claude Code 的很多设计都在围绕这个预算做文章。

**harness 保持薄。** Claude Code 没有为某一类任务写死复杂的流程。具体领域的做法交给 skill、CLAUDE.md 和用户自己的配置，harness 本身只提供通用的机制。第 10 篇说过，模型一升级，为弥补模型弱点而写的复杂逻辑可能就成了累赘；薄的 harness 更容易跟着模型一起进步。

## 10. 回顾

最后把整个系列串一遍。

一次 API 调用里，模型读进一段 token，写出一段 token，什么也不记得，什么也做不了（第 01 篇）。给它工具，它能表达“我想做什么”，由程序替它去做（第 02 篇）。把工具调用放进循环，让模型自己决定下一步，就有了 agent：Agent = 模型 + Harness（第 03 篇）。

agent 会自信地交出错误的结果，所以要给它反馈，用程序守住质量（第 04 篇）。它跑得越久，上下文越长、越贵、越糊涂，所以要管理上下文（第 05 篇），让能力按需加载（第 06 篇），把值得记住的写到上下文之外（第 07 篇），让多个上下文窗口按时间接力（第 08 篇）或者同时分工（第 09 篇）。

这些都是 harness 的部件。另一边，模型自己的 agent 能力是在 harness 里用强化学习练出来的，也带来了钻空子、谄媚这些副作用（第 10 篇）。agent 能做的事越多，越要假设它会犯错、会被注入，用沙箱和权限划定边界（第 11 篇）。所有这些改动是好是坏，要靠评估来回答（第 12 篇）。

这几年模型进步得很快，harness 的很多具体做法会过时。今天要写进 prompt 的规则，明年可能不需要了；今天要拆成十个会话的任务，明年可能一个就够。但有几件事大概不会变：上下文是有限的预算，模型需要外部的反馈才知道自己对不对，安全的边界不能交给模型自己守，以及改了任何东西，都要量一量。

## 小结

- Claude Code 启动时加载 system prompt、工具定义、多层 CLAUDE.md 和 skill 元数据；配置按组织、命令行、项目、用户分层覆盖。
- 工具集以 Bash 为核心，加上读写、搜索、网络、编排等专用工具。`Edit` 用字符串替换，和 Claude 的训练方式一致；工具多时用 `ToolSearch` 延迟加载定义。
- 主循环之外有 plan 模式和任务清单。上下文快满时自动压缩；代码检索用 `grep` 而不是向量索引。
- 子 agent 有独立上下文，主要负责调查；hooks 在几十个固定时机执行，用来守住流程和质量；权限模式和沙箱守住安全边界。
- 设计上的一贯思路：简单的原语，判断交给模型、边界交给程序，按需加载，harness 保持薄。

## 参考

- Anthropic. *Claude Code Docs*：[工具](https://code.claude.com/docs/en/tools-reference)、[Hooks](https://code.claude.com/docs/en/hooks)、[权限模式](https://code.claude.com/docs/en/permission-modes)、[配置](https://code.claude.com/docs/en/settings)、[子 agent](https://code.claude.com/docs/en/sub-agents)、[Skills](https://code.claude.com/docs/en/skills)、[MCP](https://code.claude.com/docs/en/mcp)
- Rajasekaran, P. et al. (Anthropic), 2025. *Effective context engineering for AI agents*. [博客](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Dworken, D. & Weller-Davies, O. (Anthropic), 2025. *Beyond permission prompts: making Claude Code more secure and autonomous*. [博客](https://www.anthropic.com/engineering/claude-code-sandboxing)
- Yan, W. (Cognition), 2025. *Don't Build Multi-Agents*. [博客](https://cognition.com/blog/dont-build-multi-agents)
- Trivedy, V. (LangChain), 2026. *The Anatomy of an Agent Harness*. [博客](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)
