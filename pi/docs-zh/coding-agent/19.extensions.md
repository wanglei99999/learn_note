> **译文** | 原文：[`packages/coding-agent/docs/extensions.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

> pi 自己就能编写 extension。直接让它按你的需求造一个。

# 扩展（Extensions）

Extension（扩展）是用来扩展 pi 行为的 TypeScript 模块。它们可以订阅生命周期事件、注册可供 LLM 调用的自定义工具、添加命令等等。

> **放对位置才能 /reload：** 把 extension 放在 `~/.pi/agent/extensions/`（全局）或 `.pi/extensions/`（项目本地）以便自动发现。`pi -e ./path.ts` 仅用于快速测试。放在自动发现位置的 extension 可以通过 `/reload` 热重载。

**核心能力：**
- **自定义工具** - 通过 `pi.registerTool()` 注册可供 LLM 调用的工具
- **事件拦截** - 阻止或修改工具调用、注入上下文、自定义上下文压缩
- **用户交互** - 通过 `ctx.ui` 与用户交互（select、confirm、input、notify）
- **自定义 UI 组件** - 通过 `ctx.ui.custom()` 使用支持键盘输入的完整 TUI 组件，实现复杂交互
- **自定义命令** - 通过 `pi.registerCommand()` 注册形如 `/mycommand` 的命令
- **Session 持久化** - 通过 `pi.appendEntry()` 存储可在重启后恢复的状态
- **自定义渲染** - 控制工具调用/结果以及消息在 TUI 中的展示方式

**示例用例：**
- 权限门禁（在 `rm -rf`、`sudo` 等命令前要求确认）
- Git 保存点（每个 turn 自动 stash，分支时恢复）
- 路径保护（阻止对 `.env`、`node_modules/` 的写入）
- 自定义上下文压缩（按你自己的方式总结对话）
- 对话摘要（见 `summarize.ts` 示例）
- 交互式工具（提问、向导、自定义对话框）
- 有状态工具（待办列表、连接池）
- 外部集成（文件监听、webhook、CI 触发）
- 等待时玩的小游戏（见 `snake.ts` 示例）

可运行的完整实现见 [examples/extensions/](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/)。

## 目录

- [快速上手](#快速上手)
- [Extension 存放位置](#extension-存放位置)
- [可用的导入](#可用的导入)
- [编写 Extension](#编写-extension)
  - [Extension 的组织形式](#extension-的组织形式)
- [事件](#事件)
  - [生命周期总览](#生命周期总览)
  - [资源事件](#资源事件)
  - [Session 事件](#session-事件)
  - [Agent 事件](#agent-事件)
  - [模型事件](#模型事件)
  - [工具事件](#工具事件)
- [ExtensionContext](#extensioncontext)
- [ExtensionCommandContext](#extensioncommandcontext)
- [ExtensionAPI 方法](#extensionapi-方法)
- [状态管理](#状态管理)
- [自定义工具](#自定义工具)
  - [动态工具加载](#动态工具加载)
- [自定义 UI](#自定义-ui)
- [错误处理](#错误处理)
- [各模式下的行为](#各模式下的行为)
- [示例索引](#示例索引)

## 快速上手

创建 `~/.pi/agent/extensions/my-extension.ts`：

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export default function (pi: ExtensionAPI) {
  // 响应事件
  pi.on("session_start", async (_event, ctx) => {
    ctx.ui.notify("Extension loaded!", "info");
  });

  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName === "bash" && event.input.command?.includes("rm -rf")) {
      const ok = await ctx.ui.confirm("Dangerous!", "Allow rm -rf?");
      if (!ok) return { block: true, reason: "Blocked by user" };
    }
  });

  // 注册一个自定义工具
  pi.registerTool({
    name: "greet",
    label: "Greet",
    description: "Greet someone by name",
    parameters: Type.Object({
      name: Type.String({ description: "Name to greet" }),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      return {
        content: [{ type: "text", text: `Hello, ${params.name}!` }],
        details: {},
      };
    },
  });

  // 注册一个命令
  pi.registerCommand("hello", {
    description: "Say hello",
    handler: async (args, ctx) => {
      ctx.ui.notify(`Hello ${args || "world"}!`, "info");
    },
  });
}
```

用 `--extension`（或 `-e`）标志测试：

```bash
pi -e ./my-extension.ts
```

## Extension 存放位置

> **安全提示：** extension 以你的完整系统权限运行，可以执行任意代码。只安装来自你信任的来源的 extension。

extension 会从受信任的位置自动发现。项目本地的 `.pi/extensions` 条目只有在项目被信任之后才会加载。

| 位置 | 作用域 |
|----------|-------|
| `~/.pi/agent/extensions/*.ts` | 全局（所有项目） |
| `~/.pi/agent/extensions/*/index.ts` | 全局（子目录） |
| `.pi/extensions/*.ts` | 项目本地 |
| `.pi/extensions/*/index.ts` | 项目本地（子目录） |

也可以通过 `settings.json` 添加额外路径：

```json
{
  "packages": [
    "npm:@foo/bar@1.0.0",
    "git:github.com/user/repo@v1"
  ],
  "extensions": [
    "/path/to/local/extension.ts",
    "/path/to/local/extension/dir"
  ]
}
```

要以 pi 包的形式通过 npm 或 git 分享 extension，见 [packages.md](packages.md)。

## 可用的导入

| 包 | 用途 |
|---------|---------|
| `@earendil-works/pi-coding-agent` | extension 类型（`ExtensionAPI`、`ExtensionContext`、各类事件） |
| `typebox` | 工具参数的 schema 定义 |
| `@earendil-works/pi-ai` | AI 工具函数（如兼容 Google 的枚举 `StringEnum`） |
| `@earendil-works/pi-tui` | 用于自定义渲染的 TUI 组件 |

npm 依赖同样可用。在 extension 旁边（或其父目录中）放一个 `package.json`，运行 `npm install`，之后从 `node_modules/` 的导入会自动解析。

对于通过 `pi install` 安装的分发型 pi 包（npm 或 git），运行时依赖必须放在 `dependencies` 中。包安装默认使用生产安装（`npm install --omit=dev`），因此 `devDependencies` 在运行时不可用；配置了 `npmCommand` 时，git 包会使用普通的 `install`，以兼容各种包装器。

Node.js 内置模块（`node:fs`、`node:path` 等）也可以使用。

## 编写 Extension

一个 extension 导出一个默认的工厂函数，该函数接收 `ExtensionAPI`。工厂函数可以是同步的，也可以是异步的：

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  // 订阅事件
  pi.on("event_name", async (event, ctx) => {
    // ctx.ui 用于用户交互
    const ok = await ctx.ui.confirm("Title", "Are you sure?");
    ctx.ui.notify("Done!", "info");
    ctx.ui.setStatus("my-ext", "Processing...");  // 底栏状态
    ctx.ui.setWidget("my-ext", ["Line 1", "Line 2"]);  // 编辑器上方的小部件（默认位置）
  });

  // 注册工具、命令、快捷键、标志
  pi.registerTool({ ... });
  pi.registerCommand("name", { ... });
  pi.registerShortcut("ctrl+x", { ... });
  pi.registerFlag("my-flag", { ... });
}
```

extension 通过 [jiti](https://github.com/unjs/jiti) 加载，因此 TypeScript 无需编译即可运行。

如果工厂函数返回一个 `Promise`，pi 会先等它完成再继续启动流程。这意味着异步初始化会在 `session_start` 之前、`resources_discover` 之前完成，也会在通过 `pi.registerProvider()` 排队的 provider 注册被应用之前完成。

### 异步工厂函数

需要一次性启动工作（如拉取远程配置、动态发现可用模型）时，使用异步工厂函数。

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default async function (pi: ExtensionAPI) {
  const response = await fetch("http://localhost:1234/v1/models");
  const payload = (await response.json()) as {
    data: Array<{
      id: string;
      name?: string;
      context_window?: number;
      max_tokens?: number;
    }>;
  };

  pi.registerProvider("local-openai", {
    baseUrl: "http://localhost:1234/v1",
    apiKey: "$LOCAL_OPENAI_API_KEY",
    api: "openai-completions",
    models: payload.data.map((model) => ({
      id: model.id,
      name: model.name ?? model.id,
      reasoning: false,
      input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: model.context_window ?? 128000,
      maxTokens: model.max_tokens ?? 4096,
    })),
  });
}
```

这种模式使抓取到的模型在正常启动流程和 `pi --list-models` 中都可用。

### 长生命周期资源与关停

extension 的工厂函数可能在根本不会启动 session 的调用中运行。不要在工厂函数里启动后台资源，例如进程、socket、文件监听器或定时器。

把后台资源的启动推迟到 `session_start`，或推迟到真正需要该资源的命令/工具/事件中。注册一个幂等的 `session_shutdown` 处理器，用来关闭你启动的所有 session 级资源。

### Extension 的组织形式

**单文件** - 最简单，适合小型 extension：

```
~/.pi/agent/extensions/
└── my-extension.ts
```

**带 index.ts 的目录** - 适合多文件 extension：

```
~/.pi/agent/extensions/
└── my-extension/
    ├── index.ts        # 入口（导出默认函数）
    ├── tools.ts        # 辅助模块
    └── utils.ts        # 辅助模块
```

**带依赖的包** - 适合需要 npm 包的 extension：

```
~/.pi/agent/extensions/
└── my-extension/
    ├── package.json    # 声明依赖和入口
    ├── package-lock.json
    ├── node_modules/   # npm install 之后
    └── src/
        └── index.ts
```

```json
// package.json
{
  "name": "my-extension",
  "dependencies": {
    "zod": "^3.0.0",
    "chalk": "^5.0.0"
  },
  "pi": {
    "extensions": ["./src/index.ts"]
  }
}
```

在 extension 目录中运行 `npm install`，之后从 `node_modules/` 的导入即可正常工作。

## 事件

### 生命周期总览

```
pi 启动
  │
  ├─► project_trust（仅用户/全局与 CLI extension，在项目资源加载之前）
  ├─► session_start { reason: "startup" }
  └─► resources_discover { reason: "startup" }
      │
      ▼
用户发送 prompt ───────────────────────────────────────────┐
  │                                                        │
  ├─► （先检查 extension 命令，命中则绕过后续流程）        │
  ├─► input（可拦截、变换或直接处理）                      │
  ├─► （若未被处理，进行 skill/模板展开）                  │
  ├─► before_agent_start（可注入消息、修改系统提示词）
  ├─► agent_start                                          │
  ├─► message_start / message_update / message_end         │
  │                                                        │
  │   ┌─── turn（LLM 调用工具时循环） ──────────────┐      │
  │   │                                            │       │
  │   ├─► turn_start                               │       │
  │   ├─► context（可修改消息）                    │       │
  │   ├─► before_provider_headers（可改写请求头）          |
  │   ├─► before_provider_request（可检查或替换 payload）
  │   ├─► after_provider_response（状态码 + 响应头，在消费流之前）
  │   │                                            │       │
  │   │   LLM 响应，可能调用工具：                 │       │
  │   │     ├─► tool_execution_start               │       │
  │   │     ├─► tool_call（可阻止）                │       │
  │   │     ├─► tool_execution_update              │       │
  │   │     ├─► tool_result（可修改）              │       │
  │   │     └─► tool_execution_end                 │       │
  │   │                                            │       │
  │   └─► turn_end                                 │       │
  │                                                        │
  ├─► agent_end                                            │
  └─► agent_settled（不再有重试/上下文压缩/后续消息）      │
                                                           │
用户发送下一条 prompt ◄────────────────────────────────────┘

/new（新 session）或 /resume（切换 session）
  ├─► session_before_switch（可取消）
  ├─► session_shutdown
  ├─► session_start { reason: "new" | "resume", previousSessionFile? }
  └─► resources_discover { reason: "startup" }

/fork 或 /clone
  ├─► session_before_fork（可取消）
  ├─► session_shutdown
  ├─► session_start { reason: "fork", previousSessionFile }
  └─► resources_discover { reason: "startup" }

/name 或 pi.setSessionName()
  └─► session_info_changed

/compact 或自动上下文压缩
  ├─► session_before_compact（可取消或自定义）
  └─► session_compact

/tree 导航
  ├─► session_before_tree（可取消或自定义）
  └─► session_tree

/model 或 Ctrl+P（模型选择/循环切换）
  ├─► thinking_level_select（若模型变更改变/收窄了思考级别）
  └─► model_select

思考级别变化（设置、快捷键、pi.setThinkingLevel()）
  └─► thinking_level_select

退出（Ctrl+C、Ctrl+D、SIGHUP、SIGTERM）
  └─► session_shutdown
```

### 启动事件

#### project_trust

在 pi 决定是否信任带动态配置（`.pi` 或 `.agents/skills`）的项目之前触发。它在启动期间运行，也会在 session 替换（例如 `/resume`）进入一个在当前进程中尚未解析信任状态的 cwd 时运行。只有用户/全局 extension 和 CLI `-e` extension 会参与；项目本地 extension 在信任状态确定之前不会被加载。

```typescript
pi.on("project_trust", async (event, ctx) => {
  // event.cwd - 当前工作目录
  // ctx 提供受限的信任上下文：cwd、mode、hasUI，以及 select/confirm/input/notify 这几个 UI 辅助方法
  if (await ctx.ui.confirm("Trust project?", event.cwd)) {
    return { trusted: "yes", remember: true };
  }
  return { trusted: "undecided" };
});
```

`project_trust` 处理器必须返回 `{ trusted: "yes" | "no" | "undecided" }`。返回 `"yes"` 或 `"no"` 的用户/全局或 CLI extension 拥有该决定权；第一个 yes/no 决定生效，并抑制内置的信任询问。使用 `remember: true` 可以持久化 yes/no 决定；否则它只对当前进程生效。返回 `"undecided"` 则把决定权留给后续处理器或内置信任流程。提示用户前先检查 `ctx.hasUI`。如果没有处理器返回 yes/no，正常的信任解析流程会继续：先应用 `trust.json` 中保存的决定，然后由 `defaultProjectTrust` 控制 pi 默认是询问、信任还是拒绝。

### 资源事件

#### resources_discover

在 `session_start` 之后触发，以便 extension 贡献额外的 skill、prompt 和主题路径。
启动路径使用 `reason: "startup"`；重载使用 `reason: "reload"`。

```typescript
pi.on("resources_discover", async (event, _ctx) => {
  // event.cwd - 当前工作目录
  // event.reason - "startup" | "reload"
  return {
    skillPaths: ["/path/to/skills"],
    promptPaths: ["/path/to/prompts"],
    themePaths: ["/path/to/themes"],
  };
});
```

### Session 事件

session 存储的内部结构与 SessionManager API 见 [Session 格式](session-format.md)。

#### session_start

在 session 被启动、加载或重载时触发。

```typescript
pi.on("session_start", async (event, ctx) => {
  // event.reason - "startup" | "reload" | "new" | "resume" | "fork"
  // event.previousSessionFile - 在 "new"、"resume"、"fork" 时存在
  ctx.ui.notify(`Session: ${ctx.sessionManager.getSessionFile() ?? "ephemeral"}`, "info");
});
```

#### session_info_changed

在通过 `/name`、RPC 或 `pi.setSessionName()` 设置当前 session 的显示名称时触发。

```typescript
pi.on("session_info_changed", async (event, ctx) => {
  // event.name - 当前规范化后的名称，被清除时为 undefined
  ctx.ui.notify(`Session renamed: ${event.name ?? "(none)"}`, "info");
});
```

#### session_before_switch

在开始新 session（`/new`）或切换 session（`/resume`）之前触发。

```typescript
pi.on("session_before_switch", async (event, ctx) => {
  // event.reason - "new" 或 "resume"
  // event.targetSessionFile - 将要切换到的 session（仅 "resume" 时存在）

  if (event.reason === "new") {
    const ok = await ctx.ui.confirm("Clear?", "Delete all messages?");
    if (!ok) return { cancel: true };
  }
});
```

切换或新建 session 的动作成功后，pi 会为旧的 extension 实例发出 `session_shutdown`，为新 session 重新加载并重新绑定 extension，然后带着 `reason: "new" | "resume"` 和 `previousSessionFile` 发出 `session_start`。
清理工作放在 `session_shutdown` 中做，然后在 `session_start` 中重建内存状态。

#### session_before_fork

通过 `/fork` 分叉或通过 `/clone` 克隆时触发。

```typescript
pi.on("session_before_fork", async (event, ctx) => {
  // event.entryId - 所选条目的 ID
  // event.position - /fork 时为 "before"，/clone 时为 "at"
  return { cancel: true }; // 取消 fork/clone
  // 或者
  return { skipConversationRestore: true }; // 为将来的对话恢复控制预留
});
```

fork 或 clone 成功后，pi 会为旧的 extension 实例发出 `session_shutdown`，为新 session 重新加载并重新绑定 extension，然后带着 `reason: "fork"` 和 `previousSessionFile` 发出 `session_start`。
清理工作放在 `session_shutdown` 中做，然后在 `session_start` 中重建内存状态。

#### session_before_compact / session_compact

在上下文压缩时触发。详见 [compaction.md](compaction.md)。

```typescript
pi.on("session_before_compact", async (event, ctx) => {
  const { preparation, branchEntries, customInstructions, reason, willRetry, signal } = event;

  // reason - "manual"（/compact）、"threshold" 或 "overflow"
  // willRetry - 压缩后是否重试被中止的 turn（溢出恢复）

  // 取消：
  return { cancel: true };

  // 自定义摘要：
  return {
    compaction: {
      summary: "...",
      firstKeptEntryId: preparation.firstKeptEntryId,
      tokensBefore: preparation.tokensBefore,
    }
  };
});

pi.on("session_compact", async (event, ctx) => {
  // event.compactionEntry - 保存下来的压缩结果
  // event.fromExtension - 是否由 extension 提供
  // event.reason - "manual"（/compact）、"threshold" 或 "overflow"
  // event.willRetry - 压缩后是否重试被中止的 turn（溢出恢复）
});
```

#### session_before_tree / session_tree

在 `/tree` 导航时触发。树导航的概念见 [Sessions](sessions.md)。

```typescript
pi.on("session_before_tree", async (event, ctx) => {
  const { preparation, signal } = event;
  return { cancel: true };
  // 或者提供自定义摘要：
  return { summary: { summary: "...", details: {} } };
});

pi.on("session_tree", async (event, ctx) => {
  // event.newLeafId, oldLeafId, summaryEntry, fromExtension
});
```

#### session_shutdown

在已启动的 session 运行时被拆除之前触发。用它清理从 `session_start` 或其他 session 级 hook 中打开的资源。

```typescript
pi.on("session_shutdown", async (event, ctx) => {
  // event.reason - "quit" | "reload" | "new" | "resume" | "fork"
  // event.targetSessionFile - session 替换流程的目标 session
  // 清理、保存状态等
});
```

### Agent 事件

#### before_agent_start

在用户提交 prompt 之后、agent 循环开始之前触发。可以注入一条消息和/或修改系统提示词。

```typescript
pi.on("before_agent_start", async (event, ctx) => {
  // event.prompt - 用户的 prompt 文本
  // event.images - 附带的图片（如有）
  // event.systemPrompt - 传到当前处理器的链式系统提示词
  //   （包含更早的 before_agent_start 处理器所做的修改）
  // event.systemPromptOptions - 用于构建系统提示词的结构化选项
  //   .customPrompt - 任何自定义系统提示词（来自 --system-prompt、SYSTEM.md 或自定义模板）
  //   .selectedTools - 当前在提示词中激活的工具
  //   .toolSnippets - 每个工具的单行描述
  //   .promptGuidelines - 自定义指导条目
  //   .appendSystemPrompt - 来自 --append-system-prompt 标志的文本
  //   .cwd - 工作目录
  //   .contextFiles - AGENTS.md 等已加载的上下文文件
  //   .skills - 已加载的 skill

  return {
    // 注入一条持久化消息（存入 session，发送给 LLM）
    message: {
      customType: "my-extension",
      content: "Additional context for the LLM",
      display: true,
    },
    // 替换本 turn 的系统提示词（在各 extension 之间链式传递）
    systemPrompt: event.systemPrompt + "\n\nExtra instructions for this turn...",
  };
});
```

`systemPromptOptions` 字段让 extension 能访问 Pi 用来构建系统提示词的同一份结构化数据。你可以借此了解 Pi 加载了什么——自定义提示词、指导条目、工具摘要、上下文文件、skill——而无需重新发现资源或重新解析标志。当你的 extension 需要在尊重用户配置的前提下对系统提示词做深入、有依据的修改时，用它。

在 `before_agent_start` 内部，`event.systemPrompt` 和 `ctx.getSystemPrompt()` 都反映截至当前处理器为止的链式系统提示词。更晚的 `before_agent_start` 处理器仍可以继续修改它。

#### agent_start / agent_end / agent_settled

`agent_start` 在一次底层 agent 运行开始时触发。`agent_end` 在该运行结束时触发，但 Pi 之后仍可能自动重试、自动压缩后重试，或继续处理排队的后续消息。需要确定 Pi 不会再自动继续运行的状态集成，请使用 `agent_settled`。

```typescript
pi.on("agent_start", async (_event, ctx) => {});

pi.on("agent_end", async (event, ctx) => {
  // event.messages - 本次底层运行产生的消息
});

pi.on("agent_settled", async (_event, ctx) => {
  // 此处 ctx.isIdle() 为 true，除非另一个 extension 启动了新的运行。
});
```

#### turn_start / turn_end

每个 turn（一次 LLM 响应 + 工具调用）触发一次。

```typescript
pi.on("turn_start", async (event, ctx) => {
  // event.turnIndex, event.timestamp
});

pi.on("turn_end", async (event, ctx) => {
  // event.turnIndex, event.message, event.toolResults
});
```

#### message_start / message_update / message_end

在消息生命周期更新时触发。

- `message_start` 和 `message_end` 对 user、assistant 和 toolResult 消息都会触发。
- `message_update` 只对 assistant 的流式更新触发。
- `message_end` 处理器可以返回 `{ message }` 来替换最终定稿的消息。替换后的消息必须保持相同的 `role`。

```typescript
pi.on("message_start", async (event, ctx) => {
  // event.message
});

pi.on("message_update", async (event, ctx) => {
  // event.message
  // event.assistantMessageEvent（逐 token 的流事件）
});

pi.on("message_end", async (event, ctx) => {
  if (event.message.role !== "assistant") return;

  return {
    message: {
      ...event.message,
      usage: {
        ...event.message.usage,
        cost: {
          ...event.message.usage.cost,
          total: 0.123,
        },
      },
    },
  };
});
```

#### tool_execution_start / tool_execution_update / tool_execution_end

在工具执行生命周期更新时触发。

在并行工具模式下：
- `tool_execution_start` 在预检阶段按 assistant 消息中的原始顺序发出
- `tool_execution_update` 事件可能在多个工具之间交错
- `tool_execution_end` 在每个工具定稿后按工具完成顺序发出
- 最终的 `toolResult` 消息事件仍然稍后按 assistant 消息中的原始顺序发出

```typescript
pi.on("tool_execution_start", async (event, ctx) => {
  // event.toolCallId, event.toolName, event.args
});

pi.on("tool_execution_update", async (event, ctx) => {
  // event.toolCallId, event.toolName, event.args, event.partialResult
});

pi.on("tool_execution_end", async (event, ctx) => {
  // event.toolCallId, event.toolName, event.result, event.isError
});
```

#### context

在每次 LLM 调用之前触发。以非破坏性方式修改消息。消息类型见 [Session 格式](session-format.md)。

```typescript
pi.on("context", async (event, ctx) => {
  // event.messages - 深拷贝，可安全修改
  const filtered = event.messages.filter(m => !shouldPrune(m));
  return { messages: filtered };
});
```

#### before_provider_headers

在出站 HTTP 请求头组装完成后触发。用它来添加、覆盖或删除请求头。

处理器就地修改 `event.headers`。把某个键设为字符串以添加或覆盖，设为 `null` 以删除。

```typescript
pi.on("before_provider_headers", (event, ctx) => {
  // 添加或覆盖——例如用于网关追踪/归因的 session id
  event.headers["x-session-id"] = ctx.sessionManager.getSessionId();

  // 删掉 pi 为本次调用添加的某个跟踪请求头
  event.headers["X-OpenRouter-Title"] = null;
});
```

每次 provider 请求只运行一次；重试会复用相同的请求头，而不会重新触发这个 hook。

#### before_provider_request

在 provider 特定的 payload 构建完成后、请求发送前触发。处理器按 extension 加载顺序运行。返回 `undefined` 保持 payload 不变。返回任何其他值则会替换 payload，对后续处理器和实际请求都生效。

这个 hook 可以改写 provider 级的系统指令，或将其完全移除。这类 payload 层面的修改不会反映在 `ctx.getSystemPrompt()` 中——后者报告的是 Pi 的系统提示词字符串，而不是最终序列化后的 provider payload。

```typescript
pi.on("before_provider_request", (event, ctx) => {
  console.log(JSON.stringify(event.payload, null, 2));

  // 可选：替换 payload
  // return { ...event.payload, temperature: 0 };
});
```

它主要用于调试 provider 序列化和缓存行为。

#### after_provider_response

在收到 HTTP 响应之后、其流式响应体被消费之前触发。处理器按 extension 加载顺序运行。

```typescript
pi.on("after_provider_response", (event, ctx) => {
  // event.status - HTTP 状态码
  // event.headers - 规范化后的响应头
  if (event.status === 429) {
    console.log("rate limited", event.headers["retry-after"]);
  }
});
```

响应头的可用性取决于 provider 和传输方式。对 HTTP 响应做了抽象的 provider 可能不会暴露响应头。

### 模型事件

#### model_select

在模型通过 `/model` 命令、模型循环切换（`Ctrl+P`）或 session 恢复而变化时触发。

```typescript
pi.on("model_select", async (event, ctx) => {
  // event.model - 新选中的模型
  // event.previousModel - 之前的模型（首次选择时为 undefined）
  // event.source - "set" | "cycle" | "restore"

  const prev = event.previousModel
    ? `${event.previousModel.provider}/${event.previousModel.id}`
    : "none";
  const next = `${event.model.provider}/${event.model.id}`;

  ctx.ui.notify(`Model changed (${event.source}): ${prev} -> ${next}`, "info");
});
```

用它在活动模型变化时更新 UI 元素（状态栏、底栏）或执行模型相关的初始化。

#### thinking_level_select

在思考级别变化时触发。这只是通知性质的事件；处理器的返回值会被忽略。

```typescript
pi.on("thinking_level_select", async (event, ctx) => {
  // event.level - 新选中的思考级别
  // event.previousLevel - 之前的思考级别

  ctx.ui.setStatus("thinking", `thinking: ${event.level}`);
});
```

用它在 `pi.setThinkingLevel()`、模型变化或内置思考级别控件改变活动思考级别时更新 extension 的 UI。

### 工具事件

#### tool_call

在 `tool_execution_start` 之后、工具执行之前触发。**可以阻止执行。** 使用 `isToolCallEventType` 收窄类型并获得带类型的输入。

在 `tool_call` 运行之前，pi 会等待先前发出的 Agent 事件全部经由 `AgentSession` 处理完毕。这意味着 `ctx.sessionManager` 的状态已经同步到当前发起工具调用的 assistant 消息。

在默认的并行工具执行模式下，同一条 assistant 消息中的同级工具调用会先顺序预检，然后并发执行。`tool_call` 不保证能在 `ctx.sessionManager` 中看到同一条 assistant 消息中同级工具的结果。

`event.input` 是可变的。就地修改它即可在执行前修补工具参数。

行为保证：
- 对 `event.input` 的修改会影响实际的工具执行
- 更晚的 `tool_call` 处理器能看到更早处理器所做的修改
- 修改之后不会重新做校验
- `tool_call` 的返回值只通过 `{ block: true, reason?: string }` 控制是否阻止执行

```typescript
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";

pi.on("tool_call", async (event, ctx) => {
  // event.toolName - "bash"、"read"、"write"、"edit" 等
  // event.toolCallId
  // event.input - 工具参数（可变）

  // 内置工具：无需类型参数
  if (isToolCallEventType("bash", event)) {
    // event.input 是 { command: string; timeout?: number }
    event.input.command = `source ~/.profile\n${event.input.command}`;

    if (event.input.command.includes("rm -rf")) {
      return { block: true, reason: "Dangerous command" };
    }
  }

  if (isToolCallEventType("read", event)) {
    // event.input 是 { path: string; offset?: number; limit?: number }
    console.log(`Reading: ${event.input.path}`);
  }
});
```

#### 为自定义工具的输入标注类型

自定义工具应导出其输入类型：

```typescript
// my-extension.ts
export type MyToolInput = Static<typeof myToolSchema>;
```

带显式类型参数使用 `isToolCallEventType`：

```typescript
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { MyToolInput } from "my-extension";

pi.on("tool_call", (event) => {
  if (isToolCallEventType<"my_tool", MyToolInput>("my_tool", event)) {
    event.input.action;  // 有类型
  }
});
```

#### tool_result

在工具执行结束之后、`tool_execution_end` 及最终工具结果消息事件发出之前触发。**可以修改结果。**

在并行工具模式下，`tool_result` 和 `tool_execution_end` 可能按工具完成顺序交错发生，而最终的 `toolResult` 消息事件仍然稍后按 assistant 消息中的原始顺序发出。

`tool_result` 处理器像中间件一样链式执行：
- 处理器按 extension 加载顺序运行
- 每个处理器看到的都是前一个处理器修改后的最新结果
- 处理器可以返回部分补丁（`content`、`details` 或 `isError`）；省略的字段保持当前值

在处理器内部的嵌套异步工作请使用 `ctx.signal`。这样 Esc 就能取消 extension 发起的模型调用、`fetch()` 以及其他支持中止的操作。

```typescript
import { isBashToolResult } from "@earendil-works/pi-coding-agent";

pi.on("tool_result", async (event, ctx) => {
  // event.toolName, event.toolCallId, event.input
  // event.content, event.details, event.isError

  if (isBashToolResult(event)) {
    // event.details 的类型为 BashToolDetails
  }

  const response = await fetch("https://example.com/summarize", {
    method: "POST",
    body: JSON.stringify({ content: event.content }),
    signal: ctx.signal,
  });

  // 修改结果：
  return { content: [...], details: {...}, isError: false };
});
```

### 用户 Bash 事件

#### user_bash

在用户执行 `!` 或 `!!` 命令时触发。**可以拦截。**

```typescript
import { createLocalBashOperations } from "@earendil-works/pi-coding-agent";

pi.on("user_bash", (event, ctx) => {
  // event.command - bash 命令
  // event.excludeFromContext - 使用 !! 前缀时为 true
  // event.cwd - 工作目录

  // 方式 1：提供自定义 operations（如 SSH）
  return { operations: remoteBashOps };

  // 方式 2：包装 pi 内置的本地 bash 后端
  const local = createLocalBashOperations();
  return {
    operations: {
      exec(command, cwd, options) {
        return local.exec(`source ~/.profile\n${command}`, cwd, options);
      }
    }
  };

  // 方式 3：完全接管——直接返回结果
  return { result: { output: "...", exitCode: 0, cancelled: false, truncated: false } };
});
```

### 输入事件

#### input

在收到用户输入时触发，时机在 extension 命令检查之后、skill 和模板展开之前。事件看到的是原始输入文本，因此 `/skill:foo` 和 `/template` 尚未展开。

**处理顺序：**
1. 先检查 extension 命令（`/cmd`）——命中则运行其处理器，跳过 input 事件
2. 触发 `input` 事件——可以拦截、变换或直接处理
3. 若未被处理：skill 命令（`/skill:name`）展开为 skill 内容
4. 若未被处理：提示词模板（`/template`）展开为模板内容
5. agent 处理开始（`before_agent_start` 等）

```typescript
pi.on("input", async (event, ctx) => {
  // event.text - 原始输入（skill/模板展开之前）
  // event.images - 附带的图片（如有）
  // event.source - "interactive"（用户输入）、"rpc"（API）或 "extension"（经 sendUserMessage）
  // event.streamingBehavior - "steer" | "followUp" | undefined
  //   空闲时为 undefined，流式过程中的打断为 "steer"，
  //   排队等 agent 结束的消息为 "followUp"

  // 变换：在展开前改写输入
  if (event.text.startsWith("?quick "))
    return { action: "transform", text: `Respond briefly: ${event.text.slice(7)}` };

  // 处理：不经 LLM 直接响应（extension 自行给出反馈）
  if (event.text === "ping") {
    ctx.ui.notify("pong", "info");
    return { action: "handled" };
  }

  // 按来源路由：extension 注入的消息跳过处理
  if (event.source === "extension") return { action: "continue" };

  // 在展开前拦截 skill 命令
  if (event.text.startsWith("/skill:")) {
    // 可以变换、阻止，或放行
  }

  return { action: "continue" };  // 默认：透传给展开流程
});
```

**结果：**
- `continue` - 原样透传（处理器不返回任何值时的默认行为）
- `transform` - 修改文本/图片，然后继续进入展开流程
- `handled` - 完全跳过 agent（第一个返回它的处理器生效）

变换会在各处理器之间链式传递。感知 `streamingBehavior` 的路由示例见 [input-transform.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/input-transform.ts) 和 [input-transform-streaming.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/input-transform-streaming.ts)。

## ExtensionContext

所有处理器都会收到 `ctx: ExtensionContext`。

### ctx.ui

用户交互的 UI 方法。完整说明见[自定义 UI](#自定义-ui)。

### ctx.mode

当前运行模式：`"tui"`、`"rpc"`、`"json"` 或 `"print"`。用 `ctx.mode === "tui"` 来保护只在终端可用的功能，如 `custom()`、组件工厂、终端输入和直接的 TUI 渲染。

### ctx.hasUI

在 TUI 和 RPC 模式下为 `true`；在 print 模式（`-p`）和 JSON 模式下为 `false`。用它来保护对话框方法（`select`、`confirm`、`input`、`editor`）以及在 TUI 和 RPC 两种模式下都可用的即发即弃方法（`notify`、`setStatus`、`setWidget`、`setTitle`、`setEditorText`）。在 RPC 模式下，部分 TUI 专用方法是空操作或返回默认值（见 [rpc.md](rpc.md#extension-ui-协议)）。

### ctx.cwd

当前工作目录。

构造项目本地配置路径时使用 `CONFIG_DIR_NAME`，不要硬编码 `.pi`。重新品牌化的发行版可能使用不同的配置目录名。

```typescript
import { CONFIG_DIR_NAME, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { join } from "node:path";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", (_event, ctx) => {
    const projectConfigPath = join(ctx.cwd, CONFIG_DIR_NAME, "my-extension.json");
    // ...
  });
}
```

### ctx.isProjectTrusted()

返回当前 session 上下文中项目本地信任是否处于生效状态。这包括临时信任决定和 CLI 信任覆盖，而不仅是全局信任存储中保存的决定。

在读取只应对受信任项目生效的项目本地 extension 配置之前，先调用它。

### ctx.sessionManager

对 session 状态的只读访问。完整的 SessionManager API 和条目类型见 [Session 格式](session-format.md)。

对于 `tool_call`，该状态在处理器运行前已同步到当前 assistant 消息。在并行工具执行模式下，它仍不保证包含同一条 assistant 消息中同级工具的结果。

```typescript
ctx.sessionManager.getEntries()             // 所有条目
ctx.sessionManager.getBranch()              // 当前分支
ctx.sessionManager.buildContextEntries()    // 应用了上下文压缩的活动分支条目
ctx.sessionManager.getLeafId()              // 当前叶子条目 ID
```

### ctx.modelRegistry / ctx.model

访问模型、provider 和已解析的认证信息。`ctx.modelRegistry.getProvider(id)` 返回生效的 pi-ai provider，而 `getProviderAuth(id)` 无需已加载的模型即可解析其当前 API key、请求头、base URL 和 provider 级环境变量。`ctx.model` 是当前活动模型。

### ctx.signal

当前 agent 的中止信号；没有活动的 agent turn 时为 `undefined`。

在 extension 处理器发起的、支持中止的嵌套工作中使用它，例如：
- `fetch(..., { signal: ctx.signal })`
- 接受 `signal` 的模型调用
- 接受 `AbortSignal` 的文件或进程辅助函数

`ctx.signal` 通常在活动 turn 的事件（如 `tool_call`、`tool_result`、`message_update`、`turn_end`）中有值。
在空闲或非 turn 的上下文中（如 session 事件、extension 命令、pi 空闲时触发的快捷键）通常为 `undefined`。

```typescript
pi.on("tool_result", async (event, ctx) => {
  const response = await fetch("https://example.com/api", {
    method: "POST",
    body: JSON.stringify(event),
    signal: ctx.signal,
  });

  const data = await response.json();
  return { details: data };
});
```

### ctx.isIdle() / ctx.abort() / ctx.hasPendingMessages()

流程控制辅助方法。当 Pi 正在处理一次 agent 运行、自动重试、自动压缩后重试或排队的续跑时，`ctx.isIdle()` 为 false。

### ctx.shutdown()

请求 pi 优雅关停。

- **交互模式：** 推迟到 agent 空闲之后（处理完所有排队的 steering 和后续消息）。
- **RPC 模式：** 推迟到下一次空闲状态（完成当前命令响应、等待下一条命令时）。
- **print 模式：** 空操作。所有 prompt 处理完毕后进程自动退出。

退出前会向所有 extension 发出 `session_shutdown` 事件。在所有上下文（事件处理器、工具、命令、快捷键）中都可用。

```typescript
pi.on("tool_call", (event, ctx) => {
  if (isFatal(event.input)) {
    ctx.shutdown();
  }
});
```

### ctx.getContextUsage()

返回当前活动模型的上下文用量。可用时使用最近一条 assistant 消息的 usage，然后对尾部消息做 token 估算。

```typescript
const usage = ctx.getContextUsage();
if (usage && usage.tokens > 100_000) {
  // ...
}
```

### ctx.compact()

触发上下文压缩，不等待其完成。用 `onComplete` 和 `onError` 做后续处理。

```typescript
ctx.compact({
  customInstructions: "Focus on recent changes",
  onComplete: (result) => {
    ctx.ui.notify("Compaction completed", "info");
  },
  onError: (error) => {
    ctx.ui.notify(`Compaction failed: ${error.message}`, "error");
  },
});
```

### ctx.getSystemPrompt()

返回 Pi 当前的系统提示词字符串。

- 在 `before_agent_start` 期间，它反映当前 turn 到目前为止的链式系统提示词修改。
- 它不包含之后 `context` 事件对消息的修改。
- 它不包含 `before_provider_request` 对 payload 的改写。
- 如果加载更晚的 extension 在你之后运行，它们仍可能改变最终发送的内容。

```typescript
pi.on("before_agent_start", (event, ctx) => {
  const prompt = ctx.getSystemPrompt();
  console.log(`System prompt length: ${prompt.length}`);
});
```

## ExtensionCommandContext

命令处理器收到的是 `ExtensionCommandContext`，它在 `ExtensionContext` 的基础上扩展了 session 控制方法。这些方法只在命令中可用，因为在事件处理器中调用它们可能造成死锁。

### ctx.getSystemPromptOptions()

返回 Pi 当前用于构建系统提示词的基础输入。

```typescript
const options = ctx.getSystemPromptOptions();
const contextPaths = options.contextFiles?.map((file) => file.path) ?? [];
```

它与 `before_agent_start` 的 `event.systemPromptOptions` 具有相同的形状和可变性：自定义提示词、活动工具、工具摘要、提示词指导条目、追加的系统提示词文本、cwd、已加载的上下文文件和已加载的 skill。它可能包含上下文文件的完整内容，因此应把它当作敏感的 extension 本地数据对待，避免通过命令列表、日志或自动补全元数据暴露出去。

它报告的是当前的基础提示词输入。不包含每 turn 的 `before_agent_start` 链式系统提示词修改、之后的 `context` 事件消息修改，或 `before_provider_request` 的 payload 改写。

### ctx.waitForIdle()

等待 agent 完全安定下来，包括自动重试、自动压缩后重试和排队的续跑：

```typescript
pi.registerCommand("my-cmd", {
  handler: async (args, ctx) => {
    await ctx.waitForIdle();
    // agent 现在空闲，可以安全修改 session
  },
});
```

### ctx.newSession(options?)

创建一个新 session：

```typescript
const parentSession = ctx.sessionManager.getSessionFile();
const kickoff = "Continue in the replacement session";

const result = await ctx.newSession({
  parentSession,
  setup: async (sm) => {
    sm.appendMessage({
      role: "user",
      content: [{ type: "text", text: "Context from previous session..." }],
      timestamp: Date.now(),
    });
  },
  withSession: async (ctx) => {
    // 这里只使用替换 session 的 ctx。
    await ctx.sendUserMessage(kickoff);
  },
});

if (result.cancelled) {
  // 某个 extension 取消了新建 session
}
```

选项：
- `parentSession`：写入新 session 头部的父 session 文件
- `setup`：在 `withSession` 运行之前修改新 session 的 `SessionManager`
- `withSession`：在切换后针对全新的替换 session 上下文执行工作。不要使用捕获的旧 `pi` / 命令 `ctx`；见 [Session 替换的生命周期与陷阱](#session-替换的生命周期与陷阱)。

### ctx.fork(entryId, options?)

从指定条目分叉，创建一个新的 session 文件：

```typescript
const result = await ctx.fork("entry-id-123", {
  withSession: async (ctx) => {
    // 这里只使用替换 session 的 ctx。
    ctx.ui.notify("Now in the forked session", "info");
  },
});
if (result.cancelled) {
  // 某个 extension 取消了 fork
}

const cloneResult = await ctx.fork("entry-id-456", { position: "at" });
if (cloneResult.cancelled) {
  // 某个 extension 取消了 clone
}
```

选项：
- `position`：`"before"`（默认）在所选用户消息之前分叉，并把那条 prompt 还原到编辑器中
- `position`：`"at"` 复制经过所选条目的活动路径，不还原编辑器文本
- `withSession`：在切换后针对全新的替换 session 上下文执行工作。不要使用捕获的旧 `pi` / 命令 `ctx`；见 [Session 替换的生命周期与陷阱](#session-替换的生命周期与陷阱)。

### ctx.navigateTree(targetId, options?)

导航到 session 树中的另一个位置：

```typescript
const result = await ctx.navigateTree("entry-id-456", {
  summarize: true,
  customInstructions: "Focus on error handling changes",
  replaceInstructions: false, // true = 完全替换默认提示词
  label: "review-checkpoint",
});
```

选项：
- `summarize`：是否为被放弃的分支生成摘要
- `customInstructions`：给摘要器的自定义指令
- `replaceInstructions`：为 true 时，`customInstructions` 替换默认提示词，而不是追加
- `label`：附加到分支摘要条目上的标签（不生成摘要时附加到目标条目上）

### ctx.switchSession(sessionPath, options?)

切换到另一个 session 文件：

```typescript
const result = await ctx.switchSession("/path/to/session.jsonl", {
  withSession: async (ctx) => {
    await ctx.sendUserMessage("Resume work in the replacement session");
  },
});
if (result.cancelled) {
  // 某个 extension 通过 session_before_switch 取消了切换
}
```

选项：
- `withSession`：在切换后针对全新的替换 session 上下文执行工作。不要使用捕获的旧 `pi` / 命令 `ctx`；见 [Session 替换的生命周期与陷阱](#session-替换的生命周期与陷阱)。

要发现可用的 session，使用静态方法 `SessionManager.list()` 或 `SessionManager.listAll()`：

```typescript
import { SessionManager } from "@earendil-works/pi-coding-agent";

pi.registerCommand("switch", {
  description: "Switch to another session",
  handler: async (args, ctx) => {
    const sessions = await SessionManager.list(ctx.cwd);
    if (sessions.length === 0) return;
    const choice = await ctx.ui.select(
      "Pick session:",
      sessions.map(s => s.file),
    );
    if (choice) {
      await ctx.switchSession(choice, {
        withSession: async (ctx) => {
          ctx.ui.notify("Switched session", "info");
        },
      });
    }
  },
});
```

### Session 替换的生命周期与陷阱

`withSession` 收到一个全新的 `ReplacedSessionContext`，它在 `ExtensionCommandContext` 的基础上扩展了绑定到替换 session 的异步 `sendMessage()` 和 `sendUserMessage()` 辅助方法。

生命周期与陷阱：
- `withSession` 只有在旧 session 已发出 `session_shutdown`、旧运行时已被拆除、替换 session 已重新绑定、新的 extension 实例已收到 `session_start` 之后才运行。
- 回调仍在原来的闭包中执行，而不是在新的 extension 实例内部。这意味着在 `withSession` 开始时，你的旧 extension 实例可能已经执行过关停清理。
- 捕获的旧 `pi` / 旧命令 `ctx` 中绑定 session 的对象在替换后已失效，使用它们会抛出异常。session 相关工作只使用传给 `withSession` 的 `ctx`。
- 此前提取出来的原始对象仍由你自己负责。例如，如果你在替换前捕获了 `const sm = ctx.sessionManager`，那么 `sm` 仍是旧的 `SessionManager` 对象。替换后不要再使用它。
- `withSession` 中的代码应假定被你的 `session_shutdown` 处理器清理掉的状态已经不存在。只捕获能干净地在关停后存活的纯数据，如字符串、id 和序列化配置。

安全的写法：

```typescript
pi.registerCommand("handoff", {
  handler: async (_args, ctx) => {
    const kickoff = "Continue from the replacement session";
    await ctx.newSession({
      withSession: async (ctx) => {
        await ctx.sendUserMessage(kickoff);
      },
    });
  },
});
```

不安全的写法：

```typescript
pi.registerCommand("handoff", {
  handler: async (_args, ctx) => {
    const oldSessionManager = ctx.sessionManager;
    await ctx.newSession({
      withSession: async (_ctx) => {
        // 失效的旧对象：不要这样做
        oldSessionManager.getSessionFile();
        pi.sendUserMessage("wrong");
      },
    });
  },
});
```

### ctx.reload()

运行与 `/reload` 相同的重载流程。

```typescript
pi.registerCommand("reload-runtime", {
  description: "Reload extensions, skills, prompts, themes, and context files",
  handler: async (_args, ctx) => {
    await ctx.reload();
    return;
  },
});
```

重要行为：
- `await ctx.reload()` 会为当前 extension 运行时发出 `session_shutdown`
- 然后重新加载资源，并发出 `reason: "reload"` 的 `session_start` 和 reason 为 `"reload"` 的 `resources_discover`
- 当前正在运行的命令处理器仍在旧的调用帧中继续执行
- `await ctx.reload()` 之后的代码仍然运行的是重载前的版本
- `await ctx.reload()` 之后的代码不得假定旧的内存中 extension 状态仍然有效
- 处理器返回之后，后续的命令/事件/工具调用使用新版本的 extension

为了行为可预测，把 reload 当作该处理器的终点（`await ctx.reload(); return;`）。

工具运行时拿到的是 `ExtensionContext`，因此不能直接调用 `ctx.reload()`。用一个命令作为 reload 入口，再暴露一个工具，把该命令作为后续用户消息排队。

LLM 可调用的触发 reload 的工具示例：

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export default function (pi: ExtensionAPI) {
  pi.registerCommand("reload-runtime", {
    description: "Reload extensions, skills, prompts, themes, and context files",
    handler: async (_args, ctx) => {
      await ctx.reload();
      return;
    },
  });

  pi.registerTool({
    name: "reload_runtime",
    label: "Reload Runtime",
    description: "Reload extensions, skills, prompts, themes, and context files",
    parameters: Type.Object({}),
    async execute() {
      pi.sendUserMessage("/reload-runtime", { deliverAs: "followUp" });
      return {
        content: [{ type: "text", text: "Queued /reload-runtime as a follow-up command." }],
      };
    },
  });
}
```

## ExtensionAPI 方法

### pi.on(event, handler)

订阅事件。事件类型和返回值见[事件](#事件)。

### pi.registerTool(definition)

注册可供 LLM 调用的自定义工具。完整说明见[自定义工具](#自定义工具)。

`pi.registerTool()` 在 extension 加载期间和启动之后都可用。你可以在 `session_start`、命令处理器或其他事件处理器中调用它。新工具会在同一 session 中立即刷新，出现在 `pi.getAllTools()` 中并可被 LLM 调用，无需 `/reload`。

使用 `pi.setActiveTools()` 在运行时启用或禁用工具（包括动态添加的工具）。

使用 `promptSnippet` 让自定义工具在 `Available tools` 中获得单行条目；使用 `promptGuidelines` 在工具处于活动状态时向默认 `Guidelines` 部分追加工具专属条目。

**重要：** `promptGuidelines` 条目会被平铺追加到 `Guidelines` 部分，不带工具名前缀。每条指导必须点名它所指的工具——避免写"Use this tool when..."，因为 LLM 无法分辨"this"指的是哪个工具。要写"Use my_tool when..."。

完整示例见 [dynamic-tools.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/dynamic-tools.ts)。

```typescript
import { Type } from "typebox";
import { StringEnum } from "@earendil-works/pi-ai";

pi.registerTool({
  name: "my_tool",
  label: "My Tool",
  description: "What this tool does",
  promptSnippet: "Summarize or transform text according to action",
  promptGuidelines: ["Use my_tool when the user asks to summarize previously generated text."],
  parameters: Type.Object({
    action: StringEnum(["list", "add"] as const),
    text: Type.Optional(Type.String()),
  }),
  prepareArguments(args) {
    // 可选的兼容垫片。在 schema 校验之前运行。
    // 返回符合当前 schema 形状的对象，例如把旧字段
    // 折叠进现在的参数对象。
    return args;
  },

  async execute(toolCallId, params, signal, onUpdate, ctx) {
    // 流式报告进度
    onUpdate?.({ content: [{ type: "text", text: "Working..." }] });

    return {
      content: [{ type: "text", text: "Done" }],
      details: { result: "..." },
    };
  },

  // 可选：自定义渲染
  renderCall(args, theme, context) { ... },
  renderResult(result, options, theme, context) { ... },
});
```

### pi.sendMessage(message, options?)

向 session 注入一条自定义消息。自定义消息会参与 LLM 上下文。对于不应发送给 LLM 的持久化 TUI 专用内容，请使用 [`pi.appendEntry()`](#piappendentrycustomtype-data) 搭配 [`pi.registerEntryRenderer()`](#piregisterentryrenderercustomtype-renderer)。

```typescript
pi.sendMessage({
  customType: "my-extension",
  content: "Message text",
  display: true,
  details: { ... },
}, {
  triggerTurn: true,
  deliverAs: "steer",
});
```

**选项：**
- `deliverAs` - 投递模式：
  - `"steer"`（默认）- 流式过程中排队。在当前 assistant turn 执行完其工具调用之后、下一次 LLM 调用之前投递。
  - `"followUp"` - 等 agent 结束。仅当 agent 不再有工具调用时投递。
  - `"nextTurn"` - 排队等下一条用户 prompt。不打断也不触发任何东西。
- `triggerTurn: true` - 若 agent 空闲，立即触发一次 LLM 响应。只对 `"steer"` 和 `"followUp"` 模式生效（`"nextTurn"` 忽略它）。

### pi.sendUserMessage(content, options?)

向 agent 发送一条用户消息。与发送自定义消息的 `sendMessage()` 不同，它发送的是一条真正的用户消息，看起来就像用户亲自输入的一样。总是会触发一个 turn。

```typescript
// 简单文本消息
pi.sendUserMessage("What is 2+2?");

// 使用内容数组（文本 + 图片）
pi.sendUserMessage([
  { type: "text", text: "Describe this image:" },
  { type: "image", source: { type: "base64", mediaType: "image/png", data: "..." } },
]);

// 流式过程中——必须指定投递模式
pi.sendUserMessage("Focus on error handling", { deliverAs: "steer" });
pi.sendUserMessage("And then summarize", { deliverAs: "followUp" });
```

**选项：**
- `deliverAs` - agent 正在流式输出时必填：
  - `"steer"` - 在当前 assistant turn 执行完其工具调用之后投递
  - `"followUp"` - 等 agent 完成所有工具后投递

非流式时，消息立即发送并触发新的 turn。流式过程中未指定 `deliverAs` 时抛出错误。

完整示例见 [send-user-message.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/send-user-message.ts)。

### pi.appendEntry(customType, data?)

持久化 extension 数据。自定义条目不参与 LLM 上下文。在交互模式下，搭配 `pi.registerEntryRenderer()` 还可以渲染到聊天记录中。

```typescript
pi.appendEntry("my-state", { count: 42 });
pi.appendEntry("status-card", { title: "Indexed files", count: 17 });

// 重载时恢复
pi.on("session_start", async (_event, ctx) => {
  for (const entry of ctx.sessionManager.getEntries()) {
    if (entry.type === "custom" && entry.customType === "my-state") {
      // 从 entry.data 重建
    }
  }
});
```

### pi.setSessionName(name)

设置 session 的显示名称（在 session 选择器中代替第一条消息显示）。

```typescript
pi.setSessionName("Refactor auth module");
```

### pi.getSessionName()

获取当前 session 名称（如已设置）。

```typescript
const name = pi.getSessionName();
if (name) {
  console.log(`Session: ${name}`);
}
```

### pi.setLabel(entryId, label)

设置或清除条目上的标签。标签是用户自定义的标记，用于书签和导航（显示在 `/tree` 选择器中）。

```typescript
// 设置标签
pi.setLabel(entryId, "checkpoint-before-refactor");

// 清除标签
pi.setLabel(entryId, undefined);

// 通过 sessionManager 读取标签
const label = ctx.sessionManager.getLabel(entryId);
```

标签持久化在 session 中，重启后仍然存在。用它们标记对话树中的重要位置（turn、保存点）。

### pi.registerCommand(name, options)

注册一个命令。

如果多个 extension 注册了同名命令，pi 会全部保留，并按加载顺序分配数字调用后缀，例如 `/review:1` 和 `/review:2`。

```typescript
pi.registerCommand("stats", {
  description: "Show session statistics",
  handler: async (args, ctx) => {
    const count = ctx.sessionManager.getEntries().length;
    ctx.ui.notify(`${count} entries`, "info");
  }
});
```

可选：为 `/command ...` 添加参数自动补全：

```typescript
import type { AutocompleteItem } from "@earendil-works/pi-tui";

pi.registerCommand("deploy", {
  description: "Deploy to an environment",
  getArgumentCompletions: (prefix: string): AutocompleteItem[] | null => {
    const envs = ["dev", "staging", "prod"];
    const items = envs.map((e) => ({ value: e, label: e }));
    const filtered = items.filter((i) => i.value.startsWith(prefix));
    return filtered.length > 0 ? filtered : null;
  },
  handler: async (args, ctx) => {
    ctx.ui.notify(`Deploying: ${args}`, "info");
  },
});
```

### pi.getCommands()

获取当前 session 中可通过 `prompt` 调用的斜杠命令。包括 extension 命令、提示词模板和 skill 命令。
列表顺序与 RPC 的 `get_commands` 相同：先 extension，再模板，最后 skill。

```typescript
const commands = pi.getCommands();
const bySource = commands.filter((command) => command.source === "extension");
const userScoped = commands.filter((command) => command.sourceInfo.scope === "user");
```

每个条目的形状如下：

```typescript
{
  name: string; // 可调用的命令名，不含前导斜杠。可能带后缀，如 "review:1"
  description?: string;
  source: "extension" | "prompt" | "skill";
  sourceInfo: {
    path: string;
    source: string;
    scope: "user" | "project" | "temporary";
    origin: "package" | "top-level";
    baseDir?: string;
  };
}
```

把 `sourceInfo` 作为来源的权威字段。不要通过命令名或临时的路径解析来推断归属。

内置的交互式命令（如 `/model` 和 `/settings`）不包含在内。它们只在交互模式下处理，通过 `prompt` 发送不会执行。

### pi.registerMessageRenderer(customType, renderer)

为带有你的 `customType` 的自定义消息注册自定义 TUI 渲染器。自定义消息通过 `pi.sendMessage()` 创建，会参与 LLM 上下文。见[自定义 UI](#自定义-ui)。

### pi.registerEntryRenderer(customType, renderer)

为带有你的 `customType` 的自定义条目注册自定义 TUI 渲染器。自定义条目通过 `pi.appendEntry()` 创建，不参与 LLM 上下文。

```typescript
import { Box, Text } from "@earendil-works/pi-tui";

pi.registerEntryRenderer("status-card", (entry, { expanded }, theme) => {
  const data = entry.data as { title: string; count: number };
  const box = new Box(1, 1, (text) => theme.bg("customMessageBg", text));
  box.addChild(new Text(`${theme.bold(data.title)}: ${data.count}`));
  if (expanded) {
    box.addChild(new Text(theme.fg("dim", JSON.stringify(data, null, 2))));
  }
  return box;
});

pi.appendEntry("status-card", { title: "Indexed files", count: 17 });
```

### pi.registerShortcut(shortcut, options)

注册一个键盘快捷键。快捷键格式与内置按键绑定见 [keybindings.md](keybindings.md)。

```typescript
pi.registerShortcut("ctrl+shift+p", {
  description: "Toggle plan mode",
  handler: async (ctx) => {
    ctx.ui.notify("Toggled!");
  },
});
```

### pi.registerFlag(name, options)

注册一个 CLI 标志。

```typescript
pi.registerFlag("plan", {
  description: "Start in plan mode",
  type: "boolean",
  default: false,
});

// 检查值
if (pi.getFlag("plan")) {
  // 已启用 plan 模式
}
```

### pi.exec(command, args, options?)

执行一条 shell 命令。

```typescript
const result = await pi.exec("git", ["status"], { signal, timeout: 5000 });
// result.stdout, result.stderr, result.code, result.killed
```

### pi.getActiveTools() / pi.getAllTools() / pi.setActiveTools(names)

管理活动工具。对内置工具和动态注册的工具都有效。`pi.getActiveTools()` 以 `string[]` 返回活动工具名；`pi.getAllTools()` 返回所有已配置工具的元数据。

```typescript
const active = pi.getActiveTools(); // ["read", "bash", ...]
const all = pi.getAllTools();
// all = [{
//   name: "read",
//   description: "Read file contents...",
//   parameters: ...,
//   promptGuidelines: ["Use read to examine files instead of cat or sed."],
//   sourceInfo: { path: "<builtin:read>", source: "builtin", scope: "temporary", origin: "top-level" }
// }, ...]
const builtinTools = all.filter((t) => t.sourceInfo.source === "builtin");
const extensionTools = all.filter((t) => t.sourceInfo.source !== "builtin" && t.sourceInfo.source !== "sdk");
pi.setActiveTools([...new Set([...active, "my_custom_tool"])]); // 保留当前工具并启用 my_custom_tool
pi.setActiveTools(["read", "bash"]); // 切换为只读
```

`pi.getAllTools()` 返回 `name`、`description`、`parameters`、`promptGuidelines` 和 `sourceInfo`。

典型的 `sourceInfo.source` 取值：
- 内置工具为 `builtin`
- 经 `createAgentSession({ customTools })` 传入的工具为 `sdk`
- extension 注册的工具为其 extension 来源元数据

### pi.setModel(model)

设置当前模型。若该模型没有可用的 API key，返回 `false`。自定义模型的配置见 [models.md](models.md)。

```typescript
const model = ctx.modelRegistry.find("anthropic", "claude-sonnet-4-5");
if (model) {
  const success = await pi.setModel(model);
  if (!success) {
    ctx.ui.notify("No API key for this model", "error");
  }
}
```

### pi.getThinkingLevel() / pi.setThinkingLevel(level)

获取或设置思考级别。级别会被收窄到模型能力范围内（不支持推理的模型始终使用 "off"）。变化会触发 `thinking_level_select`。

```typescript
const current = pi.getThinkingLevel();  // "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max"
pi.setThinkingLevel("high");
```

### pi.events

用于 extension 之间通信的共享事件总线：

```typescript
pi.events.on("my:event", (data) => { ... });
pi.events.emit("my:event", { ... });
```

### pi.registerProvider(name, config)

动态注册或覆盖模型 provider。适用于代理、自定义端点或团队级模型配置。

在 extension 工厂函数期间发起的调用会排队，在 runner 初始化后统一应用。之后发起的调用——例如用户完成设置流程后的命令处理器中——会立即生效，无需 `/reload`。

动态 provider 可以实现 `refreshModels`。Pi 在模型刷新期间调用它，把返回的列表同步发布到该 provider，并传入规范的凭证/存储/网络/信号上下文。是否通过 `context.store` 持久化目录由 extension 自行决定；llama.cpp 这类实时服务器可以忽略它。

需要原生 provider 认证、过滤、刷新或流式行为的 extension，可以注册一个来自 `@earendil-works/pi-ai` 的完整 `Provider`。该 provider 会成为组合的基础，`models.json` 的覆盖仍然叠加在它之上。

```typescript
import { createProvider, openAICompletionsApi } from "@earendil-works/pi-ai";

const provider = createProvider({
  id: "local-server",
  name: "Local Server",
  baseUrl: "http://localhost:8080/v1",
  auth: {
    apiKey: {
      name: "Local server setup",
      async login(interaction) {
        return {
          type: "api_key",
          key: await interaction.prompt({ type: "secret", message: "API key" }),
        };
      },
      async resolve({ credential }) {
        return credential?.key
          ? { auth: { apiKey: credential.key }, source: "stored API key" }
          : undefined;
      },
    },
  },
  models: [],
  api: openAICompletionsApi(),
});

pi.registerProvider(provider);

// 注册带自定义模型的新 provider
pi.registerProvider("my-proxy", {
  name: "My Proxy",
  baseUrl: "https://proxy.example.com",
  apiKey: "$PROXY_API_KEY",  // 环境变量引用
  api: "anthropic-messages",
  models: [
    {
      id: "claude-sonnet-4-20250514",
      name: "Claude 4 Sonnet (proxy)",
      reasoning: false,
      input: ["text", "image"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 200000,
      maxTokens: 16384
    }
  ]
});

// 注册一个实时的 llama.cpp 目录，不持久化发现的模型
pi.registerProvider("llama.cpp", {
  baseUrl: "http://localhost:8080/v1",
  apiKey: "local",
  api: "openai-completions",
  async refreshModels({ signal }) {
    const response = await fetch("http://localhost:8080/v1/models", { signal });
    const { data } = await response.json();
    return data.map(({ id }) => ({
      id,
      name: id,
      reasoning: false,
      input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 128000,
      maxTokens: 16384
    }));
  }
});

// 覆盖现有 provider 的 baseUrl（保留所有模型）
pi.registerProvider("anthropic", {
  baseUrl: "https://proxy.example.com"
});

// 注册支持 OAuth 的 provider，用于 /login
pi.registerProvider("corporate-ai", {
  baseUrl: "https://ai.corp.com",
  api: "openai-responses",
  models: [...],
  oauth: {
    name: "Corporate AI (SSO)",
    async login(callbacks) {
      // 自定义 OAuth 流程
      callbacks.onAuth({ url: "https://sso.corp.com/..." });
      const code = await callbacks.onPrompt({ message: "Enter code:" });
      return { refresh: code, access: code, expires: Date.now() + 3600000 };
    },
    async refreshToken(credentials) {
      // 刷新逻辑
      return credentials;
    },
    getApiKey(credentials) {
      return credentials.access;
    }
  }
});
```

对象形式接受完整的 pi-ai `Provider`，包括原生的 `auth`、`getModels`、`refreshModels`、`filterModels`、`stream` 和 `streamSimple` 行为。

**旧式配置选项：**
- `name` - provider 在 UI（如 `/login`）中的显示名称。
- `baseUrl` - API 端点 URL。定义模型时必填。
- `apiKey` - API key 字面量、环境变量插值（`$ENV_VAR` 或 `${ENV_VAR}`），或以 `!command` 开头的命令。定义模型时必填（除非提供了 `oauth`）。`$$` 转义 `$`，`$!` 转义字面 `!` 而不触发命令执行。
- `api` - API 类型：`"anthropic-messages"`、`"openai-completions"`、`"openai-responses"` 等。
- `headers` - 请求中附带的自定义请求头。
- `authHeader` - 为 true 时自动添加 `Authorization: Bearer` 请求头。
- `models` - 模型定义数组。若提供，会替换该 provider 的所有现有模型。模型定义可以设置 `baseUrl` 以针对该模型覆盖 provider 端点。
- `refreshModels` - 异步动态发现回调。其返回的模型会替换 extension 提供的模型。仅当结果需要持久化时才使用作用域化的 `context.store`。
- `oauth` - 用于 `/login` 支持的 OAuth provider 配置。提供后该 provider 会出现在登录菜单中。
- `streamSimple` - 面向非标准 API 的自定义流式实现。

进阶话题（自定义流式 API、OAuth 细节、模型定义参考）见 [custom-provider.md](custom-provider.md)。

### pi.unregisterProvider(name)

移除先前注册的 provider 及其模型。被该 provider 覆盖的内置模型会恢复。若该 provider 未曾注册，则没有任何效果。

与 `registerProvider` 一样，在初始加载阶段之后调用时立即生效，无需 `/reload`。

```typescript
pi.registerCommand("my-setup-teardown", {
  description: "Remove the custom proxy provider",
  handler: async (_args, _ctx) => {
    pi.unregisterProvider("my-proxy");
  },
});
```

## 状态管理

有状态的 extension 应把状态存进工具结果的 `details` 中，以便正确支持会话分支：

```typescript
export default function (pi: ExtensionAPI) {
  let items: string[] = [];

  // 从 session 重建状态
  pi.on("session_start", async (_event, ctx) => {
    items = [];
    for (const entry of ctx.sessionManager.getBranch()) {
      if (entry.type === "message" && entry.message.role === "toolResult") {
        if (entry.message.toolName === "my_tool") {
          items = entry.message.details?.items ?? [];
        }
      }
    }
  });

  pi.registerTool({
    name: "my_tool",
    // ...
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      items.push("new item");
      return {
        content: [{ type: "text", text: "Added" }],
        details: { items: [...items] },  // 存起来供重建使用
      };
    },
  });
}
```

## 自定义工具

通过 `pi.registerTool()` 注册可供 LLM 调用的工具。工具会出现在系统提示词中，并且可以自定义渲染。

使用 `promptSnippet` 在默认系统提示词的 `Available tools` 部分获得一条简短的单行条目。省略时，自定义工具不会出现在该部分。

使用 `promptGuidelines` 向默认系统提示词的 `Guidelines` 部分添加工具专属条目。这些条目只在工具处于活动状态时才会包含（例如经 `pi.setActiveTools([...])` 激活后）。

**重要：** `promptGuidelines` 条目会被平铺追加到 `Guidelines` 部分，没有工具名前缀，也不分组。每条指导必须点名它所指的工具——避免写"Use this tool when..."，因为 LLM 无法分辨"this"指的是哪个工具。要写"Use my_tool when..."。

注意：有些模型很蠢，会把 @ 前缀带进工具的路径参数。内置工具在解析路径前会去掉前导 @。如果你的自定义工具接受路径参数，也应同样规范化前导 @。

如果你的自定义工具会修改文件，请使用 `withFileMutationQueue()`，让它与内置的 `edit` 和 `write` 共用同一个按文件排队的队列。这很重要，因为工具调用默认并行运行。不使用该队列时，两个工具可能都读取同一份旧文件内容，各自计算出不同的更新，最终后写入的一方覆盖另一方。

失败案例示例：你的自定义工具在编辑 `foo.ts`，而同一个 assistant turn 中内置 `edit` 也在修改 `foo.ts`。如果你的工具不参与队列，两者都可能读取原始的 `foo.ts`，分别应用修改，其中一方的修改就丢了。

传给 `withFileMutationQueue()` 的应是真正的目标文件路径，而不是原始的用户参数。先相对于 `ctx.cwd` 或你工具的工作目录解析为绝对路径。对已存在的文件，该辅助函数会通过 `realpath()` 做规范化，因此指向同一文件的符号链接别名共享同一个队列。对新文件，由于还没有东西可以 `realpath()`，它退回到解析后的绝对路径。

把针对该目标路径的整个修改窗口都放进队列，包括读取-修改-写入的逻辑，而不只是最终的写入。

```typescript
import { withFileMutationQueue } from "@earendil-works/pi-coding-agent";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
  const absolutePath = resolve(ctx.cwd, params.path);

  return withFileMutationQueue(absolutePath, async () => {
    await mkdir(dirname(absolutePath), { recursive: true });
    const current = await readFile(absolutePath, "utf8");
    const next = current.replace(params.oldText, params.newText);
    await writeFile(absolutePath, next, "utf8");

    return {
      content: [{ type: "text", text: `Updated ${params.path}` }],
      details: {},
    };
  });
}
```

### 工具定义

```typescript
import { Type } from "typebox";
import { StringEnum } from "@earendil-works/pi-ai";
import { Text } from "@earendil-works/pi-tui";

pi.registerTool({
  name: "my_tool",
  label: "My Tool",
  description: "What this tool does (shown to LLM)",
  promptSnippet: "List or add items in the project todo list",
  promptGuidelines: [
    "Use my_tool for todo planning instead of direct file edits when the user asks for a task list."
  ],
  parameters: Type.Object({
    action: StringEnum(["list", "add"] as const),  // 为兼容 Google 请使用 StringEnum
    text: Type.Optional(Type.String()),
  }),
  prepareArguments(args) {
    if (!args || typeof args !== "object") return args;
    const input = args as { action?: string; oldAction?: string };
    if (typeof input.oldAction === "string" && input.action === undefined) {
      return { ...input, action: input.oldAction };
    }
    return args;
  },

  async execute(toolCallId, params, signal, onUpdate, ctx) {
    // 检查是否被取消
    if (signal?.aborted) {
      return { content: [{ type: "text", text: "Cancelled" }] };
    }

    // 流式报告进度
    onUpdate?.({
      content: [{ type: "text", text: "Working..." }],
      details: { progress: 50 },
    });

    // 通过 pi.exec 运行命令（从 extension 闭包捕获）
    const result = await pi.exec("some-command", [], { signal });

    // 返回结果
    return {
      content: [{ type: "text", text: "Done" }],  // 发送给 LLM
      details: { data: result },                   // 用于渲染与状态
      // 可选：当本批次中每个定稿的工具结果都返回 terminate: true 时，
      // 在该工具批次之后停止。
      terminate: true,
    };
  },

  // 可选：自定义渲染
  renderCall(args, theme, context) { ... },
  renderResult(result, options, theme, context) { ... },
});
```

**表示错误：** 要把一次工具执行标记为失败（在结果上设置 `isError: true` 并报告给 LLM），从 `execute` 中抛出错误。返回值永远不会设置错误标志，无论返回对象里包含什么属性。

**提前终止：** 从 `execute()` 返回 `terminate: true`，提示在当前工具批次之后跳过自动的后续 LLM 调用。只有当该批次中每个定稿的工具结果都是终止性的时才会生效。见 [examples/extensions/structured-output.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/structured-output.ts)，一个 agent 在最终结构化输出工具调用上结束的最小示例。

```typescript
// 正确：通过抛出异常表示错误
async execute(toolCallId, params) {
  if (!isValid(params.input)) {
    throw new Error(`Invalid input: ${params.input}`);
  }
  return { content: [{ type: "text", text: "OK" }], details: {} };
}
```

**重要：** 字符串枚举请使用 `@earendil-works/pi-ai` 的 `StringEnum`。`Type.Union`/`Type.Literal` 在 Google 的 API 上不可用。

**参数预处理：** `prepareArguments(args)` 是可选的。若定义，它在 schema 校验之前、`execute()` 之前运行。当 pi 恢复一个旧 session、其中存储的工具调用参数已不符合当前 schema 时，用它来模拟旧版可接受的输入形状。返回你希望按 `parameters` 校验的对象。保持公开 schema 严格。不要为了让旧的恢复 session 继续工作而往 `parameters` 里添加废弃的兼容字段。

例如：旧 session 中可能有一个 `edit` 工具调用带有顶层的 `oldText` 和 `newText`，而当前 schema 只接受 `edits: [{ oldText, newText }]`。

```typescript
pi.registerTool({
  name: "edit",
  label: "Edit",
  description: "Edit a single file using exact text replacement",
  parameters: Type.Object({
    path: Type.String(),
    edits: Type.Array(
      Type.Object({
        oldText: Type.String(),
        newText: Type.String(),
      }),
    ),
  }),
  prepareArguments(args) {
    if (!args || typeof args !== "object") return args;

    const input = args as {
      path?: string;
      edits?: Array<{ oldText: string; newText: string }>;
      oldText?: unknown;
      newText?: unknown;
    };

    if (typeof input.oldText !== "string" || typeof input.newText !== "string") {
      return args;
    }

    return {
      ...input,
      edits: [...(input.edits ?? []), { oldText: input.oldText, newText: input.newText }],
    };
  },
  async execute(toolCallId, params, signal, onUpdate, ctx) {
    // params 现在符合当前 schema
    return {
      content: [{ type: "text", text: `Applying ${params.edits.length} edit block(s)` }],
      details: {},
    };
  },
});
```

### 覆盖内置工具

extension 可以通过注册同名工具来覆盖内置工具（`read`、`bash`、`edit`、`write`、`grep`、`find`、`ls`）。发生覆盖时，交互模式会显示警告。

```bash
# extension 的 read 工具替换内置 read
pi -e ./tool-override.ts
```

或者，使用 `--no-builtin-tools` 在不加载任何内置工具的情况下启动，同时保留 extension 工具：
```bash
# 没有内置工具，只有 extension 工具
pi --no-builtin-tools -e ./my-extension.ts
```

完整示例见 [examples/extensions/tool-override.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/tool-override.ts)，它用日志和访问控制覆盖了 `read`。

**渲染：** 内置渲染器的继承按插槽（slot）解析。执行覆盖与渲染覆盖是相互独立的。若你的覆盖省略了 `renderCall`，则使用内置的 `renderCall`；若省略了 `renderResult`，则使用内置的 `renderResult`；两者都省略时，自动使用内置渲染器（语法高亮、diff 等）。这让你可以为了日志或访问控制而包装内置工具，而无需重新实现 UI。

**提示词元数据：** `promptSnippet` 和 `promptGuidelines` 不会从内置工具继承。若你的覆盖需要保留这些提示词指令，请在覆盖中显式定义。

**你的实现必须匹配完全相同的结果形状**，包括 `details` 的类型。UI 和 session 逻辑依赖这些形状进行渲染和状态跟踪。

内置工具实现：
- [read.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/tools/read.ts) - `ReadToolDetails`
- [bash.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/tools/bash.ts) - `BashToolDetails`
- [edit.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/tools/edit.ts)
- [write.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/tools/write.ts)
- [grep.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/tools/grep.ts) - `GrepToolDetails`
- [find.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/tools/find.ts) - `FindToolDetails`
- [ls.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/tools/ls.ts) - `LsToolDetails`

### 远程执行

内置工具支持可插拔的 operations，可以把执行委托给远程系统（SSH、容器等）：

```typescript
import { createReadTool, createBashTool, type ReadOperations } from "@earendil-works/pi-coding-agent";

// 用自定义 operations 创建工具
const remoteRead = createReadTool(cwd, {
  operations: {
    readFile: (path) => sshExec(remote, `cat ${path}`),
    access: (path) => sshExec(remote, `test -r ${path}`).then(() => {}),
  }
});

// 注册，在执行时检查标志
pi.registerTool({
  ...remoteRead,
  async execute(id, params, signal, onUpdate, _ctx) {
    const ssh = getSshConfig();
    if (ssh) {
      const tool = createReadTool(cwd, { operations: createRemoteOps(ssh) });
      return tool.execute(id, params, signal, onUpdate);
    }
    return localRead.execute(id, params, signal, onUpdate);
  },
});
```

**Operations 接口：** `ReadOperations`、`WriteOperations`、`EditOperations`、`BashOperations`、`LsOperations`、`GrepOperations`、`FindOperations`

对于 `user_bash`，extension 可以通过 `createLocalBashOperations()` 复用 pi 的本地 shell 后端，而不必重新实现本地进程启动、shell 解析和进程树终止。

bash 工具还支持一个 spawn hook，在执行前调整命令、cwd 或环境变量：

```typescript
import { createBashTool } from "@earendil-works/pi-coding-agent";

const bashTool = createBashTool(cwd, {
  spawnHook: ({ command, cwd, env }) => ({
    command: `source ~/.profile\n${command}`,
    cwd: `/mnt/sandbox${cwd}`,
    env: { ...env, CI: "1" },
  }),
});
```

带 `--ssh` 标志的完整 SSH 示例见 [examples/extensions/ssh.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/ssh.ts)。

### 输出截断

**工具必须截断自己的输出**，避免撑爆 LLM 上下文。过大的输出可能导致：
- 上下文溢出错误（prompt 过长）
- 上下文压缩失败
- 模型表现下降

内置限制是 **50KB**（约 1 万 token）和 **2000 行**，先到者为准。请使用导出的截断工具函数：

```typescript
import {
  truncateHead,      // 保留前 N 行/字节（适合文件读取、搜索结果）
  truncateTail,      // 保留后 N 行/字节（适合日志、命令输出）
  truncateLine,      // 把单行截断到 maxBytes 并加省略号
  formatSize,        // 人类可读的大小（如 "50KB"、"1.5MB"）
  DEFAULT_MAX_BYTES, // 50KB
  DEFAULT_MAX_LINES, // 2000
} from "@earendil-works/pi-coding-agent";

async execute(toolCallId, params, signal, onUpdate, ctx) {
  const output = await runCommand();

  // 应用截断
  const truncation = truncateHead(output, {
    maxLines: DEFAULT_MAX_LINES,
    maxBytes: DEFAULT_MAX_BYTES,
  });

  let result = truncation.content;

  if (truncation.truncated) {
    // 把完整输出写入临时文件
    const tempFile = writeTempFile(output);

    // 告诉 LLM 完整输出在哪里
    result += `\n\n[Output truncated: ${truncation.outputLines} of ${truncation.totalLines} lines`;
    result += ` (${formatSize(truncation.outputBytes)} of ${formatSize(truncation.totalBytes)}).`;
    result += ` Full output saved to: ${tempFile}]`;
  }

  return { content: [{ type: "text", text: result }] };
}
```

**要点：**
- 开头更重要的内容（搜索结果、文件读取）用 `truncateHead`
- 结尾更重要的内容（日志、命令输出）用 `truncateTail`
- 输出被截断时务必告知 LLM，并说明完整版本在哪里
- 在工具的 description 中写明截断限制

完整示例见 [examples/extensions/truncated-tool.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/truncated-tool.ts)，它包装了 `rg`（ripgrep）并正确处理了截断。

### 多个工具

一个 extension 可以注册多个共享状态的工具：

```typescript
export default function (pi: ExtensionAPI) {
  let connection = null;

  pi.registerTool({ name: "db_connect", ... });
  pi.registerTool({ name: "db_query", ... });
  pi.registerTool({ name: "db_close", ... });

  pi.on("session_shutdown", async () => {
    connection?.close();
  });
}
```

### 自定义渲染

工具可以提供 `renderCall` 和 `renderResult` 来自定义 TUI 显示。完整的组件 API 见 [tui.md](tui.md)，工具行的组合方式见 [tool-execution.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/modes/interactive/components/tool-execution.ts)。

默认情况下，工具输出会被包在一个处理内边距和背景的 `Box` 中。定义了的 `renderCall` 或 `renderResult` 必须返回一个 `Component`。如果某个插槽的渲染器未定义，`tool-execution.ts` 会对该插槽使用回退渲染。

当工具应自行渲染外壳而不使用默认 `Box` 时，设置 `renderShell: "self"`。这对需要完全控制边框或背景行为的工具很有用，例如工具结束后必须保持视觉稳定的大型预览。

```typescript
pi.registerTool({
  name: "my_tool",
  label: "My Tool",
  description: "Custom shell example",
  parameters: Type.Object({}),
  renderShell: "self",
  async execute() {
    return { content: [{ type: "text", text: "ok" }], details: undefined };
  },
  renderCall(args, theme, context) {
    return new Text(theme.fg("accent", "my custom shell"), 0, 0);
  },
});
```

`renderCall` 和 `renderResult` 各自收到一个 `context` 对象，包含：
- `args` - 当前工具调用参数
- `state` - `renderCall` 与 `renderResult` 之间共享的行内局部状态
- `lastComponent` - 该插槽上一次返回的组件（如有）
- `invalidate()` - 请求重新渲染此工具行
- `toolCallId`、`cwd`、`executionStarted`、`argsComplete`、`isPartial`、`expanded`、`showImages`、`isError`

跨插槽共享的状态用 `context.state`。想在多次渲染之间复用并原地修改同一个组件时，把插槽级缓存放在返回的组件实例上。

#### renderCall

渲染工具调用或标题行：

```typescript
import { Text } from "@earendil-works/pi-tui";

renderCall(args, theme, context) {
  const text = (context.lastComponent as Text | undefined) ?? new Text("", 0, 0);
  let content = theme.fg("toolTitle", theme.bold("my_tool "));
  content += theme.fg("muted", args.action);
  if (args.text) {
    content += " " + theme.fg("dim", `"${args.text}"`);
  }
  text.setText(content);
  return text;
}
```

#### renderResult

渲染工具结果或输出：

```typescript
renderResult(result, { expanded, isPartial }, theme, context) {
  if (isPartial) {
    return new Text(theme.fg("warning", "Processing..."), 0, 0);
  }

  if (result.details?.error) {
    return new Text(theme.fg("error", `Error: ${result.details.error}`), 0, 0);
  }

  let text = theme.fg("success", "✓ Done");
  if (expanded && result.details?.items) {
    for (const item of result.details.items) {
      text += "\n  " + theme.fg("dim", item);
    }
  }
  return new Text(text, 0, 0);
}
```

如果某个插槽有意不显示内容，返回一个空的 `Component`，例如空的 `Container`。

#### 快捷键提示

使用 `keyHint()` 显示尊重当前按键绑定配置的快捷键提示：

```typescript
import { keyHint } from "@earendil-works/pi-coding-agent";

renderResult(result, { expanded }, theme, context) {
  let text = theme.fg("success", "✓ Done");
  if (!expanded) {
    text += ` (${keyHint("app.tools.expand", "to expand")})`;
  }
  return new Text(text, 0, 0);
}
```

可用函数：
- `keyHint(keybinding, description)` - 格式化一个已配置的按键绑定 id，如 `"app.tools.expand"` 或 `"tui.select.confirm"`
- `keyText(keybinding)` - 返回某个按键绑定 id 当前配置的按键文本
- `rawKeyHint(key, description)` - 格式化一个原始按键字符串

使用带命名空间的按键绑定 id：
- coding-agent 的 id 使用 `app.*` 命名空间，例如 `app.tools.expand`、`app.editor.external`、`app.session.rename`
- 共享的 TUI id 使用 `tui.*` 命名空间，例如 `tui.select.confirm`、`tui.select.cancel`、`tui.input.tab`

按键绑定 id 与默认值的完整列表见 [keybindings.md](keybindings.md)。`keybindings.json` 使用同样的带命名空间的 id。

自定义编辑器和 `ctx.ui.custom()` 组件会以注入参数的形式收到 `keybindings: KeybindingsManager`。它们应直接使用这个注入的管理器，而不是调用 `getKeybindings()` 或 `setKeybindings()`。

#### 最佳实践

- 使用内边距为 `(0, 0)` 的 `Text`。默认 Box 会处理内边距。
- 多行内容用 `\n`。
- 处理 `isPartial` 以支持流式进度。
- 支持 `expanded`，按需展示细节。
- 保持默认视图紧凑。
- 在 `renderResult` 中读取 `context.args`，而不是把 args 复制进 `context.state`。
- `context.state` 只用于必须在 call 和 result 两个插槽之间共享的数据。
- 当同一个组件实例可以原地更新时，复用 `context.lastComponent`。
- 只有当默认的盒式外壳碍事时才使用 `renderShell: "self"`。在自渲染外壳模式下，工具要自己负责边框、内边距和背景。

#### 回退

如果某个插槽的渲染器未定义或抛出异常：
- `renderCall`：显示工具名
- `renderResult`：显示 `content` 中的原始文本

### 动态工具加载

extension 可以注册许多工具，但初始只激活一小部分。之后某个工具可以在执行期间通过 `pi.setActiveTools()` 添加更多工具。Pi 会检测纯增量的变更，把新增可用的工具名记录到那个工具结果上，并在下一次模型请求之前应用更新后的活动集合。

这对所有模型都有效。原生支持延迟加载的模型会保留稳定的提示词前缀，并在工具结果的位置加载新定义。其他模型使用下文描述的回退方案。

生命周期如下：

1. 用 `pi.registerTool()` 注册每一个工具，使其出现在 `pi.getAllTools()` 中。
2. 保持加载器工具（如 `search_tools`）处于活动状态，可搜索的工具保持非活动。
3. 在加载器执行期间，调用 `pi.setActiveTools([...currentTools, ...matchingTools])`。变更必须是增量的：不要在同一次调用中移除当前活动的工具。
4. Pi 把新增的工具记录在加载器的工具结果上。
5. 在下一次模型响应之前，Pi 在支持的情况下用原生延迟加载暴露新增的定义，否则用普通的活动工具列表。

你不需要返回 provider 特定的工具引用，也不需要把加载器标记为特殊的搜索工具。活动工具的变更本身就是信号。传给 `pi.setActiveTools()` 的名称必须已经注册；未知名称会被忽略。

#### 支持原生延迟加载的模型

- **Anthropic**
  - **模型：** Sonnet、Opus，以及 4.5 或更新版本的 Fable（不含 Haiku）
  - **原生表示：** 延迟的定义使用 `defer_loading`；加载点使用 `tool_reference` 内容。
- **OpenAI**
  - **模型：** `gpt-5.4` 及更新系列
  - **原生表示：** Pi 在加载点添加已完成的客户端 `tool_search_call` 和 `tool_search_output` 项。

对于经过验证的自定义模型或代理，可以通过 `compat.supportsToolReferences: true`（`anthropic-messages`）或 `compat.supportsToolSearch: true`（`openai-responses` 和 `openai-codex-responses`）启用原生处理。除非端点和模型确实接受对应的原生协议，否则不要启用。

#### 回退行为

对于所有其他模型和 provider，动态激活仍然有效：Pi 在下一次请求中正常发送完整的当前活动工具列表。模型可以调用新激活的工具，但添加它们的定义可能使 provider 缓存的提示词前缀失效。

当活动集合不是纯增量时（例如用一组工具替换另一组），Pi 也使用这种安全回退。因此移除工具是可行的，只是不走延迟加载。

为获得最佳缓存行为，让加载器工具在整个 session 中保持活动，并且只添加工具而不是替换活动集合。还要注意：激活带有 `promptSnippet` 或 `promptGuidelines` 的工具会重建系统提示词；即使 provider 支持延迟 schema，这个系统提示词变更也可能使前缀失效。惰性加载的工具通常应只依赖其工具 `description`，省略仅在活动时生效的提示词元数据。

#### 搜索工具示例

下面的 extension 注册了两个可搜索的工具，把它们从初始活动集合中移除，只保留 `search_tools` 作为它们的加载器。示例使用简单的关键词匹配，但搜索实现也可以用 BM25、向量嵌入、远程目录或项目专属的路由。

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const SEARCHABLE_TOOL_NAMES = new Set(["lookup_weather", "search_issues"]);

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "lookup_weather",
    label: "Lookup Weather",
    description: "Look up the current weather for a city",
    parameters: Type.Object({ city: Type.String() }),
    async execute(_toolCallId, params) {
      return {
        content: [{ type: "text", text: `Weather for ${params.city}: sunny` }],
        details: {},
      };
    },
  });

  pi.registerTool({
    name: "search_issues",
    label: "Search Issues",
    description: "Search project issues by keyword",
    parameters: Type.Object({ query: Type.String() }),
    async execute(_toolCallId, params) {
      return {
        content: [{ type: "text", text: `No open issues matching ${params.query}` }],
        details: {},
      };
    },
  });

  pi.registerTool({
    name: "search_tools",
    label: "Search Tools",
    description: "Search for and enable tools relevant to a task",
    promptSnippet: "Search for additional tools when the active tools cannot perform the task",
    promptGuidelines: [
      "Use search_tools when a task requires a capability that is not currently available.",
    ],
    parameters: Type.Object({
      query: Type.String({ description: "Capability or task to search for" }),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 10 })),
    }),
    async execute(_toolCallId, params) {
      const terms = params.query.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
      const matches = pi.getAllTools()
        .filter((tool) => SEARCHABLE_TOOL_NAMES.has(tool.name))
        .map((tool) => ({
          tool,
          score: terms.reduce(
            (score, term) =>
              score + (`${tool.name} ${tool.description}`.toLowerCase().includes(term) ? 1 : 0),
            0,
          ),
        }))
        .filter((match) => match.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, params.limit ?? 3)
        .map((match) => match.tool.name);

      if (matches.length === 0) {
        return {
          content: [{ type: "text", text: `No tools found for: ${params.query}` }],
          details: { matches: [] },
        };
      }

      const active = pi.getActiveTools();
      const added = matches.filter((name) => !active.includes(name));
      pi.setActiveTools([...new Set([...active, ...added])]);

      return {
        content: [{
          type: "text",
          text: added.length > 0
            ? `Loaded tools: ${added.join(", ")}`
            : `Matching tools already active: ${matches.join(", ")}`,
        }],
        details: { matches, added },
      };
    },
  });

  pi.on("session_start", () => {
    // 让可搜索工具保持注册但初始不激活。保留内置工具
    // 和其他 extension 拥有的工具，并让加载器自身保持活动。
    const initialTools = pi.getActiveTools().filter(
      (name) => !SEARCHABLE_TOOL_NAMES.has(name),
    );
    pi.setActiveTools([...new Set([...initialTools, "search_tools"])]);
  });
}
```

当 `search_tools` 添加了一个匹配项时，模型会在紧随其后的请求中收到该定义。在原生支持的模型上，该定义锚定在搜索结果之后，不改变初始的工具 schema 前缀；在其他模型上，它出现在同一后续请求的普通工具列表中。

## 自定义 UI

extension 可以通过 `ctx.ui` 方法与用户交互，并自定义消息/工具的渲染方式。

**自定义组件见 [tui.md](tui.md)**，其中有可直接复制的模式：
- 选择对话框（SelectList）
- 可取消的异步操作（BorderedLoader）
- 设置开关（SettingsList）
- 状态指示（setStatus）
- 流式期间的工作消息、可见性与指示器（`setWorkingMessage`、`setWorkingVisible`、`setWorkingIndicator`）
- 编辑器上方/下方的小部件（setWidget）
- 叠加在内置斜杠/路径补全之上的自动补全 provider（addAutocompleteProvider）
- 自定义底栏（setFooter）

### 对话框

```typescript
// 从选项中选择
const choice = await ctx.ui.select("Pick one:", ["A", "B", "C"]);

// 确认对话框
const ok = await ctx.ui.confirm("Delete?", "This cannot be undone");

// 文本输入
const name = await ctx.ui.input("Name:", "placeholder");

// 多行编辑器
const text = await ctx.ui.editor("Edit:", "prefilled text");

// 通知（非阻塞）
ctx.ui.notify("Done!", "info");  // "info" | "warning" | "error"
```

#### 带倒计时的定时对话框

对话框支持 `timeout` 选项，会带着实时倒计时显示自动关闭：

```typescript
// 对话框显示 "Title (5s)" → "Title (4s)" → ... → 到 0 时自动关闭
const confirmed = await ctx.ui.confirm(
  "Timed Confirmation",
  "This dialog will auto-cancel in 5 seconds. Confirm?",
  { timeout: 5000 }
);

if (confirmed) {
  // 用户确认了
} else {
  // 用户取消或超时
}
```

**超时时的返回值：**
- `select()` 返回 `undefined`
- `confirm()` 返回 `false`
- `input()` 返回 `undefined`

#### 用 AbortSignal 手动关闭

需要更精细的控制时（例如区分超时和用户取消），使用 `AbortSignal`：

```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 5000);

const confirmed = await ctx.ui.confirm(
  "Timed Confirmation",
  "This dialog will auto-cancel in 5 seconds. Confirm?",
  { signal: controller.signal }
);

clearTimeout(timeoutId);

if (confirmed) {
  // 用户确认了
} else if (controller.signal.aborted) {
  // 对话框超时
} else {
  // 用户取消（按了 Escape 或选择了 "No"）
}
```

完整示例见 [examples/extensions/timed-confirm.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/timed-confirm.ts)。

### 小部件、状态与底栏

```typescript
// 底栏状态（持续显示直到清除）
ctx.ui.setStatus("my-ext", "Processing...");
ctx.ui.setStatus("my-ext", undefined);  // 清除

// 工作加载指示（流式期间显示）
ctx.ui.setWorkingMessage("Thinking deeply...");
ctx.ui.setWorkingMessage();  // 恢复默认
ctx.ui.setWorkingVisible(false);  // 完全隐藏内置工作加载行
ctx.ui.setWorkingVisible(true);   // 显示内置工作加载行

// 工作指示器（流式期间显示）
ctx.ui.setWorkingIndicator({ frames: [ctx.ui.theme.fg("accent", "●")] });  // 静态圆点
ctx.ui.setWorkingIndicator({
  frames: [
    ctx.ui.theme.fg("dim", "·"),
    ctx.ui.theme.fg("muted", "•"),
    ctx.ui.theme.fg("accent", "●"),
    ctx.ui.theme.fg("muted", "•"),
  ],
  intervalMs: 120,
});
ctx.ui.setWorkingIndicator({ frames: [] });  // 隐藏指示器
ctx.ui.setWorkingIndicator();  // 恢复默认加载动画

// 编辑器上方的小部件（默认位置）
ctx.ui.setWidget("my-widget", ["Line 1", "Line 2"]);
// 编辑器下方的小部件
ctx.ui.setWidget("my-widget", ["Line 1", "Line 2"], { placement: "belowEditor" });
ctx.ui.setWidget("my-widget", (tui, theme) => new Text(theme.fg("accent", "Custom"), 0, 0));
ctx.ui.setWidget("my-widget", undefined);  // 清除

// 自定义底栏（完全替换内置底栏）
ctx.ui.setFooter((tui, theme) => ({
  render(width) { return [theme.fg("dim", "Custom footer")]; },
  invalidate() {},
}));
ctx.ui.setFooter(undefined);  // 恢复内置底栏

// 终端标题
ctx.ui.setTitle("pi - my-project");

// 编辑器文本
ctx.ui.setEditorText("Prefill text");
const current = ctx.ui.getEditorText();

// 粘贴到编辑器（触发粘贴处理，包括大内容折叠）
ctx.ui.pasteToEditor("pasted content");

// 在内置 provider 之上叠加自定义自动补全行为
ctx.ui.addAutocompleteProvider((current) => ({
  triggerCharacters: ["#"],
  async getSuggestions(lines, line, col, options) {
    const beforeCursor = (lines[line] ?? "").slice(0, col);
    const match = beforeCursor.match(/(?:^|[ \t])#([^\s#]*)$/);
    if (!match) {
      return current.getSuggestions(lines, line, col, options);
    }

    return {
      prefix: `#${match[1] ?? ""}`,
      items: [{ value: "#2983", label: "#2983", description: "Extension API for autocomplete" }],
    };
  },
  applyCompletion(lines, line, col, item, prefix) {
    return current.applyCompletion(lines, line, col, item, prefix);
  },
  shouldTriggerFileCompletion(lines, line, col) {
    return current.shouldTriggerFileCompletion?.(lines, line, col) ?? true;
  },
}));

// 工具输出展开
const wasExpanded = ctx.ui.getToolsExpanded();
ctx.ui.setToolsExpanded(true);
ctx.ui.setToolsExpanded(wasExpanded);

// 自定义编辑器（vim 模式、emacs 模式等）
ctx.ui.setEditorComponent((tui, theme, keybindings) => new VimEditor(tui, theme, keybindings));
const currentEditor = ctx.ui.getEditorComponent();
ctx.ui.setEditorComponent((tui, theme, keybindings) =>
  new WrappedEditor(tui, theme, keybindings, currentEditor?.(tui, theme, keybindings))
);
ctx.ui.setEditorComponent(undefined);  // 恢复默认编辑器

// 主题管理（创建主题见 themes.md）
const themes = ctx.ui.getAllThemes();  // [{ name: "dark", path: "/..." | undefined }, ...]
const lightTheme = ctx.ui.getTheme("light");  // 加载但不切换
const result = ctx.ui.setTheme("light");  // 按名称切换
if (!result.success) {
  ctx.ui.notify(`Failed: ${result.error}`, "error");
}
ctx.ui.setTheme(lightTheme!);  // 或按 Theme 对象切换
ctx.ui.theme.fg("accent", "styled text");  // 访问当前主题
```

自定义工作指示器的帧会原样渲染。想要颜色的话，自己把颜色加到帧字符串里，例如用 `ctx.ui.theme.fg(...)`。

### 自动补全 provider

使用 `ctx.ui.addAutocompleteProvider()` 把自定义自动补全逻辑叠加在内置的斜杠命令与路径 provider 之上。设置 `triggerCharacters` 可以添加 `$` 之类的自定义自然触发字符。

典型模式：

- 检查光标前的文本
- 当匹配你 extension 专属的语法时返回你自己的建议
- 否则委托给 `current.getSuggestions(...)`
- 除非需要自定义插入行为，否则委托 `applyCompletion(...)`

```typescript
pi.on("session_start", (_event, ctx) => {
  ctx.ui.addAutocompleteProvider((current) => ({
    triggerCharacters: ["#"],
    async getSuggestions(lines, cursorLine, cursorCol, options) {
      const line = lines[cursorLine] ?? "";
      const beforeCursor = line.slice(0, cursorCol);
      const match = beforeCursor.match(/(?:^|[ \t])#([^\s#]*)$/);
      if (!match) {
        return current.getSuggestions(lines, cursorLine, cursorCol, options);
      }

      return {
        prefix: `#${match[1] ?? ""}`,
        items: [
          { value: "#2983", label: "#2983", description: "Extension API for registering custom @ autocomplete providers" },
          { value: "#2753", label: "#2753", description: "Reload stale resource settings" },
        ],
      };
    },

    applyCompletion(lines, cursorLine, cursorCol, item, prefix) {
      return current.applyCompletion(lines, cursorLine, cursorCol, item, prefix);
    },

    shouldTriggerFileCompletion(lines, cursorLine, cursorCol) {
      return current.shouldTriggerFileCompletion?.(lines, cursorLine, cursorCol) ?? true;
    },
  }));
});
```

完整示例见 [github-issue-autocomplete.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/github-issue-autocomplete.ts)，它用 `gh issue list` 预加载最新的开放 GitHub issue，并在本地过滤实现快速的 `#...` 补全。它需要 GitHub CLI（`gh`）和一个 GitHub 仓库检出。

### 自定义组件

复杂 UI 使用 `ctx.ui.custom()`。它会用你的组件临时替换编辑器，直到 `done()` 被调用：

```typescript
import { Text, Component } from "@earendil-works/pi-tui";

const result = await ctx.ui.custom<boolean>((tui, theme, keybindings, done) => {
  const text = new Text("Press Enter to confirm, Escape to cancel", 1, 1);

  text.onKey = (key) => {
    if (key === "return") done(true);
    if (key === "escape") done(false);
    return true;
  };

  return text;
});

if (result) {
  // 用户按了 Enter
}
```

回调收到：
- `tui` - TUI 实例（用于屏幕尺寸、焦点管理）
- `theme` - 当前主题，用于样式
- `keybindings` - 应用按键绑定管理器（用于检查快捷键）
- `done(value)` - 调用后关闭组件并返回值

完整的组件 API 见 [tui.md](tui.md)。

#### 覆盖层模式（实验性）

传入 `{ overlay: true }` 可以把组件渲染为浮在现有内容之上的模态框，而不清屏：

```typescript
const result = await ctx.ui.custom<string | null>(
  (tui, theme, keybindings, done) => new MyOverlayComponent({ onClose: done }),
  { overlay: true }
);
```

需要高级定位（锚点、边距、百分比、响应式可见性）时，传入 `overlayOptions`。用 `onHandle` 以编程方式控制焦点或可见性：

```typescript
const result = await ctx.ui.custom<string | null>(
  (tui, theme, keybindings, done) => new MyOverlayComponent({ onClose: done }),
  {
    overlay: true,
    overlayOptions: { anchor: "top-right", width: "50%", margin: 2 },
    onHandle: (handle) => {
      handle.focus(); // 聚焦此覆盖层并将其带到视觉最前
      // handle.unfocus({ target: editorComponent }); // 把输入让给某个特定组件
      // handle.setHidden(true/false); // 切换可见性
      // handle.hide(); // 永久移除
    }
  }
);
```

处于焦点的可见覆盖层可以在临时的非覆盖层自定义 UI 关闭后重新拿回输入。如果你有意让另一个组件在覆盖层保持可见的同时持有输入，调用 `handle.unfocus({ target })`。传 `{ target: null }` 释放覆盖层且不聚焦其他组件。

完整的 `OverlayOptions` 与 `OverlayHandle` API 见 [tui.md](tui.md)，示例见 [overlay-qa-tests.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/overlay-qa-tests.ts)。

### 自定义编辑器

用自定义实现替换主输入编辑器（vim 模式、emacs 模式等）：

```typescript
import { CustomEditor, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { matchesKey } from "@earendil-works/pi-tui";

class VimEditor extends CustomEditor {
  private mode: "normal" | "insert" = "insert";

  handleInput(data: string): void {
    if (matchesKey(data, "escape") && this.mode === "insert") {
      this.mode = "normal";
      return;
    }
    if (this.mode === "normal" && data === "i") {
      this.mode = "insert";
      return;
    }
    super.handleInput(data);  // 应用按键绑定 + 文本编辑
  }
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", (_event, ctx) => {
    ctx.ui.setEditorComponent((tui, theme, keybindings) =>
      new VimEditor(tui, theme, keybindings)
    );
  });
}
```

**要点：**
- 继承 `CustomEditor`（而不是基类 `Editor`），以获得应用按键绑定（escape 中止、ctrl+d、模型切换）
- 对你不处理的按键调用 `super.handleInput(data)`
- 工厂函数从应用收到 `tui`、`theme` 和 `keybindings`
- 在 `setEditorComponent()` 之前用 `ctx.ui.getEditorComponent()` 包装先前配置的自定义编辑器
- 传 `undefined` 恢复默认：`ctx.ui.setEditorComponent(undefined)`

要与另一个已经替换过编辑器的 extension 组合，在设置你的编辑器之前先捕获之前的工厂函数：

```typescript
const previous = ctx.ui.getEditorComponent();
ctx.ui.setEditorComponent((tui, theme, keybindings) =>
  new MyEditor(tui, theme, keybindings, { base: previous?.(tui, theme, keybindings) })
);
```

带模式指示器的完整示例见 [tui.md](tui.md) 的 Pattern 7。

### 消息与条目渲染

为带有你的 `customType` 的消息注册自定义渲染器。消息渲染器用于应参与 LLM 上下文的内容：

```typescript
import { Text } from "@earendil-works/pi-tui";

pi.registerMessageRenderer("my-extension", (message, options, theme) => {
  const { expanded } = options;
  let text = theme.fg("accent", `[${message.customType}] `);
  text += message.content;

  if (expanded && message.details) {
    text += "\n" + theme.fg("dim", JSON.stringify(message.details, null, 2));
  }

  return new Text(text, 0, 0);
});
```

消息通过 `pi.sendMessage()` 发送：

```typescript
pi.sendMessage({
  customType: "my-extension",  // 与 registerMessageRenderer 匹配
  content: "Status update",
  display: true,               // 在 TUI 中显示
  details: { ... },            // 渲染器中可用
});
```

对于不应发送给 LLM 的 TUI 专用内容，改用自定义条目渲染：

```typescript
pi.registerEntryRenderer("my-card", (entry, options, theme) => {
  return new Text(theme.fg("accent", JSON.stringify(entry.data)));
});

pi.appendEntry("my-card", { status: "done" });
```

### 主题颜色

所有渲染函数都会收到一个 `theme` 对象。创建自定义主题与完整调色板见 [themes.md](themes.md)。

```typescript
// 前景色
theme.fg("toolTitle", text)   // 工具名
theme.fg("accent", text)      // 高亮
theme.fg("success", text)     // 成功（绿色）
theme.fg("error", text)       // 错误（红色）
theme.fg("warning", text)     // 警告（黄色）
theme.fg("muted", text)       // 次要文本
theme.fg("dim", text)         // 三级文本

// 文本样式
theme.bold(text)
theme.italic(text)
theme.strikethrough(text)
```

在自定义工具渲染器中做语法高亮：

```typescript
import { highlightCode, getLanguageFromPath } from "@earendil-works/pi-coding-agent";

// 用显式语言高亮代码
const highlighted = highlightCode("const x = 1;", "typescript", theme);

// 从文件路径自动检测语言
const lang = getLanguageFromPath("/path/to/file.rs");  // "rust"
const highlighted = highlightCode(code, lang, theme);
```

## 错误处理

- extension 错误会被记录日志，agent 继续运行
- `tool_call` 中的错误会阻止该工具（故障安全）
- 工具 `execute` 中的错误必须通过抛出异常表示；抛出的错误会被捕获，以 `isError: true` 报告给 LLM，执行继续

## 各模式下的行为

| 模式 | `ctx.mode` | `ctx.hasUI` | 说明 |
|------|------------|-------------|-------|
| 交互模式 | `"tui"` | `true` | 完整 TUI，终端渲染 |
| RPC（`--mode rpc`） | `"rpc"` | `true` | 对话框和通知走 JSON 协议；`custom()` 返回 `undefined`。见 [rpc.md](rpc.md) |
| JSON（`--mode json`） | `"json"` | `false` | 事件流输出到 stdout；UI 方法是空操作 |
| print 模式（`-p`） | `"print"` | `false` | extension 会运行，但不能弹出提示 |

在 TUI 专用功能（`custom()`、组件工厂、终端输入）之前用 `ctx.mode === "tui"` 判断。在 TUI 和 RPC 两种模式下都可用的对话框和通知方法之前用 `ctx.hasUI` 判断。

## 示例索引

所有示例都在 [examples/extensions/](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/) 中。

| 示例 | 描述 | 关键 API |
|---------|-------------|----------|
| **工具** |||
| `hello.ts` | 最小化的工具注册 | `registerTool` |
| `question.ts` | 带用户交互的工具 | `registerTool`、`ui.select` |
| `questionnaire.ts` | 多步向导工具 | `registerTool`、`ui.custom` |
| `todo.ts` | 带持久化的有状态工具 | `registerTool`、`appendEntry`、`renderResult`、session 事件 |
| `dynamic-tools.ts` | 启动后及命令中注册工具 | `registerTool`、`session_start`、`registerCommand` |
| `structured-output.ts` | 带 `terminate: true` 的最终结构化输出工具 | `registerTool`、终止性工具结果 |
| `truncated-tool.ts` | 输出截断示例 | `registerTool`、`truncateHead` |
| `tool-override.ts` | 覆盖内置 read 工具 | `registerTool`（与内置同名） |
| **命令** |||
| `pirate.ts` | 按 turn 修改系统提示词 | `registerCommand`、`before_agent_start` |
| `summarize.ts` | 对话摘要命令 | `registerCommand`、`ui.custom` |
| `handoff.ts` | 跨 provider 模型交接 | `registerCommand`、`ui.editor`、`ui.custom` |
| `qna.ts` | 带自定义 UI 的问答 | `registerCommand`、`ui.custom`、`setEditorText` |
| `send-user-message.ts` | 注入用户消息 | `registerCommand`、`sendUserMessage` |
| `reload-runtime.ts` | reload 命令与 LLM 工具交接 | `registerCommand`、`ctx.reload()`、`sendUserMessage` |
| `shutdown-command.ts` | 优雅关停命令 | `registerCommand`、`shutdown()` |
| **事件与门禁** |||
| `permission-gate.ts` | 阻止危险命令 | `on("tool_call")`、`ui.confirm` |
| `project-trust.ts` | 从用户/全局或 CLI extension 决定或推迟项目信任 | `on("project_trust")`、信任 UI、必需的信任结果 |
| `protected-paths.ts` | 阻止写入特定路径 | `on("tool_call")` |
| `confirm-destructive.ts` | 确认 session 变更 | `on("session_before_switch")`、`on("session_before_fork")` |
| `dirty-repo-guard.ts` | 对脏 git 仓库告警 | `on("session_before_*")`、`exec` |
| `input-transform.ts` | 变换用户输入 | `on("input")` |
| `input-transform-streaming.ts` | 感知流式状态的输入变换 | `on("input")`、`streamingBehavior` |
| `model-status.ts` | 响应模型变化 | `on("model_select")`、`setStatus` |
| `provider-payload.ts` | 检查 payload 和 provider 响应头 | `on("before_provider_request")`、`on("after_provider_response")` |
| `system-prompt-header.ts` | 显示系统提示词信息 | `on("agent_start")`、`getSystemPrompt` |
| `claude-rules.ts` | 从文件加载规则 | `on("session_start")`、`on("before_agent_start")` |
| `prompt-customizer.ts` | 用 `systemPromptOptions` 添加上下文感知的工具指导 | `on("before_agent_start")`、`BuildSystemPromptOptions` |
| `file-trigger.ts` | 文件监听触发消息 | `sendMessage` |
| **上下文压缩与 session** |||
| `custom-compaction.ts` | 自定义压缩摘要 | `on("session_before_compact")` |
| `trigger-compact.ts` | 手动触发上下文压缩 | `compact()` |
| `git-checkpoint.ts` | 按 turn 做 git stash | `on("turn_start")`、`on("session_before_fork")`、`exec` |
| `git-merge-and-resolve.ts` | 拉取、合并并解决冲突 | `on("agent_end")`、`exec`、`sendUserMessage` |
| `auto-commit-on-exit.ts` | 关停时提交 | `on("session_shutdown")`、`exec` |
| **UI 组件** |||
| `status-line.ts` | 底栏状态指示 | `setStatus`、session 事件 |
| `working-indicator.ts` | 自定义流式期间的工作指示器 | `setWorkingIndicator`、`registerCommand` |
| `github-issue-autocomplete.ts` | 通过用 `gh issue list` 预加载最近的开放 issue，在内置自动补全之上添加 `#1234` 补全 | `addAutocompleteProvider`、`on("session_start")`、`exec` |
| `custom-footer.ts` | 完全替换底栏 | `registerCommand`、`setFooter` |
| `custom-header.ts` | 替换启动头部 | `on("session_start")`、`setHeader` |
| `modal-editor.ts` | Vim 风格模态编辑器 | `setEditorComponent`、`CustomEditor` |
| `rainbow-editor.ts` | 自定义编辑器样式 | `setEditorComponent` |
| `widget-placement.ts` | 编辑器上方/下方的小部件 | `setWidget` |
| `overlay-test.ts` | 覆盖层组件 | `ui.custom` 与覆盖层选项 |
| `overlay-qa-tests.ts` | 全面的覆盖层测试 | `ui.custom`、所有覆盖层选项 |
| `notify.ts` | 简单通知 | `ui.notify` |
| `timed-confirm.ts` | 带超时的对话框 | 带 timeout/signal 的 `ui.confirm` |
| `mac-system-theme.ts` | 自动切换主题 | `setTheme`、`exec` |
| **复杂 extension** |||
| `plan-mode/` | 完整的 plan 模式实现 | 所有事件类型、`registerCommand`、`registerShortcut`、`registerFlag`、`setStatus`、`setWidget`、`sendMessage`、`setActiveTools` |
| `preset.ts` | 可保存的预设（模型、工具、思考级别） | `registerCommand`、`registerShortcut`、`registerFlag`、`setModel`、`setActiveTools`、`setThinkingLevel`、`appendEntry` |
| `tools.ts` | 工具开关 UI | `registerCommand`、`setActiveTools`、`SettingsList`、session 事件 |
| **远程与沙箱** |||
| `ssh.ts` | SSH 远程执行 | `registerFlag`、`on("user_bash")`、`on("before_agent_start")`、工具 operations |
| `interactive-shell.ts` | 持久 shell 会话 | `on("user_bash")` |
| `sandbox/` | 沙箱化的工具执行 | 工具 operations |
| `gondolin/` | 把内置工具和 `!` 命令路由进 Gondolin 微虚拟机 | 工具 operations、内置工具覆盖、`on("user_bash")` |
| `subagent/` | 派生子 agent | `registerTool`、`exec` |
| **游戏** |||
| `snake.ts` | 贪吃蛇 | `registerCommand`、`ui.custom`、键盘处理 |
| `space-invaders.ts` | 太空侵略者 | `registerCommand`、`ui.custom` |
| `doom-overlay/` | 覆盖层里的 Doom | 带覆盖层的 `ui.custom` |
| **Provider** |||
| `custom-provider-anthropic/` | 自定义 Anthropic 代理 | `registerProvider` |
| `custom-provider-gitlab-duo/` | GitLab Duo 集成 | 带 OAuth 的 `registerProvider` |
| **消息与通信** |||
| `message-renderer.ts` | 自定义消息渲染 | `registerMessageRenderer`、`sendMessage` |
| `entry-renderer.ts` | TUI 专用的自定义条目渲染 | `registerEntryRenderer`、`appendEntry` |
| `event-bus.ts` | extension 间事件 | `pi.events` |
| **Session 元数据** |||
| `session-name.ts` | 为选择器命名 session | `setSessionName`、`getSessionName` |
| `bookmark.ts` | 为 /tree 添加条目书签 | `setLabel` |
| **杂项** |||
| `inline-bash.ts` | 工具调用中的内联 bash | `on("tool_call")` |
| `bash-spawn-hook.ts` | 执行前调整 bash 命令、cwd 和环境变量 | `createBashTool`、`spawnHook` |
| `with-deps/` | 带 npm 依赖的 extension | 含 `package.json` 的包结构 |
