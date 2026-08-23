> **译文** | 原文：[`packages/coding-agent/examples/sdk/README.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/sdk/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-23

# SDK 示例

通过 `createAgentSession()` 和 `createAgentSessionRuntime()` 以编程方式使用 pi-coding-agent。

runtime 示例展示了如何构建一个 recreate 函数：它闭包捕获进程级的全局固定输入，并在活动会话的 cwd 变化时重建绑定到 cwd 的服务和会话。

## 示例

| 文件 | 描述 |
|------|-------------|
| `01-minimal.ts` | 使用全部默认值的最简单用法 |
| `02-custom-model.ts` | 选择模型和 thinking 级别 |
| `03-custom-prompt.ts` | 替换或修改 system prompt |
| `04-skills.ts` | 发现、过滤或替换 skills |
| `05-tools.ts` | 内置工具 allowlist |
| `06-extensions.ts` | 日志、拦截、修改结果 |
| `07-context-files.ts` | AGENTS.md 上下文文件 |
| `08-slash-commands.ts` | 基于文件的斜杠命令 |
| `09-api-keys-and-oauth.ts` | API key 解析、OAuth 配置 |
| `10-settings.ts` | 覆盖 compaction、重试、终端设置 |
| `11-sessions.ts` | 内存会话、持久化会话、继续会话、列出会话 |
| `12-full-control.ts` | 替换一切，不做自动发现 |
| `13-session-runtime.ts` | 管理由 runtime 支撑的会话替换 |

## 运行

```bash
cd packages/coding-agent
npx tsx examples/sdk/01-minimal.ts
```

## 快速参考

```typescript
import { getModel } from "@earendil-works/pi-ai";
import {
  createAgentSession,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

const modelRuntime = await ModelRuntime.create();

// 最简用法
const { session } = await createAgentSession({ modelRuntime });

// 自定义模型
const model = getModel("anthropic", "claude-opus-4-5");
const { session } = await createAgentSession({ model, thinkingLevel: "high", modelRuntime });

// 修改 prompt
const loader = new DefaultResourceLoader({
  systemPromptOverride: (base) => `${base}\n\nBe concise.`,
});
await loader.reload();
const { session } = await createAgentSession({ resourceLoader: loader, modelRuntime });

// 只读
const { session } = await createAgentSession({ tools: ["read", "grep", "find", "ls"], modelRuntime });

// 内存会话
const { session } = await createAgentSession({
  sessionManager: SessionManager.inMemory(),
  modelRuntime,
});

// 完全控制
const customRuntime = await ModelRuntime.create({
  authPath: "/my/app/auth.json",
  modelsPath: "/my/app/models.json",
});
await customRuntime.setRuntimeApiKey("anthropic", process.env.MY_KEY!);

const resourceLoader = new DefaultResourceLoader({
  systemPromptOverride: () => "You are helpful.",
  extensionFactories: [myExtension],
  skillsOverride: () => ({ skills: [], diagnostics: [] }),
  agentsFilesOverride: () => ({ agentsFiles: [] }),
  promptsOverride: () => ({ prompts: [], diagnostics: [] }),
});
await resourceLoader.reload();

const { session } = await createAgentSession({
  model,
  modelRuntime: customRuntime,
  resourceLoader,
  tools: ["read", "bash", "my_tool"],
  customTools: [myTool],
  sessionManager: SessionManager.inMemory(),
  settingsManager: SettingsManager.inMemory(),
});

// 运行 prompt
session.subscribe((event) => {
  if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
    process.stdout.write(event.assistantMessageEvent.delta);
  }
});
await session.prompt("Hello");
```

## 选项

| 选项 | 默认值 | 描述 |
|--------|---------|-------------|
| `modelRuntime` | 使用 `agentDir/auth.json` 和 `models.json` 的 runtime | 规范的模型与认证 runtime |
| `cwd` | `process.cwd()` | 工作目录 |
| `agentDir` | `~/.pi/agent` | 配置目录 |
| `model` | 来自设置/第一个可用模型 | 要使用的模型 |
| `thinkingLevel` | 来自设置/"off" | off、low、medium、high |
| `tools` | `["read", "bash", "edit", "write"]` 内置工具 | 跨内置、extension 和自定义工具的工具名 allowlist |
| `customTools` | `[]` | 额外的工具定义 |
| `resourceLoader` | DefaultResourceLoader | 加载 extensions、skills、prompts、themes 和上下文文件的资源加载器 |
| `sessionManager` | `SessionManager.create(cwd)` | 持久化 |
| `settingsManager` | `SettingsManager.create(cwd, agentDir)` | 设置覆盖 |

## 事件

```typescript
session.subscribe((event) => {
  switch (event.type) {
    case "message_update":
      if (event.assistantMessageEvent.type === "text_delta") {
        process.stdout.write(event.assistantMessageEvent.delta);
      }
      break;
    case "tool_execution_start":
      console.log(`Tool: ${event.toolName}`);
      break;
    case "tool_execution_end":
      console.log(`Result: ${event.result}`);
      break;
    case "agent_settled":
      console.log("Done");
      break;
  }
});
```

