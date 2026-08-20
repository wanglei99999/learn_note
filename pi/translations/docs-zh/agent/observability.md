> **译文** | 原文：[`packages/agent/docs/observability.md`](https://github.com/earendil-works/pi/blob/main/packages/agent/docs/observability.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

<!-- 由 jot qe0ikdqs 同步而来。此后请直接在仓库内编辑本文件。 -->

# Pi 可观测性设计笔记

## 目标

让 `packages/ai` 与 `packages/agent`/harness 具备可观测性，同时不依赖 OpenTelemetry、Sentry 或任何 APM 厂商。

Pi 应当发出稳定、结构化的生命周期事件。外部监听器可以把这些事件转换成 OTel span、Sentry span、日志、指标或自定义遥测数据。

## 心智模型

一条 trace 是一棵因果关系的工作树，例如一次用户轮次（turn）。

一个 span 是这棵树中一次计时的操作。它通常用 ID 表示，而不是对象指针：

```ts
interface SpanRecord {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  name: string;
  startTime: number;
  endTime?: number;
  attributes: Record<string, unknown>;
  status: "ok" | "error";
}
```

示例树：

```text
traceId=t1 spanId=s1 parent=-  name=pi.agent.prompt
traceId=t1 spanId=s2 parent=s1 name=pi.agent.turn
traceId=t1 spanId=s3 parent=s2 name=pi.ai.provider.request
traceId=t1 spanId=s4 parent=s2 name=pi.agent.tool_call
traceId=t1 spanId=s5 parent=s4 name=pi.session.append_entry
```

## 异步上下文

JavaScript 只有一个事件循环，但多条异步链可以交错执行。一个全局的 `currentContext` 在并发场景下会失效。

`AsyncLocalStorage` 是 Node 中相当于异步延续（async continuation）版 `ThreadLocal` 的机制。它让并发操作各自保有独立的当前上下文：

```ts
await Promise.all([
  runWithPiContext({ userId: "alice" }, () => harness.prompt("A")),
  runWithPiContext({ userId: "bob" }, () => harness.prompt("B")),
]);
```

深层代码随后就能为当前活跃的异步链读取正确的当前上下文。

Pi 必须能运行在 Node、Bun、浏览器、worker 及其它 JS 运行时中，因此 ALS 不能作为核心抽象。它应当是一个运行时适配器。

## 核心设计

Pi 自己持有一个小巧、与运行时无关的可观测性抽象：

```ts
export interface PiObservabilityContext {
  traceId?: string;
  currentSpanId?: string;
  userContext?: Record<string, unknown>;
}

export interface PiObservabilityEvent {
  type: "start" | "end" | "error" | "event";
  name: string;
  traceId: string;
  spanId?: string;
  parentSpanId?: string;
  timestamp: number;
  durationMs?: number;
  context?: Record<string, unknown>;
  payload?: Record<string, unknown>;
  error?: { name: string; message: string };
}

export interface PiObservability {
  getContext(): PiObservabilityContext | undefined;
  runWithContext<T>(context: PiObservabilityContext, fn: () => T): T;
  emit(event: PiObservabilityEvent): void;
  hasSubscribers(): boolean;
}
```

公共 API：

```ts
export function configurePiObservability(observability: PiObservability): void;
export function subscribePiObservability(listener: (event: PiObservabilityEvent) => void): () => void;
export function runWithPiContext<T>(userContext: Record<string, unknown>, fn: () => T): T;
export function traceOperation<T>(name: string, payload: Record<string, unknown>, fn: () => T): T;
```

`traceOperation()`：

1. 读取当前上下文
2. 若缺失则创建 `traceId`
3. 创建一个新的 `spanId`
4. 把当前 span 用作 `parentSpanId`
5. 发出 `start` 事件
6. 在子上下文中运行回调
7. 发出 `end` 或 `error` 事件
8. 出错时重新抛出

伪代码：

```ts
function traceOperation<T>(name: string, payload: Record<string, unknown>, fn: () => T): T {
  const parent = getContext();
  const traceId = parent?.traceId ?? createId();
  const spanId = createId();
  const parentSpanId = parent?.currentSpanId;

  const child = { ...parent, traceId, currentSpanId: spanId };

  emit({ type: "start", name, traceId, spanId, parentSpanId, timestamp: Date.now(), context: parent?.userContext, payload });

  return runWithContext(child, () => {
    try {
      const result = fn();
      // 支持 Promise 的实现会在 Promise 敲定（settle）之后再发出 end/error。
      emit({ type: "end", name, traceId, spanId, parentSpanId, timestamp: Date.now(), context: child.userContext, payload });
      return result;
    } catch (error) {
      emit({ type: "error", name, traceId, spanId, parentSpanId, timestamp: Date.now(), context: child.userContext, payload, error: serializeError(error) });
      throw error;
    }
  });
}
```

## 运行时适配器

核心包不应导入仅限 Node 的 API。

可能的实现：

- Node 适配器：用 `AsyncLocalStorage` 承载上下文，可选地通过 `diagnostics_channel` 发布事件。
- 浏览器/worker 回退方案：本地订阅者集合，加上受限的/手动的上下文传播。
- Bun/Deno 适配器：若运行时提供特有的异步上下文机制则加以利用。

在 Node 上，diagnostics channel 可以用作被动的事件总线：

```ts
import { channel } from "diagnostics_channel";
channel("pi.observability").publish(event);
```

订阅者无需对 pi 做 monkey-patch 就能创建 OTel/Sentry span。

## pi 发出什么

Pi 发出的是「发生了什么」。它不直接创建 OTel/Sentry span。

初始的最小事件名集合：

```text
pi.agent.prompt
pi.agent.skill
pi.agent.prompt_template
pi.agent.compaction
pi.agent.branch_navigation
pi.agent.session.append_entry
pi.ai.provider.request
```

每个操作都会发出：

```text
start
end
error
```

后续再增加：

```text
pi.agent.turn
pi.agent.tool_call
pi.agent.queue_update
pi.ai.provider.retry
pi.ai.provider.first_token
pi.ai.provider.usage
pi.session.read
pi.session.write
```

## 最小插桩点

### packages/agent

包裹以下方法：

- `AgentHarness.prompt()`
- `AgentHarness.skill()`
- `AgentHarness.promptFromTemplate()`
- `AgentHarness.compact()`
- `AgentHarness.navigateTree()`
- `Session.appendTypedEntry()` 或存储追加门面（facade）

示例：

```ts
return traceOperation(
  "pi.agent.prompt",
  {
    sessionId: turnState.sessionId,
    provider: turnState.model.provider,
    model: turnState.model.id,
    promptLength: text.length,
    imageCount: options?.images?.length ?? 0,
  },
  () => this.executeTurn(turnState, text, options),
);
```

session 写入：

```ts
return traceOperation(
  "pi.agent.session.append_entry",
  { entryType: entry.type },
  async () => {
    await this.unwrap(this.storage.appendEntry(entry));
    return entry.id;
  },
);
```

### packages/ai

包裹常见的 provider 边界：

- `streamSimple()`
- `completeSimple()`

示例：

```ts
return traceOperation(
  "pi.ai.provider.request",
  {
    api: model.api,
    provider: model.provider,
    model: model.id,
    sessionId: options.sessionId,
    reasoning: options.reasoning,
  },
  () => actualStreamSimple(model, context, options),
);
```

end/error 的 payload 可以包含安全的元数据：

- 停止原因（stop reason）
- 状态码
- 重试次数
- 输入/输出/总 token 数
- 总成本
- 中止/超时标志

## 安全与脱敏

默认 payload 必须是安全的。

默认安全：

- provider
- 模型
- API 标识符
- session id
- 条目类型
- tool 名称
- 状态码
- 停止原因
- token 计数
- 成本
- 耗时

默认不安全：

- prompt
- 补全内容（completions）
- tool 参数
- tool 结果
- shell 输出
- 文件内容
- provider 请求 payload
- provider 响应体
- API key
- 请求头（headers）

内容捕获可以在后续以显式脱敏 hook 的方式按需开启（opt-in）。

## 监听器行为

可观测性绝不能影响 pi 的执行。

订阅者抛出的错误应当被吞掉或隔离。Harness hook 属于控制面、可能影响执行；可观测性订阅者是被动的，绝不能影响执行。

## 用户上下文

用户可以把任意上下文关联到一次轮次上：

```ts
await runWithPiContext(
  {
    userId: "u123",
    orgId: "acme",
    region: "eu",
  },
  () => harness.prompt("fix this"),
);
```

该异步链内发出的每个事件都会包含这份上下文：

```ts
{
  type: "start",
  name: "pi.ai.provider.request",
  traceId: "t1",
  spanId: "s3",
  parentSpanId: "s1",
  context: {
    userId: "u123",
    orgId: "acme",
    region: "eu",
  },
  payload: {
    provider: "anthropic",
    model: "claude-sonnet-4",
  },
}
```

OTel 适配器可以把它映射为 span 属性。Sentry 适配器可以把它映射为 Sentry 上下文/span。自定义用户可以直接记录 JSON 日志。

## 包规划

最小的初始包：

```text
packages/observability
  与运行时无关的上下文 + traceOperation + subscribe
```

然后：

```text
packages/ai
  发出 pi.ai.* 事件

packages/agent
  发出 pi.agent.* / pi.session.* 事件
```

之后可选：

```text
packages/observability-node
  AsyncLocalStorage + diagnostics_channel 桥接

packages/otel
  订阅 pi 事件并创建 OpenTelemetry span
```

## 核心主张

Pi 定义一份稳定、安全的事件契约。适配器决定事件流向哪里。

这样就能让 ai/harness 具备可观测性，而无需把核心包绑定到 OTel、Sentry、仅限 Node 的 API，也无需 monkey-patch。
