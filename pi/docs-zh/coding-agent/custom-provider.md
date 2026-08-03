> **译文** | 原文：[`packages/coding-agent/docs/custom-provider.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/custom-provider.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 自定义 Provider

Extension 可以通过 `pi.registerProvider()` 注册自定义模型 provider。这可以实现：

- **代理** —— 让请求经由企业代理或 API 网关转发
- **自定义端点** —— 使用自托管或私有的模型部署
- **OAuth/SSO** —— 为企业 provider 添加认证流程
- **自定义 API** —— 为非标准 LLM API 实现 streaming

## 示例 Extension

参见以下完整的 provider 示例：

- [`examples/extensions/custom-provider-anthropic/`](https://github.com/earendil-works/pi/tree/main/packages/coding-agent/examples/extensions/custom-provider-anthropic/)
- [`examples/extensions/custom-provider-gitlab-duo/`](https://github.com/earendil-works/pi/tree/main/packages/coding-agent/examples/extensions/custom-provider-gitlab-duo/)

## 目录

- [示例 Extension](#示例-extension)
- [快速参考](#快速参考)
- [覆盖已有 Provider](#覆盖已有-provider)
- [注册新 Provider](#注册新-provider)
- [注销 Provider](#注销-provider)
- [OAuth 支持](#oauth-支持)
- [自定义 Streaming API](#自定义-streaming-api)
- [上下文溢出错误](#上下文溢出错误)
- [测试你的实现](#测试你的实现)
- [配置参考](#配置参考)
- [模型定义参考](#模型定义参考)

## 快速参考

Extension 既可以注册一个完整的 pi-ai `Provider`，也可以使用旧式的 provider-config 形式。当需要自定义认证、过滤、刷新或 streaming 行为时，优先选择完整的 provider。pi 会把 `models.json` 的覆盖配置叠加在已注册的原生 provider 之上。

```typescript
import { createProvider, openAICompletionsApi } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerProvider(createProvider({
    id: "native-local",
    name: "Native Local",
    baseUrl: "http://localhost:8080/v1",
    auth: {
      apiKey: {
        name: "Local server API key",
        async login(interaction) {
          return {
            type: "api_key",
            key: await interaction.prompt({ type: "secret", message: "API key" })
          };
        },
        async resolve({ credential }) {
          return credential?.key
            ? { auth: { apiKey: credential.key }, source: "stored API key" }
            : undefined;
        }
      }
    },
    models: [],
    api: openAICompletionsApi()
  }));

  // 旧式 provider-config 形式：
  // 为已有 provider 覆盖 baseUrl
  pi.registerProvider("anthropic", {
    baseUrl: "https://proxy.example.com"
  });

  // 注册携带模型列表的新 provider
  pi.registerProvider("my-provider", {
    name: "My Provider",
    baseUrl: "https://api.example.com",
    apiKey: "$MY_API_KEY",
    api: "openai-completions",
    models: [
      {
        id: "my-model",
        name: "My Model",
        reasoning: false,
        input: ["text", "image"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128000,
        maxTokens: 4096
      }
    ]
  });
}
```

Extension 工厂函数也可以是 `async` 的。若需动态发现模型，请在工厂函数中获取并注册模型，而不是在 `session_start` 里做。pi 会先等待工厂函数完成再继续启动，因此该 provider 在交互式启动期间以及 `pi --list-models` 中都可用。

## 覆盖已有 Provider

最简单的用例：把已有 provider 的请求重定向到代理。

```typescript
// 现在所有 Anthropic 请求都会经过你的代理
pi.registerProvider("anthropic", {
  baseUrl: "https://proxy.example.com"
});

// 给 OpenAI 请求添加自定义 header
pi.registerProvider("openai", {
  headers: {
    "X-Custom-Header": "value"
  }
});

// 同时指定 baseUrl 和 headers
pi.registerProvider("google", {
  baseUrl: "https://ai-gateway.corp.com/google",
  headers: {
    "X-Corp-Auth": "$CORP_AUTH_TOKEN"  // 环境变量或字面量
  }
});
```

当只提供 `baseUrl` 和/或 `headers`（不提供 `models`）时，该 provider 的所有现有模型都会保留，并使用新的端点。

## 注册新 Provider

要添加一个全新的 provider，请在必需配置之外指定 `models`。

如果模型列表来自远程端点，使用异步 extension 工厂函数：

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

这样会在启动完成之前注册好获取到的模型。

```typescript
pi.registerProvider("my-llm", {
  baseUrl: "https://api.my-llm.com/v1",
  apiKey: "$MY_LLM_API_KEY",  // 环境变量引用
  api: "openai-completions",  // 使用哪种 streaming API
  models: [
    {
      id: "my-llm-large",
      name: "My LLM Large",
      reasoning: true,        // 支持扩展 thinking
      input: ["text", "image"],
      cost: {
        input: 3.0,           // 美元/百万 token
        output: 15.0,
        cacheRead: 0.3,
        cacheWrite: 3.75
      },
      contextWindow: 200000,
      maxTokens: 16384
    }
  ]
});
```

当提供了 `models` 时，它会**替换**该 provider 的所有现有模型。

`apiKey` 和自定义 header 的值使用与 `models.json` 相同的配置值语法：以 `!command` 开头会执行命令并把输出作为整个值，`$ENV_VAR` 和 `${ENV_VAR}` 插值环境变量，`$$` 输出字面量 `$`，`$!` 输出字面量 `!`。

## 注销 Provider

使用 `pi.unregisterProvider(name)` 移除之前通过 `pi.registerProvider(name, ...)` 注册的 provider：

```typescript
// 注册
pi.registerProvider("my-llm", {
  baseUrl: "https://api.my-llm.com/v1",
  apiKey: "$MY_LLM_API_KEY",
  api: "openai-completions",
  models: [
    {
      id: "my-llm-large",
      name: "My LLM Large",
      reasoning: true,
      input: ["text", "image"],
      cost: { input: 3.0, output: 15.0, cacheRead: 0.3, cacheWrite: 3.75 },
      contextWindow: 200000,
      maxTokens: 16384
    }
  ]
});

// 之后再移除它
pi.unregisterProvider("my-llm");
```

注销会移除该 provider 的动态模型、API key 回退、OAuth provider 注册以及自定义 stream 处理器注册。任何被覆盖的内置模型或 provider 行为都会被恢复。

在初始 extension 加载阶段之后发起的调用会立即生效，因此不需要 `/reload`。

### API 类型

`api` 字段决定使用哪种 streaming 实现：

| API | 适用于 |
|-----|---------|
| `anthropic-messages` | Anthropic Claude API 及兼容 API |
| `openai-completions` | OpenAI Chat Completions API 及兼容 API |
| `openai-responses` | OpenAI Responses API |
| `azure-openai-responses` | Azure OpenAI Responses API |
| `openai-codex-responses` | OpenAI Codex Responses API |
| `mistral-conversations` | Mistral SDK Conversations/Chat streaming |
| `google-generative-ai` | Google Generative AI API |
| `google-vertex` | Google Vertex AI API |
| `bedrock-converse-stream` | Amazon Bedrock Converse API |

大多数 OpenAI 兼容 provider 使用 `openai-completions` 即可。用模型级的 `thinkingLevelMap` 设置模型特有的 thinking 级别，用 `compat` 处理 provider 的兼容性怪癖。`xhigh` 和 `max` 级别需要显式启用（opt-in），要求对应的映射条目非 null，且中间允许被不支持的空档隔开：

```typescript
models: [{
  id: "custom-model",
  // ...
  reasoning: true,
  thinkingLevelMap: {              // 把 pi 的级别映射为 provider 的值；null 表示隐藏不支持的级别
    minimal: null,
    low: null,
    medium: null,
    high: "default",
    xhigh: null,
    max: "max"
  },
  compat: {
    supportsDeveloperRole: false,   // 使用 "system" 而不是 "developer"
    supportsReasoningEffort: true,
    maxTokensField: "max_tokens",   // 代替 "max_completion_tokens"
    requiresToolResultName: true,   // 工具结果需要 name 字段
    thinkingFormat: "qwen",        // 顶层 enable_thinking: true
    cacheControlFormat: "anthropic" // Anthropic 风格的 cache_control 标记
  }
}]
```

对 OpenRouter 风格的 `reasoning: { effort }` 控制使用 `openrouter`。对 Together 风格的 `reasoning: { enabled }` 控制使用 `together`；启用 `supportsReasoningEffort` 后，它还会发送 `reasoning_effort`。对读取 `chat_template_kwargs.enable_thinking` 且需要 `preserve_thinking` 的本地 Qwen 兼容服务器使用 `qwen-chat-template`。
对于通过系统提示词、最后一个工具定义以及最后一条 user/assistant 文本内容上的 `cache_control` 暴露 Anthropic 风格 prompt 缓存的 OpenAI 兼容 provider，使用 `cacheControlFormat: "anthropic"`。

对于使用 `api: "anthropic-messages"` 的 Anthropic 兼容 provider，如果其上游模型要求自适应 thinking（`thinking.type: "adaptive"` 加 `output_config.effort`），请在模型或 provider 上设置 `compat.forceAdaptiveThinking: true`。内置的自适应 Claude 模型会自动设置它。只有当 provider 会发出空的 thinking 签名并且期望在重放时收到 `signature: ""` 时，才设置 `compat.allowEmptySignature: true`。

> 迁移说明：Mistral 已从 `openai-completions` 迁移到 `mistral-conversations`。
> 原生 Mistral 模型请使用 `mistral-conversations`。
> 如果你有意让 Mistral 兼容/自定义端点走 `openai-completions`，请按需显式设置 `compat` 标志。

### 认证 Header

如果你的 provider 期望 `Authorization: Bearer <key>` 但没有使用标准 API，设置 `authHeader: true`：

```typescript
pi.registerProvider("custom-api", {
  baseUrl: "https://api.example.com",
  apiKey: "$MY_API_KEY",
  authHeader: true,  // 添加 Authorization: Bearer header
  api: "openai-completions",
  models: [...]
});
```

key 会在每次请求时解析。请求中显式指定的 `Authorization` header 优先于生成的值。

## OAuth 支持

添加与 `/login` 集成的 OAuth/SSO 认证：

```typescript
import type { OAuthCredentials, OAuthLoginCallbacks } from "@earendil-works/pi-ai";

pi.registerProvider("corporate-ai", {
  baseUrl: "https://ai.corp.com/v1",
  api: "openai-responses",
  models: [...],
  oauth: {
    name: "Corporate AI (SSO)",

    async login(callbacks: OAuthLoginCallbacks): Promise<OAuthCredentials> {
      const method = await callbacks.onSelect({
        message: "Select login method:",
        options: [
          { id: "browser", label: "Browser OAuth" },
          { id: "device", label: "Device code" }
        ]
      });
      if (!method) throw new Error("Login cancelled");

      let code: string;
      if (method === "device") {
        callbacks.onDeviceCode({
          userCode: "ABCD-1234",
          verificationUri: "https://sso.corp.com/device",
          intervalSeconds: 5,
          expiresInSeconds: 900
        });
        code = await pollDeviceCodeUntilComplete();
      } else {
        callbacks.onAuth({ url: "https://sso.corp.com/authorize?..." });
        code = await callbacks.onPrompt({ message: "Enter SSO code:" });
      }

      // 用授权码交换 token（由你实现）
      const tokens = await exchangeCodeForTokens(code);

      return {
        refresh: tokens.refreshToken,
        access: tokens.accessToken,
        expires: Date.now() + tokens.expiresIn * 1000
      };
    },

    async refreshToken(credentials: OAuthCredentials): Promise<OAuthCredentials> {
      const tokens = await refreshAccessToken(credentials.refresh);
      return {
        refresh: tokens.refreshToken ?? credentials.refresh,
        access: tokens.accessToken,
        expires: Date.now() + tokens.expiresIn * 1000
      };
    },

    getApiKey(credentials: OAuthCredentials): string {
      return credentials.access;
    }
  }
});
```

注册后，用户即可通过 `/login corporate-ai` 认证。

### OAuthLoginCallbacks

`callbacks` 对象为 provider 自有的认证流程提供与 UI 无关的交互能力：

```typescript
interface OAuthLoginCallbacks {
  // 在浏览器中打开 URL（用于 OAuth 重定向）
  onAuth(params: { url: string }): void;

  // 显示设备码（用于设备授权流程）
  onDeviceCode(params: {
    userCode: string;
    verificationUri: string;
    intervalSeconds?: number;
    expiresInSeconds?: number;
  }): void;

  // 显示临时进度信息
  onProgress?(message: string): void;

  // 提示用户输入（用于手动输入 token）
  onPrompt(params: { message: string }): Promise<string>;

  // 显示交互式选择器，例如在浏览器 OAuth 和设备码之间选择
  onSelect(params: {
    message: string;
    options: { id: string; label: string }[];
  }): Promise<string | undefined>;
}
```

### OAuthCredentials

凭据持久化在 `~/.pi/agent/auth.json`：

```typescript
interface OAuthCredentials {
  refresh: string;   // 刷新 token（供 refreshToken() 使用）
  access: string;    // 访问 token（由 getApiKey() 返回）
  expires: number;   // 过期时间戳，单位毫秒
}
```

## 自定义 Streaming API

对于使用非标准 API 的 provider，实现 `streamSimple`。在自己动手之前，请先研究已有的 provider 实现：

**参考实现：**
- [anthropic.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/providers/anthropic.ts) —— Anthropic Messages API
- [mistral.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/providers/mistral.ts) —— Mistral Conversations API
- [openai-completions.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/providers/openai-completions.ts) —— OpenAI Chat Completions
- [openai-responses.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/providers/openai-responses.ts) —— OpenAI Responses API
- [google.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/providers/google.ts) —— Google Generative AI
- [amazon-bedrock.ts](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/providers/amazon-bedrock.ts) —— AWS Bedrock

### Stream 模式

所有 provider 都遵循同一套模式：

```typescript
import {
  type AssistantMessage,
  type AssistantMessageEventStream,
  type Context,
  type Model,
  type SimpleStreamOptions,
  calculateCost,
  createAssistantMessageEventStream,
} from "@earendil-works/pi-ai";

function streamMyProvider(
  model: Model<any>,
  context: Context,
  options?: SimpleStreamOptions
): AssistantMessageEventStream {
  const stream = createAssistantMessageEventStream();

  (async () => {
    // 初始化输出消息
    const output: AssistantMessage = {
      role: "assistant",
      content: [],
      api: model.api,
      provider: model.provider,
      model: model.id,
      usage: {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
      stopReason: "stop",
      timestamp: Date.now(),
    };

    try {
      // 推送 start 事件
      stream.push({ type: "start", partial: output });

      // 发起 API 请求并处理响应……
      // 随着数据到达推送内容事件……

      // 推送 done 事件
      stream.push({
        type: "done",
        reason: output.stopReason as "stop" | "length" | "toolUse",
        message: output
      });
      stream.end();
    } catch (error) {
      output.stopReason = options?.signal?.aborted ? "aborted" : "error";
      output.errorMessage = error instanceof Error ? error.message : String(error);
      stream.push({ type: "error", reason: output.stopReason, error: output });
      stream.end();
    }
  })();

  return stream;
}
```

### 事件类型

通过 `stream.push()` 按以下顺序推送事件：

1. `{ type: "start", partial: output }` —— stream 已开始

2. 内容事件（可重复，为每个块跟踪 `contentIndex`）：
   - `{ type: "text_start", contentIndex, partial }` —— 文本块开始
   - `{ type: "text_delta", contentIndex, delta, partial }` —— 文本片段
   - `{ type: "text_end", contentIndex, content, partial }` —— 文本块结束
   - `{ type: "thinking_start", contentIndex, partial }` —— thinking 开始
   - `{ type: "thinking_delta", contentIndex, delta, partial }` —— thinking 片段
   - `{ type: "thinking_end", contentIndex, content, partial }` —— thinking 结束
   - `{ type: "toolcall_start", contentIndex, partial }` —— 工具调用开始
   - `{ type: "toolcall_delta", contentIndex, delta, partial }` —— 工具调用 JSON 片段
   - `{ type: "toolcall_end", contentIndex, toolCall, partial }` —— 工具调用结束

3. `{ type: "done", reason, message }` 或 `{ type: "error", reason, error }` —— stream 结束

每个事件中的 `partial` 字段包含当前的 `AssistantMessage` 状态。随着数据到达更新 `output.content`，然后把 `output` 作为 `partial` 一并推送。

### 内容块

随着数据到达向 `output.content` 添加内容块：

```typescript
// 文本块
output.content.push({ type: "text", text: "" });
stream.push({ type: "text_start", contentIndex: output.content.length - 1, partial: output });

// 文本到达时
const block = output.content[contentIndex];
if (block.type === "text") {
  block.text += delta;
  stream.push({ type: "text_delta", contentIndex, delta, partial: output });
}

// 块完成时
stream.push({ type: "text_end", contentIndex, content: block.text, partial: output });
```

### 工具调用

工具调用需要累积 JSON 并解析：

```typescript
// 开始工具调用
output.content.push({
  type: "toolCall",
  id: toolCallId,
  name: toolName,
  arguments: {}
});
stream.push({ type: "toolcall_start", contentIndex: output.content.length - 1, partial: output });

// 累积 JSON
let partialJson = "";
partialJson += jsonDelta;
try {
  block.arguments = JSON.parse(partialJson);
} catch {}
stream.push({ type: "toolcall_delta", contentIndex, delta: jsonDelta, partial: output });

// 完成
stream.push({
  type: "toolcall_end",
  contentIndex,
  toolCall: { type: "toolCall", id, name, arguments: block.arguments },
  partial: output
});
```

### 用量与费用

根据 API 响应更新用量并计算费用：

```typescript
output.usage.input = response.usage.input_tokens;
output.usage.output = response.usage.output_tokens;
output.usage.cacheRead = response.usage.cache_read_tokens ?? 0;
output.usage.cacheWrite = response.usage.cache_write_tokens ?? 0;
output.usage.totalTokens = output.usage.input + output.usage.output +
                           output.usage.cacheRead + output.usage.cacheWrite;
calculateCost(model, output.usage);
```

### 上下文溢出错误

当请求超出模型的上下文窗口时，pi 可以通过压缩会话（上下文压缩）并重试来自动恢复。只有当 pi 把失败识别为溢出时，这种恢复才会启动。

检测在最终确定的 assistant 消息上进行：

- `stopReason === "error"`
- `errorMessage` 匹配 pi 已知的溢出模式之一（参见 [`packages/ai/src/utils/overflow.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/utils/overflow.ts)）

如果你的 provider 返回的溢出错误消息 pi 无法识别，请在注册该 provider 的同一个 extension 中对错误进行归一化。使用 `message_end` 处理器改写 assistant 消息，使其 `errorMessage` 以 pi 能识别的短语开头。通用回退值 `context_length_exceeded` 是最稳妥的选择。

```typescript
const MY_PROVIDER_OVERFLOW_PATTERN = /your provider's overflow phrase/i;

export default function (pi: ExtensionAPI) {
  pi.registerProvider("my-provider", { /* ... */ });

  pi.on("message_end", (event, ctx) => {
    const message = event.message;
    if (message.role !== "assistant") return;
    if (message.stopReason !== "error") return;
    if (
      message.provider !== "my-provider" &&
      ctx.model?.provider !== "my-provider"
    )
      return;

    const errorMessage = message.errorMessage ?? "";
    if (errorMessage.includes("context_length_exceeded")) return;
    if (!MY_PROVIDER_OVERFLOW_PATTERN.test(errorMessage)) return;

    return {
      message: {
        ...message,
        errorMessage: `context_length_exceeded: ${errorMessage}`,
      },
    };
  });
}
```

`message_end` 在 pi 出于自动上下文压缩目的跟踪该 assistant 消息之前运行，因此 pi 检查的正是改写后的 `errorMessage`。有了这个处理器，pi 将会：

1. 从 `errorMessage` 检测到溢出。
2. 把失败的 assistant 消息从活动上下文中移除。
3. 运行上下文压缩。
4. 重试一次请求。

改写时要谨慎设防：

- 把范围限定到你的 provider（`message.provider` 和 `ctx.model?.provider`），确保其他 provider 的无关错误不受影响。
- 匹配 provider 特有的模式，而不是 pi 的通用溢出模式。若改写了限流或节流错误（`rate limit`、`too many requests`），会错误地触发上下文压缩，而不是走 pi 正常的带退避重试路径。
- 当 `errorMessage` 已包含 `context_length_exceeded` 时跳过，使处理器具有幂等性。

### 注册

注册你的 stream 函数：

```typescript
pi.registerProvider("my-provider", {
  baseUrl: "https://api.example.com",
  apiKey: "$MY_API_KEY",
  api: "my-custom-api",
  models: [...],
  streamSimple: streamMyProvider
});
```

## 测试你的实现

用内置 provider 使用的同一批测试套件来测试你的 provider。从 [packages/ai/test/](https://github.com/earendil-works/pi-mono/tree/main/packages/ai/test) 复制并改编这些测试文件：

| 测试 | 目的 |
|------|------|
| `stream.test.ts` | 基础 streaming、文本输出 |
| `tokens.test.ts` | token 计数和用量 |
| `abort.test.ts` | AbortSignal 处理 |
| `empty.test.ts` | 空/极简响应 |
| `context-overflow.test.ts` | 上下文窗口限制 |
| `image-limits.test.ts` | 图片输入处理 |
| `unicode-surrogate.test.ts` | Unicode 边界情况 |
| `tool-call-without-result.test.ts` | 工具调用边界情况 |
| `image-tool-result.test.ts` | 工具结果中的图片 |
| `total-tokens.test.ts` | 总 token 计算 |
| `cross-provider-handoff.test.ts` | provider 之间的上下文交接 |

用你的 provider/模型组合运行这些测试以验证兼容性。

## 配置参考

```typescript
interface ProviderConfig {
  /** provider 在 /login 等 UI 中的显示名。 */
  name?: string;

  /** API 端点 URL。定义模型时必填。 */
  baseUrl?: string;

  /** API key 字面量、环境变量插值（$ENV_VAR 或 ${ENV_VAR}）或 !command。定义模型时必填（使用 oauth 时除外）。 */
  apiKey?: string;

  /** streaming 使用的 API 类型。定义模型时须在 provider 或模型级别指定。 */
  api?: Api;

  /** 为非标准 API 提供的自定义 streaming 实现。 */
  streamSimple?: (
    model: Model<Api>,
    context: Context,
    options?: SimpleStreamOptions
  ) => AssistantMessageEventStream;

  /** 请求中要携带的自定义 header。其值使用与 apiKey 相同的解析语法。 */
  headers?: Record<string, string>;

  /** 若为 true，添加携带已解析 API key 的 Authorization: Bearer header。 */
  authHeader?: boolean;

  /** 要注册的模型。若提供，会替换该 provider 的所有现有模型。 */
  models?: ProviderModelConfig[];

  /** 为 /login 支持提供的 OAuth provider。 */
  oauth?: {
    name: string;
    login(callbacks: OAuthLoginCallbacks): Promise<OAuthCredentials>;
    refreshToken(credentials: OAuthCredentials): Promise<OAuthCredentials>;
    getApiKey(credentials: OAuthCredentials): string;
  };
}
```

## 模型定义参考

```typescript
interface ProviderModelConfig {
  /** 模型 ID（例如 "claude-sonnet-4-20250514"）。 */
  id: string;

  /** 显示名（例如 "Claude 4 Sonnet"）。 */
  name: string;

  /** 该模型专属的 API 类型覆盖。 */
  api?: Api;

  /** 该模型专属的 API 端点 URL 覆盖。 */
  baseUrl?: string;

  /** 模型是否支持扩展 thinking。 */
  reasoning: boolean;

  /** 把 pi 的 thinking 级别映射为 provider/模型特有的值；null 表示该级别不受支持。 */
  thinkingLevelMap?: Partial<Record<"off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max", string | null>>;

  /** 支持的输入类型。 */
  input: ("text" | "image")[];

  /** 每百万 token 的费用（用于用量跟踪）。 */
  cost: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
  };

  /** 最大上下文窗口大小，单位 token。 */
  contextWindow: number;

  /** 最大输出 token 数。 */
  maxTokens: number;

  /** 该模型专属的自定义 header。 */
  headers?: Record<string, string>;

  /** 针对所选 API 的兼容性设置。 */
  compat?: {
    // openai-completions
    supportsStore?: boolean;
    supportsDeveloperRole?: boolean;
    supportsReasoningEffort?: boolean;
    supportsUsageInStreaming?: boolean;
    maxTokensField?: "max_completion_tokens" | "max_tokens";
    requiresToolResultName?: boolean;
    requiresAssistantAfterToolResult?: boolean;
    requiresThinkingAsText?: boolean;
    requiresReasoningContentOnAssistantMessages?: boolean;
    thinkingFormat?: "openai" | "openrouter" | "deepseek" | "together" | "zai" | "qwen" | "chat-template" | "qwen-chat-template" | "string-thinking" | "ant-ling";
    chatTemplateKwargs?: Record<string, string | number | boolean | null | { "$var": "thinking.enabled" | "thinking.effort"; omitWhenOff?: boolean }>;
    cacheControlFormat?: "anthropic";
    sessionAffinityFormat?: "openai" | "openai-nosession" | "openrouter";
    sendSessionAffinityHeaders?: boolean;

    // anthropic-messages
    supportsEagerToolInputStreaming?: boolean;
    supportsLongCacheRetention?: boolean;
    sendSessionAffinityHeaders?: boolean;
    supportsCacheControlOnTools?: boolean;
    forceAdaptiveThinking?: boolean;
    allowEmptySignature?: boolean;
  };
}
```

`openrouter` 发送 `reasoning: { effort }`。`deepseek` 发送 `thinking: { type: "enabled" | "disabled" }`，启用时还发送 `reasoning_effort`。`together` 发送 `reasoning: { enabled }`，当 `supportsReasoningEffort` 启用时还发送 `reasoning_effort`。`qwen` 用于 DashScope 风格的顶层 `enable_thinking`。对读取 `chat_template_kwargs.enable_thinking` 且需要 `preserve_thinking` 的本地 Qwen 兼容服务器使用 `qwen-chat-template`。`chat-template` 用于可配置的 `chat_template_kwargs`，例如 vLLM 后面的 DeepSeek V3.x 配合 `chatTemplateKwargs: { "thinking": { "$var": "thinking.enabled" } }`。
`cacheControlFormat: "anthropic"` 会把 Anthropic 风格的 `cache_control` 标记应用到系统提示词、最后一个工具定义以及最后一条 user/assistant 文本内容上。
