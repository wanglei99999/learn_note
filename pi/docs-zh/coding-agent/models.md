> **译文** | 原文：[`packages/coding-agent/docs/models.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 自定义模型

通过 `~/.pi/agent/models.json` 添加自定义 provider 和模型（Ollama、vLLM、LM Studio、代理等）。

## 目录

- [最小示例](#最小示例)
- [完整示例](#完整示例)
- [支持的 API](#支持的-api)
- [Provider 配置](#provider-配置)
- [模型配置](#模型配置)
- [覆盖内置 Provider](#覆盖内置-provider)
- [按模型覆盖](#按模型覆盖)
- [Anthropic Messages 兼容性](#anthropic-messages-兼容性)
- [OpenAI 兼容性](#openai-兼容性)

## 最小示例

对于本地模型（Ollama、LM Studio、vLLM），每个模型只需要 `id`：

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "models": [
        { "id": "llama3.1:8b" },
        { "id": "qwen2.5-coder:7b" }
      ]
    }
  }
}
```

这里的 `apiKey` 值只是占位符，因为 Ollama 会忽略它。但 pi 仍然要求模型配置了认证之后才会出现在 `/model` 中，所以对于无需密钥的本地服务，应保留一个占位值、用 `/login` 为该 provider 保存一个密钥，或在选择模型时传入 `--api-key`。

有些 OpenAI 兼容服务器不理解推理模型使用的 `developer` 角色。对于这类 provider，将 `compat.supportsDeveloperRole` 设为 `false`，pi 就会改用 `system` 消息发送系统提示词。如果服务器也不支持 `reasoning_effort`，则同时将 `compat.supportsReasoningEffort` 设为 `false`。

`compat` 可以设置在 provider 级别（对所有模型生效），也可以设置在模型级别（覆盖特定模型）。这通常适用于 Ollama、vLLM、SGLang 及类似的 OpenAI 兼容服务器。

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [
        {
          "id": "gpt-oss:20b",
          "reasoning": true
        }
      ]
    }
  }
}
```

## 完整示例

需要指定具体值时，可以覆盖默认值：

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "models": [
        {
          "id": "llama3.1:8b",
          "name": "Llama 3.1 8B (Local)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 128000,
          "maxTokens": 32000,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
```

每次打开 `/model` 时该文件都会重新加载。可以在会话进行中编辑，无需重启。

## Google AI Studio 示例

使用带 `baseUrl` 的 `google-generative-ai` 可以添加来自 Google AI Studio 的模型，包括自定义的 Gemma 4 条目：

```json
{
  "providers": {
    "my-google": {
      "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
      "api": "google-generative-ai",
      "apiKey": "$GEMINI_API_KEY",
      "models": [
        {
          "id": "gemma-4-31b-it",
          "name": "Gemma 4 31B",
          "input": ["text", "image"],
          "contextWindow": 262144,
          "reasoning": true
        }
      ]
    }
  }
}
```

向 `google-generative-ai` API 类型添加自定义模型时，`baseUrl` 是必填的。

## 支持的 API

| API | 说明 |
|-----|-------------|
| `openai-completions` | OpenAI Chat Completions（兼容性最好） |
| `openai-responses` | OpenAI Responses API |
| `anthropic-messages` | Anthropic Messages API |
| `google-generative-ai` | Google Generative AI |

`api` 可以设置在 provider 级别（作为所有模型的默认值）或模型级别（按模型覆盖）。

## Provider 配置

| 字段 | 说明 |
|-------|-------------|
| `baseUrl` | API 端点 URL |
| `api` | API 类型（见上文） |
| `apiKey` | 可选的 API key 配置（见下文的值解析规则）。当认证由 `/login`/`auth.json` 或 CLI `--api-key` 提供时可省略。 |
| `oauth` | 动态 OAuth provider 类型。目前支持 `"radius"`；需要网关的 `baseUrl`。 |
| `headers` | 自定义 header（见下文的值解析规则） |
| `authHeader` | 设为 `true` 时自动添加 `Authorization: Bearer <apiKey>` |
| `models` | 模型配置数组 |
| `modelOverrides` | 对该 provider 上内置模型或由 extension 注册模型的按模型覆盖 |

对于带 `models` 的 provider，非内置的 provider 配置需要 `baseUrl`，并在 provider 或模型级别提供 `api` 值。加载该文件并不要求 `apiKey`：只要通过 `/login`/`auth.json`、CLI `--api-key` 或 provider 的 `apiKey` 配置了认证，模型就会变为可用。如果没有配置任何认证，模型仍会被加载，但在 `/model` 和 `--list-models` 中保持不可用状态。

### 值解析

`apiKey` 和 `headers` 字段支持命令执行、环境变量插值和字面量：

- **Shell 命令：**以 `"!command"` 开头时，整个值会作为命令执行，并使用其 stdout
  ```json
  "apiKey": "!security find-generic-password -ws 'anthropic'"
  "apiKey": "!op read 'op://vault/item/credential'"
  ```
- **环境变量插值：**`"$ENV_VAR"` 或 `"${ENV_VAR}"` 使用同名变量的值。插值也可以出现在更长的字面量内部。
  ```json
  "apiKey": "$MY_API_KEY"
  "apiKey": "${KEY_PREFIX}_${KEY_SUFFIX}"
  ```
  `$FOO_BAR` 表示变量 `FOO_BAR`；当 `BAR` 是字面文本时请使用 `${FOO}_BAR`。环境变量缺失会导致该值无法解析。
- **转义：**`"$$"` 输出字面的 `"$"`；`"$!"` 输出字面的 `"!"` 且不会触发命令执行。
  ```json
  "apiKey": "$$literal-dollar-prefix"
  "apiKey": "$!literal-bang-prefix"
  ```
- **字面量：**直接使用。像 `MY_API_KEY` 这样的普通大写字符串是字面量；要引用环境变量请写 `$MY_API_KEY`。
  ```json
  "apiKey": "sk-..."
  ```

对于 `models.json`，shell 命令在发起请求时解析。pi 有意不为任意命令内置 TTL、过期值复用或故障恢复逻辑：不同的命令需要不同的缓存和失败策略，pi 无法推断哪种才是正确的。

如果你的命令很慢、开销大、有速率限制，或希望在瞬时失败时继续沿用之前的值，请把它包装到你自己的脚本或命令中，由后者实现你想要的缓存或 TTL 行为。

`/model` 的可用性检查只查看是否配置了认证，不会执行 shell 命令。

### 自定义 Header

```json
{
  "providers": {
    "custom-proxy": {
      "baseUrl": "https://proxy.example.com/v1",
      "apiKey": "$MY_API_KEY",
      "api": "anthropic-messages",
      "headers": {
        "x-portkey-api-key": "$PORTKEY_API_KEY",
        "x-secret": "!op read 'op://vault/item/secret'"
      },
      "models": [...]
    }
  }
}
```

## 模型配置

| 字段 | 必填 | 默认值 | 说明 |
|-------|----------|---------|-------------|
| `id` | 是 | — | 模型标识符（传递给 API） |
| `name` | 否 | `id` | 人类可读的模型名称。用于匹配（`--model` 模式），并作为模型的次要详情文本显示。 |
| `api` | 否 | provider 的 `api` | 为该模型覆盖 provider 的 API |
| `reasoning` | 否 | `false` | 是否支持扩展思考 |
| `thinkingLevelMap` | 否 | 省略 | 将 pi 思考等级映射到 provider 的值，并标记不支持的等级（见下文） |
| `input` | 否 | `["text"]` | 输入类型：`["text"]` 或 `["text", "image"]` |
| `contextWindow` | 否 | `128000` | 上下文窗口大小（token 数） |
| `maxTokens` | 否 | `16384` | 最大输出 token 数 |
| `cost` | 否 | 全为零 | 每百万 token 的费率，可选按整个请求生效的输入定价梯度 |
| `compat` | 否 | provider 的 `compat` | Provider 兼容性覆盖。与 provider 级别的 `compat` 同时设置时会合并。 |

一个费率梯度（tier）提供一整套替代费率，当输入总用量（`input + cacheRead + cacheWrite`）超过 `inputTokensAbove` 时应用于整个请求。多个梯度同时匹配时，阈值最高者胜出。

```json
{
  "cost": {
    "input": 5,
    "output": 30,
    "cacheRead": 0.5,
    "cacheWrite": 6.25,
    "tiers": [
      {
        "inputTokensAbove": 272000,
        "input": 10,
        "output": 45,
        "cacheRead": 1,
        "cacheWrite": 12.5
      }
    ]
  }
}
```

当前行为：
- `/model`、`--list-models` 和交互模式底栏均按模型 `id` 显示条目。
- 配置的 `name` 用于模型匹配和次要详情文本，不会取代底栏/状态栏中的模型 id。

### 思考等级映射

在模型上使用 `thinkingLevelMap` 描述该模型特有的思考控制。键是 pi 的思考等级：`off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`。映射可以留有空缺；例如，一个模型可以暴露 `high` 和 `max` 而不暴露 `xhigh`。

值是三态的：

| 值 | 含义 |
|-------|---------|
| 省略 | 到 `high` 为止的标准等级使用 provider 的默认映射；扩展等级 `xhigh` 和 `max` 不受支持 |
| 字符串 | 该等级受支持，并把此值发送给 provider |
| `null` | 该等级不受支持，会被隐藏/跳过/收敛到其他等级 |

一个只支持 off、high 和 max 推理的模型示例：

```json
{
  "id": "deepseek-v4-pro",
  "reasoning": true,
  "thinkingLevelMap": {
    "minimal": null,
    "low": null,
    "medium": null,
    "high": "high",
    "xhigh": null,
    "max": "max"
  }
}
```

一个无法关闭思考的模型示例：

```json
{
  "id": "always-thinking-model",
  "reasoning": true,
  "thinkingLevelMap": {
    "off": null
  }
}
```

迁移：曾使用 `compat.reasoningEffortMap` 的旧配置应把该映射移到模型级别的 `thinkingLevelMap`。对不应出现在 UI 中的等级使用 `null`。

## 覆盖内置 Provider

将内置 provider 路由到代理，且无需重新定义模型：

```json
{
  "providers": {
    "anthropic": {
      "baseUrl": "https://my-proxy.example.com/v1"
    }
  }
}
```

所有内置的 Anthropic 模型仍然可用。已有的 OAuth 或 API key 认证继续有效。

要把自定义模型合并进内置 provider，加入 `models` 数组：

```json
{
  "providers": {
    "anthropic": {
      "baseUrl": "https://my-proxy.example.com/v1",
      "apiKey": "$ANTHROPIC_API_KEY",
      "api": "anthropic-messages",
      "models": [...]
    }
  }
}
```

合并语义：
- 内置模型会被保留。
- 自定义模型在该 provider 内按 `id` 执行 upsert（存在则更新，不存在则插入）。
- 若自定义模型的 `id` 与某个内置模型的 `id` 相同，则自定义模型替换该内置模型。
- 若自定义模型的 `id` 是新的，则与内置模型并列添加。

## 按模型覆盖

使用 `modelOverrides` 定制内置模型以及匹配到的由 extension 注册的模型，无需替换 provider 的完整模型列表。

```json
{
  "providers": {
    "openrouter": {
      "modelOverrides": {
        "anthropic/claude-sonnet-4": {
          "name": "Claude Sonnet 4 (Bedrock Route)",
          "compat": {
            "openRouterRouting": {
              "only": ["amazon-bedrock"]
            }
          }
        }
      }
    }
  }
}
```

`modelOverrides` 对每个模型支持以下字段：`name`、`reasoning`、`thinkingLevelMap`、`input`、`cost`（部分覆盖）、`contextWindow`、`maxTokens`、`headers`、`compat`。

直连 OpenAI 的 GPT-5.6 Sol、Terra 和 Luna 默认上下文窗口为 `272000`，以使请求保持在 OpenAI 的短上下文定价档位内。要启用 OpenAI 的 1.05M 上下文窗口，请为你使用的每个模型分别调大它：

```json
{
  "providers": {
    "openai": {
      "modelOverrides": {
        "gpt-5.6-sol": {
          "contextWindow": 1050000
        }
      }
    }
  }
}
```

该覆盖会保留内置的定价元数据。输入 token 总量超过 272K 的请求，整个请求都按 GPT-5.6 的长上下文费率计费。需要时对 `gpt-5.6-terra` 或 `gpt-5.6-luna` 应用相同的覆盖。

行为说明：
- `modelOverrides` 应用于内置 provider 模型以及匹配到的由 extension 注册的 provider 模型。
- 未知的模型 ID 会被忽略。
- Provider 级别的 `baseUrl`/`headers` 可以与 `modelOverrides` 组合使用。
- 覆盖 `name` 只改变模型匹配和次要详情文本；底栏和主模型列表仍然显示模型 `id`。
- 如果该 provider 同时定义了 `models`，自定义模型会在内置覆盖之后合并。`id` 相同的自定义模型会替换被覆盖后的内置模型条目。

## Anthropic Messages 兼容性

对于使用 `api: "anthropic-messages"` 的 provider 或代理，通过 `compat` 控制 Anthropic 特有的请求兼容性。

默认情况下 pi 会为每个 tool 发送 `eager_input_streaming: true`。如果代理或 Anthropic 兼容后端拒绝该字段，将 `supportsEagerToolInputStreaming` 设为 `false`。此时 pi 会省略 `tools[].eager_input_streaming`，并在启用 tool 的请求上改为发送旧的 `fine-grained-tool-streaming-2025-05-14` beta header。

有些 Anthropic 模型要求自适应思考（`thinking.type: "adaptive"` 加 `output_config.effort`），而不是旧的基于预算的思考负载。内置模型会自动设置这一点。对于路由到这些模型的自定义 provider 或别名，将 `forceAdaptiveThinking` 设为 `true`。

有些 Anthropic 兼容 provider 会输出签名为空的思考块，并且在回放时仍然要求带上它们。只对这类 provider 将 `allowEmptySignature` 设为 `true`；真正的 Anthropic 会拒绝空的思考签名。

```json
{
  "providers": {
    "anthropic-proxy": {
      "baseUrl": "https://proxy.example.com",
      "api": "anthropic-messages",
      "apiKey": "$ANTHROPIC_PROXY_KEY",
      "compat": {
        "supportsEagerToolInputStreaming": false,
        "supportsLongCacheRetention": true,
        "forceAdaptiveThinking": true,
        "allowEmptySignature": true
      },
      "models": [
        {
          "id": "claude-opus-4-7",
          "reasoning": true,
          "input": ["text", "image"]
        }
      ]
    }
  }
}
```

| 字段 | 说明 |
|-------|-------------|
| `supportsEagerToolInputStreaming` | Provider 是否接受按 tool 的 `eager_input_streaming`。默认：`true`。设为 `false` 时省略该字段，并在启用 tool 的请求上使用旧的细粒度 tool streaming beta header。 |
| `supportsLongCacheRetention` | 当缓存保留策略为 `long` 时，provider 是否接受 Anthropic 的长缓存保留（`cache_control.ttl: "1h"`）。默认：`true`。 |
| `sendSessionAffinityHeaders` | 启用缓存时是否根据会话 id 发送 `x-session-affinity`。默认：对已知 provider 自动检测。 |
| `supportsCacheControlOnTools` | Provider 是否接受工具定义上的 Anthropic 风格 `cache_control` 标记。默认：`true`。 |
| `forceAdaptiveThinking` | 是否为该模型发送自适应思考（`thinking.type: "adaptive"` 加 `output_config.effort`）。内置的自适应模型会自动设置。默认：`false`。 |
| `allowEmptySignature` | 是否将空的思考签名以 `signature: ""` 回放，而不是把思考转换为文本。默认：`false`。 |

## OpenAI 兼容性

对于只部分兼容 OpenAI 的 provider，使用 `compat` 字段。

- Provider 级别的 `compat` 为该 provider 下所有模型提供默认值。
- 模型级别的 `compat` 为该模型覆盖 provider 级别的值。

```json
{
  "providers": {
    "local-llm": {
      "baseUrl": "http://localhost:8080/v1",
      "api": "openai-completions",
      "compat": {
        "supportsUsageInStreaming": false,
        "maxTokensField": "max_tokens"
      },
      "models": [...]
    }
  }
}
```

| 字段 | 说明 |
|-------|-------------|
| `supportsStore` | Provider 是否支持 `store` 字段 |
| `supportsDeveloperRole` | 使用 `developer` 还是 `system` 角色 |
| `supportsReasoningEffort` | 是否支持 `reasoning_effort` 参数 |
| `supportsUsageInStreaming` | 是否支持 `stream_options: { include_usage: true }`（默认：`true`） |
| `maxTokensField` | 使用 `max_completion_tokens` 还是 `max_tokens` |
| `requiresToolResultName` | 在工具结果消息上包含 `name` |
| `requiresAssistantAfterToolResult` | 在工具结果之后、用户消息之前插入一条 assistant 消息 |
| `requiresThinkingAsText` | 将思考块转换为纯文本 |
| `requiresReasoningContentOnAssistantMessages` | 启用推理时在所有回放的 assistant 消息上包含空的 `reasoning_content` |
| `thinkingFormat` | 使用 `reasoning_effort`、`openrouter`、`deepseek`、`together`、`zai`、`qwen`、`chat-template` 或 `qwen-chat-template` 思考参数 |
| `chatTemplateKwargs` | `thinkingFormat: "chat-template"` 使用的 `chat_template_kwargs` 值；用 `{ "$var": "thinking.enabled" }` 或 `{ "$var": "thinking.effort" }` 引用由 pi 控制的思考值 |
| `cacheControlFormat` | 在系统提示词、最后一个工具定义以及最后的 user/assistant 文本内容上使用 Anthropic 风格的 `cache_control` 标记。目前仅支持 `anthropic`。 |
| `sendSessionAffinityHeaders` | 对 `openai-completions`，启用缓存时根据会话 id 发送会话亲和 header。默认：`false`。 |
| `sessionAffinityFormat` | 对 `openai-completions` 和 `openai-responses`，会话亲和 header 的格式：`openai` 发送 `session_id`/`x-client-request-id`（completions 还会发送 `x-session-affinity`），`openai-nosession` 省略含下划线的 `session_id` header，`openrouter` 发送 `x-session-id`。不影响请求体参数 `prompt_cache_key`。默认：自动检测。 |
| `supportsStrictMode` | 在工具定义中包含 `strict` 字段 |
| `deferredToolsMode` | 使用 provider 特有的延迟 tool 序列化。目前仅支持 `"kimi"`，用于 Kimi 的 OpenAI 兼容 Chat Completions 格式。 |
| `supportsLongCacheRetention` | 当缓存保留策略为 `long` 时 provider 是否接受长缓存保留：OpenAI prompt caching 使用 `prompt_cache_retention: "24h"`，`cacheControlFormat` 为 `anthropic` 时使用 `cache_control.ttl: "1h"`。默认：`true`。 |
| `openRouterRouting` | OpenRouter 的 provider 路由偏好。该对象会原样放入 [OpenRouter API 请求](https://openrouter.ai/docs/guides/routing/provider-selection)的 `provider` 字段。 |
| `vercelGatewayRouting` | Vercel AI Gateway 的 provider 选择路由配置（`only`、`order`） |

`openrouter` 使用 `reasoning: { effort }`。`together` 使用 `reasoning: { enabled }`，并在启用 `supportsReasoningEffort` 时同时使用 `reasoning_effort`。`qwen` 使用顶层的 `enable_thinking`。对于要求 `chat_template_kwargs.enable_thinking` 和 `preserve_thinking` 的本地 Qwen 兼容服务器，使用 `qwen-chat-template`。对于需要可配置 `chat_template_kwargs` 的 vLLM/Hugging Face 聊天模板，使用 `chat-template`，例如为 DeepSeek V3.x 模板配置 `chatTemplateKwargs: { "thinking": { "$var": "thinking.enabled" } }`。

`cacheControlFormat: "anthropic"` 适用于那些通过文本内容和工具定义上的 `cache_control` 标记暴露 Anthropic 风格 prompt caching 的 OpenAI 兼容 provider。

示例：

```json
{
  "providers": {
    "openrouter": {
      "baseUrl": "https://openrouter.ai/api/v1",
      "apiKey": "$OPENROUTER_API_KEY",
      "api": "openai-completions",
      "models": [
        {
          "id": "openrouter/anthropic/claude-3.5-sonnet",
          "name": "OpenRouter Claude 3.5 Sonnet",
          "compat": {
            "openRouterRouting": {
              "allow_fallbacks": true,
              "require_parameters": false,
              "data_collection": "deny",
              "zdr": true,
              "enforce_distillable_text": false,
              "order": ["anthropic", "amazon-bedrock", "google-vertex"],
              "only": ["anthropic", "amazon-bedrock"],
              "ignore": ["gmicloud", "friendli"],
              "quantizations": ["fp16", "bf16"],
              "sort": {
                "by": "price",
                "partition": "model"
              },
              "max_price": {
                "prompt": 10,
                "completion": 20
              },
              "preferred_min_throughput": {
                "p50": 100,
                "p90": 50
              },
              "preferred_max_latency": {
                "p50": 1,
                "p90": 3,
                "p99": 5
              }
            }
          }
        }
      ]
    }
  }
}
```

Vercel AI Gateway 示例：

```json
{
  "providers": {
    "vercel-ai-gateway": {
      "baseUrl": "https://ai-gateway.vercel.sh/v1",
      "apiKey": "$AI_GATEWAY_API_KEY",
      "api": "openai-completions",
      "models": [
        {
          "id": "moonshotai/kimi-k2.5",
          "name": "Kimi K2.5 (Fireworks via Vercel)",
          "reasoning": true,
          "input": ["text", "image"],
          "cost": { "input": 0.6, "output": 3, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 262144,
          "maxTokens": 262144,
          "compat": {
            "vercelGatewayRouting": {
              "only": ["fireworks", "novita"],
              "order": ["fireworks", "novita"]
            }
          }
        }
      ]
    }
  }
}
```
