> **译文** | 原文：[`packages/coding-agent/docs/sdk.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sdk.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

> pi 可以帮助你使用 SDK。让它为你的使用场景构建一个集成即可。

# SDK

SDK 提供对 pi agent 能力的编程式访问。可以用它把 pi 嵌入其它应用、构建自定义界面，或与自动化工作流集成。

**示例使用场景：**
- 构建自定义 UI（Web、桌面、移动端）
- 将 agent 能力集成到现有应用中
- 创建带 agent 推理的自动化流水线
- 构建可派生子 agent 的自定义工具
- 以编程方式测试 agent 行为

从最小示例到完全控制的可运行示例见 [examples/sdk/](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/)。

## 快速上手

```typescript
import { createAgentSession, ModelRuntime, SessionManager } from "@earendil-works/pi-coding-agent";

const modelRuntime = await ModelRuntime.create();
const { session } = await createAgentSession({
  sessionManager: SessionManager.inMemory(),
  modelRuntime,
});

session.subscribe((event) => {
  if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
    process.stdout.write(event.assistantMessageEvent.delta);
  }
});

await session.prompt("What files are in the current directory?");
```

## 安装

```bash
npm install @earendil-works/pi-coding-agent
```

SDK 包含在主包中，无需单独安装。

## 核心概念

### createAgentSession()

创建单个 `AgentSession` 的主工厂函数。

`createAgentSession()` 使用一个 `ResourceLoader` 来提供 extension、skill、提示词模板、主题和上下文文件。如果你不提供，它会使用带标准发现逻辑的 `DefaultResourceLoader`。

```typescript
import { createAgentSession, SessionManager } from "@earendil-works/pi-coding-agent";

// 最小用法：使用 DefaultResourceLoader 的默认配置
const { session } = await createAgentSession();

// 自定义：覆盖特定选项
const { session } = await createAgentSession({
  model: myModel,
  tools: ["read", "bash"],
  sessionManager: SessionManager.inMemory(),
});
```

### AgentSession

session 管理 agent 生命周期、消息历史、模型状态、上下文压缩和事件流。

```typescript
interface AgentSession {
  // 发送 prompt 并等待完成
  prompt(text: string, options?: PromptOptions): Promise<void>;

  // 在 streaming 期间排队消息
  steer(text: string): Promise<void>;
  followUp(text: string): Promise<void>;

  // 订阅事件（返回取消订阅函数）
  subscribe(listener: (event: AgentSessionEvent) => void): () => void;

  // session 信息
  sessionFile: string | undefined;
  sessionId: string;

  // 模型控制
  setModel(model: Model): Promise<void>;
  setThinkingLevel(level: ThinkingLevel): void;
  cycleModel(): Promise<ModelCycleResult | undefined>;
  cycleThinkingLevel(): ThinkingLevel | undefined;

  // 状态访问
  agent: Agent;
  model: Model | undefined;
  thinkingLevel: ThinkingLevel;
  messages: AgentMessage[];
  isStreaming: boolean;

  // 在当前 session 文件内进行原地树导航
  navigateTree(targetId: string, options?: { summarize?: boolean; customInstructions?: string; replaceInstructions?: boolean; label?: string }): Promise<{ editorText?: string; cancelled: boolean }>;

  // 上下文压缩
  compact(customInstructions?: string): Promise<CompactionResult>;
  abortCompaction(): void;

  // 中止当前操作
  abort(): Promise<void>;

  // 清理
  dispose(): void;
}
```

新建会话、恢复、fork、导入等 session 替换 API 位于 `AgentSessionRuntime` 上，而不是 `AgentSession` 上。

### createAgentSessionRuntime() 与 AgentSessionRuntime

当你需要替换当前活动 session 并重建与 cwd 绑定的运行时状态时，使用 runtime API。
这与内置的交互模式、print 模式和 RPC 模式使用的是同一层。

`createAgentSessionRuntime()` 接收一个运行时工厂，加上初始的 cwd/session 目标。工厂闭包持有进程级的固定输入，为生效的 cwd 重建与 cwd 绑定的服务，基于这些服务解析 session 选项，并返回完整的运行时结果。

```typescript
import {
  type CreateAgentSessionRuntimeFactory,
  createAgentSessionFromServices,
  createAgentSessionRuntime,
  createAgentSessionServices,
  getAgentDir,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

const createRuntime: CreateAgentSessionRuntimeFactory = async ({ cwd, sessionManager, sessionStartEvent }) => {
  const services = await createAgentSessionServices({ cwd });
  return {
    ...(await createAgentSessionFromServices({
      services,
      sessionManager,
      sessionStartEvent,
    })),
    services,
    diagnostics: services.diagnostics,
  };
};

const runtime = await createAgentSessionRuntime(createRuntime, {
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  sessionManager: SessionManager.create(process.cwd()),
});
```

`AgentSessionRuntime` 负责在以下操作中替换活动运行时：

- `newSession()`
- `switchSession()`
- `fork()`
- 通过 `fork(entryId, { position: "at" })` 实现的克隆流程
- `importFromJsonl()`

重要行为：

- 上述操作之后 `runtime.session` 会发生变化
- 事件订阅绑定在特定的 `AgentSession` 上，因此替换后需要重新订阅
- 如果使用了 extension，需要对新 session 再次调用 `runtime.session.bindExtensions(...)`
- 创建过程会在 `runtime.diagnostics` 上返回诊断信息
- 如果运行时创建或替换失败，该方法会抛出异常，由调用方决定如何处理

```typescript
let session = runtime.session;
let unsubscribe = session.subscribe(() => {});

await runtime.newSession();

unsubscribe();
session = runtime.session;
unsubscribe = session.subscribe(() => {});
```

### 发送 Prompt 与消息排队

`PromptOptions` 控制 prompt 展开、streaming 期间的排队行为，以及 prompt 预检（preflight）通知：

```typescript
interface PromptOptions {
  expandPromptTemplates?: boolean;
  images?: ImageContent[];
  streamingBehavior?: "steer" | "followUp";
  source?: InputSource;
  preflightResult?: (success: boolean) => void;
}
```

`preflightResult` 在每次 `prompt()` 调用中只被调用一次：

- `true`：prompt 被接受、排队或被立即处理
- `false`：prompt 在被接受之前被预检拒绝

它会在 `prompt()` resolve 之前触发。`prompt()` 仍然只在被接受的完整运行（包括重试）结束后才 resolve。被接受之后发生的失败通过正常的事件和消息流上报，而不是通过 `preflightResult(false)`。

`prompt()` 方法处理提示词模板、extension 命令和消息发送：

```typescript
// 基本 prompt（非 streaming 期间）
await session.prompt("What files are here?");

// 附带图片
await session.prompt("What's in this image?", {
  images: [{ type: "image", source: { type: "base64", mediaType: "image/png", data: "..." } }]
});

// streaming 期间：必须指定消息的排队方式
await session.prompt("Stop and do this instead", { streamingBehavior: "steer" });
await session.prompt("After you're done, also check X", { streamingBehavior: "followUp" });
```

**行为：**
- **Extension 命令**（例如 `/mycommand`）：即使在 streaming 期间也立即执行。它们通过 `pi.sendMessage()` 自行管理与 LLM 的交互。
- **基于文件的提示词模板**（来自 `.md` 文件）：在发送或排队前展开为其内容。
- **streaming 期间未指定 `streamingBehavior`**：抛出错误。请直接使用 `steer()` 或 `followUp()`，或指定该选项。
- **`preflightResult(true)`**：表示 prompt 被接受、排队或被立即处理。
- **`preflightResult(false)`**：表示在被接受之前被预检拒绝。

在 streaming 期间显式排队：

```typescript
// 排队一条 steering 消息，在当前助手回合完成其工具调用后投递
await session.steer("New instruction");

// 等待 agent 完成（只在 agent 停止后投递）
await session.followUp("After you're done, also do this");
```

`steer()` 和 `followUp()` 都会展开基于文件的提示词模板，但遇到 extension 命令会报错（extension 命令不能排队）。

### Agent 与 AgentState

`Agent` 类（来自 `@earendil-works/pi-agent-core`）负责核心的 LLM 交互。通过 `session.agent` 访问。

```typescript
// 访问当前状态
const state = session.agent.state;

// state.messages: AgentMessage[] - 会话历史
// state.model: Model - 当前模型
// state.thinkingLevel: ThinkingLevel - 当前思考级别
// state.systemPrompt: string - 系统提示词
// state.tools: AgentTool[] - 可用工具
// state.streamingMessage?: AgentMessage - 当前未完成的助手消息
// state.errorMessage?: string - 最近的助手错误

// 替换消息（可用于分支或恢复）
session.agent.state.messages = messages; // 复制顶层数组

// 替换工具
session.agent.state.tools = tools; // 复制顶层数组

// 等待 agent 完成处理
await session.agent.waitForIdle();
```

### 事件

订阅事件以接收 streaming 输出和生命周期通知。

```typescript
session.subscribe((event) => {
  switch (event.type) {
    // 助手的 streaming 文本
    case "message_update":
      if (event.assistantMessageEvent.type === "text_delta") {
        process.stdout.write(event.assistantMessageEvent.delta);
      }
      if (event.assistantMessageEvent.type === "thinking_delta") {
        // 思考输出（如果启用了思考）
      }
      break;

    // 工具执行
    case "tool_execution_start":
      console.log(`Tool: ${event.toolName}`);
      break;
    case "tool_execution_update":
      // streaming 工具输出
      break;
    case "tool_execution_end":
      console.log(`Result: ${event.isError ? "error" : "success"}`);
      break;

    // 消息生命周期
    case "message_start":
      // 新消息开始
      break;
    case "message_end":
      // 消息完成
      break;

    // agent 生命周期
    case "agent_start":
      // agent 开始处理 prompt
      break;
    case "agent_end":
      // agent 完成（event.messages 包含新消息）
      break;

    // 回合生命周期（一次 LLM 响应 + 工具调用）
    case "turn_start":
      break;
    case "turn_end":
      // event.message: 助手响应
      // event.toolResults: 本回合的工具结果
      break;

    // session 事件（队列、上下文压缩、重试）
    case "queue_update":
      console.log(event.steering, event.followUp);
      break;
    case "compaction_start":
    case "compaction_end":
    case "auto_retry_start":
    case "auto_retry_end":
      break;
  }
});
```

## 选项参考

### 目录

```typescript
const { session } = await createAgentSession({
  // DefaultResourceLoader 发现资源所用的工作目录
  cwd: process.cwd(), // 默认值

  // 全局配置目录
  agentDir: "~/.pi/agent", // 默认值（会展开 ~）
});
```

`DefaultResourceLoader` 使用 `cwd` 来查找：
- 项目 extension（`.pi/extensions/`）
- 项目 skill：
  - `.pi/skills/`
  - `cwd` 及其祖先目录中的 `.agents/skills/`（向上直到 git 仓库根目录；不在仓库中时直到文件系统根目录）
- 项目 prompt（`.pi/prompts/`）
- 上下文文件（从 cwd 向上查找 `AGENTS.md`）
- session 目录命名

`DefaultResourceLoader` 使用 `agentDir` 来查找：
- 全局 extension（`extensions/`）
- 全局 skill：
  - `agentDir` 下的 `skills/`（例如 `~/.pi/agent/skills/`）
  - `~/.agents/skills/`
- 全局 prompt（`prompts/`）
- 全局上下文文件（`AGENTS.md`）
- 设置（`settings.json`）
- 自定义模型（`models.json`）
- 凭据（`auth.json`）
- session（`sessions/`）

当你传入自定义 `ResourceLoader` 时，`cwd` 和 `agentDir` 不再控制资源发现，但仍会影响 session 命名和工具路径解析。

### 模型

```typescript
import { getModel } from "@earendil-works/pi-ai";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";

const modelRuntime = await ModelRuntime.create();

// 查找特定的内置模型（不检查 API key 是否存在）
const opus = getModel("anthropic", "claude-opus-4-5");
if (!opus) throw new Error("Model not found");

// 按 provider/id 查找任意模型，包括 models.json 中的自定义模型
// （不检查 API key 是否存在）
const customModel = modelRuntime.getModel("my-provider", "my-model");

// 只获取配置了有效认证的模型
const available = await modelRuntime.getAvailable();

const { session } = await createAgentSession({
  model: opus,
  thinkingLevel: "medium", // off, minimal, low, medium, high, xhigh, max

  // 用于循环切换的模型（交互模式下的 Ctrl+P）
  scopedModels: [
    { model: opus, thinkingLevel: "high" },
    { model: haiku, thinkingLevel: "off" },
  ],

  modelRuntime,
});
```

如果没有提供模型：
1. 尝试从 session 恢复（如果是继续会话）
2. 使用设置中的默认模型
3. 回退到第一个可用模型

若要与 CLI 的模型解析行为保持一致，使用导出的解析辅助函数：

```typescript
import {
  resolveCliModel,
  resolveModelScopeWithDiagnostics,
} from "@earendil-works/pi-coding-agent";

const cliModel = resolveCliModel({
  cliModel: "anthropic/claude-opus-4-5:high",
  modelRuntime,
});
if (cliModel.error) throw new Error(cliModel.error);
if (cliModel.warning) console.warn(cliModel.warning);

const { scopedModels, diagnostics } = await resolveModelScopeWithDiagnostics(
  ["anthropic/*:high", "gpt-5"],
  modelRuntime,
);
for (const diagnostic of diagnostics) {
  console.warn(diagnostic.message);
}
```

`resolveCliModel()` 使用所有已注册的模型，因此 `--api-key` 这类首次配置流程可以在存储的认证信息尚不存在时就解析出模型。`resolveModelScopeWithDiagnostics()` 与 `--models` 和 `enabledModels` 的语义一致，但以返回值形式给出警告而不是直接打印。

> 参见 [examples/sdk/02-custom-model.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/02-custom-model.ts)

### API Key 与 OAuth

认证解析优先级（由 `ModelRuntime` 处理）：
1. 运行时覆盖（通过 `setRuntimeApiKey`，不持久化）
2. `auth.json` 中存储的凭据（API key 或 OAuth token）
3. 环境变量（`ANTHROPIC_API_KEY`、`OPENAI_API_KEY` 等）
4. 兜底解析器（用于 `models.json` 中自定义 provider 的 key）

```typescript
import { InMemoryCredentialStore } from "@earendil-works/pi-ai";
import { createAgentSession, ModelRuntime } from "@earendil-works/pi-coding-agent";

// 默认：使用 ~/.pi/agent/auth.json 和 ~/.pi/agent/models.json
const modelRuntime = await ModelRuntime.create();

// provider 自有的认证方式及当前状态
for (const provider of modelRuntime.getProviders()) {
  const status = await modelRuntime.checkAuth(provider.id);
  console.log(provider.name, provider.auth, status);
}

// 运行时 API key 覆盖（不持久化到磁盘）
modelRuntime.setRuntimeApiKey("anthropic", "sk-my-temp-key");

// 自定义凭据和模型文件位置
const customRuntime = await ModelRuntime.create({
  authPath: "/my/app/auth.json",
  modelsPath: "/my/app/models.json",
});

// 或注入任意 pi-ai CredentialStore
const credentials = new InMemoryCredentialStore();
const inMemoryRuntime = await ModelRuntime.create({ credentials });

const { session } = await createAgentSession({
  modelRuntime: customRuntime,
});
```

> 参见 [examples/sdk/09-api-keys-and-oauth.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/09-api-keys-and-oauth.ts)

### 系统提示词

使用 `ResourceLoader` 覆盖系统提示词：

```typescript
import { createAgentSession, DefaultResourceLoader } from "@earendil-works/pi-coding-agent";

const loader = new DefaultResourceLoader({
  systemPromptOverride: () => "You are a helpful assistant.",
});
await loader.reload();

const { session } = await createAgentSession({ resourceLoader: loader });
```

> 参见 [examples/sdk/03-custom-prompt.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/03-custom-prompt.ts)

### 工具

指定要启用哪些内置工具：

- 内置工具名：`read`、`bash`、`edit`、`write`、`grep`、`find`、`ls`
- 默认启用的内置工具：`read`、`bash`、`edit`、`write`
- `noTools: "all"` 禁用所有工具
- `noTools: "builtin"` 禁用默认内置工具，同时保留 extension 工具和自定义工具
- `excludeTools` 在应用 `tools` 白名单之后，再按名称禁用特定的内置、extension 或自定义工具

`edit` 工具返回的 `details.diff` 用于 pi 的 TUI 展示，`details.patch` 则是标准 unified patch 格式，供 SDK 使用方消费。

```typescript
import { createAgentSession } from "@earendil-works/pi-coding-agent";

// 只读模式
const { session } = await createAgentSession({
  tools: ["read", "grep", "find", "ls"],
});

// 挑选特定工具
const { session } = await createAgentSession({
  tools: ["read", "bash", "grep"],
});

// 禁用某个工具，其余保持可用
const { session } = await createAgentSession({
  excludeTools: ["ask_question"],
});
```

#### 自定义 cwd 下的工具

当你传入自定义 `cwd` 时，`createAgentSession()` 会为该 cwd 构建所选的内置工具。

```typescript
import { createAgentSession, SessionManager } from "@earendil-works/pi-coding-agent";

const cwd = "/path/to/project";

// 为自定义 cwd 使用默认工具
const { session } = await createAgentSession({
  cwd,
  sessionManager: SessionManager.inMemory(cwd),
});

// 或为自定义 cwd 挑选特定工具
const { session } = await createAgentSession({
  cwd,
  tools: ["read", "bash", "grep"],
  sessionManager: SessionManager.inMemory(cwd),
});
```

> 参见 [examples/sdk/05-tools.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/05-tools.ts)

### 自定义工具

```typescript
import { Type } from "typebox";
import { createAgentSession, defineTool } from "@earendil-works/pi-coding-agent";

// 内联自定义工具
const myTool = defineTool({
  name: "my_tool",
  label: "My Tool",
  description: "Does something useful",
  parameters: Type.Object({
    input: Type.String({ description: "Input value" }),
  }),
  execute: async (_toolCallId, params) => ({
    content: [{ type: "text", text: `Result: ${params.input}` }],
    details: {},
  }),
});

// 直接传入自定义工具
const { session } = await createAgentSession({
  customTools: [myTool],
});
```

对独立的工具定义以及 `customTools: [myTool]` 这类数组，使用 `defineTool()`。内联的 `pi.registerTool({ ... })` 本身已能正确推断参数类型。

通过 `customTools` 传入的自定义工具会与 extension 注册的工具合并。由 ResourceLoader 加载的 extension 也可以通过 `pi.registerTool()` 注册工具。

如果你传了 `tools`，需要把想启用的每个自定义或 extension 工具名都包含进去，例如 `tools: ["read", "bash", "my_tool"]`。

> 参见 [examples/sdk/05-tools.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/05-tools.ts)

### Extensions

Extension 由 `ResourceLoader` 加载。`DefaultResourceLoader` 从 `~/.pi/agent/extensions/`、`.pi/extensions/` 以及 settings.json 的 extension 来源中发现 extension。

```typescript
import { createAgentSession, DefaultResourceLoader } from "@earendil-works/pi-coding-agent";

const loader = new DefaultResourceLoader({
  additionalExtensionPaths: ["/path/to/my-extension.ts"],
  extensionFactories: [
    (pi) => {
      pi.on("agent_start", () => {
        console.log("[Inline Extension] Agent starting");
      });
    },
  ],
});
await loader.reload();

const { session } = await createAgentSession({ resourceLoader: loader });
```

Extension 可以注册工具、订阅事件、添加命令等。完整 API 见 [extensions.md](extensions.md)。

**具名内联 extension：** 默认情况下，内联工厂在启动时的 Extensions 列表中显示为 `<inline:1>`、`<inline:2>` 等。若要显示描述性名称，将工厂包装一下：

```typescript
import type { InlineExtension } from "@earendil-works/pi-coding-agent";

const myProvider: InlineExtension = {
  name: "my-provider",
  factory: (pi) => {
    pi.on("agent_start", () => {
      console.log("[my-provider] Agent starting");
    });
  },
};

const loader = new DefaultResourceLoader({
  extensionFactories: [myProvider],
});
```

这样会显示为 `<inline:my-provider>` 而不是 `<inline:1>`。为了向后兼容，裸工厂函数仍然可以使用。

**事件总线：** Extension 之间可以通过 `pi.events` 通信。如果你需要从外部发送或监听事件，向 `DefaultResourceLoader` 传入一个共享的 `eventBus`：

```typescript
import { createEventBus, DefaultResourceLoader } from "@earendil-works/pi-coding-agent";

const eventBus = createEventBus();
const loader = new DefaultResourceLoader({
  eventBus,
});
await loader.reload();

eventBus.on("my-extension:status", (data) => console.log(data));
```

> 参见 [examples/sdk/06-extensions.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/06-extensions.ts) 和 [docs/extensions.md](extensions.md)

### Skills

```typescript
import {
  createAgentSession,
  DefaultResourceLoader,
  type Skill,
} from "@earendil-works/pi-coding-agent";

const customSkill: Skill = {
  name: "my-skill",
  description: "Custom instructions",
  filePath: "/path/to/SKILL.md",
  baseDir: "/path/to",
  source: "custom",
};

const loader = new DefaultResourceLoader({
  skillsOverride: (current) => ({
    skills: [...current.skills, customSkill],
    diagnostics: current.diagnostics,
  }),
});
await loader.reload();

const { session } = await createAgentSession({ resourceLoader: loader });
```

> 参见 [examples/sdk/04-skills.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/04-skills.ts)

### 上下文文件

```typescript
import { createAgentSession, DefaultResourceLoader } from "@earendil-works/pi-coding-agent";

const loader = new DefaultResourceLoader({
  agentsFilesOverride: (current) => ({
    agentsFiles: [
      ...current.agentsFiles,
      { path: "/virtual/AGENTS.md", content: "# Guidelines\n\n- Be concise" },
    ],
  }),
});
await loader.reload();

const { session } = await createAgentSession({ resourceLoader: loader });
```

> 参见 [examples/sdk/07-context-files.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/07-context-files.ts)

### 斜杠命令

```typescript
import {
  createAgentSession,
  DefaultResourceLoader,
  type PromptTemplate,
} from "@earendil-works/pi-coding-agent";

const customCommand: PromptTemplate = {
  name: "deploy",
  description: "Deploy the application",
  source: "(custom)",
  content: "# Deploy\n\n1. Build\n2. Test\n3. Deploy",
};

const loader = new DefaultResourceLoader({
  promptsOverride: (current) => ({
    prompts: [...current.prompts, customCommand],
    diagnostics: current.diagnostics,
  }),
});
await loader.reload();

const { session } = await createAgentSession({ resourceLoader: loader });
```

> 参见 [examples/sdk/08-prompt-templates.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/08-prompt-templates.ts)

### 会话管理

session 使用带 `id`/`parentId` 链接的树结构，支持原地分支。

```typescript
import {
  type CreateAgentSessionRuntimeFactory,
  createAgentSession,
  createAgentSessionFromServices,
  createAgentSessionRuntime,
  createAgentSessionServices,
  getAgentDir,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

// 内存中（不持久化）
const { session } = await createAgentSession({
  sessionManager: SessionManager.inMemory(),
});

// 新的持久化 session
const { session: persisted } = await createAgentSession({
  sessionManager: SessionManager.create(process.cwd()),
});

// 继续最近的 session
const { session: continued, modelFallbackMessage } = await createAgentSession({
  sessionManager: SessionManager.continueRecent(process.cwd()),
});
if (modelFallbackMessage) {
  console.log("Note:", modelFallbackMessage);
}

// 打开特定文件
const { session: opened } = await createAgentSession({
  sessionManager: SessionManager.open("/path/to/session.jsonl"),
});

// 列出 session
const currentProjectSessions = await SessionManager.list(process.cwd());
const allSessions = await SessionManager.listAll(process.cwd());

// 用于 /new、/resume、/fork、/clone 及导入流程的 session 替换 API。
const createRuntime: CreateAgentSessionRuntimeFactory = async ({ cwd, sessionManager, sessionStartEvent }) => {
  const services = await createAgentSessionServices({ cwd });
  return {
    ...(await createAgentSessionFromServices({
      services,
      sessionManager,
      sessionStartEvent,
    })),
    services,
    diagnostics: services.diagnostics,
  };
};

const runtime = await createAgentSessionRuntime(createRuntime, {
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  sessionManager: SessionManager.create(process.cwd()),
});

// 用一个全新 session 替换当前活动 session
await runtime.newSession();

// 用另一个已保存的 session 替换当前活动 session
await runtime.switchSession("/path/to/session.jsonl");

// 用从特定用户条目分叉出的 session 替换当前活动 session
await runtime.fork("entry-id");

// 克隆经过特定条目的活动路径
await runtime.fork("entry-id", { position: "at" });
```

**SessionManager 树 API：**

```typescript
const sm = SessionManager.open("/path/to/session.jsonl");

// session 列表
const currentProjectSessions = await SessionManager.list(process.cwd());
const allSessions = await SessionManager.listAll(process.cwd());

// 树遍历
const entries = sm.getEntries();        // 所有条目（不含头部）
const tree = sm.getTree();              // 完整树结构
const path = sm.getPath();              // 从根到当前叶子的路径
const leaf = sm.getLeafEntry();         // 当前叶子条目
const entry = sm.getEntry(id);          // 按 ID 获取条目
const children = sm.getChildren(id);    // 条目的直接子节点

// 标签
const label = sm.getLabel(id);          // 获取条目的标签
sm.appendLabelChange(id, "checkpoint"); // 设置标签

// 分支
sm.branch(entryId);                     // 将叶子移动到更早的条目
sm.branchWithSummary(id, "Summary...");  // 带上下文摘要的分支
sm.createBranchedSession(leafId);       // 将路径提取为新文件
```

> 参见 [examples/sdk/11-sessions.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/11-sessions.ts) 和 [Session 格式](session-format.md)

### 设置管理

```typescript
import { createAgentSession, SettingsManager, SessionManager } from "@earendil-works/pi-coding-agent";

// 默认：从文件加载（全局 + 项目合并）
const { session } = await createAgentSession({
  settingsManager: SettingsManager.create(),
});

// 带覆盖项
const settingsManager = SettingsManager.create();
settingsManager.applyOverrides({
  compaction: { enabled: false },
  retry: { enabled: true, maxRetries: 5 },
});
const { session } = await createAgentSession({ settingsManager });

// 内存中（无文件 I/O，用于测试）
const { session } = await createAgentSession({
  settingsManager: SettingsManager.inMemory({ compaction: { enabled: false } }),
  sessionManager: SessionManager.inMemory(),
});

// 自定义目录
const { session } = await createAgentSession({
  settingsManager: SettingsManager.create("/custom/cwd", "/custom/agent"),
});
```

**静态工厂：**
- `SettingsManager.create(cwd?, agentDir?)` - 从文件加载
- `SettingsManager.inMemory(settings?)` - 无文件 I/O

**项目级设置：**

设置从两个位置加载并合并：
1. 全局：`~/.pi/agent/settings.json`
2. 项目：`<cwd>/.pi/settings.json`

项目设置覆盖全局设置。嵌套对象按键合并。setter 默认修改全局设置。

**持久化与错误处理语义：**

- 设置的 getter/setter 对内存状态是同步的。
- setter 会异步地将持久化写入加入队列。
- 当你需要一个持久化边界时（例如进程退出前，或在测试中断言文件内容前），调用 `await settingsManager.flush()`。
- `SettingsManager` 不会打印设置 I/O 错误。请使用 `settingsManager.drainErrors()`，并在你的应用层上报这些错误。

> 参见 [examples/sdk/10-settings.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/10-settings.ts)

## ResourceLoader

使用 `DefaultResourceLoader` 发现 extension、skill、prompt、主题和上下文文件。

```typescript
import {
  DefaultResourceLoader,
  getAgentDir,
} from "@earendil-works/pi-coding-agent";

const loader = new DefaultResourceLoader({
  cwd,
  agentDir: getAgentDir(),
});
await loader.reload();

const extensions = loader.getExtensions();
const skills = loader.getSkills();
const prompts = loader.getPrompts();
const themes = loader.getThemes();
const contextFiles = loader.getAgentsFiles().agentsFiles;
```

## 返回值

`createAgentSession()` 返回：

```typescript
interface CreateAgentSessionResult {
  // session 本身
  session: AgentSession;

  // extension 加载结果（用于 runner 的初始化）
  extensionsResult: LoadExtensionsResult;

  // 若 session 模型无法恢复时的警告
  modelFallbackMessage?: string;
}

interface LoadExtensionsResult {
  extensions: Extension[];
  errors: Array<{ path: string; error: string }>;
  runtime: ExtensionRuntime;
}
```

## 完整示例

```typescript
import { getModel } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import {
  createAgentSession,
  DefaultResourceLoader,
  defineTool,
  ModelRuntime,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

const modelRuntime = await ModelRuntime.create({
  authPath: "/custom/agent/auth.json",
  modelsPath: "/custom/agent/models.json",
});
if (process.env.MY_KEY) {
  modelRuntime.setRuntimeApiKey("anthropic", process.env.MY_KEY);
}

// 内联工具
const statusTool = defineTool({
  name: "status",
  label: "Status",
  description: "Get system status",
  parameters: Type.Object({}),
  execute: async () => ({
    content: [{ type: "text", text: `Uptime: ${process.uptime()}s` }],
    details: {},
  }),
});

const model = getModel("anthropic", "claude-opus-4-5");
if (!model) throw new Error("Model not found");

// 带覆盖项的内存设置
const settingsManager = SettingsManager.inMemory({
  compaction: { enabled: false },
  retry: { enabled: true, maxRetries: 2 },
});

const loader = new DefaultResourceLoader({
  cwd: process.cwd(),
  agentDir: "/custom/agent",
  settingsManager,
  systemPromptOverride: () => "You are a minimal assistant. Be concise.",
});
await loader.reload();

const { session } = await createAgentSession({
  cwd: process.cwd(),
  agentDir: "/custom/agent",

  model,
  thinkingLevel: "off",
  modelRuntime,

  tools: ["read", "bash", "status"],
  customTools: [statusTool],
  resourceLoader: loader,

  sessionManager: SessionManager.inMemory(),
  settingsManager,
});

session.subscribe((event) => {
  if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
    process.stdout.write(event.assistantMessageEvent.delta);
  }
});

await session.prompt("Get status and list files.");
```

## 运行模式

SDK 导出了若干运行模式工具，便于在 `createAgentSession()` 之上构建自定义界面：

### InteractiveMode

完整的 TUI 交互模式，带编辑器、聊天历史和所有内置命令：

```typescript
import {
  type CreateAgentSessionRuntimeFactory,
  createAgentSessionFromServices,
  createAgentSessionRuntime,
  createAgentSessionServices,
  getAgentDir,
  InteractiveMode,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

const createRuntime: CreateAgentSessionRuntimeFactory = async ({ cwd, sessionManager, sessionStartEvent }) => {
  const services = await createAgentSessionServices({ cwd });
  return {
    ...(await createAgentSessionFromServices({ services, sessionManager, sessionStartEvent })),
    services,
    diagnostics: services.diagnostics,
  };
};
const runtime = await createAgentSessionRuntime(createRuntime, {
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  sessionManager: SessionManager.create(process.cwd()),
});

const mode = new InteractiveMode(runtime, {
  migratedProviders: [],
  modelFallbackMessage: undefined,
  initialMessage: "Hello",
  initialImages: [],
  initialMessages: [],
});

await mode.run();
```

### runPrintMode

一次性模式：发送 prompt、输出结果、退出：

```typescript
import {
  type CreateAgentSessionRuntimeFactory,
  createAgentSessionFromServices,
  createAgentSessionRuntime,
  createAgentSessionServices,
  getAgentDir,
  runPrintMode,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

const createRuntime: CreateAgentSessionRuntimeFactory = async ({ cwd, sessionManager, sessionStartEvent }) => {
  const services = await createAgentSessionServices({ cwd });
  return {
    ...(await createAgentSessionFromServices({ services, sessionManager, sessionStartEvent })),
    services,
    diagnostics: services.diagnostics,
  };
};
const runtime = await createAgentSessionRuntime(createRuntime, {
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  sessionManager: SessionManager.create(process.cwd()),
});

await runPrintMode(runtime, {
  mode: "text",
  initialMessage: "Hello",
  initialImages: [],
  messages: ["Follow up"],
});
```

### runRpcMode

用于子进程集成的 JSON-RPC 模式：

```typescript
import {
  type CreateAgentSessionRuntimeFactory,
  createAgentSessionFromServices,
  createAgentSessionRuntime,
  createAgentSessionServices,
  getAgentDir,
  runRpcMode,
  SessionManager,
} from "@earendil-works/pi-coding-agent";

const createRuntime: CreateAgentSessionRuntimeFactory = async ({ cwd, sessionManager, sessionStartEvent }) => {
  const services = await createAgentSessionServices({ cwd });
  return {
    ...(await createAgentSessionFromServices({ services, sessionManager, sessionStartEvent })),
    services,
    diagnostics: services.diagnostics,
  };
};
const runtime = await createAgentSessionRuntime(createRuntime, {
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  sessionManager: SessionManager.create(process.cwd()),
});

await runRpcMode(runtime);
```

JSON 协议见 [RPC 文档](rpc.md)。

## RPC 模式替代方案

如果想做基于子进程的集成而不使用 SDK 构建，可以直接使用 CLI：

```bash
pi --mode rpc --no-session
```

JSON 协议见 [RPC 文档](rpc.md)。

以下情况优先选 SDK：
- 你需要类型安全
- 你在同一个 Node.js 进程中
- 你需要直接访问 agent 状态
- 你想以编程方式自定义工具/extension

以下情况优先选 RPC 模式：
- 你在从其它语言做集成
- 你需要进程隔离
- 你在构建与语言无关的客户端

## 导出

主入口导出：

```typescript
// 工厂
createAgentSession
createAgentSessionRuntime
AgentSessionRuntime

// 认证与模型
ModelRuntime // 实现 pi-ai 的 Models 接口，并负责凭据存储
ModelRegistry // 同步的 extension 兼容门面
resolveCliModel
resolveModelScopeWithDiagnostics

// 资源加载
DefaultResourceLoader
type ResourceLoader
createEventBus

// 常量与辅助函数
CONFIG_DIR_NAME
defineTool
getAgentDir
getPackageDir
getReadmePath
getDocsPath
getExamplesPath

// 会话管理
SessionManager
SettingsManager

// 工具工厂
createCodingTools
createReadOnlyTools
createReadTool, createBashTool, createEditTool, createWriteTool
createGrepTool, createFindTool, createLsTool

// 类型
type CreateAgentSessionOptions
type CreateAgentSessionResult
type ExtensionFactory
type InlineExtension
type ExtensionAPI
type ToolDefinition
type Skill
type PromptTemplate
type Tool
```

Extension 相关类型的完整 API 见 [extensions.md](extensions.md)。
