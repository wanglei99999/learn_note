> **译文** | 原文：[`packages/coding-agent/docs/providers.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/providers.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# Provider

Pi 支持通过 OAuth 使用基于订阅的 provider，也支持通过环境变量或认证文件使用 API key provider。pi 自带内置模型目录；已配置的 provider 可能会刷新更新的目录，并缓存到 `~/.pi/agent/models-store.json` 以供离线使用。

## 目录

- [订阅](#订阅)
- [API Key](#api-key)
- [认证文件](#认证文件)
- [云端 Provider](#云端-provider)
- [llama.cpp](#llamacpp)
- [自定义 Provider](#自定义-provider)
- [解析顺序](#解析顺序)

## 订阅

在交互模式中使用 `/login`，然后选择一个 provider：

- ChatGPT Plus/Pro（Codex）
- Claude Pro/Max
- GitHub Copilot
- xAI（Grok/X 订阅）
- Radius

使用 `/logout` 清除凭据。token 存储在 `~/.pi/agent/auth.json` 中，过期后会自动刷新。

### OpenAI Codex

- 需要 ChatGPT Plus 或 Pro 订阅
- 获得 OpenAI 官方认可：[Codex for OSS](https://developers.openai.com/community/codex-for-oss)

### Claude Pro/Max

Anthropic 订阅认证对 Claude Pro/Max 账户可用。第三方 harness 的用量计入[额外用量（extra usage）](https://claude.ai/settings/usage)，按 token 计费，不占用 Claude 套餐额度。

### GitHub Copilot

- 按 Enter 使用 github.com，或输入你的 GitHub Enterprise Server 域名
- 如果遇到 "model not supported"，请在 VS Code 中启用该模型：Copilot Chat → 模型选择器 → 选中模型 → "Enable"

### xAI（Grok/X 订阅）

- 运行 `/login xai`，然后选择 **Use a subscription**
- 通过 **Use an API key** 仍可使用 `XAI_API_KEY`

### Radius

Radius 是一个动态的 `pi-messages` 网关。`/login radius` 会把 OAuth token 存入 `auth.json`；网关模型目录独立刷新并缓存在 `models-store.json` 中。自定义 Radius 网关可以在 `models.json` 中声明，使用 `"oauth": "radius"` 加网关 `baseUrl`。

## API Key

### 环境变量或认证文件

在交互模式中使用 `/login` 并选择一个 provider，把 API key 存入 `auth.json`；或者通过环境变量设置凭据：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pi
```

| Provider | 环境变量 | `auth.json` 键名 |
|----------|----------------------|------------------|
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic` |
| Ant Ling | `ANT_LING_API_KEY` | `ant-ling` |
| Azure OpenAI Responses | `AZURE_OPENAI_API_KEY` | `azure-openai-responses` |
| OpenAI | `OPENAI_API_KEY` | `openai` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek` |
| NVIDIA NIM | `NVIDIA_API_KEY` | `nvidia` |
| Google Gemini | `GEMINI_API_KEY` | `google` |
| Amazon Bedrock | `AWS_BEARER_TOKEN_BEDROCK` | `amazon-bedrock` |
| Mistral | `MISTRAL_API_KEY` | `mistral` |
| Groq | `GROQ_API_KEY` | `groq` |
| Cerebras | `CEREBRAS_API_KEY` | `cerebras` |
| Cloudflare AI Gateway | `CLOUDFLARE_API_KEY`（+ `CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_GATEWAY_ID`） | `cloudflare-ai-gateway` |
| Cloudflare Workers AI | `CLOUDFLARE_API_KEY`（+ `CLOUDFLARE_ACCOUNT_ID`） | `cloudflare-workers-ai` |
| xAI | `XAI_API_KEY` | `xai` |
| OpenRouter | `OPENROUTER_API_KEY` | `openrouter` |
| Vercel AI Gateway | `AI_GATEWAY_API_KEY` | `vercel-ai-gateway` |
| ZAI Coding Plan（国际版） | `ZAI_API_KEY` | `zai` |
| ZAI Coding Plan（中国版） | `ZAI_CODING_CN_API_KEY` | `zai-coding-cn` |
| OpenCode Zen | `OPENCODE_API_KEY` | `opencode` |
| OpenCode Go | `OPENCODE_API_KEY` | `opencode-go` |
| Radius | `RADIUS_API_KEY` | `radius` |
| Hugging Face | `HF_TOKEN` | `huggingface` |
| Fireworks | `FIREWORKS_API_KEY` | `fireworks` |
| Together AI | `TOGETHER_API_KEY` | `together` |
| Kimi For Coding | `KIMI_API_KEY` | `kimi-coding` |
| MiniMax | `MINIMAX_API_KEY` | `minimax` |
| MiniMax（中国版） | `MINIMAX_CN_API_KEY` | `minimax-cn` |
| Xiaomi MiMo | `XIAOMI_API_KEY` | `xiaomi` |
| Xiaomi MiMo Token Plan（中国） | `XIAOMI_TOKEN_PLAN_CN_API_KEY` | `xiaomi-token-plan-cn` |
| Xiaomi MiMo Token Plan（阿姆斯特丹） | `XIAOMI_TOKEN_PLAN_AMS_API_KEY` | `xiaomi-token-plan-ams` |
| Xiaomi MiMo Token Plan（新加坡） | `XIAOMI_TOKEN_PLAN_SGP_API_KEY` | `xiaomi-token-plan-sgp` |

环境变量与 `auth.json` 键名的权威参考：[`packages/ai/src/env-api-keys.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/env-api-keys.ts) 中的 [`const envMap`](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/env-api-keys.ts)。

#### 认证文件

将凭据存储在 `~/.pi/agent/auth.json` 中：

```json
{
  "anthropic": { "type": "api_key", "key": "sk-ant-..." },
  "ant-ling": { "type": "api_key", "key": "..." },
  "openai": { "type": "api_key", "key": "sk-..." },
  "deepseek": { "type": "api_key", "key": "sk-..." },
  "nvidia": { "type": "api_key", "key": "nvapi-..." },
  "google": { "type": "api_key", "key": "..." },
  "opencode": { "type": "api_key", "key": "..." },
  "opencode-go": { "type": "api_key", "key": "..." },
  "together": { "type": "api_key", "key": "..." },
  "xiaomi": { "type": "api_key", "key": "..." },
  "xiaomi-token-plan-cn":  { "type": "api_key", "key": "..." },
  "xiaomi-token-plan-ams": { "type": "api_key", "key": "..." },
  "xiaomi-token-plan-sgp": { "type": "api_key", "key": "..." }
}
```

该文件以 `0600` 权限创建（仅用户可读写）。认证文件中的凭据优先级高于环境变量。

API key 凭据还可以包含 provider 级别的环境变量值。在解析凭据 key、provider/模型请求头以及 provider 配置（如 Cloudflare 账户 ID、Azure OpenAI 设置、Vertex 项目/区域、Bedrock 设置、`PI_CACHE_RETENTION`、`HTTP_PROXY`/`HTTPS_PROXY` 等）时，这些值会先于进程环境变量被使用。

```json
{
  "cloudflare-ai-gateway": {
    "type": "api_key",
    "key": "$CLOUDFLARE_API_KEY",
    "env": {
      "CLOUDFLARE_API_KEY": "...",
      "CLOUDFLARE_ACCOUNT_ID": "account-id",
      "CLOUDFLARE_GATEWAY_ID": "gateway-id"
    }
  }
}
```

当你希望 pi 使用与项目 shell 环境不同的 provider 设置时，可以使用这种方式。

### 密钥解析

`key` 字段支持命令执行、环境变量插值和字面量：

- **Shell 命令：** 以 `"!command"` 开头时，整个值会作为命令执行，并使用其标准输出（在进程生命周期内缓存）
  ```json
  { "type": "api_key", "key": "!security find-generic-password -ws 'anthropic'" }
  { "type": "api_key", "key": "!op read 'op://vault/item/credential'" }
  ```
- **环境变量插值：** `"$ENV_VAR"` 或 `"${ENV_VAR}"` 使用同名环境变量的值。插值也可以嵌在更大的字面量内部。
  ```json
  { "type": "api_key", "key": "$MY_ANTHROPIC_KEY" }
  { "type": "api_key", "key": "${KEY_PREFIX}_${KEY_SUFFIX}" }
  ```
  `$FOO_BAR` 表示变量 `FOO_BAR`；当 `BAR` 是字面文本时请使用 `${FOO}_BAR`。环境变量缺失会导致该值无法解析。
- **转义：** `"$$"` 输出字面 `"$"`；`"$!"` 输出字面 `"!"` 且不会触发命令执行。
  ```json
  { "type": "api_key", "key": "$$literal-dollar-prefix" }
  { "type": "api_key", "key": "$!literal-bang-prefix" }
  ```
- **字面量：** 直接使用。像 `MY_API_KEY` 这样的纯大写字符串是字面量；要引用环境变量请使用 `$MY_API_KEY`。
  ```json
  { "type": "api_key", "key": "sk-ant-..." }
  { "type": "api_key", "key": "public" }
  ```

`/login` 之后 OAuth 凭据也会存储在这里，并自动管理。

## 云端 Provider

### Azure OpenAI

```bash
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_BASE_URL=https://your-resource.ai.azure.com
# 也支持：https://your-resource.cognitiveservices.azure.com
# 也支持：https://your-resource.openai.azure.com
# 根端点会自动规范化为 /openai/v1
# 或者用资源名代替 base URL
export AZURE_OPENAI_RESOURCE_NAME=your-resource

# 可选
export AZURE_OPENAI_API_VERSION=2024-02-01
export AZURE_OPENAI_DEPLOYMENT_NAME_MAP=gpt-4=my-gpt4,gpt-4o=my-gpt4o
```

### Amazon Bedrock

使用 `/login amazon-bedrock` 存储 Bedrock API key，或配置下面任一环境级 AWS 凭据来源：

```bash
# 方式 1：AWS Profile
export AWS_PROFILE=your-profile

# 方式 2：IAM 密钥
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...

# 方式 3：Bearer Token
export AWS_BEARER_TOKEN_BEDROCK=...

# 可选的区域设置（默认 us-east-1）
export AWS_REGION=us-west-2
```

同时支持 ECS 任务角色（`AWS_CONTAINER_CREDENTIALS_*`）和 IRSA（`AWS_WEB_IDENTITY_TOKEN_FILE`）。

```bash
pi --provider amazon-bedrock --model us.anthropic.claude-sonnet-4-20250514-v1:0
```

对于模型 ID 中包含可识别模型名的 Claude 模型（基础模型和系统定义的推理配置文件），prompt 缓存会自动启用。对于应用推理配置文件（其 ARN 不包含模型名），设置 `AWS_BEDROCK_FORCE_CACHE=1` 以启用缓存点：

```bash
export AWS_BEDROCK_FORCE_CACHE=1
pi --provider amazon-bedrock --model arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/abc123
```

如果你连接的是 Bedrock API 代理，可以使用以下环境变量：

```bash
# 设置 Bedrock 代理的 URL（标准 AWS SDK 环境变量）
export AWS_ENDPOINT_URL_BEDROCK_RUNTIME=https://my.corp.proxy/bedrock

# 如果代理不需要认证则设置此项
export AWS_BEDROCK_SKIP_AUTH=1

# 如果代理只支持 HTTP/1.1 则设置此项
export AWS_BEDROCK_FORCE_HTTP1=1
```

### Cloudflare AI Gateway

`CLOUDFLARE_API_KEY` 可以通过 `/login` 设置。账户 ID 和网关 slug 可以设置为环境变量，也可以放在 `auth.json` 中 API key 凭据的 `env` 对象里。

```bash
export CLOUDFLARE_API_KEY=...           # 或使用 /login
export CLOUDFLARE_ACCOUNT_ID=...
export CLOUDFLARE_GATEWAY_ID=...        # 在 dash.cloudflare.com → AI → AI Gateway 创建
pi --provider cloudflare-ai-gateway --model "claude-sonnet-4-5"
```

通过 Cloudflare AI Gateway 路由到 OpenAI、Anthropic 和 Workers AI。Workers AI 使用 Unified API（`/compat`）和带前缀的模型 ID（`workers-ai/@cf/...`）。OpenAI 使用 OpenAI 直通路由（`/openai`）及原生 OpenAI 模型 ID（如 `gpt-5.1`）。Anthropic 使用 Anthropic 直通路由（`/anthropic`）及原生 Anthropic 模型 ID（如 `claude-sonnet-4-5`）。

AI Gateway 的认证使用 `CLOUDFLARE_API_KEY` 作为 `cf-aig-authorization`。上游认证可以是以下之一：

| 模式 | 请求认证 | 上游认证 |
|------|--------------|---------------|
| Workers AI | 仅 Cloudflare token | Cloudflare 原生 |
| 统一计费（Unified billing） | 仅 Cloudflare token | Cloudflare 处理上游认证并扣除额度 |
| 托管 BYOK（Stored BYOK） | 仅 Cloudflare token | Cloudflare 注入存储在 AI Gateway 控制台中的 provider 密钥 |
| 内联 BYOK（Inline BYOK） | Cloudflare token 加上游 `Authorization` 请求头 | 由请求提供上游 provider 密钥 |

对于常规的 pi 使用，建议采用统一计费或托管 BYOK。内联 BYOK 需要为 Cloudflare AI Gateway provider 配置额外的上游 `Authorization` 请求头，例如通过 `models.json` 的 provider/模型覆盖配置。

### Cloudflare Workers AI

`CLOUDFLARE_API_KEY` 可以通过 `/login` 设置。`CLOUDFLARE_ACCOUNT_ID` 可以设置为环境变量，也可以放在 `auth.json` 中 API key 凭据的 `env` 对象里。

```bash
export CLOUDFLARE_API_KEY=...           # 或使用 /login
export CLOUDFLARE_ACCOUNT_ID=...
pi --provider cloudflare-workers-ai --model "@cf/moonshotai/kimi-k2.6"
```

Pi 会自动设置 `x-session-affinity`，以获得[前缀缓存](https://developers.cloudflare.com/workers-ai/features/prompt-caching/)折扣。

### Google Vertex AI

使用应用默认凭据（Application Default Credentials）：

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project
export GOOGLE_CLOUD_LOCATION=us-central1
```

或者将 `GOOGLE_APPLICATION_CREDENTIALS` 设置为服务账号密钥文件。

## llama.cpp

Pi 支持 llama.cpp 路由服务器。使用 `/login llama.cpp` 进行配置，用 `/llama` 管理已加载的模型，用 `/model` 选择已加载的模型。

服务器搭建、模型目录结构、环境变量与命令用法参见 [llama.cpp](llama-cpp.md)。

## 自定义 Provider

**通过 models.json：** 添加 Ollama、LM Studio、vLLM，或任何使用受支持 API 的 provider（OpenAI Completions、OpenAI Responses、Anthropic Messages、Google Generative AI）。参见 [models.md](models.md)。

**通过 extension：** 对于需要自定义 API 实现或 OAuth 流程的 provider，可以创建 extension。参见 [custom-provider.md](custom-provider.md) 和 [examples/extensions/custom-provider-gitlab-duo](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/custom-provider-gitlab-duo/)。

## 解析顺序

为 provider 解析凭据时的顺序：

1. CLI `--api-key` 标志
2. `auth.json` 条目（API key 或 OAuth token）
3. 环境变量
4. `models.json` 中的自定义 provider 密钥
