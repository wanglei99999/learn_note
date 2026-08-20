# Pi Coding Agent 文档带读笔记

这份笔记记录 `docs-zh/coding-agent` 的带读内容，方便后续复习。每读完一篇，就继续往这里追加。

目前读过：

- `index.md`
- `quickstart.md`
- `usage.md`
- `providers.md`
- `llama-cpp.md`
- `security.md`
- `containerization.md`
- `json.md`

## 1. index.md：Pi 是什么

Pi 是一个极简的终端 Coding Agent 运行框架。它没有把各种工作流全部写进核心，而是让用户通过以下机制扩展：

- Extension
- Skill
- Prompt Template
- Theme
- Pi Package

理解整个项目时可以一直抓住一条主线：

> Pi 更像一个可扩展的 Agent 运行框架，而不是功能全部内置的编码工具。

它有四种主要运行方式：

| 方式 | 用途 |
|---|---|
| 普通 `pi` | 人在终端 UI 中持续交互 |
| `pi -p` | 执行一次请求，输出最终回答后退出 |
| `pi --mode json` | 执行请求并输出完整生命周期事件流 |
| `pi --mode rpc` | 保持进程运行，供其他程序双向控制 |

其中，JSON 模式偏向观察执行过程，RPC 模式偏向控制 Pi。

## 2. quickstart.md：Pi 怎么运行起来

### 基本运行模型

```text
当前项目目录
  + AGENTS.md 项目规则
  + 用户请求
  + 模型
  + 文件和命令工具
  = 一次 Pi Session
```

从哪个目录启动 `pi`，哪个目录就是它主要操作的项目。这会影响：

- Pi 能看到哪些文件
- 加载哪些 `AGENTS.md`
- 命令在哪个目录执行
- Session 按哪个工作目录保存

### Pi、Provider 和 Model

Pi 本身不提供模型，它负责组织 Agent 运行；实际推理由 Provider 提供的 Model 完成。

```text
Pi       = Agent 运行框架
Provider = 模型服务提供方
Model    = 实际执行推理的模型
```

认证可以使用订阅登录，也可以使用 API Key：

```text
/login
```

或者在启动前设置相应 Provider 的环境变量。

### 默认工具与 Agent 循环

文档列出的默认工具是：

- `read`：读取文件
- `write`：创建或覆盖文件
- `edit`：修改文件
- `bash`：运行命令

另外还有 `grep`、`find`、`ls` 等内置只读工具，可以通过工具选项启用。

最基本的 Agent 循环是：

```text
用户提出任务
    ↓
模型判断是否需要调用工具
    ↓
Pi 执行工具
    ↓
工具结果返回模型
    ↓
模型继续调用工具或给出回答
```

后面读源码时，需要寻找这条循环分别在哪些包和类中实现。

### AGENTS.md

Pi 会加载全局、父目录和当前目录中的 `AGENTS.md` 或 `CLAUDE.md`，用来约束项目中的工作方式，例如：

```markdown
- 修改代码后运行 npm run check
- 不执行生产环境迁移
- 保持回答简洁
```

修改这些文件后，需要重启 Pi 或执行 `/reload`。

### Session

Session 会自动保存，可以通过以下方式恢复：

```text
pi -c                  继续最近的 Session
pi -r                  浏览历史 Session
pi --name "my task"    设置 Session 名称
pi --session <path|id> 打开指定 Session
```

Pi 的 Session 不只是线性聊天记录，它还支持树状分支、Fork、Clone 和上下文压缩。

本篇最需要记住的是：

> Pi 的最小核心是模型、工具、项目上下文和可持久化 Session，其余能力主要建立在这个核心上。

## 3. usage.md：用户如何操作 Pi Agent

`usage.md` 本质上是 Pi Coding Agent 的用户操作手册，也是外部行为的说明书。它描述的是 Agent 怎么被使用，不是 Agent 内部怎么实现。

### 交互界面

Pi 的终端 UI 分为四个区域：

1. 启动头部：显示快捷键、上下文文件、Skill、Extension 和提示词模板。
2. 消息区：显示用户消息、模型回复、工具调用、结果、通知和错误。
3. 编辑器：输入任务，边框颜色反映 Thinking 级别。
4. 底栏：显示工作目录、Session、模型、Token、缓存、费用和上下文占用。

编辑器并不是固定组件。内置界面或 Extension 可以临时替换它，也可以增加选择器、状态栏和自定义终端组件。

### `@文件` 与模型主动读取

```text
@src/app.ts 解释这个文件
```

两种读取方式的区别：

- `@文件`：用户明确把文件加入当前消息。
- `read`：模型在执行过程中判断是否需要读取。

目标文件明确时，`@` 更直接；探索项目时，让模型主动调用工具更自然。

### `!command` 与 `!!command`

```text
!git status
```

命令会执行，输出也会发送给模型。

```text
!!npm run format
```

命令会执行，但输出不会加入模型上下文。

```text
!command  = 执行 + 模型可见
!!command = 执行 + 模型不可见
```

后者适合输出很长、但模型不需要分析的命令，可以减少上下文占用。

### Steering 与 Follow-up

Agent 仍在工作时，用户可以继续发送消息。

按 Enter 提交的是 Steering 消息。它会在当前工具调用结束后尽快交给 Agent，用来纠正正在执行的任务，例如：

```text
先不要修改文件，只分析调用链
```

按 Alt+Enter 提交的是 Follow-up 消息。它会等当前任务完成后再处理，例如：

```text
完成后再补一份测试
```

```text
Steering：改变正在执行的任务
Follow-up：当前任务结束后继续做
```

Pi 的默认 Enter 行为比较特别。很多其他 Coding Agent 的 Enter 更接近 Pi 的 Alt+Enter，只负责排队下一项任务；Pi 默认假设用户在 Agent 工作期间发送的新消息是要纠正当前方向。

不过，Steering 并不是把消息插入一个正在生成 Token 的模型请求中。实际边界是：

```text
正在进行的模型请求
    ↓
模型返回工具调用
    ↓
工具执行结束
    ↓
注入 Steering 消息
    ↓
发起下一次模型请求
```

因此，它是在同一次 Agent 任务的工具循环之间插入用户消息，而不是修改已经发出的模型请求。

### Session 是一棵树

Session 自动保存在 `~/.pi/agent/sessions/`，并按工作目录组织。

```text
pi -c                  继续最近的 Session
pi -r                  浏览并选择 Session
pi --no-session        临时会话，不保存
pi --session <path|id> 打开指定 Session
pi --fork <path|id>    Fork 指定 Session
```

`/tree`、`/fork` 和 `/clone` 容易混淆：

| 操作 | 是否创建新文件 | 用途 |
|---|---:|---|
| `/tree` | 否 | 在当前 Session 树中切换历史节点 |
| `/fork` | 是 | 从较早的用户消息重新开始 |
| `/clone` | 是 | 复制当前活动分支后继续 |

在同一 Session 中回到历史节点并继续，会形成分支：

```text
A → B → C
      └→ D
```

`/compact` 会总结较早的消息，释放模型上下文。磁盘中的原始 Session 历史仍然保留，但模型后续看到的是摘要，所以它属于有损压缩。

### 上下文文件与系统提示词

`AGENTS.md` 和 `CLAUDE.md` 用于记录项目规则。

`.pi/SYSTEM.md` 或全局 `SYSTEM.md` 会替换默认系统提示词；`APPEND_SYSTEM.md` 只在默认系统提示词后追加内容。

通常：

- 项目约定写在 `AGENTS.md`
- 彻底改变 Agent 基础行为时才使用 `SYSTEM.md`
- 只想补充系统级行为时使用 `APPEND_SYSTEM.md`

### 项目信任

Pi 区分“可以读取的项目说明”和“可以执行的项目代码”。未信任项目时，可以加载上下文文件，但不会直接加载可能执行代码的项目资源，例如：

- 项目级 `.pi/settings.json`
- 项目 Extension
- 项目 Pi Package

非交互模式无法显示信任询问：

```text
pi -p
pi --mode json
pi --mode rpc
```

因此可以使用：

```text
--approve     本次信任项目资源
--no-approve  本次忽略项目资源
```

这对 CI 和自动化程序很重要，否则同一命令可能因为信任状态不同而加载不同资源。

### 工具和资源控制

只允许只读工具：

```text
pi --tools read,grep,find,ls -p "审查这个项目"
```

禁用所有工具：

```text
pi --no-tools -p "回答一个知识问题"
```

只加载一个明确指定的 Extension：

```text
pi --no-extensions -e ./my-extension.ts
```

这种“先关闭自动发现，再精确开启”的方式适合测试、隔离和排查问题。

### 设计理念

Pi 有意不把 MCP、Sub-agent、Plan Mode、权限弹窗、Todo 和后台 Shell 等工作流写死在核心里，而是交给 Extension、Skill、Package、容器和 tmux。

开发 Pi 时需要先判断：

```text
这是所有用户都必须具备的核心能力？
还是特定工作流需要的扩展能力？
```

如果只是特定工作流需要，通常更适合做成 Extension。

## 4. providers.md：Pi 如何连接模型服务

### Provider、Model 与 Credential

```text
Provider   = 提供模型 API 的服务
Model      = 具体使用的模型
Credential = 访问 Provider 的凭据
```

例如：

```text
Provider   = OpenAI
Model      = 某个 GPT 模型
Credential = OPENAI_API_KEY 或 OAuth Token
```

同一个模型家族也可能通过多个 Provider 使用。虽然模型接近，但认证方式、请求地址、模型 ID、计费和 API 协议可能不同。

### 模型目录和认证存储

Pi 自带模型目录，部分 Provider 还可以动态刷新并缓存模型列表：

```text
~/.pi/agent/models-store.json
```

要区分：

```text
auth.json         → 是否具有调用 Provider 的凭据
models-store.json → Provider 有哪些模型可以使用
```

强制刷新模型目录：

```text
pi update --models
```

### OAuth 与 API Key

订阅 Provider 通过 `/login` 登录，OAuth Token 会保存到 `auth.json`，过期后由 Pi 管理刷新。

API Key 可以来自环境变量，也可以保存在 `auth.json`。

### 凭据解析顺序

这是本篇最重要的规则：

```text
1. CLI --api-key
2. auth.json
3. 进程环境变量
4. models.json
```

一个容易误判的地方是：`auth.json` 的优先级高于环境变量。如果修改环境变量后 Pi 仍然使用旧账号，应检查 `auth.json` 是否已有同一 Provider 的凭据。

### auth.json 中的动态 Key

Key 可以直接保存：

```json
{"type":"api_key","key":"sk-..."}
```

可以引用环境变量：

```json
{"type":"api_key","key":"$OPENAI_API_KEY"}
```

也可以执行密码管理器命令：

```json
{"type":"api_key","key":"!op read 'op://vault/item/credential'"}
```

以 `!` 开头意味着会执行 Shell 命令，所以不能随便使用别人提供的认证配置。

`auth.json` 中的凭据还可以携带 Provider 专用环境变量，使 Pi 使用一套独立于项目 Shell 的模型服务配置。

### 云 Provider 为什么更复杂

普通 Provider 通常只需要 API Key 和模型 ID。Azure、Bedrock、Vertex 等云平台还可能需要：

- 资源地址或部署名称
- 云账号和区域
- 临时凭据或应用默认凭据
- 请求签名
- 特殊缓存配置

所以 Provider 层不只是“把 API Key 放进请求头”，还要负责认证生命周期、配置解析、模型发现和协议适配。

### 自定义 Provider 的两条路线

如果服务兼容 Pi 已支持的 API 协议，可以使用 `models.json`，例如 Ollama、LM Studio、vLLM 或企业内部 OpenAI 兼容网关。

如果服务需要自定义请求协议、响应流、OAuth 或模型发现逻辑，则需要编写 Extension。

```text
协议兼容，只是地址不同 → models.json
协议或认证流程不同       → Extension
```

## 5. llama-cpp.md：Pi 如何接入本地模型

Pi 不直接解析 GGUF 或执行本地推理，而是连接 llama.cpp Router：

```text
Pi
 │ HTTP
 ▼
llama-server Router
 ├─ 发现 GGUF 模型
 ├─ 加载和卸载模型
 ├─ 管理 GPU、内存和上下文
 └─ 执行本地推理
```

### Router 模式

启动 `llama-server` 时不能传 `--model`、`-m` 或 `-hf`，否则会进入单模型模式。Pi 需要 Router 模式来发现和管理多个模型。

重要参数：

- `--models-dir`：扫描本地 GGUF 模型。
- `--no-models-autoload`：只允许显式加载模型。
- `--jinja`：启用聊天模板和工具调用模板。
- `-ngl 999`：尽量把模型层放到 GPU。
- `-c 32768`：设置上下文窗口大小。

上下文越大，KV Cache 占用越多。显存不足时，可以先降低 `-c`，或者卸载其他模型。

`--jinja` 对 Coding Agent 很重要。模型不仅要生成文本，还要按照正确模板表达工具名称和结构化参数。缺少正确聊天模板时，普通对话可能正常，但工具调用可能失败。

### 模型发现、加载与选择

本地模型需要经历三个不同阶段：

```text
GGUF 文件存在
    ↓
Router 发现模型
    ↓
/llama 加载模型
    ↓
/model 选择当前模型
```

`/llama` 管理 Router 中的模型状态：

- 查看模型
- 加载模型
- 卸载模型
- 下载模型
- 处理 Router 连接状态

`/model` 只负责选择当前 Pi Session 使用哪个已加载模型。

如果模型文件存在但 `/model` 中看不到，通常是模型尚未通过 `/llama` 加载。

### 下载模型时的进程边界

Pi 提供 Hugging Face 搜索界面，但真正下载模型的是 `llama-server`：

```text
Pi 进程          → 搜索模型
llama-server进程 → 下载并保存模型
```

访问受限仓库时，两个进程可能都需要 `HF_TOKEN`。只给 Pi 配置 Token，不代表服务器进程也有下载权限。

### Pi 不拥有 Router

Router 可能被多个客户端共享。Pi 因此不会：

- 悄悄卸载已有模型
- 删除 GGUF 文件
- 假设本地保存的状态就是服务器当前状态

`/llama` 会读取 Router 的真实状态。连接中断后，Retry 只重新连接和刷新状态，不会重放中断的加载、卸载或下载操作，因为这些操作具有副作用。

### 常见故障

| 现象 | 常见原因 |
|---|---|
| `/llama` 没有模型 | 模型目录错误，或者添加模型后没有重启 Router |
| `/model` 没有模型 | 模型已发现但尚未加载 |
| 加载时显存不足 | 上下文太大或同时加载模型过多 |
| Router 功能不可用 | 启动时进入了单模型模式 |
| 能聊天但工具调用异常 | 缺少 `--jinja` 或聊天模板不兼容 |

本篇最重要的是：Pi 不执行本地推理，只控制 llama.cpp Router；模型发现、加载和选择是三个不同阶段。

## 6. json.md：JSON 生命周期事件流

`--mode json` 不渲染普通终端界面，而是把 Pi 运行过程中产生的事件逐行写到标准输出：

```text
pi --mode json "列出当前目录"
```

它输出 JSONL：每一行都是一个独立 JSON 对象，而不是等任务结束后再输出一个完整 JSON 数组。外部程序可以逐行读取、立即解析和实时更新界面，不需要把全部事件积压在内存中。

第一行是 Session 元数据：

```json
{"type":"session","version":3,"id":"uuid","timestamp":"...","cwd":"/path"}
```

它相当于事件流的文件头，提供协议版本、Session ID、时间和工作目录。后面才是 Agent 实际运行时产生的事件。

事件可以理解为三层生命周期：

```text
Agent：处理一次用户请求的完整循环
└─ Turn：循环中的一轮模型处理
   ├─ Message：一条消息的流式生成过程
   └─ Tool Execution：一次工具调用的执行过程
```

典型事件包括：

| 事件 | 含义 |
|---|---|
| `session` | Session ID、版本和工作目录 |
| `agent_start/end` | 整次 Agent 执行开始和结束 |
| `turn_start/end` | 一轮模型处理开始和结束；一个 Agent 循环可能因工具调用包含多轮 |
| `message_start/update/end` | 消息开始、流式增量和最终完成 |
| `tool_execution_start/update/end` | 工具开始执行、中间结果和最终结果 |
| `queue_update` | Steering 与 Follow-up 队列的完整当前状态 |
| `compaction_start/end` | 手动、阈值触发或溢出触发的上下文压缩 |
| `auto_retry_start/end` | Provider 请求失败后的自动重试 |

简化输出如下：

```json
{"type":"session","version":3,"id":"abc","cwd":"D:\\project"}
{"type":"agent_start"}
{"type":"turn_start"}
{"type":"message_start","message":{"role":"assistant","content":[]}}
{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"当前"}}
{"type":"message_end","message":{"role":"assistant","content":[]}}
{"type":"turn_end","toolResults":[]}
{"type":"agent_end","messages":[]}
```

`message_update` 同时带有当前累计消息和本次 `assistantMessageEvent` 增量。实时界面可以用增量立即显示文字；保存最终结果时，应以 `message_end.message` 为准。

工具事件使用 `toolCallId` 关联同一次调用。`tool_execution_update` 可以报告长时间命令的部分输出，`tool_execution_end` 则通过 `result` 和 `isError` 表示最终结果。外部程序不需要分析工具输出文字来猜测执行状态。

`queue_update` 对应 Pi 的 Steering 和 Follow-up。它输出的是两个队列的完整快照，不只是新增或删除的差异，因此 UI 收到事件后可以直接覆盖旧队列状态。

`compaction_end` 会说明压缩是否中止、是否重试、压缩结果和错误信息。`auto_retry_start` 则提供当前次数、最大次数、等待时间和失败原因，使外部 UI 能明确展示 Pi 正在等待重试，而不是看起来像卡住。

事件中的消息也不只有用户、助手和工具结果。Coding Agent 还会产生 Bash 执行消息、自定义消息、分支摘要和上下文压缩摘要。因此 JSON 模式暴露的既有聊天过程，也有 Pi 管理 Session 树和模型上下文时产生的内部记录。

JSON 事件写入 `stdout`，诊断信息可能写入 `stderr`。集成程序应分别读取两者，否则普通错误日志混进标准输出后会导致逐行 `JSON.parse` 失败。

它输出的不只是最终回答，而是 Pi 执行过程中的全部事件，适合保存运行日志、观察生命周期、接入日志系统或构建只负责展示的自定义 UI。

```text
普通 pi       → 人在终端中持续交互
pi -p         → 执行一次，只要最终回答
--mode json   → 执行任务，并观察完整事件过程
--mode rpc    → 保持运行，由外部程序持续控制
```

三者的边界可以概括为：

```text
JSON 模式：Pi → 外部程序，单向输出运行事件
RPC 模式：Pi ↔ 外部程序，持续双向控制
SDK：把 Pi 作为程序内部组件直接调用
```

因此 JSON 模式适合“观察一次运行过程”。如果外部程序还要继续发消息、切换模型或控制 Session，应使用 RPC；如果需要把 Pi 深度嵌入自己的应用，则使用 SDK。

## 7. security.md：Pi 的安全边界

Pi 是本地 Coding Agent。它以启动它的用户账户权限运行，并把该用户能够读写和执行的本地资源视为同一个信任边界。

```text
用户账户能做什么
        ↓
Pi 进程通常也能做什么
        ↓
内置工具和 Extension 通常也能做什么
```

这意味着 Pi 默认不是一个受限代码执行环境。

### 项目信任不是沙箱

Project Trust 只控制 Pi 是否加载项目提供的配置和可执行扩展资源，例如：

- `.pi/settings.json`
- `.pi/extensions`、`.pi/skills`、`.pi/prompts`、`.pi/themes`
- `.pi/SYSTEM.md` 和 `.pi/APPEND_SYSTEM.md`
- 项目或祖先目录中的 `.agents/skills`
- 项目 Pi Package 提供的 Extension 和其他资源

信任检查解决的是：

```text
这个仓库能不能在 Pi 启动时改变 Pi 的配置和行为？
```

它不解决的是：

```text
Pi 运行后，模型调用工具时能访问哪些文件和进程？
```

所以即使拒绝信任项目，Pi 仍然不是沙箱；它只是跳过项目级设置、Extension、Skill 等受保护资源。

### 为什么 AGENTS.md 仍然会加载

除非使用 `--no-context-files`，`AGENTS.md` 和 `CLAUDE.md` 不受 Project Trust 控制，即使项目未受信任也会加载。

原因是上下文文件被视为项目说明，而不是直接执行的 TypeScript 模块。但它们仍然可能包含恶意或误导性的指令，因此“可以加载”不等于“内容可信”。

### 信任决定如何解析

保存的决定位于：

```text
~/.pi/agent/trust.json
```

Pi 会根据规范化后的当前目录和父目录寻找决定。离当前目录最近的已保存决定优先于全局 `defaultProjectTrust`。

交互模式默认可以询问用户；非交互模式不能弹出确认：

```text
pi -p
pi --mode json
pi --mode rpc
```

当没有已保存决定时：

- `defaultProjectTrust: "ask"`：非交互模式中忽略项目资源。
- `defaultProjectTrust: "never"`：忽略项目资源。
- `defaultProjectTrust: "always"`：加载项目资源。
- `--approve`：本次运行明确加载。
- `--no-approve`：本次运行明确忽略。

### Pi 没有内置沙箱

内置工具和 Extension 都以 Pi 进程的权限运行：

- `read` 可以读取当前用户有权读取的文件。
- `write` 和 `edit` 可以修改当前用户有权修改的文件。
- Shell 工具可以启动本地进程。
- Extension 是具有同等本地权限的 TypeScript 代码。
- 测试、语言服务器、包管理器和开发工具也是普通本地进程。

Pi 没有在进程内部模拟一个看似安全但不完整的权限系统，因为真正的隔离还涉及宿主文件系统、Shell、网络、凭据、子进程和动态加载的 Extension。可靠边界需要由操作系统、容器或虚拟化层提供。

### Prompt Injection 仍然存在

仓库中的以下内容都可能影响模型：

- 源码注释
- Markdown 文档
- `AGENTS.md` 或 `CLAUDE.md`
- 构建产物和日志
- 工具输出
- 第三方依赖中的文本

模型可能把这些内容中的恶意文字当成指令。Project Trust 无法可靠阻止这种 Prompt Injection，因为它只能控制资源是否加载，不能可靠判断自然语言内容是否恶意。

因此需要区分：

```text
Project Trust  → 控制项目资源是否自动改变 Pi 行为
Tool Allowlist → 限制这次运行暴露哪些工具
OS Sandbox     → 真正限制文件、进程、网络和凭据权限
```

### 处理不受信任和无人监督的任务

对于不受信任仓库、无人值守自动化或不准备密切检查的生成代码，应把 Pi 放进真正的隔离环境：

- 容器
- VM 或 micro-VM
- 远程沙箱
- 策略控制型沙箱

并遵循最小权限原则：

- 只挂载任务需要的工作目录。
- 不需要时不要挂载宿主机的 `~/.pi/agent`。
- 只传入必要的 API Key，优先使用短期凭据。
- 不需要网络时关闭网络。
- 将结果复制回可信环境之前先审查 Diff 和输出。

需要注意，读写方式挂载宿主工作区并不等于隔离写入。容器中的 Agent 修改挂载目录时，宿主文件也会改变。若要防止意外写入，应使用只读挂载或复制进、复制出的工作方式。

### 安全问题与预期行为

以下情况通常属于 Pi 已声明的边界，而不自动构成 Pi 安全漏洞：

- Pi 能使用当前用户本来就拥有的本地权限。
- Pi 没有内置沙箱。
- 不受信任内容产生 Prompt Injection。
- 用户自行安装的 Extension 或 Skill 执行危险操作。

真正需要重点报告的是：

- Pi 绕过了已经声明的权限边界。
- Pi 获得了启动用户原本没有的访问权限。
- 受保护资源在未信任时仍被加载或执行。

本篇最需要记住的是：

> Project Trust 是“是否加载项目行为”的门禁，不是“模型能做什么”的沙箱。Pi 的真正安全上限由启动用户权限和外部隔离环境决定。

### 为什么 Pi 选择不内置权限沙箱

这个设计有几方面考虑：

1. Pi 的目标是直接使用用户现有的源码、Shell、包管理器、语言服务器和开发环境。越强的默认隔离，工具兼容成本越高。
2. 进程内的命令匹配和确认弹窗很容易被误解为真正安全边界。Shell 可以间接运行脚本、子进程和包管理器，单纯检查命令文本很难覆盖真实副作用。
3. Pi 希望保持核心小，把不同用户的权限工作流交给 Extension，并把真正隔离交给容器、VM 或操作系统。
4. 不内置一个不完整的沙箱，可以更诚实地暴露风险，避免用户误以为陌生仓库和 Prompt Injection 已经安全。

代价同样明确：Pi 默认不是安全优先设计。面对不受信任仓库、无人监督任务和高价值凭据时，如果用户没有额外配置沙箱，潜在影响范围会比默认受限的 Agent 更大。

作者在原始设计文章中进一步把风险归纳为三种能力的组合：

```text
读取敏感数据
    +
执行代码
    +
访问网络
    ↓
产生难以靠应用层规则完全阻止的数据泄漏路径
```

只检查表面的 Bash 命令并不可靠。`npm test`、构建脚本或包管理器都可以继续启动任意子进程；用户频繁看到确认弹窗后，也可能形成授权疲劳，最终一路批准。Pi 因此不把命令分类和确认弹窗作为核心安全保证，而是默认完整权限，并要求高风险场景使用外部隔离。

但“有 Bash 就无法限制”并不是严格结论。准确说法是：

```text
应用层分析 Bash 会做什么 → 很难完整、容易漏判
操作系统限制 Bash 能做什么 → 可以真实强制
```

Seatbelt、bubblewrap、seccomp、容器和 VM 不需要理解命令意图。它们直接限制进程可以访问的文件、网络和系统资源，所有子进程继承同一边界。因此 Pi 作者否定的是把不完整的进程内权限检查当成可信沙箱，而不是认为 OS 级隔离没有意义。

### 权限弹窗与真正沙箱的区别

可以把权限控制分为三层：

```text
模型和提示词规则
    → 依赖模型遵守，不是安全边界

工具权限与确认弹窗
    → 能防误操作，但依赖规则匹配和用户判断

操作系统沙箱、容器、VM
    → 由内核或虚拟化层拒绝越界访问
```

确认弹窗是有效的产品安全措施，能让用户阻止明显危险操作；但它不是完整隔离。它可能受到授权疲劳、命令包装、脚本间接副作用和用户误判影响。一旦用户批准越界操作，限制就被主动放宽。

### 与 Codex 的区别

Codex 把 Approval Policy 和 Sandbox Mode 分成两层：

- Approval Policy 决定什么时候询问用户。
- Sandbox Mode 决定命令在技术上能够访问什么。

默认的 `workspace-write` 使用操作系统级机制限制写入范围，并默认关闭命令网络访问；macOS 使用 Seatbelt，Linux 默认使用 `bwrap` 与 `seccomp`，Windows使用对应的本地实现或 WSL2 Linux 沙箱。这类限制对沙箱内命令及其子进程具有真实约束，不依赖模型自觉。

但它也不是绝对安全：

- 用户可以批准越界访问。
- `danger-full-access` 或 `--yolo` 会关闭沙箱和审批。
- 配置过宽、实现漏洞、Unix Socket 和网络代理都可能扩大边界。
- 沙箱中允许读取的数据仍可能被模型看到；网络一旦同时开放，就要考虑数据外泄。

### 与 Claude Code 的区别

Claude Code 也区分权限规则与 Bash 沙箱：

- Allow、Ask、Deny 和不同 Permission Mode 主要控制工具是否可执行。
- Read/Edit 的 Deny 规则约束内置文件工具，但不能阻止 Bash 使用 `cat` 等命令读取同一文件。
- 启用 Sandbox 后，Bash 及其子进程才会受到操作系统级文件系统和网络限制。

Claude Code 的 Bash 沙箱在 macOS 使用 Seatbelt，在 Linux 和 WSL2 使用 `bubblewrap`。它对被沙箱覆盖的 Bash 子进程是真实边界，但内置 Read/Edit/Write 工具仍通过权限系统控制，Computer Use 等能力也有自己的边界。因此不能笼统地说“Claude 全部能力都在同一个沙箱里”。

### 比较结论

| 机制 | 能否防一般误操作 | 能否对抗 Prompt Injection 后的越界尝试 |
|---|---:|---:|
| 模型指令 | 有限 | 否 |
| Allow/Deny 与确认弹窗 | 有一定效果 | 不稳定，取决于覆盖范围和用户审批 |
| OS 级沙箱 | 是 | 在配置和覆盖范围内有效 |
| 独立容器或 VM | 是 | 通常最强，但仍取决于挂载、网络和凭据配置 |

所以，Codex 和 Claude 的权限控制不能一概说是假的：它们的审批层主要防误操作，操作系统沙箱层则是真实的强制边界。Pi 选择省略内置边界，换取简单、透明和开发环境兼容性，同时把隔离责任明确交给用户和外部运行环境。

### Codex 与 Claude 本地 Sandbox 的完整工作方式

Codex CLI 和 Claude Code 的本地 Sandbox 不是 Docker、远程 VM，也没有把项目上传后再下载。它们采用的是“主进程留在宿主机，工具执行受到本机 OS 策略限制”的架构：

```text
宿主机
└─ Agent 主进程
   ├─ TUI、Session 与模型通信
   ├─ 内置文件工具
   └─ Shell 命令
      ↓
      OS 级 Sandbox
      ├─ 允许访问当前工作区
      ├─ 限制工作区外写入
      ├─ 限制敏感路径
      ├─ 限制网络
      └─ 约束命令启动的全部子进程
```

两者使用的平台机制大致如下：

| 平台 | Codex | Claude Code Bash Sandbox |
|---|---|---|
| macOS | Seatbelt / `sandbox-exec` | Seatbelt |
| Linux | `bubblewrap` + `seccomp` | `bubblewrap` |
| WSL2 | Linux Sandbox | Linux `bubblewrap` |
| 原生 Windows | Codex Windows Sandbox | 主要依赖权限层，OS Sandbox 支持范围与 Unix 平台不同 |

Codex 把 `Sandbox Mode` 和 `Approval Policy` 明确分开。Sandbox 决定操作系统实际允许什么；Approval 决定 Agent 请求跨越边界时是否询问用户。默认 `workspace-write` 允许读写当前工作区，禁止或询问工作区外写入，并默认关闭命令网络。详见 [Codex Sandbox](https://learn.chatgpt.com/docs/sandboxing) 和 [Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)。

Claude Code 则把内置工具权限与 Bash Sandbox 分开。Read/Edit/Write 主要经过 Allow、Ask、Deny 权限规则；Bash 及其子进程启用 Sandbox 后，才由 OS 级机制限制文件系统和网络。内置 Read 的拒绝规则不能单独阻止 Bash 使用 `cat` 读取同一文件，因此两层需要配合。详见 [Claude Code Permissions](https://code.claude.com/docs/en/permissions) 和 [Sandboxing](https://code.claude.com/docs/en/sandboxing)。

#### 为什么能直接修改本地文件仍然叫隔离

当前工作区本来就是显式授权区域：

```text
D:\project\src\app.ts
        ↑
Sandbox Policy 允许在 Workspace 内写入
```

Agent 修改的是本地原文件，不需要上传下载。Sandbox 隔离的是工作区之外的权限：

```text
允许
├─ 当前项目源码
├─ 构建输出
└─ 必要临时目录

限制
├─ 其他项目
├─ 用户配置与凭据
├─ Shell 启动文件
├─ 系统目录
├─ 本地 Socket 和服务
└─ 未授权网络
```

所以 OS Sandbox 不负责保证当前项目不被破坏。它负责把可能的破坏范围从“当前用户能访问的整台机器”缩小到“明确授权的工作区和资源”。当前项目内部的恢复与审查主要依赖 Git 和备份。

#### OS Sandbox 为什么比命令审批更强

Agent 执行 `npm test` 时，后续可能出现多层脚本和子进程：

```text
npm test
└─ package script
   └─ Node
      └─ Shell 或其他可执行程序
```

命令审批器很难提前理解完整副作用；OS Sandbox 不需要理解命令意图，而是在每个实际文件、网络和进程访问发生时由内核执行策略。所有子进程继承限制，因此即使 Prompt Injection 或恶意依赖改变了执行路径，也不能仅靠换一种命令写法绕过内核边界。

#### 仍然存在的限制

- Agent 可以破坏被授权写入的当前工作区。
- 默认允许读取的范围可能大于允许写入的范围，具体取决于产品策略。
- 用户批准越界操作后，边界会相应扩大。
- Full Access、`--yolo` 或禁用 Sandbox 会恢复宿主用户权限。
- Sandbox 配置过宽、危险 Socket、网络代理或实现漏洞仍可能形成逃逸路径。

因此，Codex 和 Claude 的本地 Sandbox 是真实但有限的强制边界：它们不是为了让 Agent 无法修改项目，而是让 Agent 只能在用户授权的范围内修改项目和执行工具。

## 8. containerization.md：在 Pi 外部建立隔离

Pi 自身没有内置沙箱，因此容器化的关键是决定隔离边界画在哪里。文档给出两种总体架构：

```text
方式一：隔离整个 Pi 进程

宿主机
└─ 沙箱或容器
   └─ Pi
      ├─ 内置工具
      ├─ ! 命令
      └─ Extension

方式二：Pi 留在宿主机，只代理工具执行

宿主机 Pi
├─ 模型认证
├─ Session 和 UI
├─ Extension
└─ 内置工具请求 → VM 或沙箱
```

第一种覆盖范围更完整；第二种更方便保留宿主机认证和交互体验，但必须确认哪些工具真的被代理，哪些代码仍在宿主机执行。

### Gondolin：只隔离内置工具

Gondolin 是本地 Linux micro-VM。Pi 仍运行在宿主机，示例 Extension 覆盖以下内置工具：

- `read`
- `write`
- `edit`
- `bash`
- `grep`
- `find`
- `ls`
- 用户输入的 `!` 命令

这些操作被路由到 VM 中执行，而模型认证、Pi UI、Session 和 Pi 主进程留在宿主机。

它的优点是原始 Provider 凭据不必进入 VM，Pi 仍能直接使用宿主机配置。需要注意的边界是：

- 其他自定义 Extension 仍在宿主机运行，除非它们也主动把操作委托给 VM。
- 宿主当前目录会挂载到 VM 的 `/workspace`。
- `/workspace` 中的写入会直接修改宿主文件。

因此 Gondolin 隔离的是工具执行环境和宿主其他资源，不是保护被挂载项目不被修改。

### 纯 Docker：隔离整个 Pi 进程

Docker 模式把 Pi、内置工具、`!` 命令和 Extension 全部放进容器。覆盖范围比工具路由更统一：

```text
Docker 容器
├─ Pi 进程
├─ Extension
├─ Shell 与开发工具
├─ Provider API Key
└─ /workspace → 宿主项目目录
```

这种方式的主要权衡是凭据也需要进入容器。示例通过环境变量传入 API Key，并用命名卷保存容器自己的 Pi 配置和 Session。

不建议为了方便直接挂载宿主机的 `~/.pi/agent`，因为这会把宿主认证、Session 和全局配置一起暴露给容器。

同样，下面的读写挂载会让容器改动直接写回宿主机：

```text
-v "$PWD:/workspace"
```

容器在这里限制的是对其他宿主资源的访问，不会自动提供工作区写入回滚能力。

### OpenShell：策略控制型完整沙箱

OpenShell 把整个 Pi 进程放入由网关管理的沙箱，并可以统一控制：

- 文件系统
- 进程
- 网络
- 凭据
- 模型推理路由

本地网关可以由 Docker、Podman 或 VM 支撑；远程网关可以运行在 Kubernetes 上。

远程模式不需要把宿主工作区直接 Bind Mount 到沙箱。项目通过上传、沙箱内克隆和下载结果的方式传递：

```text
宿主项目
    ↓ upload
远程沙箱内工作副本
    ↓ Agent 修改
    ↓ download
宿主上的输出目录
```

这种复制边界比读写挂载更容易审查，因为沙箱中的修改不会立即写穿到宿主机。

OpenShell 还可以把原始模型 API Key 留在沙箱之外：沙箱只访问 `inference.local`，由网关向真正的模型 Provider 注入凭据。这降低了恶意代码直接读取和外泄模型密钥的风险。

### 三种模式的区别

| 模式 | Pi 在哪里 | 隔离范围 | 原始模型凭据 | 工作区修改 |
|---|---|---|---|---|
| Gondolin | 宿主机 | 指定内置工具和 `!` 命令 | 留在宿主机 | 通过挂载直接写回 |
| 纯 Docker | 容器 | 整个 Pi 及 Extension | 通常进入容器 | 通过挂载直接写回 |
| OpenShell | 完整沙箱 | 文件、进程、网络、凭据、推理 | 可由网关注入 | 远程模式可上传下载，不直接写回 |

选择时应先回答三个问题：

1. 是否需要隔离全部 Extension，还是只隔离内置工具？
2. 原始 Provider 凭据能否进入执行环境？
3. Agent 的修改是否应该实时写回宿主工作区？

本篇最需要记住的是：

> “运行在容器里”不等于“宿主项目不会被修改”。安全效果由 Pi 进程放在哪里、哪些目录被挂载、凭据放在哪里以及网络如何配置共同决定。

### 延伸：共享挂载与复制传输

执行环境被隔离后，项目文件仍有两种进入方式。它们决定 Agent 的修改是否立即影响宿主机。

#### 共享挂载

```text
宿主项目文件
      ↕ 同一个文件
容器或 VM 中的挂载路径
```

Gondolin 把宿主当前目录挂载为 `/workspace`，文档中的 Docker 示例也使用读写 Bind Mount。Pi 在隔离环境中修改挂载路径时，宿主文件立即改变，不存在上传和下载过程。

共享挂载的优点是无需同步，适合日常交互开发；缺点是隔离环境仍能直接覆盖或删除工作区内容。VM 或容器保护的是未挂载的宿主资源，不是被主动暴露的目录。

#### 复制进、复制出

```text
宿主项目
    ↓ 上传或 Git Clone
远程工作副本
    ↓ Agent 修改
    ↓ 下载、Patch 或 Git
宿主输出目录
```

E2B 和远程 OpenShell 无法直接挂载用户电脑的磁盘，因此通常使用上传、下载或 Git。修改先留在独立副本中，可以审查后再取回，但需要处理传输、依赖初始化和同步冲突。

所以，文件映射不是隔离机制，而是在隔离边界上主动开放的一项访问能力。

### 延伸：E2B 在这些方案中的位置

[E2B](https://e2b.dev/docs) 是面向 Agent 的托管远程 Linux Sandbox 平台，提供独立文件系统、命令执行、文件上传下载、暂停恢复、模板和快照。

Pi 可以采用两种接入方式：

```text
方式一：本机 Pi
        └─ 内置工具 → E2B Sandbox

方式二：E2B Sandbox
        └─ 整个 Pi 进程和全部 Extension
```

第一种类似 Gondolin，只是执行环境从本地 micro-VM 变成云端 Sandbox。第三方 [`pi-extension-e2b`](https://pi.dev/packages/pi-extension-e2b) 会替换 `bash`、`read`、`write`、`edit`、`ls`、`find`、`grep`，并提供项目同步、下载、暂停和重连能力。模型认证可以继续留在本机 Pi，但其他没有被代理的 Extension 仍在宿主进程中运行。

第二种类似远程 OpenShell：通过 E2B Template 安装 Pi，把整个进程放入远程环境。隔离覆盖更完整，但模型凭据通常也要进入 Sandbox，除非另设推理代理。

E2B 相比本地 Docker 或 Gondolin，更适合不可信代码、临时环境、并行 Agent 和快照 Fork；代价是代码离开本机、依赖云服务、存在网络延迟和持续成本，还需要单独控制出站网络与 Sandbox 凭据。

### 延伸：WSL2 为什么不能直接当安全沙箱

WSL2 使用轻量 VM 和真实 Linux 内核，但它同时强调 Windows 与 Linux 的互操作。需要区分两套文件系统：

```text
WSL Linux 文件系统
/home/user/project
    → 位于 WSL 的 ext4.vhdx 中

Windows 文件系统映射
/mnt/c、/mnt/d
    → 对应宿主 C:、D: 的真实文件
```

如果 Pi 在 `/mnt/d/project` 中修改文件，实际修改会立即反映到 `D:\project`，因为二者是同一个文件。项目位于 `/home/user/project` 时，修改发生在 WSL 的虚拟磁盘副本里；但 WSL 默认仍可访问 `/mnt/c`、`/mnt/d`。

此外，WSL 支持从 Linux 启动 `powershell.exe` 等 Windows 程序、共享文件、传递环境变量和网络互通。微软把这些能力定义为 [WSL Interop](https://learn.microsoft.com/windows/wsl/interop)。因此 WSL2 的 VM 提供 Linux 运行环境隔离，但默认配置没有把宿主资源视为不可信边界。

```text
WSL2 VM
├─ Linux 内核和独立根文件系统
├─ /mnt/c、/mnt/d → 主动暴露的宿主磁盘
└─ Windows 可执行程序与网络互操作
```

普通 WSL2 不能直接等同于不可信 Agent 沙箱。若要强化边界，需要禁用 Windows 磁盘自动挂载和进程互操作、限制网络，并在 WSL 内继续使用 `bubblewrap`、容器或其他 OS 级沙箱。

### 隔离方案的统一判断方法

分析任何 Sandbox 方案时，不要只问“是不是容器或 VM”，而要逐项确认：

1. Pi 主进程和 Extension 在宿主还是沙箱？
2. 哪些工具被代理到沙箱？
3. 项目使用共享挂载还是独立副本？
4. 原始 Provider 凭据位于哪里？
5. 沙箱能访问哪些网络、宿主目录、Socket 和外部程序？
6. 修改是立即写回，还是经过下载与审查？

只有这些问题都明确后，才能判断一个方案真正限制了什么。

### Sandbox、Git 与备份的职责

Sandbox 通常会故意允许 Agent 修改当前工作区，因为写代码正是 Coding Agent 的任务。它的主要职责不是保护当前项目完全不变，而是防止 Agent 从“修改这个项目”扩大为“控制当前用户的整个开发环境”。

```text
Sandbox
    → 限制 Agent 权限和破坏范围
    → 保护工作区之外的文件、系统、网络与凭据

Git
    → 记录工作区内的版本变化
    → 用于审查 Diff、比较方案和恢复已跟踪文件

备份
    → 保护未跟踪文件、未提交数据和 Git 之外的重要内容
```

Git 本身不是安全隔离。如果 `.git` 可以被 Agent 修改，历史和引用也可能被破坏；未跟踪文件和未保存的数据也不一定能通过 Git 恢复。因此 Codex 等工具会在可写工作区内继续把 `.git` 设为只读，必要时还应使用外部备份。

可以用房间类比理解：

```text
整台电脑 = 一栋房子
当前项目 = 一间工作室
OS Sandbox = 把 Agent 限制在工作室
Git = 记录工作室内部发生了哪些变化
远程 Sandbox = 在另一栋楼给 Agent 准备工作室
```

最终结论：Sandbox 负责防越权，Git 负责工作区内的审查与恢复，二者解决的不是同一个问题。
