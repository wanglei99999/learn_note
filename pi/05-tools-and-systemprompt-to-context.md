# 05 — 汇合：`tools` 与 `systemPrompt` 怎么进 `Context`

> 学习系列第 5 篇，与 04 篇直接接续，也是 01–05 这一环的**合龙点**。
>
> 02 篇跟完了 `Context.messages`（树 → 路径 → 消息 → 报文），03 篇跟完了它怎么回来，04 篇跟完了扩展从磁盘文件变成盒子。但 `Context` 是三个字段：
>
> ```typescript
> export interface Context {
> 	systemPrompt?: string;   // ← 本篇
> 	messages: Message[];     // ← 02 + 03
> 	tools?: Tool[];          // ← 本篇
> }
> ```
>
> 本篇把剩下两条支流跟到底：**盒子里的工具怎么变成模型能调用的清单，散落各处的资源怎么拼成一段系统提示词。** 跟完之后，`Context` 三个字段全部溯源到底。
>
> 04 篇停在 `_refreshToolRegistry` 这个名字上，本篇从这里开始。
>
> 第 4 章是路旁参照，但值得单独一提：它从 `defer_loading` 这个不起眼的标记出发，挖出了**前缀缓存**这条横切线——为什么改动的代价取决于它落在第几个 token，为什么"每轮重发全部历史"离了缓存就不成立，以及 pi 为此付出的三道安全闸。这条线和 `generated/robustness-and-cost` 的主题重叠，但入口完全不同。
>
> 所有 `文件:行号` 基于 commit `859bd29bd`。核心文件六个：`core/agent-session.ts`（结算与覆盖）、`core/system-prompt.ts`（拼装）、`core/extensions/runner.ts`（链式改写）、`core/extensions/wrapper.ts`（工具包装）、`packages/ai/src/utils/deferred-tools.ts` + `packages/ai/src/api/anthropic-messages.ts`（前缀缓存与延迟加载）、`packages/agent/src/agent-loop.ts`（每轮取用）。

## 目录

- 第 1 章 全景：三个字段，三种更新策略
- 第 2 章 `tools` 支流：从盒子到 `Context.tools`
- 第 3 章 `systemPrompt` 支流（上）：备料与拼装
- 第 4 章 提示词三字段的分工 + 前缀缓存与延迟加载（路旁参照表）
- 第 5 章 `systemPrompt` 支流（下）：每轮的覆盖与复位
- 第 6 章 汇合：`prepareNextTurnWithContext`
- 第 7 章 工程模式清单
- 第 8 章 复习自测

---

## 第 1 章 全景：三个字段，三种更新策略

先把结论摆在前面。`Context` 三个字段虽然一起发出去，但**各自的更新节奏完全不同**：

| 字段 | 什么时候变 | 策略 | 在哪篇 |
|---|---|---|---|
| `messages` | 每轮 | **现算**：树 → 路径 → 消息，每次重新走一遍 | 09 |
| `tools` | 工具集变化时 | **结算 + 快照**：提前算好存住，每轮 `.slice()` 拷贝 | 本篇第 2 章 |
| `systemPrompt` | 料变时重建 + 每轮覆盖 | **底稿 + 覆盖层**：分层存储，取用时合成 | 本篇第 3、5 章 |

**同一个 `Context`，三个字段各按自己的变化频率选了不同的方案。** 这个对照是本篇的主线；每一章都在解释其中一种为什么是那样。

本篇的路径：

```text
盒子.tools ──────┐
内置 / SDK 工具 ──┼─► 结算 ─► activeTools ─► agent.state.tools ─┐
                 │              │                                │
ResourceLoader ──┤              │（供稿 promptSnippet）          ├─► Context
cwd ─────────────┼─► 拼装 ─► _baseSystemPrompt ─► ?? override ──┘
扩展改写 ─────────┘
```

---

## 第 2 章 `tools` 支流：从盒子到 `Context.tools`

### 2.1 摊平：`getAllRegisteredTools`（`runner.ts:464`）

04 篇讲过，扩展的工具躺在各自盒子的 `tools` Map 里。第一步是摊平：

```typescript
getAllRegisteredTools(): RegisteredTool[] {
	const toolsByName = new Map<string, RegisteredTool>();
	for (const ext of this.extensions) {
		for (const tool of ext.tools.values()) {
			if (!toolsByName.has(tool.definition.name)) {   // ★ 先来先得
				toolsByName.set(tool.definition.name, tool);
			}
		}
	}
	return Array.from(toolsByName.values());
}
```

**同名工具，先加载的赢。** 又是那个"先来先得"——04 篇的发现段去重、`getMessageRenderer` 都是这个套路。所以项目扩展的工具会挡住全局扩展的同名工具。

### 2.2 三个来源汇总（`agent-session.ts:2733`）

```typescript
const registeredTools = this._extensionRunner.getAllRegisteredTools();       // ① 扩展
const allCustomTools = [
	...registeredTools,
	...this._customTools.map((definition) => ({                                // ② SDK 内嵌
		definition,
		sourceInfo: createSyntheticSourceInfo(`<sdk:${definition.name}>`, { source: "sdk" }),
	})),
].filter((tool) => isAllowedTool(tool.definition.name));

const definitionRegistry = new Map<string, ToolDefinitionEntry>(
	Array.from(this._baseToolDefinitions.entries())                            // ③ 内置，铺底
		.filter(([name]) => isAllowedTool(name))
		.map(([name, definition]) => [name, {
			definition,
			sourceInfo: createSyntheticSourceInfo(`<builtin:${name}>`, { source: "builtin" }),
		}]),
);

for (const tool of allCustomTools) {
	definitionRegistry.set(tool.definition.name, { ... });   // ★ 后写，自定义覆盖内置
}
```

三个来源各自被套上 `sourceInfo` 标明出身：`<builtin:read>` / `<sdk:xxx>` / 扩展自己的路径。**尖括号合成标识**跟 04 篇内联扩展的 `<inline>` 是同一个约定。

**覆盖方向：内置铺底，自定义后写。** 所以扩展可以用同名工具替换掉内置的 `read`——这是有意留的口子。

`isAllowedTool` 是统一的闸：

```typescript
const isAllowedTool = (name: string): boolean =>
	(!allowedToolNames || allowedToolNames.has(name)) && !excludedToolNames?.has(name);
```

白名单（有就必须在里面）+ 黑名单（在里面就毙），三个来源都要过。

### 2.3 提示词供稿在这里被抽出来（`:2767`）

```typescript
this._toolPromptSnippets = new Map(
	Array.from(definitionRegistry.values())
		.map(({ definition }) => {
			const snippet = this._normalizePromptSnippet(definition.promptSnippet);
			return snippet ? ([definition.name, snippet] as const) : undefined;
		})
		.filter((entry): entry is readonly [string, string] => entry !== undefined),
);
this._toolPromptGuidelines = new Map(/* 同理，收集 definition.promptGuidelines */);
```

**这是两条支流第一次交叉。** 工具定义里除了 `description`（发给模型当说明书），还能带 `promptSnippet` 和 `promptGuidelines`，这些会被拼进系统提示词（第 3、4 章）。

**"工具结算"和"提示词拼装"不是两件独立的事**，后者依赖前者的产物。

### 2.4 两份平行的注册表（`:2766-2799`）

结算的产物不是一个，是两个：

```typescript
this._toolDefinitions = definitionRegistry;                                  // ① 定义 + sourceInfo

const wrappedExtensionTools = wrapRegisteredTools(allCustomTools, runner);
const wrappedBuiltInTools   = wrapRegisteredTools(/* 内置的 */, runner);
const toolRegistry = new Map(wrappedBuiltInTools.map((tool) => [tool.name, tool]));
for (const tool of wrappedExtensionTools as AgentTool[]) toolRegistry.set(tool.name, tool);
this._toolRegistry = toolRegistry;                                           // ② 可执行的 AgentTool
```

| | `_toolDefinitions` | `_toolRegistry` |
|---|---|---|
| 元素类型 | `ToolDefinitionEntry`（definition + sourceInfo） | `AgentTool`（包装后） |
| 含渲染器 / 提示词元数据 | ✅ | ❌ 丢了 |
| 含来源信息 | ✅ | ❌ |
| 给谁用 | TUI 渲染、`/tools` 显示、诊断 | agent-core 执行、发给模型 |

**同一批工具，两种投影。** 跟 02 篇 `sessionEntryToContextMessages` 是同一个模式——**一份源数据，按消费方的需要各投一份，谁也别迁就谁**。

#### `wrapRegisteredTool` 到底干什么（`extensions/wrapper.ts:22`）

先破除一个想当然的误解，文件开头注释直说了：

```typescript
 * These wrappers only adapt tool execution so extension tools receive the runner context.
 * 包装器只调整执行入口，为扩展工具注入 runner context；它不是安全沙箱或权限检查层。
 * Tool call and tool result interception is handled by AgentSession via agent-core hooks.
 * 工具调用和结果的拦截由 AgentSession 通过 agent-core hooks 处理，不在此处重复实现。
```

**包装层不是拦截层。** 它只干两件小事。

**事一：类型适配 + 补第五个参数**（`tools/tool-definition-wrapper.ts:6`）

```typescript
export function wrapToolDefinition(definition, ctxFactory?): AgentTool {
	return {
		name: definition.name,
		label: definition.label,
		description: definition.description,
		parameters: definition.parameters,
		constrainedSampling: definition.constrainedSampling,
		prepareArguments: definition.prepareArguments,
		executionMode: definition.executionMode,
		execute: (toolCallId, params, signal, onUpdate, ctx?) =>
			definition.execute(toolCallId, params, signal, onUpdate, ctx ?? ctxFactory?.()),
			//                                                       ↑★ 唯一的实质动作
	};
}
```

注意**没被复制的**：`renderCall` / `renderResult` / `promptSnippet` / `promptGuidelines`。因为 `AgentTool` 是 agent-core 的类型，它不认识渲染器和提示词元数据——那些留在 `_toolDefinitions` 里给 TUI 和提示词拼装用。

唯一实质动作是补 `ctx`：扩展写的 `execute` 有五个参数，agent-core 调用时只传四个，包装时把 `ctxFactory()` 补上。而且是**每次调用现取**：

> 所有工具共享同一上下文工厂，但每次实际调用都会创建最新的 runner context，而非复用旧快照。

跟 04 篇第 7 章的"现查现用"同源——**不缓存派生状态，用的时候现造，永不过期**。

**事二：探测工具是否"解锁"了新工具**（`wrapper.ts:28-41`）

```typescript
execute: async (toolCallId, params, signal, onUpdate) => {
	const activeBefore = runner.getActiveTools();
	const result = await execute(toolCallId, params, signal, onUpdate);
	const activeAfter = runner.getActiveTools();
	if (!activeBefore.every((name) => activeAfter.includes(name))) return result;   // 有移除 → 不报告
	const beforeNames = new Set(activeBefore);
	const addedToolNames = activeAfter.filter((name) => !beforeNames.has(name));
	if (addedToolNames.length === 0) return result;
	return { ...result, addedToolNames: [...new Set([...(result.addedToolNames ?? []), ...addedToolNames])] };
}
```

某个工具在 `execute` 里调了 `pi.setActiveTools(...)`（比如"进入计划模式后解锁一批工具"），包装层**前后各拍一次激活清单做差集**，把新增的名字报上去，让模型下一轮能看到新工具。

**只报增量、不报减量**——第一个 `if` 一旦发现有工具被移除，原样返回不做任何报告。

为什么只关心新增、这个字段最终被谁消费，见 4.5：它不是"通知工具集变了"，而是**延迟加载的加载点标记**，整条链路是为前缀缓存服务的。

### 2.5 注册表 ≠ 发给模型的清单（`:2801-2823`）

这是本章最需要分清的一处：

```text
_toolRegistry     = 这个会话【知道】哪些工具        （全集）
activeToolNames   = 这一轮【真发给模型】哪些工具    （子集）★ Context.tools 的来源
```

`/tools` 面板里勾掉的工具仍在注册表里，只是不发给模型。结算的最后一段就是在算重算之后这些开关状态怎么办：

```typescript
const nextActiveToolNames = (
	options?.activeToolNames ? [...options.activeToolNames] : [...previousActiveToolNames]
).filter((name) => isAllowedTool(name));                     // ★ 默认沿用旧激活清单

if (allowedToolNames) {
	for (const toolName of this._toolRegistry.keys())          // 白名单模式：白名单里的全开
		if (allowedToolNames.has(toolName)) nextActiveToolNames.push(toolName);
} else if (options?.includeAllExtensionTools) {
	for (const tool of wrappedExtensionTools) nextActiveToolNames.push(tool.name);   // 全开模式
} else if (!options?.activeToolNames) {
	for (const toolName of this._toolRegistry.keys())
		if (!previousRegistryNames.has(toolName))                // ★ 默认模式：只开【新出现】的
			nextActiveToolNames.push(toolName);
}
this.setActiveToolsByName([...new Set(nextActiveToolNames)]);
```

`previousRegistryNames` 是函数开头拍的快照（`:2734`）：

```typescript
const previousRegistryNames = new Set(this._toolRegistry.keys());   // 重算前，注册表里有谁
```

**注册表新旧对比，只有新增的名字才自动激活。** 这一条规则同时满足两个矛盾的需求：

| | 若不做新旧对比 | 现在的做法 |
|---|---|---|
| 你手动关掉的 `bash` | 被重新打开 ❌ | 保持关闭 ✅ |
| 扩展运行期新注册的工具 | 需要手动去开 ❌ | 自动可用 ✅ |

写成"注册表里全部激活"就毁了第一行；写成"完全沿用旧清单"新工具永远出不来。**"沿用旧状态 + 只补新增"是唯一同时成立的规则。**

默认激活的只有四个（`:2870`）：

```typescript
const defaultActiveToolNames = ["read", "bash", "edit", "write"];
```

### 2.6 `setActiveToolsByName`：名字换对象，顺带重建提示词（`:1038`）

```typescript
setActiveToolsByName(toolNames: string[]): void {
	const tools: AgentTool[] = [];
	const validToolNames: string[] = [];
	for (const name of toolNames) {
		const tool = this._toolRegistry.get(name);
		if (tool) {                        // ★ 查不到静默跳过
			tools.push(tool);
			validToolNames.push(name);
		}
	}
	this.agent.state.tools = tools;       // ★ 落点

	// Rebuild base system prompt with new tool set
	this._baseSystemPrompt = this._rebuildSystemPrompt(validToolNames);
	this.agent.state.systemPrompt = this._systemPromptOverride ?? this._baseSystemPrompt;
}
```

三件事：

① **名字 → 对象。** 查不到的静默丢弃，用 `validToolNames` 记录真正生效的那些。给一批不存在的名字不会炸。

② **落到 `agent.state.tools`。** 工具清单的旅程到此为止，剩下的是每轮取用。

③ **顺手重建系统提示词。** 这是两条支流第二次交叉，而且更硬：

```text
激活工具集变了  →  systemPrompt 必须跟着重建
```

因为 `_rebuildSystemPrompt(validToolNames)` 收的正是**生效的工具名**，要据此抽取 `promptSnippet` / `promptGuidelines`。**开关一个工具，不只是 `tools` 数组变了，`systemPrompt` 也变了。**

### 2.7 `Context.tools` 的双重身份

模型吐回来的 `toolCall` 块里**只有名字和参数，没有实现**：

```json
{ "type": "toolCall", "id": "toolu_01x", "name": "git_recent", "arguments": { "count": 5 } }
```

要真去执行，得拿这个 `name` 回查——查的正是 `Context.tools`。03 篇的 T3 段里查了两次：

**① 决定串行还是并行**（`agent-loop.ts:449-456`）

```typescript
const toolCalls = assistantMessage.content.filter((c) => c.type === "toolCall");
const hasSequentialToolCall = toolCalls.some(
	(tc) => currentContext.tools?.find((t) => t.name === tc.name)?.executionMode === "sequential",
);
if (config.toolExecution === "sequential" || hasSequentialToolCall) {
	return executeToolCallsSequential(...);
}
return executeToolCallsParallel(...);
```

`executionMode` 只存在于工具定义里，只能查表拿到。`.some(...)` 意味着**只要有一个工具声明 `sequential`，整批退回串行**（03 篇记的"一个 sequential 拖累全批"）——因为 `sequential` 的语义是"我不能和别人同时跑"，批次里就没有安全的并行划分了。

注意 `?.executionMode`：查不到时整个表达式是 `undefined`，**不算 sequential**。这里不处理"找不到"，留给下一处。

**② 取出真正要用的实现**（`agent-loop.ts:631-645`）

```typescript
const tool = currentContext.tools?.find((t) => t.name === toolCall.name);
if (!tool) {
	return { kind: "immediate", result: createErrorToolResult(`Tool ${toolCall.name} not found`), isError: true };
}
const preparedToolCall = prepareToolCallArguments(tool, toolCall);   // 用 tool.prepareArguments
const validatedArgs = validateToolArguments(tool, preparedToolCall); // 用 tool.parameters 校验
// → 最后调 tool.execute
```

`kind: "immediate"` 的意思是"不用真执行，结果已经有了"。它和正常路径共用同一个返回类型，所以上层不必区分"没找到"和"执行失败"——**都变成一条 `toolResult` 消息回到对话里**，模型下一轮读到 `Tool xxx not found` 自行纠正。同一函数里 `signal?.aborted`、`beforeResult?.block` 走的也是这个形状：**中断、被扩展拦截、工具不存在，三种原因同一种表达**（`generated/robustness-and-cost` 讲的"错误即数据"的兑现）。

`if (!tool)` 不是防御性冗余，几条路径都会真走到：模型幻觉编了个名字；某工具执行时调 `setActiveTools` 关掉了同批次里的另一个；模型基于上一轮的清单作答而这一轮清单变了。

**小结**

```text
发出去时  →  convertTools 序列化成 JSON schema，告诉模型"你可以调这些"    说明书
回来时    →  .find(t => t.name === ...)，找到 execute 真去执行            调度表
```

**同一个数组，两个方向各用一次。** 这也是 6.1 那个 `.slice()` 快照的真正理由——**如果发出去的清单和回来查表用的清单不是同一份，就会凭空多出一批 `not found`**。快照保证说明书和调度表是同一份文件。

---

## 第 3 章 `systemPrompt` 支流（上）：备料与拼装

### 3.1 `_rebuildSystemPrompt` 凑七样料（`agent-session.ts:1144`）

它自己不拼字符串，只负责把料凑齐：

```typescript
private _rebuildSystemPrompt(toolNames: string[]): string {
	const validToolNames = toolNames.filter((name) => this._toolRegistry.has(name));

	// ① 从激活的工具里抽供稿
	const toolSnippets: Record<string, string> = {};
	const promptGuidelines: string[] = [];
	for (const name of validToolNames) {
		const snippet = this._toolPromptSnippets.get(name);
		if (snippet) toolSnippets[name] = snippet;
		const toolGuidelines = this._toolPromptGuidelines.get(name);
		if (toolGuidelines) promptGuidelines.push(...toolGuidelines);
	}

	// ② 从 ResourceLoader 取四样
	const loaderSystemPrompt       = this._resourceLoader.getSystemPrompt();          // 整体替换用
	const loaderAppendSystemPrompt = this._resourceLoader.getAppendSystemPrompt();    // 追加用（数组）
	const loadedSkills             = this._resourceLoader.getSkills().skills;
	const loadedContextFiles       = this._resourceLoader.getAgentsFiles().agentsFiles;  // AGENTS.md / CLAUDE.md

	this._baseSystemPromptOptions = {          // ★ 存下来，第 5 章要用
		cwd: this._cwd,
		skills: loadedSkills,
		contextFiles: loadedContextFiles,
		customPrompt: loaderSystemPrompt,
		appendSystemPrompt: loaderAppendSystemPrompt.length > 0 ? loaderAppendSystemPrompt.join("\n\n") : undefined,
		selectedTools: validToolNames,
		toolSnippets,
		promptGuidelines,
	};
	return buildSystemPrompt(this._baseSystemPromptOptions);
}
```

**四条线在这里汇合**：激活工具的供稿、ResourceLoader 的四类资源、cwd、工具名单本身。

`this._baseSystemPromptOptions = ...` 这个赋值不是顺手写的——扩展的 `before_agent_start` 需要拿到它（第 5 章），才能知道"当前提示词是基于什么料拼的"。

### 3.2 两条分叉：`customPrompt` 只替换主体（`system-prompt.ts:50`）

```typescript
if (customPrompt) {
	let prompt = customPrompt;                 // ← 主体被整个换掉
	if (appendSection) prompt += appendSection;
	// ...项目上下文、技能、cwd 照常追加
	return prompt;
}
// 否则走默认主体（:132 那一大段）
```

文件头注释说明了边界：

> 自定义提示会替换默认主体，但仍附加用户追加段、项目上下文、可用技能、日期和工作目录。

⚠️ 这条注释里的**"日期"已过时**——当前版本 `system-prompt.ts` 全文没有任何日期相关代码，只有 `Current working directory`。其余四样都对得上。

**可替换的是"人格与指令"，不可绕过的是"这个会话的客观事实"。**

| 段 | 性质 | 能否被替换 |
|---|---|---|
| 主体 | pi 对模型的**主张**——你是谁、怎么干活 | ✅ 你可以有自己的主张 |
| `appendSection` | 用户自己配的追加内容 | 本来就是你的 |
| `<project_context>` | 这个项目的 `AGENTS.md` **确实存在** | ❌ 客观事实 |
| skill 清单 | 这些 skill **确实装了** | ❌ 客观事实 |
| cwd | 当前**确实**在这个目录 | ❌ 客观事实 |

**"我想让模型换个人格"和"我想让模型不知道项目里有 AGENTS.md"是两回事。** 前者合理，后者会让模型在错误的前提下工作。所以 pi 的选择是：**主张可以换，事实必须给。**

#### 3.2.1 一个容易漏掉的后果：工具的提示词供稿也会一起消失

`Available tools` 和 `Guidelines` **属于主体**，被 `customPrompt` 一起替换掉了：

```text
❌ 一起消失（属于主体）
   "You are an expert coding assistant..."
   Available tools:  - read: Read file contents ...     ← ★
   Guidelines:       - Use read instead of cat ...      ← ★
   Pi documentation: ...

✅ 保留（客观事实类）
   appendSection / <project_context> / skill 清单 / cwd
```

对"工具"必须分两层说：

| | 配了 `customPrompt` 之后 |
|---|---|
| 工具**能不能调用** | ✅ 能，完全不受影响——走 API 的 `tools` 字段（见 4.2/4.3） |
| 工具的 `promptSnippet` | ❌ 那段清单没了 |
| 工具的 `promptGuidelines` | ❌ Guidelines 段没了 |

**这正好是第 4 章那个判断的实战验证**：清单是可删的导读（删了功能无损），但 `Guidelines` **是有损失的**——"该用 read 还是 bash""write 只用于新文件"这类跨工具取舍全没了，模型行为会明显变糙。

skill 清单则照常保留，因为它属于客观事实类。**同样是"和工具/技能有关的内容"，一个消失一个保留，判据不是主题而是性质。**

#### 3.2.2 定制的三个层次

由此可以把"做一个自定义 agent"的手段排清楚，从轻到重：

| | 手段 | 作用 | 何时生效 |
|---|---|---|---|
| ① | `appendSystemPrompt` | 在默认主体**后面**追加 | 启动时定（`ResourceLoader`） |
| ② | `customPrompt` | **替换**主体 | 启动时定（`ResourceLoader`） |
| ③ | `before_agent_start` | 链式改写最终成品 | **每轮**跑（扩展，见第 5 章） |

**多数需求用 ① 就够**——只是想加几条规则，没必要把 pi 的工具指南整段扔掉。

真要完全掌控人格才用 ②，此时你的 `customPrompt` 里**必须自己补回**：

```text
必须自己写：
  - 人格与任务定义              （本来就是你要写的）
  - 工具的使用取舍（原 Guidelines）  ← ★ 最容易漏
  - 需要的话，工具能力概览（原 Available tools）

不用写（pi 自动追加）：
  - AGENTS.md / CLAUDE.md 内容
  - skill 清单及其调用协议
  - cwd
```

③ 是唯一能**按轮次变化**的——比如进入计划模式时追加"不要修改文件"，退出时撤掉。第 5 章那套"底稿 + 覆盖层"机制就是为它准备的。

**另外注意开关的位置**：想让 `<project_context>` 或 skill 清单不出现，不能靠改提示词，得在**资源加载层**关（`--no-context-files` / `--no-skills`，或让 `read` 工具不可用）。这符合第 1 章那条时间线——**`ResourceLoader` 决定"有哪些料"，`buildSystemPrompt` 只负责"怎么拼"，不负责"要不要给"。**

### 3.3 默认分支的拼装顺序

```text
┌─ 主体 ────────────────────────────────
│  "You are an expert coding assistant operating inside pi..."
│  Available tools:
│  ${toolsList}              ← 来自 toolSnippets           ★ 3.4
│  Guidelines:
│  ${guidelines}             ← promptGuidelines + 条件生成  ★ 3.5
│  Pi documentation: ...     ← 绝对路径                     ★ 3.6
├─ appendSection             ← ResourceLoader 的追加段
├─ <project_context>         ← AGENTS.md 等，每文件一节点   ★ 3.7
├─ skills 清单               ← 仅当 read 工具可用           ★ 3.8
└─ Current working directory: ...
```

### 3.4 `Available tools` 的准入门槛（`:89-92`）

```typescript
const tools = selectedTools || ["read", "bash", "edit", "write"];
const visibleTools = tools.filter((name) => !!toolSnippets?.[name]);      // ★ 没 snippet 的不列
const toolsList = visibleTools.length > 0
	? visibleTools.map((name) => `- ${name}: ${toolSnippets![name]}`).join("\n")
	: "(none)";
```

> Available tools 只展示同时被选择且有说明片段的工具，**未提供描述的自定义工具不在此处伪造信息**。

**没写 `promptSnippet` 的工具不出现在这个列表里，但它仍在 `Context.tools` 数组里，模型照样能调。** 紧跟着那句兜底就是为此写的：

```text
In addition to the tools above, you may have access to other custom tools depending on the project.
```

详见第 4 章——这两个"工具列表"的区别是本篇最容易混的点。

### 3.5 Guidelines 按实际工具能力生成（`:96-128`）

```typescript
const addGuideline = (guideline: string): void => {
	if (guidelinesSet.has(guideline)) return;    // 去重
	guidelinesSet.add(guideline);
	guidelinesList.push(guideline);              // 但保留插入顺序
};

if (hasBash && !hasGrep && !hasFind && !hasLs) {
	addGuideline("Use bash for file operations like ls, rg, find");   // ★ 条件生成
}
for (const guideline of promptGuidelines ?? []) { addGuideline(guideline.trim()); }   // 工具供稿
addGuideline("Be concise in your responses");                                          // 永久项
addGuideline("Show file paths clearly when working with files");
```

那条 bash 指南**只在没有专用工具时才加**——有了 `grep`/`find`/`ls` 就不说了，免得和专用工具的说明打架。

**这句话不属于任何一个工具**：它是关于"当前工具集缺了什么"的推论。`bash` 的 description 不可能知道 `grep` 在不在场。这种依赖**工具集组合**的指导，只能在拼装提示词时算。

### 3.6 文档路径用绝对路径（`:82-84`）

```typescript
const readmePath = getReadmePath();   // config.ts 的路径解析，不是 __dirname
```

> 文档路径使用安装包绝对位置，避免模型错误地在当前项目中解析 pi 自身文档。

跟 CLAUDE.md 那条"路径解析必须走 `src/config.ts`"同源——pi 可能以 npm 包 / Bun 二进制 / tsx 源码三种形态运行。

### 3.7 项目上下文每个文件一个带路径的节点（`:157-164`）

```typescript
prompt += "\n\n<project_context>\n\nProject-specific instructions and guidelines:\n\n";
for (const { path: filePath, content } of contextFiles) {
	prompt += `<project_instructions path="${filePath}">\n${content}\n</project_instructions>\n\n`;
}
prompt += "</project_context>\n";
```

> 项目指令使用带来源路径的独立 XML 节点，**避免不同文件内容失去归属**。

多个 `AGENTS.md`（根目录、子包、全局）不会被拼成一坨，每个带 `path` 属性单独包起来，模型能分辨哪条规则来自哪个文件。**又是"保留归属"那个模式**——跟 `sourceInfo` 同源。

### 3.8 skills 依赖 read 工具（`:168`）

```typescript
if (hasRead && skills.length > 0) prompt += formatSkillsForPrompt(skills);
```

> 技能要求模型按需读取文件，因此只有 read 工具可用时才暴露技能清单。

**能力不具备时，不给模型看它做不到的选项。**

---

## 第 4 章 提示词三字段的分工 + 前缀缓存与延迟加载（路旁参照表）

> 本章不是路径上的一站，是理解第 2、3 章那两个"工具列表"必需的参照。
>
> 4.1–4.3 讲三个提示词字段各自去哪；4.4–4.5 顺着 `defer_loading` 这条线索挖下去，讲**前缀缓存如何把"提示词的排布顺序"变成工程约束**，并回填 2.4 节留下的"为什么只报新增"。4.6–4.8 收束回 pi 的取舍。

### 4.1 三个并列字段（`extensions/types.ts:482`）

```typescript
export interface ToolDefinition<...> {
	name: string;
	label: string;
	/** Description for LLM */
	description: string;
	/** Optional one-line snippet for the Available tools section in the default system prompt.
	    Custom tools are omitted from that section when this is not provided. */
	promptSnippet?: string;
	/** Optional guideline bullets appended to the default system prompt Guidelines section
	    when this tool is active. */
	promptGuidelines?: string[];
	parameters: TParams;
	// ...
}
```

拿 `read` 的实际值对比（`core/tools/read.ts:220-224`）：

```typescript
description: `Read the contents of a file. Supports text files and images (jpg, png, gif, webp, bmp).
  Images are sent as attachments. For text files, output is truncated to 2000 lines or 250KB
  (whichever is hit first). Use offset/limit for large files...`,

promptSnippet: "Read file contents",

promptGuidelines: ["Use read to examine files instead of cat or sed."],
```

| 字段 | 去哪 | 形式 | 回答什么 |
|---|---|---|---|
| `description` | API 的 `tools` 字段 | 长，含边界条件、截断规则 | **选定之后怎么调** |
| `promptSnippet` | system 的 `Available tools` | 一行 | 大致有哪些本事（导读） |
| `promptGuidelines` | system 的 `Guidelines` | 祈使句 | **选定之前怎么选** |

### 4.2 `description` 走的是 API 通道，不是提示词

`convertTools`（`packages/ai/src/api/anthropic-messages.ts:1344`）：

```typescript
return {
	name: tool.name,
	description: tool.description,      // ← 完整 description 走这里
	input_schema: inputSchema,
	...(cacheControl && index === tools.length - 1 ? { cache_control: cacheControl } : {}),
	...(deferLoading ? { defer_loading: true } : {}),
};
```

请求体的形态：

```json
{
  "system": "...Available tools:\n- read: Read file contents\n...",
  "messages": [...],
  "tools": [{ "name": "read", "description": "Read the contents of a file. Supports...",
              "input_schema": {...} }]
}
```

**同一个工具，对模型讲两遍，详略取决于读它的时机。** `description` 是模型已经决定调这个工具之后才看的，所以可以长；`promptSnippet` 每轮都在提示词开头被通读，所以必须短。

### 4.3 工具确实进 token 流——"提示词"的两个意思

这里必须先拆开一个歧义词。"提示词"在两种意义上被使用，混起来会得出自相矛盾的结论：

```text
【意思一】system 字段  —— 开发者手写的那段文本
【意思二】token 流     —— 模型实际读到的全部内容
```

**"工具不进提示词"说的是意思一；"工具在最前面"说的是意思二。** 两句话都对。

你发出去的 JSON：

```json
{
  "system": "You are an expert coding assistant...
             Available tools:
             - read: Read file contents          ← pi 自己加的一行清单
             ...",
  "tools": [                                      ← 独立字段，不在 system 里
    { "name": "read",
      "description": "Read the contents of a file. Supports text files and images...",
      "input_schema": {...} }
  ],
  "messages": [...]
}
```

服务端渲染给模型的 token 流（**判断**：确切格式是 Anthropic 内部实现，但下面三处代码痕迹只有在这个模型下才讲得通）：

```text
<工具定义区>                     ← tools 字段渲染到这里，最前面
  read — Read the contents of a file. Supports text files and images...
  参数 schema: { path: {...}, offset: {...} }
  bash — Execute a bash command...
</工具定义区>

You are an expert coding assistant...     ← system 字段的内容
Available tools:
- read: Read file contents                ← pi 加的那行，在这里
...

[messages]
```

**同一个工具，模型在一次请求里读到两遍**——工具定义区一遍（完整、Anthropic 格式、模型训练过），system 段一遍（一行、pi 格式）。4.4 节说的"物理冗余"就是指这个。

三处代码痕迹佐证工具确实在 token 流里、且在最前面：

- **`cache_control` 只打在最后一个工具上**（`convertTools` 里的 `index === tools.length - 1`）：提示词缓存按前缀逐字节匹配，"在最后一个工具后切一刀"只有当工具是连续有序的 token 前缀时才有意义。
- **存在 `defer_loading`**：说明工具定义有 token 成本，且位置可调——见 4.5。
- **工具计入 input tokens**：加十个工具，输入 token 会涨。

|  | `description` | `promptSnippet` |
|---|---|---|
| 在 JSON 里 | `tools[]` 数组 | `system` 字符串里 |
| 在 token 流里 | **最前面**，工具定义区 | 中间，system 段 |
| 格式谁定 | **Anthropic**，模型训练过 | **pi**，随便写 |
| 能不能省 | 不能，省了模型没法调 | 能，删了不影响功能 |

**所以"工具不在系统提示词里"的准确含义是：不在开发者手写的那段文本里**，而不是模型看不见。原生 function calling 比手写 `toolname: description` 可靠，不是机制上更高级，而是**格式约定被固化进了权重里**。

### 4.4 前缀缓存：位置决定改动的代价

工具在 token 流最前面这件事，带来一个 pi 里到处留痕的工程约束。

**提示词缓存按前缀逐字节匹配**，于是：

```text
第 N 个 token 处发生改动  →  第 N 个 token 之后的全部缓存失效
```

**同样大小的改动，代价差几个数量级，只取决于位置。** 一个跑了一阵的会话：

```text
tools     ≈  2,000 token      ← 最前面
system    ≈  3,000 token
messages  ≈ 80,000 token
─────────────────────────
合计      ≈ 85,000 token
```

扩展在第 N 轮注册了一个新工具，它自己大约 200 token。若直接塞进 `tools` 数组：

```text
tools: [read, bash, edit, plan_write]   ← 第 2,000 个 token 处变了
       ↓
后面 83,000 token 的缓存全部作废
```

**用 200 token 的新增，废掉 83,000 token 的缓存。** 按 `generated/robustness-and-cost` 的价格结构（cacheRead 约 0.1× 基础输入价），这一轮的输入成本差着近十倍。

这解释了两件事：

**① 为什么"每轮重发全部历史"在经济上成立。** 01/03 篇讲过 pi 每轮把完整历史重新发一遍。若没有前缀缓存，80k token 的会话每轮全价重发，没人用得起。**缓存不是锦上添花的优化，是这个架构能跑起来的前提。**

**② 为什么工具集中途变化是个专门要处理的问题。** 计划模式切换、扩展运行期注册工具——这些场景一旦发生往往反复发生，每次都打穿一次缓存。

### 4.5 延迟加载：把改动挪出前缀

解法不是让改动变小（200 token 已经很小了），而是**让改动落在不敏感的位置**。

#### 4.5.1 `defer_loading` 的真实语义

关键在 `packages/ai/src/utils/deferred-tools.ts` 的函数注释：

```typescript
/** Split current tools into prefix and transcript-loaded definitions. */
export function splitDeferredTools(...)
```

**`prefix` vs `transcript-loaded`**——两批工具的定义根本不在同一个地方渲染。

`params.tools` 这个 JSON 数组只是**传输清单**，告诉服务端"总共存在这些工具"。`defer_loading: true` 是在说：**别把这个渲染进开头的前缀，等看到它的 `tool_reference` 时再就地展开。**

所以 **JSON 数组位置 ≠ token 流位置**：

```text
JSON:  tools: [ read, bash, edit(cache_control), plan_write(defer_loading) ]
                                                  ↑ 数组第 4 位

token 流：
┌────────────────────────────────────────────────────────────┐
│ [immediate tools: read, bash, edit]        ← 前缀，就这些   │
│ [system prompt]                                            │
│ [messages 1..k]                                            │
│ ┌── toolResult 里的 tool_reference: plan_write ──┐         │
│ │   ★ plan_write 的完整定义在【这里】才展开       │         │
│ └────────────────────────────────────────────────┘         │
│ [messages k+1..n]                                          │
└────────────────────────────────────────────────────────────┘
                                              ↑ token 流第 k 条消息之后
```

于是新增一个 deferred 工具，变化范围是：

```text
immediate tools    一字未变  ✅ 命中
system prompt      一字未变  ✅ 命中
messages 1..k      一字未变  ✅ 命中
                   ────── 从这里往后才变 ──────
tool_reference     新增
messages k+1..n    位置后移
```

**同样是"加一个工具"，变化点从第 2,000 个 token 推到了第 60,000 个 token。** 中间那 58,000 token 的缓存全部保住。

"deferred loading" 里的 loading 是字面意思——**不是传得晚，是渲染进上下文的位置靠后**。

#### 4.5.2 拼装现场（`anthropic-messages.ts:991-1069`）

```typescript
const toolPlacement = splitDeferredTools(
	{ ...context, messages: transformedMessages },
	compat.supportsToolReferences,        // ★ 模型不支持就整体关掉
	normalizeToolName,
);
let immediateTools = toolPlacement.immediate;
let deferredTools = [...toolPlacement.deferred.values()];
if (immediateTools.length === 0 && deferredTools.length > 0) {
	immediateTools = deferredTools;       // ★ 兜底，见 4.5.4
	deferredTools = [];
}
// ...
params.tools = [
	...convertTools(immediateTools, ..., compat.supportsCacheControlOnTools ? cacheControl : undefined),
	...convertTools(deferredTools,  ..., undefined, true),   // 无缓存 + defer_loading
];
```

**顺序是"分类 → 拼接 → 打标记"，位置是结果不是原因。** 不是"排在 `cache_control` 之后所以被延迟"，而是 `splitDeferredTools` 先判定谁能延迟，拼接时才把它们放到后面——这样 `convertTools` 内部的 `index === tools.length - 1` 才能取到 immediate 那批的最后一个。

**真正起作用的是 `defer_loading: true` 这个标记，不是数组下标。** 就算把它插到第 0 位，服务端照样按延迟加载处理。

两个能力开关是独立的，任一不支持就退回最朴素的做法：

```typescript
compat.supportsToolReferences        // 不支持 → 整个延迟加载机制关掉，全进 immediate
compat.supportsCacheControlOnTools   // 不支持 → tools 数组里一个 cache_control 都不打
```

**又是那条"前提不成立就退回全量"**——这次是按模型能力退。

#### 4.5.3 谁能被延迟：`splitDeferredTools` 的单向扫描

```typescript
const deferredNames = new Set<string>();
const usedNames = new Set<string>();
for (const message of context.messages) {                    // ★ 按时间顺序，单向一遍
	if (message.role === "assistant") {
		for (const block of message.content)
			if (block.type === "toolCall") usedNames.add(normalizeName(block.name));
	} else if (message.role === "toolResult") {
		for (const name of message.addedToolNames ?? []) {
			const normalizedName = normalizeName(name);
			if (!usedNames.has(normalizedName)) deferredNames.add(normalizedName);   // ★
		}
	}
}
for (const [name, tool] of uniqueTools) {
	if (deferredNames.has(name)) deferred.set(name, tool);
	else immediate.push(tool);
}
```

`usedNames` 只累积**到当前位置为止**已经被调用过的工具名。那个 `if` 是一道**"定义必须先于使用"的闸**：

延迟加载会把工具定义从开头挪到第 k 条消息处。**如果模型在第 3 条消息就调用了它，就成了"在定义出现之前 60,000 个 token 就用了它"**——不是排序美观问题，是真的引用了尚不存在的东西。

```text
✅ 允许延迟
   消息 2  assistant  toolCall: enter_plan_mode
   消息 3  toolResult addedToolNames: ["plan_write"]   ← usedNames={enter_plan_mode}，plan_write 不在
   消息 4  assistant  toolCall: plan_write             ← 调用在出生点【之后】，合法

❌ 拒绝延迟
   消息 2  assistant  toolCall: read                   ← usedNames.add("read")
   消息 5  toolResult addedToolNames: ["read", ...]    ← read 已用过 → 不加入 deferredNames
                                                          → 落进 immediate，定义留在前缀
```

"已被调用的工具又出现在 `addedToolNames` 里"是可能的：`addedToolNames` 是**包装层差集与工具自报的并集**（见 2.4），工具自报那部分没人校验；工具集来回切换也会造成同名工具被重复声明。**这道闸不追究原因，只要此刻之前用过就一律不延迟。**

配套的守卫在 `convertToolResult`（`anthropic-messages.ts:1142`）：

```typescript
if (!deferredToolNames.has(normalizedName) || loadedToolNames.has(normalizedName)) continue;
```

- 不在 `deferredNames` 里 → 它在前缀中，**不该再发 `tool_reference`**（否则重复定义）
- 已在 `loadedToolNames` 里 → 同一工具被多条 toolResult 声明过，**只在第一次插入**

**`splitDeferredTools` 决定"谁能延迟"，`convertToolResult` 决定"在哪一条真正插入且只插一次"。** 两处配合，保证每个工具定义在整个请求里**恰好出现一次，且在首次使用之前**。

#### 4.5.4 同一个取舍出现了三次

这条链路上有三处判断，形式各异但道理相同：

| 位置 | 判断 | 不满足时 |
|---|---|---|
| `wrapper.ts:32` | 这次是不是"纯新增" | 完全不报告，让 `Context.tools` 全量重发兜底 |
| `deferred-tools.ts` | 这个工具是不是"先定义后使用" | 不延迟，塞进前缀 |
| `anthropic-messages.ts:998` | 是不是"全部都被判成延迟" | 全部提回 immediate |

第三条的理由：**"一个立即可用的工具都没有"是病态状态**——缓存断点无处可打，模型开局手上空空。宁可放弃这次优化。

**三处都是静默退回全量/前缀那条永远正确的路，不报错、不抛异常，只是少省一点钱。** 这是缓存类设计的通用底线：**缓存失效只是变贵，缓存用错是直接出错。**

#### 4.5.5 回填：为什么只报新增不报移除

2.4 节留了个尾巴——`wrapper.ts` 为什么只探测新增。现在能回答了，而且理由有两层：

**① `addedToolNames` 根本不是"通知工具集变了"，而是"延迟加载的加载点标记"。** 类型注释写得很清楚（`packages/ai/src/types.ts:490`）：

```typescript
/**
 * Names from `Context.tools` that became available after this result.
 * Providers with native deferred tool loading use this as the load point;
 * other providers ignore it and use `Context.tools` normally.
 */
addedToolNames?: string[];
```

它表达的是**位置信息**（这个工具的定义插在哪一条），而不是状态变化。"移除"没有对应的位置可言，所以全仓库不存在 `removedToolNames`。

**② 移除本来就藏不住。** `Context.tools` 每轮全量重发，少发一个就是移除了——天然生效，不需要任何标记。而且移除必然改变 `tools` 数组，缓存前缀本来就要变，没有可优化的余地。

**只有新增能被"藏"到前缀之外，移除藏不了。这套机制天生单向。**

### 4.6 由此看 pi 那份清单：一半冗余，一半不可替代

pi 没有任何"不支持原生工具调用"的降级路径（全仓库没有 `supportsTools` 之类的能力位）。所以：

| | 冗余？ | 判断 |
|---|---|---|
| `Available tools` 清单 | **是** | 信息 `tools` 字段全有且更详细。pi 自己让扩展工具**默认缺席**，说明它不是机制而是可选装饰 |
| `Guidelines` 段 | **否** | 跨工具取舍 + 工具集组合推论，`description` 装不下 |

关键的边界：

> **`description` 是"选定之后怎么用"，天然属于工具自身，走 API 的 `tools` 字段；
> `Guidelines` 是"选定之前怎么选"，天然属于工具**集合**，只能进系统提示词。**

模型读 `read` 的 description 时并不在比较 `read` 和 `bash`，所以"别拿 bash 干 read 的活"这句话写进 description 是无效的。

### 4.7 对照：skill 为什么必须走提示词（`core/skills.ts:362`）

```typescript
export function formatSkillsForPrompt(skills: Skill[]): string {
	const visibleSkills = skills.filter((s) => !s.disableModelInvocation);
	if (visibleSkills.length === 0) return "";
	const lines = [
		"\n\nThe following skills provide specialized instructions for specific tasks.",
		"Use the read tool to load a skill's file when the task matches its description.",
		"When a skill file references a relative path, resolve it against the skill directory ...",
		"", "<available_skills>",
	];
	for (const skill of visibleSkills) {
		lines.push("  <skill>");
		lines.push(`    <name>${escapeXml(skill.name)}</name>`);
		lines.push(`    <description>${escapeXml(skill.description)}</description>`);
		lines.push(`    <location>${escapeXml(skill.filePath)}</location>`);   // ★ 关键
		lines.push("  </skill>");
	}
	lines.push("</available_skills>");
	return lines.join("\n");
}
```

**skill 没有 API 通道。** 它本质上是一个 Markdown 文件，模型要用它必须自己去 `read`。所以 `location`（绝对路径）是必需的，那三句开场白是在**用自然语言约定一套调用协议**——正是"ReAct 时代"的做法。

| | 信息在哪 | 模型怎么用 | 协议谁定 |
|---|---|---|---|
| 工具 | API `tools` 字段 | 输出 `tool_use` 结构块 | 模型厂商，训练过 |
| **skill** | system 的 `<available_skills>` | 读 description 判断 → 用 read 加载文件 → 按内容行事 | **pi 自己用自然语言约定** |
| 工具的 snippet 清单 | system 的 `Available tools` | —（导读，删了不影响） | 无所谓 |

两个佐证印证这个区别：

- **`if (hasRead && ...)`**：read 工具不在就不列 skill，因为列了也加载不了。而工具没有 snippet 照样能调。
- **`disableModelInvocation` 靠"不写进提示词"实现**：提示词是模型知道 skill 存在的**唯一途径**，不列 = 对模型隐身。工具想隐藏则必须从 `activeToolNames` 里摘掉，光不写 `promptSnippet` 藏不住。

**同样是"从提示词里拿掉"，对 skill 是彻底禁用，对工具只是不做导读——因为两者的真实载体不同。**

### 4.8 一个越界的补丁

`core/tools/bash.ts:518-523`：

```typescript
const tool = wrapToolDefinition(definition);
Object.assign(tool, {
	promptSnippet: definition.promptSnippet,
	promptGuidelines: definition.promptGuidelines,
});
```

`wrapToolDefinition` 不复制这两个字段（`AgentTool` 类型里没有），这里手动补回去，给某些直接拿 `AgentTool` 的调用路径用。**侧面印证那条边界：`AgentTool` 是 agent-core 的执行契约，提示词元数据属于 coding-agent 层**，只有特殊场合才越界携带。

---

## 第 5 章 `systemPrompt` 支流（下）：每轮的覆盖与复位

### 5.1 两个字段（`agent-session.ts:420-424`）

```typescript
// Base system prompt (without extension appends) - used to apply fresh appends each turn
// 不含扩展追加内容的基础系统提示词，用于每轮重新应用最新追加内容
private _baseSystemPrompt = "";
private _baseSystemPromptOptions!: BuildSystemPromptOptions;
private _systemPromptOverride?: string;
```

取值规则在三处以完全相同的形式出现：

```typescript
this._systemPromptOverride ?? this._baseSystemPrompt
```

- `_baseSystemPrompt`：`buildSystemPrompt` 的产物，**工具集/资源变化时重建**，跨轮存活
- `_systemPromptOverride`：扩展改写的结果，**每轮清零、每轮重设**

### 5.2 为什么必须是两个字段

这是本章的核心问题。扩展改了直接写回 `_baseSystemPrompt` 不行吗？三条理由：

**① 防止累积。** 扩展的 `before_agent_start` 每轮都跑。写回底稿的话：

```text
第 1 轮：base = "You are..."        → "You are...\n[计划模式]"
第 2 轮：扩展基于已污染的 base 再加 → "You are...\n[计划模式]\n[计划模式]"
第 3 轮：三段…
```

**② 底稿要作为"原料"反复交出去。** 扩展需要一个稳定的出发点；底稿被污染的话，扩展无法判断"这段文字里哪些是我上次加的"，只能做字符串匹配去猜。

**③（决定性）两者按不同频率独立变化。** 看 `setActiveToolsByName`（`:1052`）：

```typescript
this._baseSystemPrompt = this._rebuildSystemPrompt(validToolNames);          // 重建底稿
this.agent.state.systemPrompt = this._systemPromptOverride ?? this._baseSystemPrompt;
//                              ↑★ 覆盖层仍然优先
```

**场景：一轮进行中，某工具在 `execute` 里调了 `setActiveTools`。** 底稿必须重建（工具集变了，`Available tools` 和 `Guidelines` 都要变），但扩展这一轮的改写不能丢。

| | 只有一个字段 | 分成两个 |
|---|---|---|
| 工具集变化 → 重建底稿 | 扩展的改写被冲掉 ❌ | 底稿更新，覆盖保留 ✅ |
| 一轮结束 → 清理 | 无法区分哪部分是扩展加的 ❌ | 清空覆盖层即可 ✅ |

```text
_baseSystemPrompt      ← 工具集/资源变化时重建   （事件驱动，跨轮存活）
_systemPromptOverride  ← 扩展每轮改写           （每轮驱动，一轮即弃）
              ↓
      override ?? base   ← 求值时才合成
```

**分层存储、取用时合成，别提前把层压平。** 压平了就再也拆不开——跟 01 篇会话树是同一个思路。

### 5.3 每轮怎么设（`agent-session.ts:1372-1402`）

```typescript
const result = await this._extensionRunner.emitBeforeAgentStart(
	expandedText,
	currentImages,
	this._baseSystemPrompt,          // ★ 传【底稿】，不是上一轮改过的
	this._baseSystemPromptOptions,   // ★ 拼装用的原料一并给
);

if (result?.messages) {              // 扩展注入的自定义消息，进这一轮的消息列表
	for (const msg of result.messages) {
		messages.push({
			role: "custom", customType: msg.customType,
			// Untyped extensions can pass null/missing content; normalize at ingestion.
			content: msg.content ?? [],
			display: msg.display, details: msg.details, timestamp: Date.now(),
		});
	}
}

// Apply extension-modified system prompt, or reset to base
if (result?.systemPrompt !== undefined) {
	this._systemPromptOverride = result.systemPrompt;
	this.agent.state.systemPrompt = result.systemPrompt;
} else {
	// Ensure we're using the base prompt (in case previous turn had modifications)
	this._systemPromptOverride = undefined;      // ★ 显式复位
}
```

**`else` 分支不是可有可无的。** 这轮没有扩展改写时，必须显式清掉覆盖层，否则上一轮的修改会一直粘着。**"没人改"和"改回原样"必须产生相同结果。**

**连 `systemPromptOptions` 一起传**，扩展拿到的不只是拼好的字符串，还有原料（`skills` / `contextFiles` / `selectedTools` / `toolSnippets`…），可以自己调 `buildSystemPrompt` 换参数重拼，而不是在成品字符串上做正则替换。

### 5.4 链式改写的含义（`runner.ts:1110-1153`）

04 篇第 7 章列过四种聚合语义，这里是"链式"的实例。四种的区别：

```text
【广播】     每个收到同样的输入，返回值丢弃
【收集】     每个收到同样的输入，返回值攒成数组
【短路投票】 依次问，谁先明确表态谁赢，后面不问
【链式】 ★  上一个的输出是下一个的输入，每个看到的输入都不一样
   底稿 ──► handler1 ──► X' ──► handler2 ──► X'' ──► handler3 ──► X'''
```

代码上就是一个循环外的累计变量：

```typescript
let currentSystemPrompt = systemPrompt;                    // 循环外，累计
const messages = [];

for (const ext of this.extensions) {
	for (const handler of ext.handlers.get("before_agent_start") ?? []) {
		const event = { type: "before_agent_start", prompt, images,
		                systemPrompt: currentSystemPrompt, systemPromptOptions };   // ← 用当前累计值构造
		const result = await handler(event, ctx);
		if (result?.message)                    messages.push(result.message);        // 收集
		if (result?.systemPrompt !== undefined) currentSystemPrompt = result.systemPrompt;  // 链式
	}
}
```

**同一个 handler 的返回值，两个字段走两种语义**：`message` 收集（人人有份），`systemPrompt` 链式（一棒接一棒）。

链式是"多个扩展能叠加修改同一样东西"的前提：

```typescript
// 扩展 A
pi.on("before_agent_start", (event) => ({ systemPrompt: event.systemPrompt + "\n\n本项目禁止使用 any。" }));
// 扩展 B
pi.on("before_agent_start", (event) => ({ systemPrompt: event.systemPrompt + "\n\n当前处于计划模式。" }));
```

链式下两段都在；若每个 handler 都拿到底稿，B 会覆盖 A，只剩最后一个生效。

#### 5.4.1 为什么是 `=` 而不是 `+=`

容易卡住的一点：既然是"累积"，为什么赋值是覆盖？

**因为链的"链"发生在输入端，不在输出端。**

```typescript
const event = { ..., systemPrompt: currentSystemPrompt };   // ① 把累计值【喂给】handler
const result = await handler(event, ctx);                    // ② handler 加工
currentSystemPrompt = result.systemPrompt;                   // ③ 把产出【存回】
```

**拼接动作在 handler 里，框架只做①传递和③存储。** `result.systemPrompt` 返回的已经是**改完之后的完整提示词**，不是增量片段，所以框架直接覆盖即可。

```text
event.systemPrompt  →  handler  →  result.systemPrompt
   改之前的完整版                      改之后的完整版
        ↑                                   ↓
   上一棒交过来                         交给下一棒
```

如果框架改成 `+=`，而 handler 照旧返回 `event.systemPrompt + "..."`，**整段底稿会被重复一遍**。反之若要求 handler 只返回增量片段，它就**只能追加，不能干别的**：

| handler 想干的事 | 返回全量（现行） | 只能返回增量 |
|---|---|---|
| 末尾追加 | ✅ | ✅ |
| 开头插入 | ✅ | ❌ |
| 替换某一段 | ✅ | ❌ |
| 整个换掉 | ✅ | ❌ |
| 用 `systemPromptOptions` 重拼一份 | ✅ | ❌ |

**框架不替 handler 决定加工方式**，只保证"你能看到前面所有人的成果，你的成果也会传给后面"。代价是最后一种写法（整个换掉）会丢弃前人的修改——**那是它的权利**，链式给的是能力不是约束。这也是加载顺序会影响最终结果的原因之一。

#### 5.4.2 对比同一循环里的"收集"

```typescript
if (result?.message)                    messages.push(result.message);              // 收集
if (result?.systemPrompt !== undefined) currentSystemPrompt = result.systemPrompt;  // 链式
```

**两行相邻，机制相反：**

|  | `message`（收集） | `systemPrompt`（链式） |
|---|---|---|
| 谁负责累积 | **框架**（`push`） | **handler**（自己拼） |
| handler 看得到别人的产出吗 | ❌ | ✅（`event.systemPrompt`） |
| handler 返回什么 | 自己那一份 | 完整的新版本 |
| 框架的动作 | 追加进数组 | 覆盖累计变量 |

**"收集"的产物是多份并列（数组），框架能替你合并；"链式"的产物是一份不断演化的东西，合并规则只有 handler 知道，框架无法代劳。**

### 5.5 为什么要重写 `ctx.getSystemPrompt`（`runner.ts:1117-1125`）

```typescript
const ctx = Object.defineProperties({}, Object.getOwnPropertyDescriptors(this.createContext())) as ExtensionContext;
ctx.getSystemPrompt = () => {
	// before_agent_start 链中 getSystemPrompt 返回当前累计值，而非事件开始前的静态提示词。
	this.assertActive();
	return currentSystemPrompt;
};
```

handler 有**两条路**读到当前提示词：

```typescript
(event, ctx) => ({ systemPrompt: event.systemPrompt + "..." })      // 循环内现造，永远是累计值 ✅
(event, ctx) => ({ systemPrompt: ctx.getSystemPrompt() + "..." })   // 默认实现读会话字段，本轮还没更新 ❌
```

会话字段 `this.agent.state.systemPrompt` 要等整个链跑完才更新（`:1398`）。不重写的话第二个 handler 用 `ctx.getSystemPrompt()` 就会拿到底稿，把前一个的修改冲掉。

**同一个信息的两个读取入口必须给出同一个答案**，否则 API 就藏了个陷阱：单个扩展测试完全正常，只有多个扩展并存才暴露，且极难排查。

#### 5.5.1 为什么不能用展开：`createContext()` 返回的全是 getter

代码里另一处同样写法的地方（`runner.ts:773-775`，命令上下文）配了英文注释，把理由写死了：

```text
// createContext() stay lazy. A spread would eagerly read them once and freeze the
// old values into the returned object, bypassing stale-instance checks.
// 属性描述符复制保留 getter 本身，使命令上下文同样受失效检查和最新 UI/core 绑定约束。
```

看 `createContext()` 返回什么（`runner.ts:695-731`）：

```typescript
return {
	get ui()            { runner.assertActive(); return runner.uiContext; },
	get mode()          { runner.assertActive(); return runner.mode; },
	get cwd()           { runner.assertActive(); return runner.cwd; },
	get model()         { runner.assertActive(); return getModel(); },
	get thinkingLevel() { runner.assertActive(); return runner.runtime.getThinkingLevel(); },
	// ...
};
```

**全是 `get` 访问器**，每个都干两件事：检查是否失效、读当前值。展开会当场调用它们，把返回值固化成普通字段：

```javascript
// 展开前：每次读都重新求值
{ get model() { assertActive(); return getModel(); } }
// 展开后：死值，永远不变
{ model: <展开那一刻的模型对象> }
```

两个后果，注释里都点了：

- **惰性没了**（`stay lazy`）——本轮中途换了模型，handler 读到的还是旧的。
- **失效检查被绕过**（`bypassing stale-instance checks`）——`assertActive()` 只在展开那一刻跑过一次；此后会话被替换、ctx 已失效，读 `ctx.cwd` 照样返回旧值，**该抛的错不抛了**。这正是 04 篇那两道防线之一被拆掉。

|  | `{ ...ctx }` | `defineProperties` + `getOwnPropertyDescriptors` |
|---|---|---|
| 复制的是 | 当前**值** | **取值行为** |
| getter 还活着吗 | ❌ 变成死值 | ✅ |
| `assertActive` 还生效吗 | ❌ 只跑过一次 | ✅ |

`getOwnPropertyDescriptors` 拿到的是 `{ model: { get: [Function], enumerable, configurable }, ... }`——**getter 函数本身，不是它的返回值**；`defineProperties` 再把它们原样装到新对象上。

于是整行的含义是：**造一个"除了 `getSystemPrompt` 之外与原版完全等价（含惰性与失效检查）"的副本，只替换那一个方法**，别的事件不受影响。

注意手写的那个覆盖里也调了 `this.assertActive()`——**不能因为是自己加的就漏掉这道检查**，否则副本上会多出一个比别人宽松的方法，成为绕过失效保护的口子。

**一般形式**：想局部覆盖一个对象的某个成员，而对象里有 getter 时，不能用展开。展开是"求值 + 拷贝"，描述符复制是"结构 + 行为拷贝"。改错了很隐蔽——代码照跑，只是值不再更新、检查不再触发。

### 5.6 生命周期双保险（`:1193`）

```typescript
private async _runAgentPrompt(messages: AgentMessage | AgentMessage[]): Promise<void> {
	this._isAgentRunActive = true;
	try {
		await this.agent.prompt(messages);
		while (await this._handlePostAgentRun()) { await this.agent.continue(); }
	} finally {
		this._systemPromptOverride = undefined;      // ★ finally 里清
		this._flushPendingBashMessages();
		await this._emitAgentSettled();
	}
}
```

`finally` 保证正常结束、抛错、被 abort 三条路径都清干净；5.3 的 `else` 保证"这轮没人改"不继承上轮。**进来重设，出去清空。**

#### 5.6.1 顺带认识这个函数：一次"用户回合"的边界

05 篇只用到它 `finally` 里的一行，但这个函数本身是**会话层生命周期的骨架**，值得整段看懂。它的两个调用点（`:1415` 用户 prompt、`:1639` 扩展 `sendMessage` 触发轮次）收拢了所有"跑一次 agent"的路径。

**`while` 里的"继续"和 agent 循环内部的"继续"不是一回事。** `agent.prompt()` 返回时，03 篇讲的那个 `while(true)` 已经跑完、`agent_end` 已经发过了；是**会话层**决定还要不要再来一轮（`_handlePostAgentRun`，`:1199`）：

```typescript
private async _handlePostAgentRun(): Promise<boolean> {
	const msg = this._lastAssistantMessage;
	this._lastAssistantMessage = undefined;
	if (!msg) return false;

	if (this._isRetryableError(msg) && (await this._prepareRetry(msg))) return true;   // ① 重试
	if (msg.stopReason === "error" && this._retryAttempt > 0) { /* 广播重试失败，但不再继续 */ }
	if (await this._checkCompaction(msg)) return true;                                 // ② 压缩后继续
	// The agent loop drains both queues before emitting agent_end. Any messages
	// here were queued by agent_end extension handlers and need a continuation.
	return this.agent.hasQueuedMessages();                                             // ③ 扩展补刀
}
```

第 ③ 条的注释点出一个微妙处：**agent 自己清过队列才发 `agent_end`，但 `agent_end` 的扩展处理器又能往队列里塞消息**——那批只能由外层再转一圈才送得出去。

于是循环层次比 03 篇画的多一层：

```text
_runAgentPrompt 的 while          ← 会话层：重试 / 压缩 / 扩展补刀
  └─ agent-loop 的 while(true)    ← 03 篇：follow-up
       └─ 内层 while              ← 03 篇：工具轮次
            └─ for await          ← 03 篇：SSE 事件
```

`finally` 里另外两行也各有职责：`_flushPendingBashMessages()` 把 agent 运行期间用 `!` 执行的命令结果统一落地（中途不能插进消息流）；`_emitAgentSettled()` 置 `_isAgentRunActive = false` 并唤醒等在 `waitForIdle` 上的人。

而 `_isAgentRunActive`（`:355`）是"这个会话正忙"的唯一真相来源——`isStreaming`（`:979`）、`isIdle`（`:985`）、扩展的 `ctx.isIdle()`、`prompt()` 判断该直发还是排队（steer / followUp），全依赖它。**注意它跨越整个 `while`**：中间的重试、压缩、补刀轮次仍算"忙"，不会在两轮之间短暂变成 idle，否则界面会闪、排队逻辑会错乱。

**一句话**：`_runAgentPrompt` 定义了"一个用户回合"的边界——进来上锁，里面可能跑好几轮 agent 循环，出去时无论成败都清掉本回合的临时状态（提示词覆盖层）、结算攒下的东西（bash 消息）、解锁并广播。

---

## 第 6 章 汇合：`prepareNextTurnWithContext`

### 6.1 每轮刷入（`agent-session.ts:584-598`）

```typescript
this.agent.prepareNextTurnWithContext = async (turn, signal) => {
	const previousSnapshot = await previousPrepareNextTurnWithContext?.(turn, signal);
	const previousContext = previousSnapshot?.context ?? turn.context;
	return {
		...previousSnapshot,
		context: {
			...previousContext,
			systemPrompt: this._systemPromptOverride ?? this._baseSystemPrompt,   // ★
			tools: this.agent.state.tools.slice(),                                 // ★ 拷贝
		},
		model: this.agent.state.model,
		thinkingLevel: this.agent.state.thinkingLevel,
	};
};
```

这是个每轮开始时被调的钩子，把当前的提示词和工具"刷"进 context。**所以运行期的工具增删（`refreshTools`）和提示词改写，下一轮立刻反映。**

`tools` 用 `.slice()` 拷贝：给出去的是快照，本轮执行途中 `state.tools` 再变也不影响已发出的清单。**这是"当轮固定"的落实处。**

### 6.2 最终组装（`packages/agent/src/agent-loop.ts:321`）

```typescript
// Build LLM context
const llmContext: Context = {
	systemPrompt: context.systemPrompt,
	messages: llmMessages,           // ← 02 篇：每轮现算（树 → 路径 → 消息）
	tools: context.tools,            // ← 直接取，不重算
};
```

对比很说明问题：`messages` 每轮要重新走一遍完整的组装链，`tools` 只是引用一下。**`tools` 是三个字段里最"静"的一个**——它在 `setActiveToolsByName` 时就已是最终形态（`AgentTool[]`）。这正是"结算"的意义：需要当轮固定的快照，所以提前算好存住。

### 6.3 全链路合龙

```text
                          ┌─ ResourceLoader ──► customPrompt / append / skills / AGENTS.md
                          ├─ 激活工具 ────────► promptSnippet   → Available tools
systemPrompt ─┬─ 底稿 ────┤                     promptGuidelines → Guidelines
              │           └─ cwd
              │              ↓ buildSystemPrompt()
              │           _baseSystemPrompt              ← 工具集变化时重建
              └─ 覆盖 ──── before_agent_start 链式改写 → _systemPromptOverride
                             ↓ 进来重设、finally 清空
                          override ?? base

tools ────── 盒子.tools → 摊平 → 三来源汇总 → 闸 → definitionRegistry
                                                      ├─ _toolDefinitions（TUI）
                                                      ├─ _toolPromptSnippets ──┘（供稿）
                                                      └─ _toolRegistry（wrap）
                                                            ↓ 沿用旧状态 + 只补新增
                                                    agent.state.tools → .slice()

messages ─── 会话树 → buildSessionPath → buildContextEntries → convertToLlm   （02 篇）

                          ↓ prepareNextTurnWithContext 每轮刷入
                    Context { systemPrompt, messages, tools }
                          ↓ convertTools / 消息序列化
                    HTTP 请求                                                   （02 篇）
                          ↓ SSE
                    状态机 → AssistantMessage → 落盘                             （03 篇）
```

**01–05 的闭环合上了。** 从磁盘上的会话文件和扩展文件出发，到发给模型的请求体，再从模型的字节流回到磁盘。

---

## 第 7 章 工程模式清单

1. **按变化频率选更新策略。** `messages` 每轮现算、`tools` 结算加快照、`systemPrompt` 底稿加覆盖层——同一个结构里三个字段可以各用各的方案，不必统一。
2. **先来先得贯穿始终。** 扩展摊平、目录发现去重、`getMessageRenderer`——同一个冲突规则复用到底，用户只需记一条。
3. **铺底 + 后写实现可覆盖。** 内置工具先进 Map，自定义后 `set` 覆盖同名项；覆盖能力是排列顺序的自然结果，不需要额外机制。
4. **统一闸门前置。** `isAllowedTool` 一个谓词管住白名单和黑名单，三个来源都过同一道闸。
5. **一份源数据，多种投影。** `definitionRegistry` 同时投出 `_toolDefinitions`（含渲染器，给 TUI）和 `_toolRegistry`（精简，给执行），谁也不迁就谁。
6. **适配层只做适配。** `wrapToolDefinition` 只补参数、转类型，明确声明自己不是沙箱也不是拦截层——拦截在别处用 hooks 做，不重复实现。
7. **上下文每次调用现取。** `ctx ?? ctxFactory?.()` 而非包装时快照，与"现查现用胜过缓存"同源。
8. **前后差集探测副作用。** 工具执行前后各拍一次激活清单，把新增工具报给上层；只报增量不报减量，语义收窄换取确定性。
9. **注册表与激活清单分离。** 全集与子集是两个概念，前者是"知道什么"，后者才是"发出去什么"。
10. **重算时沿用旧状态，只自动打开新增项。** 同时满足"尊重用户手动选择"和"新工具开箱即用"两个矛盾需求，靠一条规则。
11. **查不到就静默跳过，并回报真正生效的子集。** `validToolNames` 让下游拿到的永远是已验证的名单。
12. **可替换主体，不可绕过事实。** `customPrompt` 换掉人格与指令，但项目上下文、skill 清单、cwd 照常追加——**主张可以换，事实必须给**。
13. **按性质而非主题划分可替换边界。** 工具的 `Available tools`/`Guidelines` 随主体消失，skill 清单却保留；同样"和工具技能有关"，判据是它属于主张还是事实。
14. **开关放在资源加载层，不放在拼装层。** 想让某段不出现就别加载那份资源；`buildSystemPrompt` 只管"怎么拼"，不管"要不要给"。
15. **不伪造信息，宁可缺席。** 没有 `promptSnippet` 就不进清单，而不是拿 description 截断顶替；配一句兜底说明覆盖缺口。
16. **依赖工具集组合的指导只能在拼装时算。** 单个工具的 description 不可能知道别的工具在不在场。
17. **按读取时机决定详略。** 每轮通读的位置放一行，选定后才读的位置放长文。
18. **能力不具备就不暴露选项。** 没有 read 工具就不列 skill 清单。
19. **保留归属。** 每个 `AGENTS.md` 一个带 `path` 的 XML 节点，不拼成一坨——与 `sourceInfo` 同一模式。
20. **分层存储、取用时合成。** 两个正交的变化源各占一个字段，`override ?? base` 求值时才合并；提前压平就再也拆不开。
21. **"没人改"必须等价于"改回原样"。** 显式 `else` 复位 + `finally` 清空，双保险。
22. **同一信息的多个读取入口必须一致。** 重写 `ctx.getSystemPrompt` 消除 `event.systemPrompt` 与 `ctx` 之间的分歧，否则单扩展测试正常、多扩展并存出错。
23. **拷贝属性描述符以保住惰性。** `Object.getOwnPropertyDescriptors` 而非展开，既保留懒 getter 又能在副本上局部覆盖而不污染原对象。
24. **把原料一并交给扩展。** 不只给拼好的字符串，还给 `BuildSystemPromptOptions`，让扩展重拼而不是正则替换成品。
25. **快照用 `.slice()`。** 当轮固定的清单必须是拷贝，执行途中源数据变化不得影响已发出的内容——**说明书和调度表必须是同一份文件**，否则凭空多出 `not found`。
26. **前缀缓存把"排布顺序"变成工程约束。** 改动的代价不取决于它多大，而取决于它落在第几个 token；越靠前越贵。
27. **稳定的在前，易变的在后。** 内置工具（几乎不变）在前，运行期新增的挪到 transcript 中间——**排布顺序即变化频率的倒序**。
28. **不缩小改动，改而移动改动。** `defer_loading` 不让新工具的定义变小，只把它渲染的位置推到缓存断点之后。
29. **传输结构与渲染位置解耦。** JSON 里 `tools` 数组的下标不等于 token 流里的位置；一个布尔标记就能把某一项挪到几万 token 之后。
30. **定义必须先于使用。** 一旦允许调整定义的渲染位置，先后关系就不再自动成立，需要显式扫描校验（`usedNames` 单向累积）。
31. **优化的前提不成立就静默退回全量。** 同一取舍在这条链路上出现三次；**缓存失效只是变贵，缓存用错是直接出错**——正确性永远优先。
32. **协议字段表达位置，而非状态。** `addedToolNames` 是"加载点标记"不是"变更通知"，所以天生单向，全仓库不存在 `removedToolNames`。
33. **异常情况折进正常返回类型。** 工具不存在 / 被中断 / 被扩展拦截，三种原因统一成 `kind: "immediate"` 的结果，上层无需分辨，最终都变成一条 `toolResult` 回到对话里由模型自行纠正。
34. **批次内有一个不能并行，整批退回串行。** `.some()` 而非逐个划分——安全的并行子集难以判定时，放弃优化比划错代价小。
35. **链式的"链"在输入端。** 框架只负责把上一棒的产出喂给下一棒并存回结果；加工方式（追加/前插/替换/重拼）留给 handler，所以赋值是覆盖而非累加。
36. **框架能替你合并的才由框架合并。** 并列产物（`messages`）框架 `push`；演化产物（`systemPrompt`）合并规则只有 handler 知道，框架不能代劳。
37. **对象含 getter 时不可用展开做副本。** 展开是"求值+拷贝"，会固化死值并绕过 `assertActive`；描述符复制是"结构+行为拷贝"，保住惰性与检查。
38. **一个"回合"的边界用 try-finally 划定。** 进来上锁，中间可跑多轮，出去无论成败都清临时状态、结算暂存、解锁广播——中途不得短暂变回 idle。

---

## 第 8 章 复习自测

1. `Context` 三个字段各自的更新策略是什么？为什么不统一？
2. `getAllRegisteredTools` 遇到同名工具怎么办？这个规则在 pi 里还出现在哪些地方？
3. 工具的三个来源是什么？覆盖方向是哪边压哪边？为什么是这个方向？
4. `isAllowedTool` 同时实现了哪两种过滤？
5. `_toolDefinitions` 和 `_toolRegistry` 分别装什么、给谁用？为什么要两份？
6. `wrapToolDefinition` 唯一的实质动作是什么？哪些字段被它丢掉了，为什么？
7. `wrapRegisteredTool` 里那段前后差集在探测什么？为什么只报增量不报减量？
8. 注册表和激活清单的区别是什么？哪个才是 `Context.tools` 的来源？
9. `previousRegistryNames` 解决了哪两个互相矛盾的需求？
10. `setActiveToolsByName` 为什么要顺手重建系统提示词？
11. `Context.tools` 的"双重身份"指什么？回来查表的两处分别在算什么？`.some()` 意味着什么？
12. `kind: "immediate"` 表达什么？哪三种不同的原因共用它？工具"找不到"什么情况下会真的发生？
13. `_rebuildSystemPrompt` 凑齐了哪几类料？为什么要把 `_baseSystemPromptOptions` 存下来？
14. `customPrompt` 替换掉了什么、没替换掉什么？这个边界的道理是什么？
15. 配了 `customPrompt` 之后，工具还能被调用吗？工具的 `promptSnippet` / `promptGuidelines` 会怎样？
16. 同样是与工具、技能有关的内容，为什么 `Available tools` 随主体消失而 skill 清单保留？判据是什么？
17. 定制系统提示词的三个层次分别是什么？各在什么时候生效？想让 skill 清单不出现，该在哪一层动手？
18. 没写 `promptSnippet` 的扩展工具会怎样？它还能被模型调用吗？
19. `description`、`promptSnippet`、`promptGuidelines` 三者的分工是什么？判据是什么？
20. 那条 bash guideline 为什么只在没有 grep/find/ls 时才加？它为什么不能写进 bash 的 description？
21. 原生 function calling 下模型怎么知道有哪些工具？`convertTools` 里哪三处能佐证工具进了 token 流？
22. 「提示词」的两个意思分别指什么？为什么"工具不进提示词"和"工具在最前面"两句话不矛盾？
23. 同一个工具在一次请求里，模型会读到几遍？分别是什么形态？
24. 为什么改动的代价取决于它落在第几个 token？举一个具体的量级例子。
25. 为什么说"每轮重发全部历史"这个架构离了前缀缓存就不成立？
26. `defer_loading` 推迟的到底是什么？JSON 数组下标和 token 流位置是什么关系？
27. `deferred-tools.ts` 那句 `prefix and transcript-loaded` 注释为什么是决定性证据？
28. `splitDeferredTools` 里 `usedNames` 为什么必须按时间顺序单向累积？那道 `if` 在防什么？
29. 什么情况下会出现"已被调用的工具又出现在 `addedToolNames` 里"？
30. `convertToolResult` 里的两个 `continue` 条件各防什么？和 `splitDeferredTools` 怎么配合？
31. 「优化前提不成立就退回全量」这个取舍在本篇出现了几次？分别在哪？为什么退回是安全的？
32. 为什么不存在 `removedToolNames`？两层理由分别是什么？
33. pi 的 `Available tools` 清单是冗余的吗？`Guidelines` 呢？判据是什么？
34. skill 为什么必须写进系统提示词？`<location>` 为什么不可缺？
35. `disableModelInvocation` 是怎么实现的？为什么同样的手法对工具无效？
36. `_systemPromptOverride` 为什么要单独成字段？三条理由里哪条是决定性的？
37. 「链式」和「广播」「收集」「短路投票」的区别是什么？没有链式会怎样？
38. `ctx.getSystemPrompt` 为什么要在 `before_agent_start` 里被重写？不重写会出现什么样的 bug？
39. `Object.getOwnPropertyDescriptors` 而不是展开运算符，解决了什么问题？
40. `else` 分支的复位和 `finally` 的清空，各防什么？
41. `prepareNextTurnWithContext` 里的 `.slice()` 是为了什么？
42. 完整复述：一个扩展工具从磁盘文件到被模型调用，要经过哪些环节？
43. 链式改写为什么是 `currentSystemPrompt = result.systemPrompt` 而不是 `+=`？改成 `+=` 会发生什么？
44. 同一个循环里 `message` 和 `systemPrompt` 两个字段的累积机制有何不同？为什么框架能合并前者不能合并后者？
45. `{ ...ctx }` 会破坏哪两件事？`getOwnPropertyDescriptors` 拿到的到底是什么？
46. `_runAgentPrompt` 的 `while` 和 agent-loop 的 `while(true)` 分别在循环什么？"扩展补刀"那一条为什么必须由外层处理？

---

> **闭环说明**：01（会话树）→ 02（Context 出去）→ 03（Context 回来）→ 04（扩展装配线）→ 05（tools 与 systemPrompt 汇合），到此 `Context` 三个字段全部溯源到底，主循环一圈走完。
>
> **第 4 章那条横切线**：前缀缓存是本系列第一次正面撞上"成本"这个维度——它不跟数据路径走，跟钱走。`generated/robustness-and-cost` 从另一个入口讲了同一件事：Usage 五桶、cacheRead 0.1× 与 1h 写 2× 的价格结构、`cache_control` 滚动前缀怎么放、`cache-stats.ts` 归因审计器，可对照读。
>
> **仍欠**：01 篇的压缩机制四块（触发时机、摘要生成、文件操作追踪、扩展接管）；skill / prompt / theme 的加载生产端；02 篇 4.3 记的 `retainedTail` 建模差异待查。
