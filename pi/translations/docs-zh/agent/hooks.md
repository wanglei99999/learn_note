> **译文** | 原文：[`packages/agent/docs/hooks.md`](https://github.com/earendil-works/pi/blob/main/packages/agent/docs/hooks.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# AgentHarness hook 设计

<!-- 从 jot 3utlzkxy 同步而来。今后请在仓库内编辑本文件。 -->

最终设计。

## 核心模型

事件以仅类型层面的幻影（phantom）字段携带其结果类型：

```ts
declare const HookResult: unique symbol;

interface HookEvent<TType extends string, TResult = void> {
	type: TType;
	readonly [HookResult]?: TResult;
}

type ResultOf<E> = E extends { readonly [HookResult]?: infer R } ? R : void;

type HookHandler<E, Ctx> = (
	event: E,
	ctx: Ctx,
	signal?: AbortSignal,
) => ResultOf<E> | void | Promise<ResultOf<E> | void>;

type HookObserver<E, Ctx> = (
	event: E,
	ctx: Ctx,
	signal?: AbortSignal,
) => void | Promise<void>;
```

示例：

```ts
interface ContextEvent extends HookEvent<"context", { messages?: AgentMessage[] }> {
	type: "context";
	messages: AgentMessage[];
}

interface ToolCallEvent extends HookEvent<"tool_call", { block?: boolean; reason?: string }> {
	type: "tool_call";
	toolName: string;
	input: Record<string, unknown>;
}

interface MessageEndEvent extends HookEvent<"message_end"> {
	type: "message_end";
	message: AgentMessage;
}
```

没有结果映射表。没有规格表。事件类型自行定义其结果。

## hooks 接口

```ts
interface AgentHarnessHooks<E extends HookEvent<string, unknown>, Ctx> {
	context: Ctx;

	setContext(ctx: Ctx): void;

	observe(handler: HookObserver<E, Ctx>): () => void;

	on<TType extends E["type"]>(
		type: TType,
		handler: HookHandler<Extract<E, { type: TType }>, Ctx>,
	): () => void;

	emit<TEvent extends E>(
		event: TEvent,
		signal?: AbortSignal,
	): Promise<ResultOf<TEvent> | undefined>;

	addCleanup(cleanup: () => void | Promise<void>): () => void;

	clear(): Promise<void>;
	dispose(): Promise<void>;
}
```

重要的职责划分：

- `observe()` 看到所有事件，只读，返回值被忽略。
- `on(type, handler)` 参与该事件的语义。
- `emit(event)` 是 `AgentHarness` 唯一调用的方法。
- `clear()` 移除观察者/处理器并运行清理函数。

## 默认实现的内部结构

```ts
class DefaultAgentHarnessHooks<E extends HookEvent<string, unknown>, Ctx>
	implements AgentHarnessHooks<E, Ctx> {
	context: Ctx;

	private observers = new Set<HookObserver<E, Ctx>>();
	private handlers = new Map<string, Set<HookHandler<any, Ctx>>>();
	private cleanups = new Set<() => void | Promise<void>>();

	constructor(ctx: Ctx) {
		this.context = ctx;
	}

	setContext(ctx: Ctx): void {
		this.context = ctx;
	}

	observe(handler: HookObserver<E, Ctx>): () => void {
		this.observers.add(handler);
		return () => this.observers.delete(handler);
	}

	on(type, handler): () => void {
		let handlers = this.handlers.get(type);
		if (!handlers) {
			handlers = new Set();
			this.handlers.set(type, handlers);
		}
		handlers.add(handler);
		return () => handlers.delete(handler);
	}

	async emit(event, signal?) {
		for (const observer of this.observers) {
			await observer(event, this.context, signal);
		}

		switch (event.type) {
			case "context":
				return this.emitContext(event, signal);
			case "before_provider_request":
				return this.emitBeforeProviderRequest(event, signal);
			case "before_provider_payload":
				return this.emitBeforeProviderPayload(event, signal);
			case "before_agent_start":
				return this.emitBeforeAgentStart(event, signal);
			case "tool_call":
				return this.emitToolCall(event, signal);
			case "tool_result":
				return this.emitToolResult(event, signal);
			case "session_before_compact":
			case "session_before_tree":
				return this.emitFirstCancelOrLast(event, signal);
			default:
				await this.emitObservationHandlers(event, signal);
				return undefined;
		}
	}
}
```

由于 `Map<string, ...>` 会丢失类型精确性，实现内部的类型断言是可以接受的。公开 API 保持强类型。

## 变更语义

### 观察

```ts
await hooks.emit({ type: "message_end", message }, signal);
```

观察者先运行。`message_end` 处理器再运行。返回值被忽略，除非该事件将来获得结果类型。

### 上下文变换

处理器按顺序运行。每个处理器看到当前的消息。

```ts
let current = event;

for (const handler of handlers("context")) {
	const result = await handler(current, ctx, signal);
	if (result?.messages) {
		current = { ...current, messages: result.messages };
	}
}

return current.messages === event.messages ? undefined : { messages: current.messages };
```

### provider 请求 / 负载

顺序变换。每个处理器看到前一个的输出。

```ts
let current = event;

for (const handler of handlers("before_provider_payload")) {
	const result = await handler(current, ctx, signal);
	if (result !== undefined) {
		current = { ...current, payload: result.payload };
	}
}

return changed ? { payload: current.payload } : undefined;
```

### agent 启动前

收集注入的消息，链式处理系统提示词。

```ts
let systemPrompt = event.systemPrompt;
const messages = [];

for (const handler of handlers("before_agent_start")) {
	const result = await handler({ ...event, systemPrompt }, ctx, signal);
	if (result?.messages) messages.push(...result.messages);
	if (result?.systemPrompt !== undefined) systemPrompt = result.systemPrompt;
}

return messages.length || systemPrompt !== event.systemPrompt
	? { messages, systemPrompt }
	: undefined;
```

### 工具调用

顺序执行，block 时提前退出。

```ts
for (const handler of handlers("tool_call")) {
	const result = await handler(event, ctx, signal);
	if (result?.block) return result;
}
```

### 工具结果

顺序累积补丁。每个处理器看到当前已打补丁的结果。

```ts
let current = event;
let modified = false;

for (const handler of handlers("tool_result")) {
	const result = await handler(current, ctx, signal);
	if (!result) continue;

	current = {
		...current,
		content: result.content ?? current.content,
		details: result.details ?? current.details,
		isError: result.isError ?? current.isError,
	};

	modified = true;
}

return modified
	? { content: current.content, details: current.details, isError: current.isError }
	: undefined;
```

### session-before 事件

顺序执行，cancel 时提前退出。

```ts
let last;

for (const handler of handlers(event.type)) {
	const result = await handler(event, ctx, signal);
	if (!result) continue;
	last = result;
	if (result.cancel) return result;
}

return last;
```

## harness 的用法

harness 只做这件事：

```ts
await this.hooks.emit(event, signal);
```

或：

```ts
const result = await this.hooks.emit({ type: "context", messages }, signal);
return result?.messages ?? messages;
```

harness 不存储处理器、不链式调用监听器，也不了解 extension 策略。

## 上下文

上下文是一个普通对象，不会在每次 emit 时重建。

```ts
const hooks = new CodingAgentHooks({
	harness: harnessFacade,
	session: sessionFacade,
	ui: noUiFacade,
});
```

之后：

```ts
hooks.setContext({
	...hooks.context,
	ui: tuiFacade,
});
```

对于动态状态，优先使用稳定的门面/方法，而不是 getter 迷宫：

```ts
interface CodingAgentHookContext {
	harness: HarnessFacade;
	session: SessionFacade;
	ui: UiFacade;
	models: ModelFacade;
}
```

按运行传递的 `signal` 作为处理器的第三个参数。

## 之后的 extension 加载

extension 加载可以放在 harness 旁边并构造 hooks：

```ts
const hooks = await loadExtensions({
	paths,
	context,
	hooks: new CodingAgentHooks(context),
});
const harness = new AgentHarness({ ..., hooks });
```

加载器向 hooks 注册：

```ts
hooks.on("context", handler);
hooks.on("tool_call", handler);
hooks.addCleanup(cleanup);
```

重新加载时：

```ts
await hooks.clear();
const nextHooks = await loadExtensions(...);
harness.setHooks(nextHooks); // 如果支持，则仅限空闲时
```

## 挑毛病

### 1. 错误策略必须显式

现有的 coding-agent 会捕获 extension 错误、上报并继续运行。新的 hooks 需要同样的策略，可能是：

```ts
errorMode: "continue" | "throw"
onError(error)
```

对于 coding-agent，默认应为 `"continue"`。

### 2. 来源元数据很重要

现有的 runner 知道哪个 extension 产生了错误/资源/工具。除非我们添加注册元数据或作用域（scope），否则单纯的 `on()` 会丢失这一信息。

大概率需要：

```ts
const scope = hooks.createScope({ sourceInfo });
scope.on("context", handler);
scope.addCleanup(...);
```

或者 `on(type, handler, { sourceInfo })`。

### 3. 部分 extension 能力是注册表，而不是 hook

以下能力不由 `emit()` 覆盖，应保留为 `CodingAgentHooks` 或某个 extension 宿主上的注册表：

- 工具
- 命令
- 快捷键
- 标志参数
- 消息渲染器
- provider 注册
- OAuth provider
- 自定义模型 provider

这没问题。它们不属于 `AgentHarness`。

### 4. 现有的 coding-agent 事件都可以表示

以下事件不存在阻碍：

- `context`
- `before_provider_request`
- `after_provider_response`
- `before_agent_start`
- `message_end`
- `tool_call`
- `tool_result`
- `input`
- `user_bash`
- `resources_discover`
- `session_before_*`
- `session_*`
- 模型/思考等级选择事件
- agent/回合/消息/工具生命周期事件

它们成为由 `CodingAgentHooks` 处理的额外事件类型。

### 5. 需要精确保留旧语义

移植 coding-agent 时，必须照搬这些特例：

- `input`：变换链，`handled` 短路。
- `user_bash`：第一个有意义的结果胜出。
- `message_end`：替换必须保持相同的角色（role）。
- `before_agent_start`：`ctx.getSystemPrompt()` 必须反映当前链式处理后的提示词。
- `resources_discover`：聚合路径并保留 extension 来源。
- `tool_call`：参数修改对后续处理器保持可见。
- `tool_result`：后续处理器看到之前的补丁。

该设计允许所有这些行为，但默认/coding hooks 实现必须把它们编码进去。

### 6. `emit()` 的 switch 可能漏掉自定义的变更事件

如果子类添加了一个产生结果的事件但忘记重写 `emit()`，该事件会表现为纯观察行为。测试应捕获这种情况。如果这变得容易出错，之后可以添加一个受保护的策略注册表，但初期不需要。

### 7. 观察者语义是有意受限的

观察者只看到最初发出的事件一次。它们看不到每一次中间变更。如果某处需要最终变换后的状态，请发出一个单独的最终事件，或使用针对该事件的处理器。

## 结论

这个设计可以实现一个新的 coding-agent。它比当前的 runner 更简单，保持 harness 干净，并且只要 `CodingAgentHooks` 添加感知来源的作用域、注册表、清理和精确的旧事件语义，就能保留重要的 extension 能力。

--- 评论 ---

Thread hn2xk0tzhj on "addCleanup(cleanup"
  [tmluyaub9v] Owner (2026-05-14T12:55:45.500Z): cleanup 应可以选择性地随 on/observe 一并传入
