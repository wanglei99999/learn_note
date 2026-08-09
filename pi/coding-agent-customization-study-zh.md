# Pi Coding Agent：扩展与个性化带读笔记

这份笔记从 `skills.md` 开始，记录 Pi 扩展机制相关文档（skills、prompt-templates、themes、keybindings、packages、extensions）的带读内容。

目前读过：

- `skills.md`
- `prompt-templates.md`
- `themes.md`
- `keybindings.md`
- `packages.md`
- `extensions.md`（进行中：已读片 1 骨架 + 片 2 事件系统，剩 ctx / API 方法 / 自定义工具与 UI）

## 1. skills.md：给模型发"说明书"

一句话主线：**Skill 不是给 pi 加功能，是给模型发说明书**——五种扩展机制里唯一不写宿主代码的，纯 Markdown + 可选脚本。Pi 实现 [Agent Skills 标准](https://agentskills.io/specification)，宽松校验（违规大多只警告）。

### 结构

装着 `SKILL.md` 的文件夹，其余自由：

```text
my-skill/
├── SKILL.md      # 必需：frontmatter + 指令
├── scripts/      # 可选辅助脚本
├── references/   # 可选深度文档
└── assets/
```

frontmatter 必填仅两个：`name`（小写-连字符、≤64 字符、不能首尾/连续连字符）、`description`（≤1024 字符）。**缺 description 不加载**——唯一的硬校验；同名冲突先发现者胜。Pi 允许 name 与父目录名不同（有意偏离标准，便于多 harness 共享 skill 目录）。

### 核心机制：渐进式披露（progressive disclosure）

上下文是稀缺资源（呼应 compaction 篇），skill 的解法：

```text
启动     → 仅 name + description 以 XML 列表进系统提示词
任务匹配 → 模型自己用 read 加载完整 SKILL.md
执行     → 按指令以相对路径调用 scripts/
```

闲置 skill 只占一行描述的成本。**description 是命门**——模型靠它决定何时加载：

- 好：`Extracts text and tables from PDF files... Use when working with PDF documents.`（做什么 + 何时用）
- 差：`Helps with PDFs.`

### 两条触发路径

| 路径 | 方式 | 备注 |
| --- | --- | --- |
| 模型自主 | 任务匹配 description → read | 模型"并不总是这样做"（文档原话） |
| 用户强制 | `/skill:name [args]` | 参数以 `User: <args>` 追加；`enableSkillCommands` 可开关 |

`disable-model-invocation: true` = 不进系统提示词的"纯手动" skill。

### 加载位置与信任

全局 `~/.pi/agent/skills/`、`~/.agents/skills/` → 项目 `.pi/skills/`、沿祖先向上的 `.agents/skills/`（**须项目已信任**）→ pi 包 → settings `skills` 数组 → CLI `--skill`（叠加于 `--no-skills` 之上）。

发现规则：`~/.pi/agent/skills/` 与 `.pi/skills/` 根目录的裸 `.md` 是独立 skill（pi 仓库的 `.pi/skills/add-llm-provider.md`、启动头部的 `[Skills] add-llm-provider` 即此例）；含 `SKILL.md` 的目录递归发现；`.agents/skills/` 根目录裸 `.md` 忽略。

**跨 harness 复用**（实用）：`{ "skills": ["~/.claude/skills"] }` 一行配置直接吃 Claude Code 的 skill。

### skill vs extension 边界（为 extensions.md 埋桩）

> 能靠"说明书 + 脚本"教会模型的 → skill；需要挂事件、注册工具、画 UI 的 → extension。

skill 不新增能力，只是知识（模型本有 read/bash，skill 教它何时如何组合）。这也是 "No MCP" 哲学的具体形态：与其起 MCP 服务器，不如写带 README 的 CLI 工具。

### 安全

skill 可指示模型执行任何操作、可携带可执行代码——装第三方 skill 前先审查（呼应 security 篇：项目 skill 在 trust 之后才加载）。

## 2. prompt-templates.md：把反复打的字变成斜杠命令

一句话：**模板 = 存起来的 prompt**，`/name` 展开成完整文字发给模型。纯字符串替换，无运行时机制——比 skill 还轻。

### 格式：文件名即命令名

```markdown
<!-- ~/.pi/agent/prompts/review.md → /review -->
---
description: Review staged git changes   # 可选，缺省取正文第一行非空内容
argument-hint: "[focus]"                 # 可选，自动补全里的参数提示
---
Review the staged changes (`git diff --cached`). Focus on: ...
```

`argument-hint` 中 `<必填>` / `[可选]` 是给人看的约定。

### 参数语法（借鉴 shell）

| 写法 | 含义 |
| --- | --- |
| `$1`、`$2` | 位置参数 |
| `$@` / `$ARGUMENTS` | 全部参数拼接 |
| `${1:-default}` | 参数 1 为空时用默认值 |
| `${@:-default}` | 无参数时用默认值 |
| `${@:N}` / `${@:N:L}` | 从第 N 个起的全部 / L 个 |

```markdown
Create a React component named $1 with features: $@
Summarize in ${1:-7} bullet points.
```

调用：`/component Button "onClick handler" "disabled support"`

### 加载位置

与 skill 同构：全局 `~/.pi/agent/prompts/*.md` → 项目 `.pi/prompts/*.md`（**须信任**）→ 包 → settings `prompts` → CLI `--prompt-template`；`--no-prompt-templates` 禁用发现。

**坑**：发现**非递归**，子目录模板需在 settings 或包清单里显式添加。

### 活教材：pi 仓库自带的五个模板

启动画面 `[Prompts] /cl, /is, /pr, /sa, /wr` 即 `.pi/prompts/` 下五个文件，是"维护者用 pi 开发 pi"的工作流标本：

| 命令 | 用途 |
| --- | --- |
| `/cl` | 发版前审计 changelog（找 tag → 列提交 → 逐条核对） |
| `/is` | 分析 GitHub issue |
| `/pr` | 从 URL 审 PR |
| `/sa` / `/wr` | 端到端完成任务 |

用法要领：**把"每次都要跟模型解释一遍的固定流程"写下来，从此一个斜杠搞定。**

### 三兄弟边界（第二次划线）

| 机制 | 是什么 | 谁触发 | 何时进上下文 |
| --- | --- | --- | --- |
| prompt template | 存起来的用户输入 | **只有你**（`/name`） | 展开瞬间 |
| skill | 给模型的说明书 | 你**或模型自己** | 描述常驻、正文按需 |
| extension | 改变 pi 行为的代码 | 事件驱动 | 不适用（代码非文本） |

关键差异：**模板永远等你开口，skill 模型可以自己伸手拿。** → "每次我都想让它这么干"用模板；"该用时希望它自己知道"用 skill。

## 3. themes.md：51 个颜色 token 的 JSON（开发优先级最低）

主题是唯一**不影响能力、只影响观感**的扩展机制——纯 JSON 数据，无逻辑无代码。

### 格式与 vars 机制

```json
{
  "$schema": "https://.../theme-schema.json",   // 启用编辑器补全与校验，别删
  "name": "my-theme",                            // 必填、唯一、不能含 /
  "vars": { "primary": "#00aaff", "secondary": 242 },
  "colors": { "accent": "primary", "text": "", ... }   // 必须齐 51 个 token
}
```

`vars` 是精髓（CSS 变量思路）：51 个 token 引用少数几个变量 → **改一处换全身**。`thinkingMax` 可缺省，回退 `thinkingXhigh`。

### 51 个 token 的六组分类（查表用，不背）

| 组 | 数量 | 含 |
| --- | --- | --- |
| 核心 UI | 11 | accent / border / success / error / warning / text… |
| 背景与内容 | 11 | 各类消息与 tool 框（pending/success/error 三态） |
| Markdown | 10 | 标题 / 链接 / 代码 / 引用 / 列表 |
| Tool Diff | 3 | 新增 / 删除 / 上下文行 |
| 语法高亮 | 9 | 注释 / 关键字 / 函数 / 字符串… |
| 思考级别边框 | 6+1 | 编辑器边框随思考等级变色 |
| Bash 模式 | 1 | `!` 前缀时的边框色 |

**反过来读这张表 = 一份 pi 界面元素清单**，写 extension 画 UI 时要引用这些 token 保持视觉一致。

### 颜色值四种写法

| 格式 | 例 | 备注 |
| --- | --- | --- |
| 十六进制 | `"#ff0000"` | 最常用 |
| 256 色 | `242` | **数字不加引号** |
| 变量 | `"primary"` | 引用 vars |
| 默认 | `""` | **用终端自己的颜色**（把决定权还给用户） |

### 要点

- **热重载**：编辑激活中的主题文件即时生效（纯数据无副作用，故独享此待遇）
- 首次运行 pi 会**检测终端背景色**自动选 dark/light
- 做主题的现实路径：**复制内置 dark.json 改**，或直接让 pi 写
- VS Code 用户须设 `terminal.integrated.minimumContrastRatio: 1`，否则看到的不是真实颜色

## 4. keybindings.md：按键 id 映射（含一条开发硬规矩）

`~/.pi/agent/keybindings.json` 覆盖默认值；改完 `/reload` 生效，无需重启。

### ★ 开发硬规矩：永不硬编码按键

文档明写：**extension 作者在 `keyHint()` 和注入的 `keybindings` 管理器中使用的是同一套带命名空间的 id**。项目 `CLAUDE.md` 对应规则：

> Never hardcode key checks (`matchesKey(keyData, "ctrl+x")`) — add defaults to `DEFAULT_EDITOR_KEYBINDINGS` / `DEFAULT_APP_KEYBINDINGS`.

**为什么**：用户可能改过绑定。硬编码 → 用户改键后你的功能失灵，且 `/hotkeys` 里看不到你的键，整个可配置体系被捅洞。`keyHint()` 会查用户实际绑定再显示提示。

### 命名空间 = 包边界

| 前缀 | 归属 | 例 |
| --- | --- | --- |
| `tui.editor.*` / `tui.input.*` / `tui.select.*` | packages/tui | `tui.editor.cursorUp` |
| `app.*` | packages/coding-agent | `app.session.tree`、`app.model.select` |

旧式无命名空间 id 启动时自动迁移。

### 两个值得注意的点

1. **部分动作默认无绑定**（`app.session.new/tree/fork/resume`）——只能斜杠命令触发，想绑键得自己加。
2. **同键在不同上下文含义不同**：`ctrl+d` = 编辑器删字符 / 会话选择器删会话 / 树视图切筛选——这正是命名空间存在的意义，互不冲突。

### 配置写法

```json
{ "tui.editor.cursorUp": ["up", "ctrl+p"] }   // 一个动作可绑多键；用户配置整体覆盖默认
```

文档附 Emacs / Vim 两套可直接抄的示例。Windows 注意：`app.suspend` 无默认绑定（终端不支持 Unix 作业控制）。

## 5. packages.md：前四种资源的分发容器

**包不是第五种资源类型，而是前四种的盒子**——正是五层加载位置里的第三层「包」。

### ★ 安全：无沙箱、无审核

> Pi 包以完整系统权限运行。extension 执行任意代码，skill 可指示模型执行任何操作。安装第三方包前请审查源码。

对比 VS Code 插件/Chrome 扩展（有审核有沙箱），**`pi install` 约等于 `curl | sh`**。这是"核心极简 / No permission popups"哲学的代价，安全责任在用户。三道防线：**`-e` 试用 → 版本固定 → 读源码**。

### 安装管理

```bash
pi install npm:@foo/bar@1.0.0 | git:github.com/user/repo@v1 | ./local/path
pi remove / pi list
pi update [--all|--extensions|--self|--models|<source>]
pi -e npm:@foo/bar     # 试用：临时目录，仅本次运行有效
```

- 默认写入全局设置，`-l` 写入项目设置
- **项目安装的妙处**：配置进 git，队友克隆并信任后 **pi 启动自动补装缺失包** → 团队工具链一键同步

### 三种来源与 ref 固定

| 来源 | 写法 | 位置 |
| --- | --- | --- |
| npm | `npm:@scope/pkg@1.2.3` | `~/.pi/agent/npm/` 或 `.pi/npm/` |
| git | `git:github.com/user/repo@v1`（也支持 ssh/https） | `~/.pi/agent/git/<host>/<path>` |
| 本地路径 | `./path`、`/abs/path` | **不复制，原地引用** |

**ref 固定（pinning）**：带版本/tag/commit 的来源被固定，`pi update` **跳过**它们；升级须显式 `pi install ...@new-ref`。设计动机呼应安全——**你审查过的那个版本不会被偷偷换掉**。

**本地路径对开发最有用**：`.pi/extensions/my-ext.ts` 原地引用 + `/reload` 即时生效，无需打包安装。

### 创建包：清单或约定目录

```json
{
  "name": "my-package",
  "keywords": ["pi-package"],          // 供 pi.dev/packages 展示页发现；可加 video/image 预览
  "pi": {
    "extensions": ["./extensions"], "skills": ["./skills"],
    "prompts": ["./prompts"], "themes": ["./themes"]
  }
}
```

无清单则按约定目录自动发现：`extensions/`(.ts/.js)、`skills/`(SKILL.md 递归 + 顶层 .md)、`prompts/`(.md)、`themes/`(.json)——**与本地 `~/.pi/agent/` 下的规则完全一致**，学一次处处适用。

### ★ 三类依赖（开发者必读）

同一个问题的三个答案：**这份代码运行时从哪来？**

| 情况 | 放哪 | 原因 |
| --- | --- | --- |
| 普通第三方库 | `dependencies` | pi 安装时跑 `npm install` 自动装 → **npm 下载** |
| **pi 核心包**（pi-ai / pi-agent-core / pi-coding-agent / pi-tui / typebox） | **`peerDependencies` + `"*"`** | pi 本体已内置 → **宿主提供** |
| 其它 pi 包 | `dependencies` + `bundledDependencies` | pi **按文件路径**加载资源，必须实际存在于 `node_modules/xxx/` → **自己带着** |

- **核心包若误写 dependencies 的后果**：内存中出现两份副本，类型对不上、`instanceof` 失败、单例被打破（如注册的 provider 落在另一个 Models 实例里，pi 看不见）。
- **其它 pi 包为何必须 bundled**：`pi` 清单里要写 `node_modules/shitty-extensions/extensions` 这类路径；只写 dependencies 时 npm 可能 hoist 到别处，路径指空。pi 以独立模块根加载各包，捎带副本不会冲突。

### 其余（用到再查）

- **包过滤**：对象形式 + glob（`!排除`、`+强制含`、`-强制排`），只能在清单允许范围内收窄
- **`pi config`**：交互式开关各资源，Tab 切换全局/项目
- **去重**：同包同时在全局与项目 → 项目优先（除非 `autoload: false` 则叠加）；身份 = npm 包名 / git URL(去 ref) / 本地绝对路径

## 6. extensions.md（片 1-2）：事件系统——"在不同的位置进行 on 监控"

全文 2900 行，按功能切五片。已读：片 1 骨架（1-274 行）、片 2 事件系统（275-926 行）。

### 片 1：骨架

**Extension = 跑在 pi 进程里的 TS 模块**（jiti 加载，无需编译）。模板是文本、skill 是文本+脚本、extension 是代码——它和 pi 同进程同内存，所以能"改变 pi 的行为"。

**核心写法：**

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {     // ← 工厂函数
  pi.on("事件名", async (event, ctx) => { ... }); // 订阅事件
  pi.registerTool({ ... });                       // 注册工具/命令/快捷键/标志
}
```

**工厂函数**：加载时被调用**一次**、只做登记的函数；跑完就结束。真正干活的是你注册的 handler（事件发生时每次被调）。

| | 工厂函数体 | handler |
| --- | --- | --- |
| 何时运行 | 加载时一次 | 事件发生时每次 |
| 拿到什么 | `pi`（注册用） | `event` + `ctx`（操作用） |
| 该干什么 | 只做注册 | 干实际的活 |

**四条规矩：**

1. `pi` 注册 / `ctx` 操作，别混
2. **放进 `.pi/extensions/` 或 `~/.pi/agent/extensions/` 才能 `/reload` 热重载**；`pi -e` 只适合一次性试用（不能热重载）
3. **工厂函数不启动后台资源**（`pi --list-models`、`pi config` 等不开 session 的命令也会调它，socket/定时器会卡住进程）——推迟到 `session_start`，配对幂等的 `session_shutdown` 清理
4. 导入 pi 核心包（pi-ai / pi-agent-core / pi-coding-agent / pi-tui / typebox）→ peerDependencies `"*"`（呼应 packages 篇）

组织形式三种：单文件 / 目录+index.ts / 带 package.json 的包。异步工厂函数会被 pi 等待（早于 session_start / resources_discover / provider 注册应用）。

### 片 2：事件系统的本质

> **pi 在运行的每个环节都喊一嗓子，你可以在任何一嗓子上挂个函数。** 剩下的全是查表。

**四层嵌套 = 会话树同构：**

```text
session（一次 pi 运行）
 └ agent（一次 prompt→回答完）
    └ turn（一次 LLM 调用+工具执行，循环多次）
       └ tool（单个工具执行）
```

**权限界定（自己总结的框架，已验证）：**

- **纯时间态**（报时，无待决事项）→ 只能看：`*_start` / `*_end` / `*_update` / `*_settled` / `model_select` 等
- **过程态**（pi 手里握着待处理的东西）→ 能改：`before_*`、`tool_call`、`tool_result`、`input`、`context`、`project_trust`
- 同一件事常成对出现：`session_before_compact`（过程态，能改）+ `session_compact`（时间态，通知）
- 判定方法：文档生命周期图的注解（"可阻止/可修改"）→ TS 返回类型 → 终极权威 `runner.ts` 的 emit 方法

**返回值约定（源码 `core/extensions/runner.ts` 验证）：**

| 你返回 | pi 反应 | 多 extension 时 |
| --- | --- | --- |
| `undefined` | 当你没意见 | 问下一个 |
| `{ block: true }`（tool_call） | 不执行工具 | **短路**：一票否决，后面不问 |
| `{ cancel: true }`（session_before_*） | 取消操作 | **短路** |
| 补丁 `{ content... }`（tool_result） | 替换对应字段 | **中间件链**：依次累积 |
| 任何值（通知类事件） | **无视** | 挨个通知 |

源码要点：每类事件有专属 emit 方法（emitToolCall :956 / emitToolResult :900 / 通用 emit :820）；严格按加载顺序+注册顺序**串行**执行；错误隔离（单 handler 异常不拖垮别人）——**唯一例外 emitToolCall 无 try/catch**，安全策略异常必须炸出来，绝不静默放行。pi 会 `await` handler，所以能弹窗阻塞等待用户。

**关键事件速查（想做 X → 挂哪个）：**

| 我想…… | 事件 |
| --- | --- |
| 拦截/修改工具调用 | `tool_call` |
| 修改工具结果（脱敏/截断） | `tool_result` |
| 每轮注入信息 / 改系统提示词 | `before_agent_start` |
| 改发给 LLM 的消息数组 | `context`（每次 LLM 调用前，深拷贝，非破坏性） |
| 拦截/改写用户输入、自造语法 | `input` |
| 接管 `!`/`!!` 命令执行 | `user_bash` |
| 自定义压缩算法 | `session_before_compact` |
| 初始化 / 清理 | `session_start` / `session_shutdown`（幂等） |
| 尘埃落定后做事（commit/通知） | `agent_settled`（不是 agent_end！） |
| 改 HTTP 层 | `before_provider_headers` / `before_provider_request` |

**必记的坑与细节：**

- **切会话（/new /resume /fork）= extension 整个重载**：`session_shutdown` → 重新加载重新绑定 → `session_start`。**闭包变量清零**！跨会话状态要存文件或 `pi.appendEntry()`
- `agent_end` 之后还可能重试/自动压缩/跑队列消息；**真结束用 `agent_settled`**（其中 `ctx.isIdle()` 为 true）
- `tool_call`：`event.input` **可变**，就地改参数（改后**不重新校验**）；返回值只管 block；用 `isToolCallEventType("bash", event)` 收窄类型；并行模式下**看不到兄弟工具的结果**
- `tool_result`：部分补丁（content/details/isError/usage 各自可选）；嵌套异步要传 **`ctx.signal`**（Esc 才能取消你的 fetch）
- `before_agent_start`：`systemPrompt` 链式传递（要 `event.systemPrompt + 追加`，别从头构造）；`systemPromptOptions` 提供 pi 构建系统提示词的全部结构化原料
- `session_before_compact`：`preparation.firstKeptEntryId` 已算好切点（呼应 study 08），只需供 summary；reason 三值 manual/threshold/overflow
- `tool_execution_*` 并行时序：start 按声明顺序、end 按完成顺序、最终 toolResult 消息仍按声明顺序
- `before_provider_headers` 每请求只跑一次，**重试复用**（别放时间戳）

**user_bash 三档力度**（通用模式：拦截/加工/换后端）：

```text
方式3 编结果   return { result: {output, exitCode, cancelled, truncated} }  ← 即 bashExecution 的四字段
方式2 包一层   包装 createLocalBashOperations()，命令改完转交本地执行
方式1 换后端   return { operations: 自己的 exec }，如 SSH 远程执行
```

**input 五站流水线：**

```text
extension命令检查 → 【input 事件】→ skill 展开 → 模板展开 → agent 开始
```

站在第 2 站，看到的是原始文本。三动作：`continue`（放行）/ `transform`（改完再过，链式）/ `handled`（到我为止，模型零感知，第一个 handled 生效）。`event.source` 区分 interactive/rpc/extension（防自己注入的消息触发自己）。

自造语法例（自测通过）：

```typescript
pi.on("input", async (event) => {
  if (event.text.startsWith("?en "))
    return { action: "transform", text: `把下面的内容翻译成英文: ${event.text.slice(4)}` };
});
```

**全系统一句话**：pi 走到某步停下来问你，你的回答永远三选一——**"你继续" / "改成这样再继续" / "别继续了"**。



## 本册小结：贯穿前五篇的三条主线

**1. 五层加载位置**（每篇都出现，已成肌肉记忆）

```text
全局(我的) → 项目(我们的,须信任) → 包(别人的) → 设置(特殊路径) → CLI(这一次)
```

**2. 扩展机制按重量分层**

```text
prompt template  纯文本替换   你触发       最轻
skill            文本+脚本    模型可自主
extension        代码         事件驱动     最重
```

判断标准：**改变"模型知道什么" → skill；改变"pi 做什么" → extension。**

**3. 极简哲学的代价**：核心不做权限沙箱与包审核，安全责任转移给用户（`-e` 试用 + 版本固定 + 读源码）。

**热重载清单**（开发时的关键差异）：主题（纯数据，编辑即生效）、keybindings / extensions / skills / prompts / themes（`/reload` 生效）。
