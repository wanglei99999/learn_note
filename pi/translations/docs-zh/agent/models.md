> **译文** | 原文：[`packages/agent/docs/models.md`](https://github.com/earendil-works/pi/blob/main/packages/agent/docs/models.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 模型架构

本文档描述下一轮 `pi-ai` 模型/provider 重构的目标设计。它描述的是期望达到的形态，而非当前实现。其内容力求完整，足以让人从一个全新会话直接开始实现。

目标：

- `Models` 是一个「傻瓜式」的 provider 运行时集合。
- 具体 provider 拥有元数据、认证（auth）、模型列表和 stream 行为。
- API 实现放在 `src/api/` 下，可复用、可懒加载。
- 具体 provider 工厂放在 `src/providers/` 下。
- 用户可以只导入自己需要的 provider。
- 导入一个 provider 不得急切（eagerly）导入重型 SDK。
- 动态模型列表是一等公民：读取是同步的（返回最近一次已知列表），拉取则通过显式的异步 `refresh` 进行。
- `models.json` 与 extension 通过包装（wrap）provider 来分层，而不是随意改动 provider 内部。
- 旧的全局 API 只在一个显式、临时的 `/compat` 入口中保留。

本轮 `pi-ai` 改造暂不包括：

- 暂不迁移 coding-agent 的 `ModelRegistry`。
- 不在 `Models` 内部保留 stream/API 注册表。
- 暂不实现 Web OAuth 流程。
- 图像生成镜像聊天侧的设计（`images-models.ts` 中的 `ImagesModels`/`ImagesProvider`）；旧的全局图像 API（`images.ts`、`images-api-registry.ts`）继续留在 compat 中。

## 包布局

目标源码布局：

```txt
packages/ai/src/
  index.ts                    # 仅核心导出；不导入任何内置 provider
  models.ts                   # Models 运行时、Provider
  images-models.ts            # ImagesModels 运行时、ImagesProvider（镜像 models.ts）
  compat.ts                   # 临时的旧 API 兼容入口
  auth/                       # 认证方式类型、辅助函数、共享的 resolveProviderAuth()、登录回调
  api/                        # API 实现及懒加载包装器
    openai-completions.ts     # 真实实现，导入 SDK，导出 stream/streamSimple
    openai-completions.lazy.ts
    openai-responses.ts
    openai-responses.lazy.ts
    openai-codex-responses.ts
    openai-codex-responses.lazy.ts
    azure-openai-responses.ts
    azure-openai-responses.lazy.ts
    anthropic-messages.ts
    anthropic-messages.lazy.ts
    google-generative-ai.ts
    google-generative-ai.lazy.ts
    google-vertex.ts
    google-vertex.lazy.ts
    mistral-conversations.ts
    mistral-conversations.lazy.ts
    bedrock-converse-stream.ts
    bedrock-converse-stream.lazy.ts
    openrouter-images.ts      # 图像生成 API 实现
    openrouter-images.lazy.ts
    lazy.ts                   # lazyStream()/lazyApi() 辅助函数
    (共享辅助模块：openai-responses-shared、google-shared、transform-messages 等)
  providers/                  # 具体 provider 工厂及各 provider 的模型目录
    openai.ts
    openai.models.ts          # 生成的 OpenAI 目录
    openai-codex.ts
    openai-codex.models.ts
    anthropic.ts
    anthropic.models.ts
    google.ts
    google.models.ts
    ...每个内置 provider 一对文件...
    openrouter-images.ts      # 图像生成 provider 工厂
    faux.ts                   # 测试用 provider 工厂
    all.ts                    # 显式聚合入口：builtinModels()、builtinImagesModels()、getBuiltin*()
  auth/oauth/                 # 规范 OAuth 实现（node），懒加载
```

`src/index.ts` 必须保持仅含核心内容。它不得导入：

- 生成的模型目录
- 内置 provider 工厂
- provider SDK 实现
- 仅限 Node 的 OAuth 模块
- `providers/all`
- `compat`

Provider、API 与 compat 入口都是显式的子路径导出（subpath exports）。

## 公开用法

最小化的 provider 用法：

```ts
import { createModels } from "@earendil-works/pi-ai";
import { openaiProvider } from "@earendil-works/pi-ai/providers/openai";

const models = createModels();
models.setProvider(openaiProvider());

const model = models.getModel("openai", "gpt-4o-mini");
if (!model) throw new Error("model not found");

const response = await models.complete(model, context);
```

多个 provider：

```ts
const models = createModels();
models.setProvider(openaiProvider());
models.setProvider(openrouterProvider());
```

全部内置 provider，通过显式的重型元数据入口：

```ts
import { builtinModels } from "@earendil-works/pi-ai/providers/all";

const models = builtinModels();
```

`providers/all` 可以导入所有 provider 的元数据/目录。但它仍不得急切导入 SDK 实现；provider 的 stream 使用懒加载包装器。

## 核心运行时：Models

`Models` 就是一个 provider 集合，外加认证应用与 stream 便捷方法。没有 stream 注册表，也没有认证解析策略对象。

```ts
export function createModels(options?: {
  /** 由应用持有的凭据存储。默认：内存存储。 */
  credentials?: CredentialStore;
  /** 认证解析所需的环境访问（环境变量、文件存在性）。默认：基于 process.env/node:fs；可注入以支持测试和非 Node 宿主。 */
  authContext?: AuthContext;
}): MutableModels;

export interface Models {
  getProviders(): readonly Provider[];
  getProvider(id: string): Provider | undefined;

  /** 同步读取最近一次已知的模型。尽力而为（best-effort）：某个 provider 的 getModels() 抛错时，该 provider 不产出任何模型。 */
  getModels(provider?: string): readonly Model<Api>[];
  /** 动态列表如实返回 Model<Api>；用 hasApi() 守卫来收窄类型。 */
  getModel(provider: string, id: string): Model<Api> | undefined;

  /**
   * 让动态 provider 重新拉取模型列表。指定 provider id 时，
   * 该 provider 失败会 reject；不指定时，并发刷新全部 provider，
   * 尽力而为。静态 provider 是 no-op。
   */
  refresh(provider?: string): Promise<void>;

  /**
   * 为某个模型解析请求认证。包含来源标签供状态 UI 使用。
   * provider 未知或未配置时 resolve 为 undefined。失败时以
   * ModelsError reject（refresh 失败为 "oauth"，api-key/存储
   * 失败为 "auth"）；状态/可用性 UI 应捕获 rejection 并渲染
   * 「需要重新登录」，而不是当作未配置处理。
   */
  getAuth(model: Model<Api>): Promise<AuthResult | undefined>;

  stream<TApi extends Api>(
    model: Model<TApi>,
    context: Context,
    options?: ApiStreamOptions<TApi>,
  ): AssistantMessageEventStream;

  complete<TApi extends Api>(
    model: Model<TApi>,
    context: Context,
    options?: ApiStreamOptions<TApi>,
  ): Promise<AssistantMessage>;

  streamSimple(model: Model<Api>, context: Context, options?: SimpleStreamOptions): AssistantMessageEventStream;
  completeSimple(model: Model<Api>, context: Context, options?: SimpleStreamOptions): Promise<AssistantMessage>;
}

export interface MutableModels extends Models {
  /** 按 provider.id upsert/替换。provider id 唯一。 */
  setProvider(provider: Provider): void;
  deleteProvider(id: string): void;
  clearProviders(): void;
}
```

被移除的概念：

```txt
不再有 Models.setStreamFunctions() / getStreamFunctions()
不再有作为真实分发机制的 api-registry
不再有 Models.provider(id) 构建器，不再有 setModel/upsertModel/patchModel 生命周期
不再有 ModelAuthResolver / setAuthResolver —— 解析策略是固定的，存储通过注入提供
```

如果应用需要不同的认证策略，就去包装 provider（包装其认证方式或 `getModels`），或在 stream options 中传入显式的请求认证。

## Provider

Provider 是具体的运行时单元。它拥有 id/名称/基础元数据、认证方式、模型列表和 stream 行为。

`Provider` 以其模型所用的 API 为泛型参数。具体工厂声明自己产出什么（`openaiProvider(): Provider<"openai-responses" | "openai-completions">`），从而为直接使用工厂的用户提供带类型的模型列表。`Models` 集合以 `Provider<Api>` 的形式持有 provider。

```ts
export interface Provider<TApi extends Api = Api> {
  readonly id: string;
  readonly name: string;

  readonly baseUrl?: string;
  readonly headers?: Record<string, string>;

  /**
   * 必填：apiKey/oauth 至少提供其一。即便是环境凭据（ambient credential）
   * provider（环境变量、AWS profile、ADC）和无需密钥的本地服务器，也要提供
   * apiKey 认证，由其 resolve() 报告 provider 是否已配置。
   * getAuth() 返回 undefined = 未配置。
   */
  readonly auth: ProviderAuth;

  /** 当前已知模型，同步返回。静态 provider：完整目录。动态 provider：最近一次 refresh 时的列表（首次 refresh 前为空）。 */
  getModels(): readonly Model<TApi>[];

  /** 仅动态 provider：拉取并更新模型列表。并发调用共享同一个进行中的拉取。 */
  refreshModels?(): Promise<void>;

  stream<T extends TApi>(model: Model<T>, context: Context, options?: ApiStreamOptions<T>): AssistantMessageEventStream;

  streamSimple(model: Model<TApi>, context: Context, options?: SimpleStreamOptions): AssistantMessageEventStream;
}
```

不存在 `Provider.api` 字段。`model.api` 承载 API 身份；provider 在内部完成分发（见 `createProvider()`）。

`Model.api` 保留：现有元数据和测试都在用它，它对诊断也有用，provider 构建时还用它来选择 API 实现。但 `Models` 从不基于它做分发；分发由 provider 完成。

### 带类型的 stream options

完整的 stream options 是按 API 区分的。`Model<TApi>` 的价值就在于能从 API 推导出对应的 options 类型：

```ts
// types.ts —— 从 API 实现模块做仅类型导入（type-only import）会被擦除，因此对 tree-shaking 安全
export interface ApiOptionsMap {
  "anthropic-messages": AnthropicOptions;
  "openai-completions": OpenAICompletionsOptions;
  "openai-responses": OpenAIResponsesOptions;
  "openai-codex-responses": OpenAICodexResponsesOptions;
  "azure-openai-responses": AzureOpenAIResponsesOptions;
  "google-generative-ai": GoogleOptions;
  "google-vertex": GoogleVertexOptions;
  "mistral-conversations": MistralOptions;
  "bedrock-converse-stream": BedrockOptions;
}

export type ApiStreamOptions<TApi extends Api> = TApi extends keyof ApiOptionsMap
  ? ApiOptionsMap[TApi]
  : StreamOptions & Record<string, unknown>;
```

自定义 api 字符串回退到通用形态。

### 带类型的模型收窄

运行时的模型列表是动态的，因此 `models.getModel()`/`getModels()` 如实返回 `Model<Api>`。类型在三处得到增强：

1. **`hasApi()` 类型守卫** —— 为动态查询提供带运行时检查的类型收窄（不做盲目断言）：

   ```ts
   export function hasApi<TApi extends Api>(model: Model<Api>, api: TApi): model is Model<TApi>;

   const model = models.getModel("anthropic", "claude-opus-4-7");
   if (model && hasApi(model, "anthropic-messages")) {
     // model: Model<"anthropic-messages">，stream options 类型完全确定
   }
   ```

2. **`getBuiltinModel()`** —— 同步的、基于生成目录的查询，带类型化重载：`(provider, id) -> Model<确切的 api 字面量>`。这是硬编码已知模型的路径。

3. **`Provider<TApi>` 工厂** —— 不经 `Models` 集合、直接使用 provider 时，可获得带类型的模型列表。

有意不做的事：让 `models.getModel(provider, ...)` 绑定到带类型的 provider/模型 id，将要求静态地知道一个可变运行时集合里装了哪些 provider。harness 路径（`streamSimple` + `SimpleStreamOptions`）与 API 无关，不受影响。

作为对比：Vercel AI SDK 把实现挂在模型对象上，这消解了分发的类型问题，却让模型不可序列化（session/RPC/目录都无法作为纯数据存在），而且其 `providerOptions` 是一个只靠 `satisfies` 约定检查的 `Record<string, JSON>` 大杂烩。纯数据模型 + provider 持有行为的方案，在真正重要的地方保留了更强的类型。

### 命名冲突

`types.ts` 目前导出 `type Provider = KnownProvider | string`（一个 provider id）。把该别名重命名为 `ProviderId` 并修复调用点。上面的 `Provider` 接口接管这个名字。

## Provider 模型列表

读取是同步的；拉取是一个显式的异步动作。`Provider.getModels()` 返回当前已知列表 —— 静态 provider 返回完整目录，动态 provider（llama.cpp、OpenRouter 实时列表）返回最近一次刷新后的列表。`refreshModels()` 是动态 provider 拉取数据的地方。

之所以这样拆分：同步或异步的联合类型（`Promise<T> | T`）会招致潜伏的同步假设，在遇到第一个异步 provider 时爆炸；而纯异步读取会迫使所有消费者（UI 列表、extension 的 `find`/`getAll` 接口）为几乎总是静态的数据走 Promise。同步读取 + 显式刷新让「数据可能过期」这一点保持可见，契约也保持单一：`getModels()` = 最近已知，`refresh()` = 使之最新。反正拉取到的列表在返回那一刻就已经过期了；把刷新点显式命名出来，是对此的诚实表达。

刷新的生命周期由应用负责：启动时、注册表重载时、打开模型选择器时。对新鲜度敏感的查询走两步：`await models.refresh("llamacpp"); models.getModel("llamacpp", id)`。

动态刷新必须是无副作用的发现（discovery）：

```txt
可以：请求 /v1/models、枚举本地目录、刷新缓存的远端模型列表
不可以：加载模型、下载模型、修改服务器状态、发送请求探测
```

provider 特有的模型生命周期操作（加载/卸载）属于应用/provider 管理命令，不属于 `refreshModels()`。

## Streaming 路径

`Models.stream()` 按 `model.provider` 找到 provider，解析认证，将其合并进请求 options，然后委托出去：

```ts
function stream(model, context, options) {
  const provider = this.getProvider(model.provider);
  if (!provider) {
    // 产出一个错误 stream，而不是 throw —— 见「错误行为」
  }

  // 异步准备工作发生在返回的 stream 内部（lazyStream 模式）
  const resolution = await this.getAuth(model);
  const requestModel = resolution?.auth.baseUrl ? { ...model, baseUrl: resolution.auth.baseUrl } : model;
  const requestOptions = mergeAuth(options, resolution?.auth); // 显式 options 逐字段优先

  return provider.stream(requestModel, context, requestOptions);
}
```

`stream()` 同步返回 `AssistantMessageEventStream`；异步准备工作（认证解析、懒加载模块）发生在返回的 stream 内部。这个转发模式在今天的 `register-builtins.ts` 里已经存在（`createLazyStream`）；把它提取为 `src/api/lazy.ts` 中的 `lazyStream()`。

请求热路径上不做模型规范化（canonicalization）：`stream()` 原样使用传入的模型对象。如果应用想要最新的模型元数据，就在开始轮次前刷新 provider 并重新读取（`await models.refresh(p); models.getModel(p, id)`）。

## `src/api` 下的 API 实现

API 实现是可复用的 stream 行为。它不是 provider。

统一的导出契约 —— 每个真实实现模块恰好导出：

```ts
// src/api/anthropic-messages.ts —— 导入 SDK
export function stream(model, context, options) { ... }
export function streamSimple(model, context, options) { ... }
```

这使模块本身就满足 `ProviderStreams`，于是懒加载包装器就是一个通用辅助函数，而不必为每个 API 定制管道。`ProviderStreams` 是无类型参数的分发形态（实现模块导出的是具体类型的函数，无法赋值给泛型方法）；按 API 的 options 类型化留在模块自身，以及通过 `ApiStreamOptions` 留在 `Provider.stream()` 上：

```ts
export interface ProviderStreams {
  stream(model: Model<Api>, context: Context, options?: StreamOptions): AssistantMessageEventStream;
  streamSimple(model: Model<Api>, context: Context, options?: SimpleStreamOptions): AssistantMessageEventStream;
}

// src/api/lazy.ts
export function lazyApi(load: () => Promise<ProviderStreams>): ProviderStreams;

// src/api/anthropic-messages.lazy.ts
export const anthropicMessagesApi = (): ProviderStreams => lazyApi(() => import("./anthropic-messages.ts"));
```

导入链：

```txt
provider 模块 -> 懒加载 API 包装器 -> 动态 import(真实 API 实现) -> SDK 依赖
```

说明：

- Bedrock 在其懒加载包装器内保留仅限 Node 的动态导入技巧（`importNodeOnlyProvider`、`.ts`/`.js` 说明符重写）。`setBedrockProviderModule()`（Bun 构建使用）移入 bedrock 的懒加载包装器模块。
- 共享辅助模块（`openai-responses-shared.ts`、`google-shared.ts`、`transform-messages.ts`、prompt-cache、copilot headers）随实现一起移入 `src/api/`。

## 多个具体 provider 共享 API 实现

许多具体 provider 共享同一个 API 实现（OpenAI-completions：OpenRouter、Groq、Cerebras、xAI、ZAI……）。它们通过引用共享懒加载 API 对象：

```ts
import { openAICompletionsApi } from "../api/openai-completions.lazy.ts";

export function openrouterProvider(): Provider {
  return createProvider({
    id: "openrouter",
    name: "OpenRouter",
    baseUrl: "https://openrouter.ai/api/v1",
    auth: { apiKey: envApiKeyAuth("OpenRouter API key", ["OPENROUTER_API_KEY"]) },
    models: OPENROUTER_MODELS,
    api: openAICompletionsApi(),
  });
}
```

这借鉴了 Vercel AI SDK 的一个有用特性：用户导入具体 provider；共享的协议实现是内部细节。

## 认证（Auth）

请求认证的输出保持精简：

```ts
export interface ModelAuth {
  apiKey?: string;
  headers?: Record<string, string>;
  baseUrl?: string;
}
```

如果某个值无法表达为 `apiKey`、`headers` 或 `baseUrl`，那它就是 provider 配置而不是认证（Vertex 的 project/location、Bedrock 的 region/profile、Azure 的 apiVersion 都是 provider 工厂选项）。

### Provider 认证

`Provider.auth` 恰好有两个槽位；真实 provider 至多有一条 api-key 路径和一条 OAuth 路径，槽位名本身就承载了 UI 的「OAuth vs API key」之分，无需 `kind` 判别字段或方法 id：

```ts
export interface ProviderAuth {
  apiKey?: ApiKeyAuth; // 存储的 key/provider 环境配置 + 环境变量/文件/ADC/IAM 等环境凭据
  oauth?: OAuthAuth;   // 登录流程 + 刷新
}

export interface ApiKeyAuth {
  name: string; // "Anthropic API key"

  /** 交互式设置（提示输入 key/provider 环境配置）。缺省 = 仅环境凭据（env、ADC、IAM）。 */
  login?(interaction: AuthInteraction): Promise<ApiKeyCredential>;

  /**
   * 从存储的凭据和/或环境来源解析认证，逐字段合并
   * （credential.key ?? env("...")、credential.env?.NAME ?? env("...")）。
   * undefined = 未配置。
   */
  resolve(input: {
    model: Model<Api>;
    ctx: AuthContext;
    credential?: ApiKeyCredential;
  }): Promise<AuthResult | undefined>;
}

export interface OAuthAuth {
  name: string; // "Anthropic (Claude Pro/Max)"

  login(interaction: AuthInteraction): Promise<OAuthCredential>;

  /** 用 refresh token 换取新凭据。网络调用；失败时抛出（invalid_grant 等）。在存储锁之下运行。 */
  refresh(credential: OAuthCredential): Promise<OAuthCredential>;

  /** 从有效凭据无副作用地推导请求认证。覆盖 Copilot 式的按凭据 baseUrl。之所以是异步，是为了让懒加载包装器能加载实现。 */
  toAuth(credential: OAuthCredential): Promise<ModelAuth>;
}

export interface AuthResult {
  auth: ModelAuth;
  /** 供状态 UI 使用的人类可读标签："ANTHROPIC_API_KEY"、"OAuth"、"~/.aws/credentials"。 */
  source?: string;
}

export interface AuthContext {
  env(name: string): Promise<string | undefined>;
  fileExists(path: string): Promise<boolean>; // 支持开头的 ~
}
```

`refresh`/`toAuth` 的拆分让 `Models` 无需闭包体操就能持有带锁的刷新模式：refresh 产出凭据，而 `toAuth` 从最终存储下来的任何凭据推导请求认证。

OAuth 实现直接使用与 provider 无关的 `AuthInteraction` 协议。回调服务器式的流程会发起一个与服务器竞速的 `manual_code` 提示，并在回调抢先完成时中止该提示，因此 UI 不需要任何 provider 特定的回调或静态的回调服务器标志。

### 凭据（Credentials）

每个 provider 一份凭据，带类型标签 —— 与今天 auth.json 的形态完全一致（每个 provider id 对应 `type: "api_key" | "oauth"`）：

```ts
export interface ApiKeyCredential {
  type: "api_key";
  key?: string;
  env?: ProviderEnv; // 例如 Cloudflare 的 account/gateway id、Azure/Vertex/Bedrock 的限定配置
}

export interface OAuthCredential extends OAuthCredentials {
  type: "oauth"; // access、refresh、expires 来自 OAuthCredentials
}

export type Credential = ApiKeyCredential | OAuthCredential;
```

`ApiKeyCredential.env` 存放 provider 范围内的环境/配置值，可与 key 并存或取代 key。`ApiKeyAuth.resolve()` 逐字段合并：`credential.key ?? env("CLOUDFLARE_API_KEY")`、`credential.env?.CLOUDFLARE_ACCOUNT_ID ?? env("CLOUDFLARE_ACCOUNT_ID")` 等等。凭据判别字段刻意与今天的 `auth.json`（`api_key`）保持一致，这样基于文件的存储就不需要有损的类型转换。

### 凭据存储

存储由应用注入；`pi-ai` 自带一个内存默认实现。按 provider id 作为键，每个 provider 一份凭据：

```ts
export interface CredentialStore {
  /** 读取存储的凭据，可能已过期。用于展示/状态；请求认证走 Models.getAuth()。 */
  read(providerId: string): Promise<Credential | undefined>;

  /**
   * 串行化的写入 —— 唯一的写路径。fn 能看到当前凭据，
   * 因为正确的写入（刷新、刷新期间登录）依赖于它；
   * 返回新凭据，或返回 undefined 表示保持该条目不变。
   * 按 provider id 互斥，在底层存储支持时也跨进程互斥
   * （文件锁）。以写入后的凭据 resolve。
   */
  modify(
    providerId: string,
    fn: (current: Credential | undefined) => Promise<Credential | undefined>,
  ): Promise<Credential | undefined>;

  /** 删除（登出）。与 modify 串行化。 */
  delete(providerId: string): Promise<void>;
}
```

刻意不提供 `set`：未串行化的写路径会招致读-改-写竞态（刷新期间的登录覆盖掉新鲜凭据、token 重复刷新）。调用点：

```ts
await store.modify(pid, async () => credential);      // 登录：存这份凭据
await store.read(pid);                                // 状态 UI（「已通过 OAuth 登录」）
await store.delete(pid);                               // 登出
// 刷新的读-改-写发生在 Models.getAuth 内部
```

错误语义：条目缺失时 `read` resolve 为 `undefined`；各方法仅在存储故障时 reject，且 `Models` 会把这类 rejection 包装为 code 为 `"auth"` 的 `ModelsError`。提供内存视图、内部记录持久化错误的尽力而为存储（今天 AuthStorage 的行为）也是合法实现。

### 解析策略（固定）

`Models.getAuth(model)` 是一棵决策树，不是循环。存储的凭据独占该 provider —— 只有在什么都没存时才咨询环境/env（与 AuthStorage 对齐：刷新失败后或凭据类型不匹配时，不做静默的 env 回退）：

```ts
const stored = await store.read(provider.id);
if (stored) {
  if (stored.type === "oauth" && provider.auth.oauth) {
    const oauth = provider.auth.oauth;
    let credential = stored;
    if (Date.now() >= credential.expires) {                 // 乐观检查，无锁
      const post = await store.modify(provider.id, async (current) => {
        if (current?.type !== "oauth") return undefined;    // 期间已登出
        return Date.now() >= current.expires                // 权威检查，持锁进行
          ? oauth.refresh(current)                          // 抛错 -> ModelsError("oauth")
          : undefined;                                      // 另一个进程/请求已刷新
      });
      if (post?.type !== "oauth") return undefined;
      credential = post;
    }
    return { auth: await oauth.toAuth(credential), source: "OAuth" };
  }
  if (stored.type === "api_key" && provider.auth.apiKey) {
    return provider.auth.apiKey.resolve({ model, ctx, credential: stored });
  }
  return undefined; // 存储的凭据没有匹配的处理器时，阻断环境回退
}
return provider.auth.apiKey?.resolve({ model, ctx, credential: undefined }); // 环境凭据
```

性质：

- 双重检查锁定，与今天的 `refreshOAuthTokenWithLock` 相同：有效 token 只花一次 `read`、零次加锁；过期 token 加锁、锁内复查、全局只刷新一次、释放前持久化。
- 显式请求认证（stream options 的 `apiKey`/`headers`）在 `stream()` 中逐字段合并在最上层，优先于一切。
- 刷新失败以 `ModelsError("oauth")` reject；存储的凭据保持原样（保留以便重试）。请求路径把它作为携带真实原因的 stream 错误暴露出来（「请运行 /login」）；状态/可用性 UI 捕获该 rejection 并渲染「需要重新登录」—— 这是 `getAuth` 上写明的契约。

### 取代 AuthStorage

coding-agent 的最终形态：删除 AuthStorage；它的能力映射到一个 `CredentialStore` 实现加上组合。

今天 `getApiKey` 的优先级及其新去处：

| 今天的 AuthStorage | 新设计 |
|---|---|
| 运行时覆盖（CLI `--api-key`） | `withRuntimeOverrides(store, overrides)` 装饰器：`read` 把覆盖值作为 `ApiKeyCredential` 返回；从不持久化 |
| 存储的 `api_key`（经 `resolveConfigValue` 支持 `$ENV`/`!command`） | 存储的 `ApiKeyCredential`；配置值解析在 coding-agent 的适配器/装饰器 `read` 时进行（命令执行仍是应用策略） |
| 存储的 `oauth` + 带锁刷新，失败返回 undefined | 上面的 `getAuth` 决策树；失败时携带原因 reject，而不是静默变成未配置 |
| 环境变量（仅在什么都没存时） | `apiKey.resolve` 的环境凭据分支 |
| `fallbackResolver`（models.json 自定义 provider） | 移除 —— 自定义 provider 自带 `auth.apiKey` |

```txt
FileCredentialStore        移植 AuthStorage 的锁后端：read = 内存快照，
                           modify = withLockAsync(重读, fn, 合并写入)，delete，
                           内部错误记录（相当于 drainErrors）
└─ withConfigValues        read 时解析 $ENV / !command
   └─ withRuntimeOverrides --api-key
      └─ createModels({ credentials: store })

登录/登出 UI               provider.auth.{oauth,apiKey}.login(interaction) + store.modify/delete
状态 UI                    store.read(pid) + getAuth try/catch（rejection 时显示「需要 /login」）
getOAuthProviders          看已注册 provider 中哪些有 provider.auth.oauth
```

### 登录回调

一个接口同时服务于 api-key 登录和 OAuth 登录：

```ts
export interface AuthInteraction {
  /** 中止整个登录流程。单个提示的取消用 AuthPrompt.signal。 */
  signal?: AbortSignal;

  prompt(prompt: AuthPrompt): Promise<string>;
  notify(event: AuthEvent): void;
}

/** `signal` 让流程在带外（out-of-band）事件解决了当前步骤时取消挂起的提示。 */
export type AuthPrompt = { signal?: AbortSignal } & (
  | { type: "text"; message: string; placeholder?: string }
  | { type: "secret"; message: string; placeholder?: string }
  | { type: "select"; message: string; options: readonly { id: string; label: string; description?: string }[] }
  | { type: "manual_code"; message: string; placeholder?: string }
);

export type AuthEvent =
  | { type: "auth_url"; url: string; instructions?: string }
  | { type: "device_code"; userCode: string; verificationUri: string; intervalSeconds?: number; expiresInSeconds?: number }
  | { type: "progress"; message: string };
```

`prompt()` 返回输入/选中的字符串（`select` 返回选项 id）。流程通过设置 `AuthPrompt.signal` 让 `manual_code` 提示与回调服务器竞速，回调抢先时中止提示。

### OAuth 挂载

支持 OAuth 的 provider 总是挂上 OAuth。没有工厂开关：流程是懒加载的，因此在 `login()`/`refresh()` 真正运行之前，声明支持 OAuth 没有任何开销；从不登录的宿主也永远不会加载它。

```ts
export function anthropicProvider(): Provider {
  return createProvider({
    id: "anthropic",
    name: "Anthropic",
    baseUrl: "https://api.anthropic.com/v1",
    auth: {
      apiKey: envApiKeyAuth("Anthropic API key", ["ANTHROPIC_API_KEY"]),
      oauth: lazyOAuth({
        name: "Anthropic (Claude Pro/Max)",
        load: () => import("../auth/oauth/anthropic.ts").then((m) => m.anthropicOAuth),
      }),
    },
    models: ANTHROPIC_MODELS,
    api: anthropicMessagesApi(),
  });
}
```

`lazyOAuth()` 包装一个动态导入的 `OAuthAuth`，让 provider 定义无需导入实现即可声明支持 OAuth（`toAuth` 是异步的，正是出于这个原因）：

```ts
export function lazyOAuth(input: {
  name: string;
  load: () => Promise<OAuthAuth>;
}): OAuthAuth;
```

OAuth 不得把仅限 Node 的代码（`node:http`、`node:crypto`）带进浏览器打包产物：`lazyOAuth()` 内部的动态导入使用与 bedrock 懒加载包装器相同的「打包器不可见的变量说明符」技巧。浏览器宿主永远不会触发这次加载（没有存储的 node OAuth 凭据、没有登录流程）。如果以后落地 Web OAuth（sitegeist 已验证可行性：Web Crypto PKCE、认证标签页、fetch 换取 token、device-code 轮询），它只是另一个 `OAuthAuth` 实现 —— 无需预留任何选项值。

`src/auth/oauth/` 中的内置流程直接实现 `OAuthAuth` 与 `AuthInteraction`，同时保持面向 Node、懒加载。Copilot 通过 `toAuth().baseUrl` 推导出与凭据绑定的请求端点。

## Provider 包装器与 models.json

`models.json` 是一个 provider 包装层。它不原地修改 provider：

```ts
function withProviderOverrides(base: Provider, overrides: ProviderOverrides): Provider {
  return {
    ...base,
    name: overrides.name ?? base.name,
    baseUrl: overrides.baseUrl ?? base.baseUrl,
    headers: mergeHeaders(base.headers, overrides.headers),

    getModels: () => applyModelOverrides(base.getModels(), overrides.models),
    refreshModels: base.refreshModels?.bind(base),

    stream: base.stream,
    streamSimple: base.streamSimple,
  };
}
```

由于 `getModels()` 委托给基础来源、`refreshModels()` 直接透传，这与动态 provider 可以良好组合。

models.json 中的请求认证配置（`$ENV`、`!command`、内联 key）仍是应用持有的旁路状态，要么以显式请求认证的形式出现，要么作为应用设置在被包装 provider 的 `auth.apiKey` 上的自定义 `ApiKeyAuth`。

## 自定义 provider：createProvider()

一个辅助函数把各部分组装成 provider；它同时处理单 API 与混合 API 的 provider：

```ts
export function createProvider(input: {
  id: string;
  name?: string;                 // 默认：id
  baseUrl?: string;
  headers?: Record<string, string>;
  auth: ProviderAuth;            // 必填，apiKey/oauth 至少其一（不存在「无认证」provider）
  /** 初始模型列表（纯动态 provider 为空）。 */
  models: readonly Model<Api>[];
  /** 动态 provider：拉取当前列表；createProvider 负责存储并对进行中的调用去重。 */
  refreshModels?: () => Promise<readonly Model<Api>[]>;
  /** 单个实现，或按 model.api 为键的映射（用于混合 API provider）。 */
  api: ProviderStreams | Record<string, ProviderStreams>;
}): Provider;
```

- 单个 `api`：所有模型都经它 stream。
- 映射形式的 `api`：`stream()`/`streamSimple()` 按 `model.api` 分发；未知 api 产出 stream 错误。

必须支持混合 API 的自定义 provider（opencode 的 Go/Zen 式 provider 在一个 provider id 下暴露由不同 API 支撑的模型）。

内置 provider 工厂在内部使用 `createProvider()`。models.json 的自定义 provider 直接映射到它：

```json
{
  "providers": {
    "my-openai-proxy": {
      "api": "openai-completions",
      "baseUrl": "https://proxy.example/v1",
      "models": [ ... ]
    }
  }
}
```

## Compat 入口

`@earendil-works/pi-ai/compat` 保留旧的全局 API 表面，直到 coding-agent 迁移完成后删除。新代码永远不导入它。

被保留的旧语义：全局 `stream()` 仍可为自定义 provider、被改动过的模型、以及覆盖了内置 API 实现的测试/extension，通过遗留 api-registry 按 `model.api` 分发。

- `stream/complete/streamSimple/completeSimple(model, ctx, opts)`：真正的内置 provider/模型/api 匹配时路由到一个单例 `builtinModels()` 集合，因此 provider 的认证/环境变量/baseUrl 行为与新运行时共享。未知 provider、被改动的模型、或被覆盖的 API 注册则回退到 api-registry 分发加 `getEnvApiKey` 注入。
- 内置 api 注册的副作用从根 barrel 移入 compat。它会跳过已有注册的 api id，因为 compat 可能在测试或 extension 已经注册了覆盖之后才加载。`registerApiProvider()/unregisterApiProviders()` 继续写入 compat 本地的注册表；`resetApiProviders()` 清空并重新注册内置项。
- 同步的 `getModel/getModels/getProviders` 是 `providers/all` 中 `getBuiltinModel/getBuiltinModels/getBuiltinProviders` 的废弃别名（它们一直都是纯粹的生成目录读取 —— 已核实：从未有代码修改过旧的 `modelRegistry`）。
- 重新导出各 API 的懒加载 stream 包装器（含 `setBedrockProviderModule`）、`env-api-keys.ts`、以及图像生成注册表/目录；这些都不再留在根 barrel 上。
- `export * from "./index.ts"`：compat 是核心入口的严格超集，因此消费方可以整体切换一个文件的导入路径，不必逐符号手术。

coding-agent（以及过渡期的 agent 包）把这些符号的导入从 `@earendil-works/pi-ai` 切到 `@earendil-works/pi-ai/compat`（仅改导入路径），在 ModelManager 迁移之前不做其它改动。

Extension 宽限期：coding-agent 的 extension 加载器（jiti 别名 + Bun `virtualModules`）把 `@earendil-works/pi-ai` 这个「根」说明符解析到 compat 入口。使用旧全局 API（`complete`、`getModel`、`registerApiProvider`……）的现有用户 extension 在运行时无需修改即可继续工作；它们只会在 ModelManager 迁移删除 compat 时才失效，届时 changelog 会附迁移指南。类型检查是引导手段：编辑器把根解析到精简的核心类型，因此想通过类型检查的 extension 源码必须从 `/compat` 导入旧全局符号 —— 仓库中的示例 extension 演示的正是这一点。

## 内置静态辅助函数

带类型、同步、仅读生成目录的辅助函数与目录放在一起（从 `providers/all` 导出）：

```ts
getBuiltinModel(provider, id)   // 同步，来自生成目录的类型化重载
getBuiltinModels(provider)      // 同步
getBuiltinProviders()           // 同步
```

经由 `Models` 实例的运行时查询是对最近已知 provider 列表的同步读取：`models.getModel(...)`。对新鲜度敏感的调用方先执行 `await models.refresh(provider)`。

生成的目录通过更新 `packages/ai/scripts/generate-models.ts` 按 provider 拆分（`providers/<id>.models.ts`）。如果生成器改动在本轮里过大，拆分可以推迟；`providers/all` 与 provider 工厂可以临时导入整体的 `models.generated.ts`，依赖 `sideEffects: false` 完成裁剪。

## Tree-shaking 与懒加载导入

规则：

1. 主入口 `@earendil-works/pi-ai` 仅含核心。
2. Provider 模块只导入自己的目录、认证辅助函数和懒加载 API 包装器。
3. 懒加载 API 包装器动态导入真实 API 实现。
4. 真实 API 实现导入 SDK 依赖。
5. OAuth 实现总是通过 `lazyOAuth()` 挂载，并藏在打包器不可见的动态导入之后懒加载；provider 元数据从不急切导入仅限 Node 的 OAuth 代码。
6. `providers/all` 导入所有内置 provider 工厂和全部目录。它是显式的重型入口。
7. Provider 模块无副作用；导入一个 provider 不会向全局注册任何东西。
8. `package.json` 的 `sideEffects` 只列出有副作用的 compat/图像注册文件；根入口与 provider 模块保持可被 tree-shake。
9. 有代码分割时，provider SDK 留在懒加载 chunk 里。没有代码分割时，打包器会把静态可达的懒加载 API 实现折叠进单一 bundle；此时 `providers/all` 会拉入所有静态可见的 SDK。Bedrock 是例外，因为它的 AWS SDK 实现藏在打包器不可见的、仅限 Node 的导入之后，独立单文件 bundle 需要 `setBedrockProviderModule()`。

导出映射（exports map）草图：

```json
{
  "exports": {
    ".": "./dist/index.js",
    "./compat": "./dist/compat.js",
    "./providers/all": "./dist/providers/all.js",
    "./providers/openai": "./dist/providers/openai.js",
    "./providers/anthropic": "./dist/providers/anthropic.js",
    "./providers/*": "./dist/providers/*.js",
    "./api/*": "./dist/api/*.js"
  }
}
```

浏览器冒烟检查（`scripts/check-browser-smoke.mjs`）必须持续通过：打包核心入口（以及任何非 node 的 provider 入口）不得拉入 `node:http`/`node:crypto`。

## AgentHarness 集成

`AgentHarness` 接收一个 `Models` 实例。

- `AgentHarnessOptions.models` 为必填。
- harness 不把 `Models` 快照进轮次状态。
- 请求路径调用 `this.models.streamSimple(model, context, options)`；上下文压缩/分支摘要路径同理。
- 请求路径从不调用异步的 `models.getModel()` 做规范化；如果模型元数据需要刷新，应用在开始轮次前先更新所选模型。
- Harness 测试构建 `createModels()` 并安装 faux provider（`providers/faux` 的 `fauxProvider()` 工厂）。

## coding-agent 的下一阶段（不在本轮）

coding-agent 分层构建 provider，并按 session 绑定：

```txt
内置 provider（builtinModels）
-> models.json provider 包装器 / 自定义 provider（createProvider）
-> extension 的 provider 包装器/新增
```

```ts
sessionModels.clearProviders();
for (const provider of layeredProviders) sessionModels.setProvider(provider);
```

coding-agent 负责：取代 AuthStorage 的 `FileCredentialStore` + 装饰器（见「取代 AuthStorage」）、models.json 认证旁路配置（`$ENV`、`!command`）、命令执行策略、provider 状态标签（来自 `AuthResult.source`）、登录/登出 UI（用 `prompt()/notify()` 驱动 `auth.{apiKey,oauth}.login()`）、extension 生命周期、provider 管理斜杠命令。

当前过渡状态：

- `AgentHarness` 已接受 `Models` 实例，并将其用于轮次 streaming、上下文压缩和分支摘要。
- coding-agent 尚未使用 `AgentHarness`；`AgentSession` 仍通过 `streamFn` 驱动底层 `Agent`。
- coding-agent 仍使用遗留的 `AuthStorage` + `ModelRegistry`，并通过 `@earendil-works/pi-ai/compat` 导入旧的全局 pi-ai API。
- extension 加载器仍把 pi-ai 根别名到 `/compat`，作为旧 extension 的运行时宽限期。

## 实现 TODO

事项落地后即勾选。保持此清单为最新；它是恢复会话时的工作状态记录。

### 第 1 阶段 —— 核心类型/运行时

- [x] 将 `types.ts` 的 `Provider` 别名重命名为 `ProviderId`；修复调用点。
- [x] 在 `types.ts` 中加入 `ApiOptionsMap` 与 `ApiStreamOptions<TApi>`（仅类型导入）。
- [x] 新的 `models.ts`：`Provider<TApi>` 接口、`hasApi()` 守卫、`ModelsError` + 错误码。认证类型放在 `src/auth/types.ts`（`ProviderAuth` = `{ apiKey?, oauth? }`、凭据、`CredentialStore`（`read`/`modify`/`delete`，每 provider 一份凭据）、`AuthResult`、`AuthContext`、`ModelAuth`、登录回调），内存存储在 `src/auth/credential-store.ts`，默认上下文在 `src/auth/context.ts`（浏览器安全的 node:fs 技巧），`lazyStream()` 在 `src/api/lazy.ts`。
- [x] `Models`/`MutableModels`/`createModels({ credentials?, authContext? })`：provider 映射、同步的 `getModel(s)`（按 provider 隔离失败）、显式异步 `refresh(provider?)`、`getAuth`（决策树、双重检查带锁刷新）、`stream/complete/streamSimple/completeSimple` 及逐字段认证合并。测试：`packages/ai/test/models-runtime.test.ts`。
- [x] 保留元数据辅助函数：`calculateCost`、`getSupportedThinkingLevels`、`clampThinkingLevel`、`modelsAreEqual`。

### 第 2 阶段 —— `src/api/`

- [x] 将 stream 实现从 `src/providers/` 移到 `src/api/`，按 API id 重命名（`anthropic.ts` -> `api/anthropic-messages.ts` 等）。
- [x] 将每个实现模块规范为恰好导出 `stream` 和 `streamSimple`。
- [x] 将共享辅助模块（`openai-responses-shared`、`google-shared`、`transform-messages`、`openai-prompt-cache`、`github-copilot-headers`、`cloudflare`、`simple-options`）移到 `src/api/`。
- [x] 将 `lazyStream()`/`lazyApi()` 提取到 `src/api/lazy.ts`。
- [x] 为每个 API 添加 `*.lazy.ts` 包装器；bedrock 保留仅限 Node 的导入技巧和 `setBedrockProviderModule()`。
- [x] 删除 `providers/register-builtins.ts`。在第 5 阶段 compat 落地前的过渡方案：内置的 api-registry 注册放在 `stream.ts`；懒加载 API 包装器从根 barrel 导出。

### 第 3 阶段 —— provider 工厂 + 目录

- [x] `src/auth/helpers.ts` 中的认证辅助函数：`envApiKeyAuth()`（带 secret 提示的 `login`）、`lazyOAuth()`。OAuth 流程加载走 `auth/oauth/load.ts`（打包器不可见的动态导入）；它引用的 `OAuthAuth` 导出在第 4 阶段落地。
- [x] `models.ts` 中的 `createProvider()`（单个 + 混合 `api` 映射，按 `model.api` 分发，未知 api -> stream 错误）。
- [x] 为所有内置目录 provider 在 `src/providers/` 下提供工厂；OAuth 通过 `lazyOAuth()` 挂载（anthropic、openai-codex、github-copilot）；amazon-bedrock（AWS 环境/profile）和 google-vertex（key 或 ADC+project+location）使用环境凭据式 `ApiKeyAuth`。
- [x] `providers/all.ts`：`builtinProviders()`、`builtinModels()`，重新导出 `getBuiltinModel/getBuiltinModels/getBuiltinProviders`。
- [x] 测试用的 faux provider 工厂（`providers/faux.ts` 的 `fauxProvider()`）；遗留的 `registerFauxProvider()` 保留至 compat 消亡。
- [x] 经 `scripts/generate-models.ts` 按 provider 拆分生成目录（`providers/<id>.models.ts`）；`models.generated.ts` 变为生成的聚合器。

### 第 4 阶段 —— OAuth 适配

- [x] 内置实现位于 `auth/oauth/` 下，直接通过 `AuthInteraction.prompt()`/`notify()` 实现 `OAuthAuth`。它们是由 provider 工厂懒加载的私有 provider 实现。
- [x] 回调服务器流程与 `manual_code` 提示竞速，流程敲定后通过 `AuthPrompt.signal` 中止提示。公开的 `oauth` 子路径仅保留 coding-agent extension 兼容类型。

### 第 5 阶段 —— 打包

- [x] `index.ts` 仅含核心且无副作用（无目录、无 provider 工厂、无 api-registry、无 env-api-keys、无图像、无 OAuth、无 compat）。类型化目录读取（`getBuiltin*`）在 `providers/all.ts` 中实现；`models.ts` 不再导入 `models.generated.ts`。
- [x] `compat.ts`：index 的超集 + 旧的 api 分发全局函数、废弃的 `getModel/getModels/getProviders` 别名、懒加载 api 包装器 + `setBedrockProviderModule`、`getEnvApiKey`、图像。注册副作用放在这里（已存在则跳过）。
- [x] 子路径导出映射（`./compat`、`./providers/*`、`./api/*`）；`sideEffects` 数组列出有副作用的模块（`compat`、图像注册），而不是 `false`。
- [x] 浏览器冒烟检查（入口现在从 `/compat` 导入旧全局符号）+ shrinkwrap 检查通过。内部的旧全局导入已切换到 `/compat`（agent/coding-agent/examples 共 42 个文件；vitest 配置将 `/compat` 别名到 src；spawn-CLI 测试解析 workspace dist，因此重建了 `packages/ai` + `packages/agent` 的 dist）。

### 第 6 阶段 —— AgentHarness

- [x] `AgentHarnessOptions.models` 必填（harness 上有 `readonly models`）；harness 的 stream 路径使用 `models.streamSimple()`。`StreamFn` 重新定义为结构化类型（不依赖 compat 类型）；`Models.streamSimple` 满足它。
- [x] 上下文压缩/分支摘要使用 harness 的 `Models` 实例。`getApiKeyAndHeaders` 被彻底移除 —— `Models` 是唯一的认证路径；按请求的 key 解析变为集合上的 provider 认证。`compact()`/`generateSummary()`/`generateBranchSummary()` 去掉了显式的 `apiKey`/`headers` 参数。
- [x] Harness 测试使用 `createModels()` + `fauxProvider()`，每个假 provider 用唯一 id；没有全局 api-registry 状态，也无需注销登记。

### 第 7 阶段 —— coding-agent 桥接（最小化）

- [x] 将旧全局导入切换到 `@earendil-works/pi-ai/compat`（随第 5 阶段落地；compat 是超集，所以切换只改路径）。extension 加载器把 pi-ai 根解析到 compat 作为运行时宽限期。
- [x] 这里最初勾画的其它内容都取决于 coding-agent 真正通过 `Models` 实例进行 streaming —— coding-agent 的 `AgentSession` 是经由 `streamFn` 驱动底层 `Agent` 的，不走 harness —— 因此移入第 9 阶段。

### 第 8 阶段 —— 收尾

- [x] 更新/新增测试；运行受影响的用例（测试随各阶段落地；`./test.sh` 全程绿）。
- [x] `packages/ai/CHANGELOG.md`：`### Breaking Changes` 附迁移指南（compat 入口、`Provider` -> `ProviderId`、api 模块搬移）+ `### Added` 记录新的 Models/provider/认证 API。
- [x] `packages/coding-agent/CHANGELOG.md`：面向 extension 作者的 `### Changed` 条目 —— 运行时不受影响（加载器把 pi-ai 根解析到 compat），类型检查引导迁移到 `/compat` 或新 API；移除发生在之后并附迁移指南。
- [x] `packages/agent/CHANGELOG.md`：`### Breaking Changes` 记录必填的 `AgentHarnessOptions.models`、上下文压缩签名变化、结构化 `StreamFn`。
- [x] `npm run check` 干净通过。

### 第 9 阶段 —— coding-agent 迁移到 Models + CredentialStore（在范围内）

coding-agent 用 `FileCredentialStore` + 一个 `MutableModels` 集合替换 AuthStorage 和 ModelRegistry 的内部实现。AgentSession 本身保留（AgentHarness 的采用属于 pi 2.0）；只替换其模型/认证底座。分层严格单向：

```txt
FileCredentialStore（auth.json，带锁，$ENV/!command 解析）+ 显式的 --api-key 覆盖层
        ↑
MutableModels：内置工厂（按 models.json 配置包装）+ 自定义 provider（models.json ∪ extension）
        ↑
ModelRegistry：兼容门面 —— 同步的最近已知读取委托给集合；registerProvider/login/logout/status 供 extension + UI 使用
        ↑
AgentSession / sdk / interactive-mode（经 models stream；只在认证/刷新路径上 await）
```

决策：

- `AuthStorage` 作为类型被删除 —— 否则它将依赖 provider 认证，而 provider 认证又依赖它的存储（循环依赖）。其表面拆分为：`get`/`set`/`remove` -> `CredentialStore`；`getApiKey` -> `Models.getAuth`；`login`/`logout`/`getAuthStatus` -> ModelRegistry 门面方法，基于 `provider.auth.oauth` + 存储实现。
- `FileCredentialStore` 自包含（路径、加锁、解析/写入、chmod、错误缓冲），并拥有 `auth.json` 语义，包括对存储的 API-key 凭据做 `$ENV`/`!command` 解析。持久化的值保持原始形式；解析结果以副本形式返回用于认证。
- 运行时 `--api-key` 覆盖是显式的存储覆盖层（覆盖值读出来是一份临时的已存 api-key 凭据，会遮蔽存储的 OAuth —— 与今天的优先级一致）。每个已注册 provider 都保证有 `apiKey` 认证槽位，因此覆盖对仅 OAuth 的 provider 也有效。
- `ModelRegistry.getAll`/`find`/`getAvailable` 为 SDK 与 extension 兼容性保持同步，委托给集合的同步最近已知模型列表和快速的「看起来已配置」状态检查。动态 provider 通过显式异步 `refresh()` 更新，请求认证仍经 `getApiKeyAndHeaders()`/`Models.getAuth()` 异步进行。extension 还会拿到集合本身作为面向未来的 API。
- models.json 保持完全的功能对等，以 provider 装饰实现：包装内置工厂，使 `getModels()` 应用 provider 级 `baseUrl`/`compat` 覆盖、`modelOverrides` 和自定义模型合并（异步安全）；provider 的 `apiKey`/`headers`/`authHeader` 配置变为该 provider 的 `ApiKeyAuth`（配置优先，工厂认证兜底）；解析错误保持 `getError()` 语义。
- Extension `ProviderConfig` 对等：按 provider 的 `streamSimple`、遗留 extension OAuth 回调适配为 `OAuthAuth`、按 provider 的完整模型替换。遗留的 `registerApiProvider` 写入仅为调用全局 `complete()` 的消费者保留在 compat 本地；随 compat 一起消亡。
- Copilot：存储凭据中的 baseUrl 在被包装的 `getModels()` 中应用（extension 可见的模型保持正确），外加按请求的 `toAuth().baseUrl`。
- Cloudflare：provider 认证替换（key + 来自凭据 `env` 或环境 `AuthContext.env()` 的 `CLOUDFLARE_ACCOUNT_ID`/`CLOUDFLARE_GATEWAY_ID` -> `ModelAuth.baseUrl`）。内置的 compat 调用路由经 `Models`，因此走同一条 provider 认证路径。

新会话的执行顺序：

1. [x] 先做 pi-ai 改造：`Provider.getModels()` 同步 + 可选 `refreshModels()`；`Models.getModels`/`getModel` 同步，`Models.refresh(provider?)` 异步；`createProvider` 接受 `models` 数组 + 可选 `refreshModels` 拉取器（进行中调用去重）。这推翻了第 1 阶段的异步列表决定 —— 理由见「Provider 模型列表」（同步或异步联合类型滋生潜伏的同步假设；纯异步会破坏 extension `find`/`getAll` 这类同步消费者接口）。
2. [x] pi-ai 工厂中的 Cloudflare provider 认证：Workers AI 与 AI Gateway 校验所需的 account/gateway 环境变量/配置，并从 provider 认证返回解析后的 `baseUrl`、provider 范围的 env、以及 header 抑制/覆盖元数据。
3. [ ] 在 coding-agent 中加入 `FileCredentialStore`。
   - 将 pi-ai 的 `CredentialStore` 接口实现为自包含的 `auth.json` 存储；不依赖旧的 `AuthStorageBackend` 抽象，但可移植其锁/重试语义。
   - 保留现有文件格式。`ApiKeyCredential` 使用 `{ type: "api_key", key?, env? }`，与今天的 `auth.json` 一致；不要把 `env` 转成元数据，也不要重写判别字段。
   - 开箱即用地解析存储的 API-key `key` 和 `env` 值中的 `$ENV`/`!command`，使用注入的执行/配置环境。`$ENV` 查找应来自该环境，`!command` 应走共享的 shell 执行路径而非直接 `execSync`。
   - 持久化原始配置值；为认证返回的已解析凭据必须是副本，且除非调用方显式存入新值，不得重写 `$ENV`/`!command` 字符串。
   - `read(provider)` 返回当前凭据快照，并记录解析/存储错误以保持状态 UI 对等。
   - `modify(provider, fn)` 必须加锁、重读、运行 `fn`、合并写入该 provider 条目、chmod `0600`，并返回写入后的凭据。
   - `delete(provider)` 必须加锁并只移除该 provider 的条目。
   - 添加基于文件和内存的测试，覆盖锁/读-改-写行为、带配置值解析的 `api_key` 读取、OAuth 读取、provider `env` 保留、删除、解析错误、以及并发的刷新式修改。
4. [ ] 为 coding-agent 策略加入运行时覆盖层。
   - `withRuntimeOverrides(store, overrides)` 实现 CLI `--api-key`：对每个被覆盖的 provider，read 返回一份临时的 `{ type: "api_key", key }`，遮蔽存储的 OAuth/API 凭据且不持久化。
   - 运行时覆盖必须对支持 OAuth 的 provider 也生效；coding-agent 中注册的每个 provider 都必须保留或获得 `apiKey` 认证槽位，覆盖层才有意义。
   - 测试覆盖优先级：运行时覆盖 > 存储凭据 > models.json 配置认证 > provider 环境凭据，且存储凭据阻断环境回退。
5. [ ] 为 `models.json` 构建 provider 装饰辅助函数。
   - 从内置 provider 工厂出发，而不是从生成的模型数组出发。
   - 包装 provider 的 `getModels()`，使 provider 级 `baseUrl`/`headers`/`compat`、按模型的 `modelOverrides`、以及自定义模型合并在每次同步读取时生效。
   - 保留 `refreshModels()` 透传，使动态 provider 与装饰可组合。
   - 将 models.json 中 provider 的 `apiKey`/`headers`/`authHeader` 配置转换为包装后的 `ApiKeyAuth`：先解析配置值，再回退到基础 provider 认证。
   - 带 `models` 的自定义 provider 使用 `createProvider()`，配以合适的懒加载 API 包装器或 extension 提供的 stream 实现。
   - 解析错误必须保持当前 `ModelRegistry.getError()` 行为：内置项仍然可用，且错误可见。
6. [ ] Copilot `getModels()` 的 baseUrl 包装。
   - GitHub Copilot OAuth 的 `toAuth()` 已为 streaming 返回按凭据的请求 `baseUrl`。
   - 当存在 OAuth 凭据时包装 Copilot 的 provider `getModels()`，使 extension/UI 可见的模型元数据也携带已认证账户的 base URL。
   - 保持 API-key/环境 token 的 Copilot 行为不变。
   - 为登录前、获得 OAuth 凭据后、刷新/baseUrl 变化后、登出后的模型元数据添加测试。
7. [x] Extension OAuth 适配器。
   - 只保留 coding-agent `ProviderConfig.oauth` 所需的遗留回调/凭据声明。
   - `login` 把遗留回调/事件映射到 `AuthInteraction.prompt()`/`notify()`。
   - `refreshToken` 映射到 `refresh`；`getApiKey` 映射到 `toAuth`。
   - 保留仅类型的 pi-ai `oauth` barrel 和 extension 加载器别名。
8. [ ] 基于 `MutableModels` 重建 coding-agent 的 `ModelRegistry`。
   - 它持有一个由装饰后的内置项 + models.json 自定义 provider + extension provider 构建的 `MutableModels` 实例。
   - `getAll()`、`find()`、`getAvailable()` 仍是基于最近已知模型列表和快速「看起来已配置」认证状态的同步兼容方法。不得破坏面向 extension 的 `modelRegistry` 读取接口。
   - `refresh()` 是显式的异步新鲜度边界：重建 provider 层，并在需要处调用 `models.refresh()`；除 compat 专属的宽限行为外，新路径不应包含全局 api-registry 重置。
   - `registerProvider()`/`unregisterProvider()` 修改 provider 层并重建集合。
   - 门面认证操作（`login`、`logout`、provider 状态、可用的 OAuth provider）驱动 `provider.auth.{apiKey,oauth}` 与 `CredentialStore`；不再有任何 `AuthStorage` 类型残留。
   - 遗留的 `registerApiProvider` 写入仅为 `/compat` 调用者保留，在第 10 阶段移除。
9. [ ] 重接消费者。
   - `AgentSession` 的 stream 函数经 `ModelRegistry`/`Models` 解析，不再走 `getApiKeyAndHeaders()` + compat 全局函数。
   - SDK options 用 `credentials?: CredentialStore` 或基于 agent 目录的默认值取代 `authStorage`；更新 `sdk.md` 与示例。
   - `model-resolver`、`--list-models`、模型选择器、登录/登出/状态 UI、provider 归属展示都使用同步的最近已知模型读取，只在显式刷新/认证操作时 await。
   - CLI `--api-key` 填充运行时覆盖装饰器，而不是修改 `AuthStorage`。
   - extension 加载器的根到 compat 别名保留至第 10 阶段，但把新的集合/门面作为面向未来的 API 暴露出去。
10. [ ] 测试迁移与真实 provider 验证。
    - 为 `FileCredentialStore`、运行时覆盖层、provider 装饰、extension OAuth 适配器、基于 Models 的 ModelRegistry 门面、消费者重接编写单元测试。
    - 为 Cloudflare account/gateway 环境变量、Copilot OAuth baseUrl 包装、运行时 `--api-key` 优先级、`$ENV`/`!command` 解析、存储凭据阻断环境回退编写回归测试。
    - 更新现有测试以适配同步的最近已知 `ModelRegistry.getAll/find/getAvailable` 加显式异步刷新行为。
    - 运行针对性的非 e2e 套件，并用 tmux 对真实 provider 验证登录流程（Anthropic OAuth/API key、OpenAI Codex OAuth、GitHub Copilot OAuth、Cloudflare AI Gateway，若有凭据则包括 Bedrock）。

### 第 10 阶段 —— 删除 compat（pi 2.0 时代，另行进行）

- [ ] AgentSession -> AgentHarness；registry 门面消亡，由 harness 的 `Models` 取代。
- [ ] 把所有内部 `/compat` 导入迁移到新 API：每个包的 src、全部测试、示例 extension（示例届时演示新 API）。到那时仓库内不得有任何代码导入 `/compat`。
- [ ] 删除 `/compat`、`env-api-keys.ts`、extension 加载器的根到 compat 别名、以及 compat 本地的遗留 API 注册表。旧的 OAuth 注册表/provider 接口已经不在了；仅类型的 `oauth` barrel 为 extension 兼容性保留。

### 推迟 / 后续事项

- [ ] Web OAuth 实现（sitegeist 风格）作为另一种 `OAuthAuth`。
- [x] 图像 API 重设计：`ImagesModels`/`ImagesProvider`/`createImagesProvider` 镜像聊天侧设计（同步读取、显式刷新、生成从不 reject）；认证解析通过 `auth/resolve.ts` 中独立的 `resolveProviderAuth()` 与聊天侧共享（`ModelsError` 也归它所有；两个集合都以参数传入各自的存储/上下文 —— 没有 resolver 对象）。`openrouterImagesProvider()` 工厂 + `providers/all` 中的 `builtinImagesProviders()`/`builtinImagesModels()`；实现移到 `api/openrouter-images.ts` 并配懒加载包装器。旧的全局图像 API（注册表 + `getImageModel*` + `generateImages`）留在 compat；types.ts 中的 `ImagesProvider` id 别名重命名为 `ImagesProviderId`（对应 `Provider` -> `ProviderId`）。

## 错误行为

`undefined` 表示未找到或未配置。真正的失败会 reject 或变成 stream 错误。

```ts
export type ModelsErrorCode =
  | "model_source"      // provider 模型刷新失败
  | "model_validation"  // 模型对象无效
  | "provider"          // 未知 provider、分发失败
  | "stream"            // stream 构建失败
  | "auth"              // 认证解析失败
  | "oauth";            // oauth 登录/刷新失败
```

- `Models.stream()` 对异步准备阶段的失败产出 stream 错误（error 事件 + error 结果）；返回 stream 之后不再 throw。
- `Models.getModels()` 是同步的尽力而为读取：某个 provider 的 `getModels()` 抛错时，该 provider 不产出模型。`Models.refresh(provider)` 在该 provider 拉取失败时 reject；`Models.refresh()`（全部 provider）是并发的尽力而为。需要拿到具体列表失败信息的应用去刷新单个 provider。
- 认证解析与凭据存储的失败大声地 reject（`ModelsError` 错误码 `auth`/`oauth`）；失败后静默回退到另一条认证路径有产生计费意外的风险。存储的凭据始终阻断环境/env 回退，包括刷新失败之后。
- 状态/可用性 UI 捕获 `getAuth` 的 rejection 并渲染「需要重新登录」；不把 rejection 当作「未配置」。
