# 13 — 压缩：一次压缩的完整生命

> 学习系列第 13 篇。08 篇跟了压缩的**一半**——切点怎么算（`findCutPoint` / `isSplitTurn` / `boundaryStart` 接力）；本篇跟另一半：**什么时候压、谁来压、摘要怎么生成、压完怎么生效**。
>
> 压缩是 pi 里唯一会**主动改写历史**的机制。别处都是只读会话树、追加新条目；只有它会说"这段以后就用摘要代替了"。也因此它同时用到前五篇的东西：
>
> ```
> 它要读会话树       → 08
> 它要重组上下文     → 09
> 它自己发一次请求   → 10
> 扩展能接管它       → 11
> 压完 Context 变了  → 12
> ```
>
> **本篇的主路径是「一次压缩的生命」**：上下文快满 → 判定 → 编排 → 生成摘要 → 落盘 → 新上下文生效。第 1 章先解决"它到底在哪儿发生"——这是理解其余一切的前提。
>
> 所有 `文件:行号` 基于 commit `859bd29bd`。核心文件三个：`core/agent-session.ts`（触发与编排）、`core/compaction/compaction.ts`（切点与生成）、`core/compaction/utils.ts`（文件操作与序列化）。
>
> ⬜ **本篇尚未覆盖**：`generateSummaryWithUsage` 内部（摘要提示词、`reserveTokens` → `maxTokens`、重试接入）、消息序列化的 `TOOL_RESULT_MAX_CHARS` 截断、手动 `/compact` 的 `customInstructions` 路径、`branch-summarization.ts`。

## 目录

- 第 1 章 全景：压缩到底在哪一层发生
- 第 2 章 触发段：什么时候压
- 第 3 章 编排段：`_runAutoCompaction` 七步
- 第 4 章 生成段：`compact()` 是个调度器
- 第 5 章 旁路：文件操作追踪
- 第 6 章 生效段：压完怎么让新上下文起作用
- 第 7 章 工程模式清单
- 第 8 章 复习自测

---

## 第 1 章 全景：压缩到底在哪一层发生

### 1.1 四个文件，一条直线

pi 的调用链就是四个文件一个调一个，没有别的花样：

```text
interactive-mode.ts      你敲字、按回车，它接住
      │  调用
      ▼
agent-session.ts         ★ 压缩住在这里
      │  调用
      ▼
agent.ts                 存着 state.messages，管"一次只能跑一个"
      │  调用
      ▼
agent-loop.ts            10 篇讲的 T0–T6 全在这
      │  调用
      ▼
anthropic-messages.ts    组请求体、发 HTTP、收 SSE
```

| 文件 | 管什么 | 对应哪篇 |
|---|---|---|
| `interactive-mode.ts` | 键盘、界面 | — |
| **`agent-session.ts`** | **会话树(.jsonl)、扩展、工具注册表、系统提示词、压缩** | 08 / 11 / 12 |
| `agent.ts` | `state.messages`、`activeRun` 生命周期 | — |
| `agent-loop.ts` | 一轮一轮转：发请求、执行工具、再发请求 | 10 |
| `anthropic-messages.ts` | 序列化与 SSE | 09 / 10 |

### 1.2 关键定位：压缩在 agent 循环【之外】

```typescript
// agent-session.ts:1185
private async _runAgentPrompt(messages): Promise<void> {
	this._isAgentRunActive = true;
	try {
		await this.agent.prompt(messages);          // ← 这一行会跑很久
		                                            //   agent.ts → agent-loop.ts → 发好几次请求
		                                            //   直到 agent-loop 全跑完才返回
		while (await this._handlePostAgentRun()) {  // ← 返回【之后】才到这
			//        └─ 里面调 _checkCompaction    ★ 压缩在这
			await this.agent.continue();            // ← 压缩完，再让下面重跑一次
		}
	} finally { /* 清覆盖层 / 落 bash 消息 / 解锁 */ }
}
```

**压缩发生在 `agent-loop.ts` 已经全部跑完、控制权交回 `agent-session.ts` 之后。不是在循环里面。**

> ⚠️ 10 篇 6.5 原先写「自动压缩挂在 `prepareNextTurn` 上、落在 T4–T5 之间」，**那是错的**，已于 2026-08-19 更正。`prepareNextTurn`（`agent-session.ts:584`）只刷 `systemPrompt` / `tools` / `model` / `thinkingLevel`（12 篇 6.1）。

### 1.3 为什么必须在外面：快照语义

这不是设计偏好，是**数学上的必然**。看 `agent.ts` 把消息交给循环之前做了什么：

```typescript
// agent.ts:453-459
private createContextSnapshot(): AgentContext {
	return {
		systemPrompt: this._state.systemPrompt,
		messages: this._state.messages.slice(),      // ★ 拷贝
		tools: this._state.tools.slice(),            // ★ 拷贝
	};
}
```

```typescript
// agent-loop.ts:110-113
const currentContext: AgentContext = {
	...context,
	messages: [...context.messages, ...prompts],     // ★ 再拷一次
};
```

**循环拿到的是快照，不是引用。** 一次 run 从头到尾就用这一份，中途不回头看 `agent.state`，更不回头看会话树。

于是：

```text
压缩改的是 agent-session.ts 里的【会话树】
                    ↓
agent-loop.ts 手里那份【副本】不会跟着变
                    ↓
必须等它跑完 → 改完树 → 重开一次 run → 重新拷快照
```

**在循环里改没用，因为循环用的是副本。**

### 1.4 三份 `messages` 的关系

同一批消息在三处各有一份，形态与寿命都不同：

```text
agent-session.ts   .jsonl 文件 + 内存索引       永久、只增不删、树状     （08 篇）
                        ↓ buildSessionPath → buildContextEntries → convertToLlm （09 篇）
agent.ts           state.messages: AgentMessage[]  线性数组、跨 run 存活
                        ↓ createContextSnapshot()  ★ .slice()
agent-loop.ts      currentContext.messages          局部变量、run 结束就没了
```

**压缩要做的，就是让第一份变、进而让第二份被整个替换、再让第三份在下次 run 重新拷到。** 第 6 章会看到这三步在代码里就是三行。

### 1.5 "一次"在每层的含义不同

```text
一个用户回合  ⊇  一次 agent run  ⊇  一个 turn  ⊇  一次请求  ⊇  一个 SSE 事件
（_runAgentPrompt）（activeRun）    （工具轮次） （HTTP）      （一行）
```

**压缩发生在「一个回合内、两次 run 之间」的缝隙里**，不是「两个 turn 之间」。这是本章最需要记住的一句话。

---

## 第 2 章 触发段：什么时候压

入口函数 `_checkCompaction`（`agent-session.ts:2201`）。

### 2.1 两个调用点

```typescript
// ① _handlePostAgentRun 里（:1220）—— agent 跑完一轮之后
if (await this._checkCompaction(msg)) return true;      // 返回 true → 外层 agent.continue()

// ② prompt() 里（:1344）—— 用户要发新消息之前
const lastAssistant = this._findLastAssistantMessage();
if (lastAssistant) {
	await this._checkCompaction(lastAssistant, false);    // ← 第二个参数不同
}
```

入口 ② 存在的理由，注释写了：

> 发送前检查是否需要压缩，以覆盖响应被中止的情况。

```text
你提问 → 模型答到一半 → 你按 Esc
              ↓
  这轮 assistant 的 stopReason = "aborted"
              ↓
  入口 ① 会跳过它（闸 2）→ 上下文很满却没压
              ↓
  你又发一条 → 入口 ② 补查，传 skipAbortedCheck = false
```

另一处注释解释了 ② 为什么不用返回值：

> 用户的新提示词会在下方发送，因此此处不要调用 `agent.continue()`。

**同一个函数，两种后续处理**：① 压完要靠 `continue()` 让模型接着答；② 压完马上就发用户的新消息了。

### 2.2 四道闸

```typescript
const settings = this.settingsManager.getCompactionSettings();
if (!settings.enabled) return false;                                              // 闸 1

if (skipAbortedCheck && assistantMessage.stopReason === "aborted") return false;  // 闸 2

const sameModel = this.model
	&& assistantMessage.provider === this.model.provider
	&& assistantMessage.model === this.model.id;                                   // 闸 3（算出来后面用）

const compactionEntry = getLatestCompactionEntry(this.sessionManager.getBranch());
const assistantIsFromBeforeCompaction =
	compactionEntry !== null && assistantMessage.timestamp <= new Date(compactionEntry.timestamp).getTime();
if (assistantIsFromBeforeCompaction) return false;                                // 闸 4
```

四道闸在回答**同一个问题**：

> 这条 assistant 消息的 usage / 错误信息，还能不能代表"当前上下文有多满"？

| 闸 | 判什么 | 为什么数据不可信 |
|---|---|---|
| 1 | 功能开关 | 不用问 |
| 2 | 消息被中断 | 数据不完整 |
| 3 | 模型换了 | 数据针对的是别的窗口 |
| 4 | 消息比上次压缩还老 | 数据已过期 |

闸 3 的注释举了很具体的例子：

> 用户从较小上下文模型（如 opus）切换到较大上下文模型（如 codex）：**旧模型的溢出错误不应触发新模型的上下文压缩。**

闸 4 的场景更隐蔽：

```text
压缩发生（树上多了一条 compaction 条目）
   ↓
你发新消息 → 入口② → _findLastAssistantMessage()
   ↓
找到的还是压缩【之前】那条（压缩后还没跑过 agent，没有新的 assistant 消息）
   ↓
那条报的是"190k，爆了" → 不拦就立刻再压一次，甚至死循环
```

**拦法是比时间戳**：assistant 消息的时间 ≤ compaction 条目的时间 → 它是压缩前的产物，用量作废。

**四道闸全是数据有效性检验，没有一条是业务判断。**

### 2.3 Case 1 溢出：事后补救

```typescript
if (sameModel && isContextOverflow(assistantMessage, contextWindow)) {
	const willRetry = assistantMessage.stopReason !== "stop";
	if (!willRetry) {
		return await this._runAutoCompaction("overflow", false);       // 压，但不重试
	}
	if (this._overflowRecoveryAttempted) {
		this._emit({ type: "compaction_end", reason: "overflow", errorMessage:
			"Context overflow recovery failed after one compact-and-retry attempt. …" });
		return false;                                                   // 一次性保险
	}
	// …否则压完重试
}
```

#### 2.3.1 一个自然的疑问：turn 中途打满怎么办

既然压缩在循环之外，一次 run 跑到中途上下文才打满，岂不是要带着爆掉的上下文继续跑？

**不会——溢出本身就会终止循环：**

```typescript
// agent-loop.ts:209-213
if (message.stopReason === "error" || message.stopReason === "aborted") {
	await emit({ type: "turn_end", message, toolResults: [] });
	await emit({ type: "agent_end", messages: newMessages });
	return;                                           // ★ 整个循环结束
}
```

```text
轮 3   请求 → 上下文溢出，provider 报错
         ↓ stopReason = "error" → agent_end → return
       回到 agent-session.ts
         ↓ _handlePostAgentRun → _checkCompaction → Case 1 → 压
         ↓ agent.continue() 用短上下文重跑
```

**"溢出把控制权交还给会话层"这件事，是循环自己做的。** 压缩不需要在循环内蹲守，只要守住出口——而溢出必然走那个出口。

#### 2.3.2 `isContextOverflow` 认三种信号（`ai/src/utils/overflow.ts:141`）

```typescript
// 情形一：明确的错误文本
if (message.stopReason === "error" && message.errorMessage) {
	const isNonOverflow = NON_OVERFLOW_PATTERNS.some((p) => p.test(message.errorMessage!));  // 限流优先级更高
	if (!isNonOverflow && OVERFLOW_PATTERNS.some((p) => p.test(message.errorMessage!))) return true;
}
// 情形二：静默溢出（z.ai 风格）——请求"成功"，但输入用量已超窗口
if (contextWindow && message.stopReason === "stop") {
	if (message.usage.input + message.usage.cacheRead > contextWindow) return true;
}
// 情形三：length 截断（小米 MiMo 风格）——服务端把超长输入截到窗口上限，没留生成空间
if (contextWindow && message.stopReason === "length" && message.usage.output === 0) {
	if (message.usage.input + message.usage.cacheRead >= contextWindow * 0.99) return true;
}
```

**有些 provider 不报错，而是悄悄截断或硬撑着返回。** 所以不能只认错误文本，还得看用量数字；情形二三都要求传入 `contextWindow`，注释说明是为了"避免仅凭用量猜测"。

`NON_OVERFLOW_PATTERNS` 优先，防止把限流误判成溢出——**两者处理方式相反**（限流该重试，溢出该压缩）。

#### 2.3.3 "要不要压"和"要不要重跑"是两个决策

```typescript
const willRetry = assistantMessage.stopReason !== "stop";
if (!willRetry) return await this._runAutoCompaction("overflow", false);
```

对应情形二：**回答其实成功了，只是用量超窗口。** 这时压缩要做（下一轮才发得出去），但不能重试，注释写明：

> 助手回答已经完成，且 `agent.continue()` 无法从助手消息继续。

### 2.4 Case 2 阈值：事前预防

判定公式本身只有一行（`compaction.ts:246`）：

```typescript
export function shouldCompact(contextTokens, contextWindow, settings): boolean {
	if (!settings.enabled) return false;
	return contextTokens > contextWindow - settings.reserveTokens;
}
```

```typescript
export const DEFAULT_COMPACTION_SETTINGS: CompactionSettings = {
	enabled: true,
	reserveTokens: 16384,      // 留给"下一次回答 + 恢复流程"的空间
	keepRecentTokens: 20000,   // 08 篇学过：保留区大小
};
```

```text
窗口 200k：
├────────────────── 当前上下文 ──────────────────┤────16k────┤
                                                 ↑ 越过这条线就压
```

**不是"用了 80% 就压"，而是"离顶还剩不到 16k 就压"。** 按剩余量而非百分比，是因为它防的是一件绝对的事：**下一次回答写不下**。不管窗口 200k 还是 8k，模型都需要一块能装下回答的空间。

#### 2.4.1 难点在 `contextTokens` 怎么算得准

```typescript
let contextTokens: number;
const directContextTokens = assistantMessage.usage ? calculateContextTokens(assistantMessage.usage) : 0;

if (assistantMessage.stopReason === "error" || directContextTokens === 0) {
	const estimate = estimateContextTokens(this.agent.state.messages);       // ── 估算 ──
	if (estimate.lastUsageIndex === null) return false;
	// …过期检查，见 2.4.2
	contextTokens = estimate.tokens;
} else {
	contextTokens = directContextTokens;                                     // ── 真值 ──
}
```

**真值：模型自己报的**

```typescript
export function calculateContextTokens(usage: Usage): number {
	return usage.totalTokens || usage.input + usage.output + usage.cacheRead + usage.cacheWrite;
}
```

> 优先采用 provider 返回的总量，缺失时才汇总输入、输出与缓存计数，**避免重复估算已确认的历史**。

注意 `cacheRead` **算进去了**——那些内容虽然命中缓存、很便宜，但**仍然占着窗口**。**省钱和省窗口是两回事**（12 篇第 4 章讲的前缀缓存管前者，这里管后者）。

**兜底：往回找最后一条有效 usage**

触发条件是 `error` 或 usage 全零。注释说明为什么必须兜底：

> 这样即使会话持续遇到 API 错误（如 529）或异常的零 usage 响应，仍可执行压缩且**不会重置上下文计数**。

场景很实在：会话已烧到 190k，然后连撞几次 529，最新消息全是错误、没有 usage。若就此认为"上下文是 0"，压缩永远不会触发。

`estimateContextTokens` 往回扫找到最后一条有效 usage，**拿它的真值 + 它之后那段的估算**：

```text
[────────── 用最后一条真实 usage ──────────][── 之后的用估算 ──]
                                            ↑ lastUsageIndex
```

**真值与估算是拼接使用的，不是二选一**——这正是"避免重复估算已确认的历史"的含义。

#### 2.4.2 又一道"过期"检查

```typescript
const usageMsg = messages[estimate.lastUsageIndex];
if (compactionEntry && usageMsg.role === "assistant"
    && (usageMsg as AssistantMessage).timestamp <= new Date(compactionEntry.timestamp).getTime()) {
	return false;
}
```

> 被保留的压缩前消息带有反映旧有较大上下文的过期 usage，可能在刚完成压缩后立即误触发下一次压缩。

**这和闸 4 是同一个问题，但发生在更隐蔽的位置。** 闸 4 拦的是"传进来那条太老"；这里拦的是"传进来那条是新的（过了闸 4），但它没有可用 usage，往回找，找到的却是压缩之前的"。

```text
压缩前的消息  usage = 190k    ← 保留区里还留着它（08 篇：保留区原样保留）
压缩发生
压缩后的消息  529 错误，无 usage
                  ↓
          往回找 → 找到那条 190k → 以为还满着 → 又压一次 ❌
```

**保留区里的老消息带着老 usage，是压缩的固有副作用**：08 篇学的"保留区原样留下"意味着它们的 `usage` 字段也原样留下，而那些数字描述的是压缩前的世界。

**凡是要用某条消息的 usage，都得先确认它产生于压缩之后。** 这个检查在 `_checkCompaction` 里出现两次，对象不同、道理相同。

---

## 第 3 章 编排段：`_runAutoCompaction` 七步

`agent-session.ts:2318`。骨架：

```text
① 取密钥               _getSummarizationRequestAuth(this.model)
② 读会话树             const pathEntries = this.sessionManager.getBranch();
③ 算切点               const preparation = prepareCompaction(pathEntries, settings);
                       if (!preparation) return false;          ← 没得压就退出
④ 发事件 + 建中断控制器  compaction_start / _autoCompactionAbortController
⑤ 问扩展要不要接管      session_before_compact
   ├─ cancel           → 直接返回
   ├─ 给了 compaction  → 用它的
   └─ 什么都没有        → compact(…) 自己生成（发 LLM 请求）
⑥ 中断检查             if (signal.aborted) return false;
⑦ 落盘 + 刷新状态       appendCompaction → buildSessionContext → agent.state.messages
                       + 发 session_compact 事件
```

### 3.1 ① 摘要有独立的认证路径

```typescript
if (this.agent.streamFunction === streamSimple) {
	({ apiKey, headers, env } = await this._getRequiredRequestAuth(this.model));
} else {
	({ apiKey, headers, env } = await this._getSummarizationRequestAuth(this.model));
}
```

压缩是一次**独立的** LLM 调用，得自己取密钥，不能复用对话那次的——与 09 篇"最后一刻才解析密钥"同源。

### 3.2 ③ `prepareCompaction` = 08 篇的全部内容

```typescript
const preparation = prepareCompaction(pathEntries, settings);
if (!preparation) return false;
```

08 篇学的 `findCutPoint`、`boundaryStart` 接力、`isSplitTurn`、`firstKeptEntryIndex`，全在 `prepareCompaction`（`compaction.ts:738`）里面。

返回 `null` 表示"压不动"（例如保留区之外已无内容），**直接放弃，不报错**。

**此刻还没有任何 LLM 调用**——切点是纯计算。这也是它能排在 `compaction_start` 事件之前的原因：**先确认真有活干，再宣布开工**。

### 3.3 ⑤ 扩展接管：三种结局

```typescript
if (this._extensionRunner.hasHandlers("session_before_compact")) {
	const extensionResult = await this._extensionRunner.emit({
		type: "session_before_compact",
		preparation,          // ★ 把算好的切点交给扩展
		branchEntries: pathEntries,
		customInstructions: undefined,
		reason,               // "overflow" | "threshold"
		willRetry,
		signal: this._autoCompactionAbortController.signal,   // ★ 中断信号也给
	});
	if (extensionResult?.cancel) { …; return false; }          // 结局一：取消
	if (extensionResult?.compaction) {                          // 结局二：接管
		extensionCompaction = extensionResult.compaction;
		fromExtension = true;
	}
	// 结局三：什么都没返回 → 往下走，pi 自己压
}
```

这是 11 篇钩子体系里**最重量级的一个**：

| 钩子 | 扩展能干什么 |
|---|---|
| `turn_end` | 知道一声（广播） |
| `before_agent_start` | 改提示词（链式） |
| **`session_before_compact`** | **取消，或者整个替你压** |

**pi 把算好的 `preparation` 交给扩展**——扩展不必自己重算切点，可以沿用 pi 的切点、只换摘要生成方式（更便宜的模型、或纯规则）；也可以完全不理，自定 `firstKeptEntryId`。

`fromExtension` 一路带到落盘，记进 compaction 条目——**将来能查出"这次压缩是谁做的"**，第 5 章会看到它的实际后果。

### 3.4 ⑤续 摘要生成复用整条流式管线

```typescript
const compactResult = await compact(
	preparation, this.model, apiKey, headers,
	undefined,                                    // customInstructions（手动 /compact 才有）
	this._autoCompactionAbortController.signal,
	this.thinkingLevel,
	this.agent.streamFunction,                    // ★ 复用同一个流式函数
	env,
	this.settingsManager.getRetrySettings(),      // ★ 重试策略也复用
	this._summarizationRetryCallbacks({ source: "compaction", reason }),
);
```

**摘要走的是和正常对话完全相同的那条管线**（10 篇学的 SSE 解析、状态机全部适用），不是另起一套。

### 3.5 ⑥ 中断检查的位置：生成之后、落盘之前

```typescript
if (this._autoCompactionAbortController.signal.aborted) {
	this._emit({ type: "compaction_end", reason, result: undefined, aborted: true, willRetry: false });
	return false;
}
```

摘要生成可能要几十秒，期间按 Esc 会触发 `_autoCompactionAbortController`。这一步卡在落盘之前，意味着：

```text
生成到一半被中断 → 摘要可能不完整 → 绝不落盘 → 会话树纹丝未动
```

**要么完整压缩并落盘，要么什么都没发生。没有中间状态。**

---

## 第 4 章 生成段：`compact()` 是个调度器

`compaction.ts:849`。它本身几乎没有逻辑，只决定**发几次请求、怎么拼结果**。

```text
preparation 解构出 8 个字段
      ↓
isSplitTurn && turnPrefixMessages.length > 0 ?
      ├─ 是 → 发【两次】请求：历史摘要 + 轮前缀摘要 → 按固定结构拼接
      └─ 否 → 发【一次】请求：历史摘要
      ↓
无论哪条路：追加文件清单（纯计算，不发请求）
      ↓
返回 { summary, firstKeptEntryId, tokensBefore, usage, details }
```

### 4.1 普通情况：一次请求

```typescript
const result = await generateSummaryWithUsage(
	messagesToSummarize,      // ★ 要摘要的那段（08 篇算出来的）
	model, settings.reserveTokens, apiKey, headers, signal,
	customInstructions,       // 手动 /compact 时用户可加要求
	previousSummary,          // ★ 上一次的摘要
	thinkingLevel, streamFn, env, retry, callbacks,
);
```

**`previousSummary`：上一次压缩的产出要喂给这一次。**

```text
第一次压缩：摘要 A（覆盖消息 0–50）
第二次压缩：摘要 B ← 输入 = previousSummary(A) + 消息 51–120
```

不传的话，第二次摘要只覆盖 51–120，**前 50 条的信息彻底消失**。

**两个接力，各管一头**：08 篇的 `boundaryStart` 接力保证"每条原始记录最多被摘要一次"（管输入范围）；`previousSummary` 保证"已被摘要的内容不会因再次压缩而丢失"（管信息传承）。

**`reserveTokens` 在这里换了用途**：阈值判定里它是"什么时候压"，这里是"摘要能写多长"。同一个配置项，两处含义。

### 4.2 复习：什么是"切在轮中间"

先把 08 篇的概念补回来。会话里的消息是**成组**的，一组 = 一轮：

```text
轮 1  ┌ user        "帮我看看 config.ts"
      │ assistant   "好的" + toolCall(read)
      │ toolResult  <config.ts 的内容>
      │ assistant   "这个文件里…" + toolCall(read)
      │ toolResult  <另一个文件>
      └ assistant   "结论是…"          ← 不再调工具，本轮结束
```

**一轮 = 从一条 `user` 开始，到模型不再调工具为止。**

切点不能随便选（`compaction.ts:320`）：

```typescript
function isCutPointMessage(message: AgentMessage): boolean {
	switch (message.role) {
		case "user": case "assistant": case "bashExecution":
		case "custom": case "branchSummary": case "compactionSummary":
			return true;
		case "toolResult":
			return false;          // ★ 唯一被禁的
	}
}
```

> `toolResult` 必须与其 `toolCall` 保持相邻，因此只能随前面的 assistant 消息一起保留，**不能单独成为新上下文开头**。

而"轮的开头"比切点更严（`:335`），**差别只有 `assistant` 一行**：

```typescript
isCutPointMessage:   user ✅  assistant ✅  toolResult ❌ …
isTurnStartMessage:  user ✅  assistant ❌  toolResult ❌ …
                                     ↑ 这里不一样
```

**`assistant` 可以被切，但它不是一轮的开头。** 于是完全可能切成这样：

```text
轮 1  ┌ user        "帮我看看 config.ts"        ┐
      │ assistant   "好的" + toolCall(read)      │ 被摘要掉
      │ toolResult  <内容>                       ┘
      ├──────────── ✂ 切点在这 ────────────
      │ assistant   "这个文件里…" + toolCall      ┐
      │ toolResult  <另一个文件>                  │ 保留
      └ assistant   "结论是…"                     ┘
```

**这就是 `isSplitTurn`——切点落在一轮中间，把一轮劈成两半。**

劈开之后协议上没问题（`assistant` 打头合法），**但语义缺了一块**：用户当初问的是什么？前面读过哪些文件？模型说"这个文件里…"——哪个文件？答案都在被摘要的那半截里。而大摘要是整个远期历史的概括，**不会专门交代紧邻的这一轮细节**。

### 4.3 轮前缀摘要：专门解释被切断的那半截

```typescript
if (isSplitTurn && turnPrefixMessages.length > 0) {
	let historyText = "No prior history.";
	if (messagesToSummarize.length > 0) {
		const historyResult = await generateSummaryWithUsage(messagesToSummarize, …);   // 请求 1
		historyText = historyResult.text;
		historyUsage = historyResult.usage;
	}
	const turnPrefixResult = await generateTurnPrefixSummary(turnPrefixMessages, …);   // 请求 2
	summary = `${historyText}\n\n---\n\n**Turn Context (split turn):**\n\n${turnPrefixResult.text}`;
	summaryUsage = historyUsage ? combineUsage(historyUsage, turnPrefixResult.usage) : turnPrefixResult.usage;
}
```

| | 摘要什么 | 目的 | 预算 |
|---|---|---|---|
| 请求 1 `generateSummaryWithUsage` | 被压缩的远期历史 | 保住信息不丢 | `reserveTokens` |
| 请求 2 `generateTurnPrefixSummary` | 被切断那一轮的前半截 | 让保留区读得懂 | **`reserveTokens / 2`** |

`generateTurnPrefixSummary` 的注释（`:956-957`）：

> 轮前缀只承担**解释保留后缀**的职责，因此使用 `reserveTokens` 的一半作为更紧凑的输出预算。

**它不求全，只求让后面接得上**，所以预算减半。

`historyText = "No prior history."` 这个默认值说明两者独立：**可能没有历史要压**（第一次压缩就撞上 split turn），**但轮前缀必须摘要**，否则保留区开头就是一堆没头没尾的工具结果。

`combineUsage` 把两次请求的用量相加——**一次压缩的成本要算全**。

### 4.4 两段不重叠：`historyEnd` 那一行

一个自然的疑问：大摘要是不是也覆盖了轮前缀那段，只是轮前缀更详细？

**不是。两段首尾相接、互不重叠。** 关键在这一行（`compaction.ts:777`）：

```typescript
const historyEnd = cutPoint.isSplitTurn ? cutPoint.turnStartIndex : cutPoint.firstKeptEntryIndex;
// 分割单轮时，常规历史摘要止于该轮起点；轮内前缀由独立摘要承接，防止重复覆盖。
```

```typescript
for (let i = boundaryStart; i < historyEnd; i++) { … messagesToSummarize.push(msg); }
if (cutPoint.isSplitTurn) {
	for (let i = cutPoint.turnStartIndex; i < cutPoint.firstKeptEntryIndex; i++) { … turnPrefixMessages.push(msg); }
}
```

而 split 时 `historyEnd === turnStartIndex`：

```text
索引：  0 ────────────── 20 ──────────── 24 ──────────►
        boundaryStart    turnStartIndex   firstKeptEntryIndex
        ├─ 大摘要 ──────┤
                        ├─ 轮前缀 ──────┤
                                        ├─ 保留区 ─►
        └── 前一段的终点 = 后一段的起点，三段严丝合缝 ──┘
```

对比不 split：`historyEnd = firstKeptEntryIndex`，只有两段。

**split 不是"多了一段重叠的"，而是把原本属于大摘要的尾巴切出来单独处理。总覆盖范围完全一样。**

不重叠的三个理由：

1. **省钱**——重叠的话那段消息要塞进两次请求的输入。
2. **摘要会打架**——同一件事被两种粒度描述，模型可能当成两件事。
3. **分工干净**——一个管"记住"，一个管"接上"。

### 4.5 一个防御的位置值得商榷

```typescript
if (!firstKeptEntryId) {
	throw new Error("First kept entry has no UUID - session may need migration");
}
```

08 篇学过"存 id，算 index"——`firstKeptEntryId` 是要持久化的 uuid。老会话文件可能没有，这里**直接抛错要求迁移，而不是编一个**。

但它抛在**所有请求都发完之后**——摘要白生成了。**判断**：放在函数开头更省钱，现有位置是可改进点。

---

## 第 5 章 旁路：文件操作追踪

压缩是有损的，但"这个会话读过 / 改过哪些文件"这条信息**丢不起**——模型如果记错自己改过哪个文件，可能重复修改、漏改，或去改一个根本没碰过的文件。

所以 pi 把它**单独抽出来，不经过 LLM 摘要**。

### 5.1 提取：只认三个工具的 `path`（`utils.ts:32`）

```typescript
export function extractFileOpsFromMessage(message, fileOps): void {
	if (message.role !== "assistant") return;              // 只看 assistant
	for (const block of message.content) {
		if (block.type !== "toolCall") continue;             // 只看其中的 toolCall
		const args = block.arguments as Record<string, unknown>;
		const path = typeof args.path === "string" ? args.path : undefined;
		if (!path) continue;
		switch (block.name) {
			case "read":  fileOps.read.add(path);    break;
			case "write": fileOps.written.add(path); break;
			case "edit":  fileOps.edited.add(path);  break;
		}
	}
}
```

**硬编码的三个工具名、一个参数名。** `grep`/`find`/`ls` 不算（不针对具体文件）；扩展注册的自定义工具也不算，哪怕它真改了文件。

举例，会话里有这些消息：

```javascript
{ role: "assistant", content: [{ type: "toolCall", name: "read",  arguments: { path: "src/config.ts" } }] }
{ role: "assistant", content: [{ type: "toolCall", name: "read",  arguments: { path: "src/db.ts" } },
                               { type: "toolCall", name: "read",  arguments: { path: "src/config.ts" } }] }
{ role: "assistant", content: [{ type: "toolCall", name: "edit",  arguments: { path: "src/db.ts", edits: […] } }] }
{ role: "assistant", content: [{ type: "toolCall", name: "write", arguments: { path: "src/new-util.ts", content: "…" } }] }
```

扫完得到：

```javascript
fileOps = {
	read:    Set { "src/config.ts", "src/db.ts" },     // config.ts 读两次，Set 去重
	edited:  Set { "src/db.ts" },
	written: Set { "src/new-util.ts" },
}
```

### 5.2 合并：读过又改过的，只算改过（`utils.ts:67`）

```typescript
export function computeFileLists(fileOps) {
	const modified = new Set([...fileOps.edited, ...fileOps.written]);         // edit 与 write 合并
	const readOnly = [...fileOps.read].filter((f) => !modified.has(f)).sort(); // ★ 减去被改过的
	return { readFiles: readOnly, modifiedFiles: [...modified].sort() };
}
```

```javascript
modifiedFiles = ["src/db.ts", "src/new-util.ts"]
readFiles     = ["src/config.ts"]        // db.ts 被剔除：它被改过
```

函数注释写着 `files only read, not modified`。**对模型有用的是"我动过手的文件"**；`db.ts` 既读又改，列进"只读过"会误导。

### 5.3 输出：XML 两段（`utils.ts:78`）

```typescript
if (readFiles.length > 0)     sections.push(`<read-files>\n${readFiles.join("\n")}\n</read-files>`);
if (modifiedFiles.length > 0) sections.push(`<modified-files>\n${modifiedFiles.join("\n")}\n</modified-files>`);
```

拼在摘要末尾：

```text
<远期历史的概括…>

---

**Turn Context (split turn):**

用户要求检查数据库配置…

<read-files>
src/config.ts
</read-files>

<modified-files>
src/db.ts
src/new-util.ts
</modified-files>
```

对比一下若交给 LLM 摘要会变成什么：

```text
❌ "在对话过程中助手查看了一些配置文件并做了若干修改"
       ↑ 路径丢了，模型下一轮不知道改的是哪个

✅ <modified-files>src/db.ts</modified-files>
       ↑ 精确、完整、可累加
```

### 5.4 双形态存储与跨压缩累加

```typescript
// compact() 里
summary += formatFileOperations(readFiles, modifiedFiles);      // 形态一：文本
// …
details: { readFiles, modifiedFiles } as CompactionDetails,     // 形态二：结构化
```

> 文件读写状态同时写入**可读摘要**与**结构化 details**，下一次压缩可继续累计而无需重扫已丢弃消息。

**为什么必须存 details**：下次压缩时这批消息已被摘要替换掉，只存文本的话得重新解析自然语言；存结构化数组，下次直接续上。

```typescript
// compaction.ts:55-68
if (prevCompactionIndex >= 0) {
	const prevCompaction = entries[prevCompactionIndex] as CompactionEntry;
	if (!prevCompaction.fromHook && prevCompaction.details) {
		const details = prevCompaction.details as CompactionDetails;
		if (Array.isArray(details.readFiles))     for (const f of details.readFiles) fileOps.read.add(f);
		if (Array.isArray(details.modifiedFiles)) for (const f of details.modifiedFiles) fileOps.edited.add(f);
	}
}
for (const msg of messages) extractFileOpsFromMessage(msg, fileOps);    // 再叠加本次的
```

```text
第一次压缩  details = { readFiles: ["a.ts"], modifiedFiles: ["b.ts"] }
第二次压缩  起点 = 上次清单 + 本次新扫到的 ["c.ts"]
            → details = { readFiles: ["a.ts","c.ts"], modifiedFiles: ["b.ts"] }
```

### 5.5 扩展接管会断掉累加链

```typescript
if (!prevCompaction.fromHook && prevCompaction.details) {
```

> 仅继承 pi 自身生成的详情，**扩展接管的压缩结果不保证遵循 `CompactionDetails` 结构**。

上一次压缩若是扩展做的，它的 `details` 是任意结构，可能根本没有 `readFiles` 字段。**盲目读会拿到脏数据，所以直接跳过。**

**代价是文件清单的累加链断了。** 这是把控制权交给扩展的必然成本——**pi 选择宁可断链也不猜结构**。

### 5.6 分段处理不影响文件清单

```typescript
const fileOps = extractFileOperations(messagesToSummarize, pathEntries, prevCompactionIndex);
if (cutPoint.isSplitTurn) {
	for (const msg of turnPrefixMessages) {
		extractFileOpsFromMessage(msg, fileOps);      // ★ 轮前缀里的也要收
	}
}
```

**摘要文本可以分段，文件清单必须是全的。** 又是那条：**重要信息走独立通道，不受分段影响。**

---

## 第 6 章 生效段：压完怎么让新上下文起作用

`agent-session.ts:2426-2429`，三行：

```typescript
this.sessionManager.appendCompaction(summary, firstKeptEntryId, tokensBefore, details, fromExtension, usage);
const sessionContext = this.sessionManager.buildSessionContext();
this.agent.state.messages = sessionContext.messages;
```

对照第 1 章那三份 `messages`，这三行正是让它们依次更新：

```text
第 1 行  往【会话树】追加一条 compaction 条目           ← agent-session.ts 的世界
第 2 行  重跑 09 篇那条组装链
         buildSessionPath → buildContextEntries → convertToLlm
         （这次会走 09 篇第 4 章那个"摘要放回坑位"的分支）
第 3 行  把结果【整个赋值】给 agent.state.messages       ← agent.ts 的世界
```

**第 3 行是整数替换，不是修改。** `state.messages` 从"完整历史"被换成"摘要 + 保留区"。

然后：

```text
_checkCompaction 返回 true
  → _handlePostAgentRun 返回 true
    → agent.continue()
      → createContextSnapshot() 从【新的】state.messages 拷一份
        → agent-loop 拿到短上下文重跑        ← 第三份 messages 更新
```

**这就是第 1.3 节那个"必须在循环外"的闭环：改 state → 重开 run → 重新拷快照。**

### 6.1 `estimatedTokensAfter` 只能估

```typescript
const estimatedTokensAfter = estimateMessagesTokens(sessionContext.messages);
```

**压缩后有多少 token 只能估**——还没发过请求，模型没报过数。这个数字纯粹用于给用户显示"压缩前 190k → 压缩后约 25k"，**不参与任何判定**。

**真值用于决策，估算用于显示。** 与 2.4.1 那个"真值优先、估算兜底"是同一原则的两面。

### 6.2 落盘之后再通知扩展

```typescript
const savedCompactionEntry = newEntries.find((e) => e.type === "compaction" && e.summary === summary) as CompactionEntry | undefined;
if (this._extensionRunner && savedCompactionEntry) {
	await this._extensionRunner.emit({ type: "session_compact", compactionEntry: savedCompactionEntry, fromExtension, reason, willRetry });
}
```

**两个压缩事件，一前一后，性质不同：**

| 事件 | 时机 | 扩展能干什么 |
|---|---|---|
| `session_before_compact` | 落盘前，切点已算好 | **取消 / 接管**（有决策权） |
| `session_compact` | **落盘后** | 知道一声（广播） |

后者传的是**已保存的条目**（从 `getEntries()` 里找回来的，带 id 和 timestamp），不是内存里那份——**扩展拿到的是最终事实**。

---

## 第 7 章 工程模式清单

1. **快照决定了改动必须发生在哪一层。** `createContextSnapshot()` 的 `.slice()` 让循环持有副本；想让改动生效只能结束这次 run 再重开——"压缩在循环外"不是偏好而是必然。
2. **一层一个"一次"。** 回合 ⊇ run ⊇ turn ⊇ 请求 ⊇ 事件；说清楚在哪一层做，比说清楚做什么更重要。
3. **判定之前先验数据。** 四道闸全在检验"这条 usage 还能不能代表当前"；30 行代码里 25 行处理数据不可信，真正的判断只有 1 行。
4. **按剩余量而非百分比设阈值。** 防的是"下一次回答写不下"，那是绝对量，与窗口大小无关。
5. **真值优先、估算兜底、二者拼接。** 用最后一条有效 usage 覆盖历史，只对其后新增的部分估算——不重复估算已确认的历史。
6. **决策用真值，显示用估算。** `estimatedTokensAfter` 只进 UI，不进任何判断。
7. **省钱和省窗口是两回事。** `cacheRead` 计入上下文占用，尽管它计费便宜。
8. **同一个数字换一个位置就换一种含义。** `reserveTokens` 在阈值判定里是"何时压"，在生成里是"摘要能写多长"。
9. **有损压缩的固有副作用要显式对冲。** 保留区里的老消息带着老 usage；凡用某条消息的 usage 都要先验证它产生于压缩之后（同一检查出现两次）。
10. **让失败自己交还控制权。** 溢出使 `stopReason === "error"`，循环当场 `return`——压缩只需守住出口，无需在循环内蹲守。
11. **同一现象的多种表现要一起认。** `isContextOverflow` 认错误文本、静默超窗、length 截断三种信号；限流模式优先级更高，防止误判。
12. **"要不要压"与"要不要重跑"是两个决策。** 回答已完成但超窗时压而不重试。
13. **不可收敛的补救给一次机会。** `_overflowRecoveryAttempted` 防止压不动时死循环，转而给出可操作的建议。
14. **先确认有活干，再宣布开工。** `prepareCompaction` 是纯计算且可能返回 `null`，排在 `compaction_start` 事件之前。
15. **把中间产物交给接管者。** `session_before_compact` 传的是已算好的 `preparation`，扩展可只替换生成方式而不必重算切点。
16. **原子性靠"检查点位置"实现。** 中断检查卡在生成之后、落盘之前：要么完整压缩并落盘，要么什么都没发生。
17. **两个接力各管一头。** `boundaryStart` 管输入范围（每条记录最多被摘要一次），`previousSummary` 管信息传承（摘要过的不因再压而丢失）。
18. **分段处理不重叠。** `historyEnd` 在 split 时退到轮起点，把尾巴交给专门的摘要；省钱、避免两种粒度打架、职责清晰。
19. **按职责分配预算。** 轮前缀只需"让后文读得懂"，故用 `reserveTokens / 2`。
20. **重要到经不起有损的信息走独立通道。** 文件路径不交给 LLM 摘要，而是结构化提取、合并、累加。
21. **同一份信息按消费方存两种形态。** 文件清单以文本进摘要（给模型），以数组进 `details`（给下次压缩累加）。
22. **归属信息要能反查。** `fromExtension` 一路带到落盘，既用于诊断，也用于判断 `details` 结构是否可信。
23. **宁可断链也不猜结构。** 扩展接管过的 `details` 不继承——把控制权交出去的必然成本。
24. **决策事件在前、通知事件在后。** `session_before_compact` 可取消可接管，`session_compact` 只广播且传已保存的条目。

---

## 第 8 章 复习自测

1. 压缩发生在哪个文件、哪一层？为什么**不能**放在 agent 循环内部？（快照那条理由）
2. 三份 `messages` 分别在哪、寿命多长？压缩要让哪几份依次更新？
3. "一个回合""一次 run""一个 turn"分别由谁界定？压缩发生在哪两者之间的缝隙？
4. `_checkCompaction` 的两个调用点分别在什么时机？为什么入口 ② 传 `skipAbortedCheck = false` 且不使用返回值？
5. 四道闸各拦什么？它们回答的是同一个什么问题？
6. 闸 3 防的是哪种具体场景？
7. 闸 4 与 2.4.2 那道检查有何异同？为什么同一件事要查两遍？
8. `shouldCompact` 的公式是什么？为什么按剩余量而不是百分比？
9. `calculateContextTokens` 为什么把 `cacheRead` 算进去？
10. 什么情况下真值不可用？兜底时"真值 + 估算"是怎么拼接的？
11. 为什么保留区里的老消息会带着"过期的 usage"？这是谁的副作用？
12. 一次 agent run 跑到中途上下文才打满，会发生什么？压缩为什么不需要在循环内蹲守？
13. `isContextOverflow` 认哪三种信号？为什么后两种必须传 `contextWindow`？
14. `NON_OVERFLOW_PATTERNS` 为什么优先级更高？
15. 什么情况下"压但不重试"？理由是什么？
16. `_runAutoCompaction` 的七步是什么？
17. `prepareCompaction` 返回 `null` 意味着什么？为什么它排在 `compaction_start` 事件之前？
18. `session_before_compact` 的三种结局是什么？pi 为什么把 `preparation` 也传给扩展？
19. 中断检查为什么卡在"生成之后、落盘之前"？换个位置会怎样？
20. 什么是"切在轮中间"？`isCutPointMessage` 与 `isTurnStartMessage` 的唯一差别是什么，为什么这个差别导致了 split turn？
21. 劈开一轮之后，协议上有问题吗？语义上缺了什么？
22. 轮前缀摘要的职责是什么？为什么预算只有一半？
23. 大摘要包含轮前缀那段吗？`historyEnd` 那一行是怎么保证的？不重叠有哪三个好处？
24. `previousSummary` 解决什么问题？它和 `boundaryStart` 接力分别管什么？
25. 文件操作追踪只认哪三个工具、哪个参数？`grep` 为什么不算？
26. 读过又改过的文件会出现在哪个清单里？为什么？
27. 文件清单为什么要同时存成文本和结构化两种形态？
28. 上一次压缩若由扩展接管，这次的文件清单会怎样？为什么 pi 宁可这样？
29. 压缩生效的三行代码分别做了什么？之后靠什么让 agent-loop 拿到新上下文？
30. `estimatedTokensAfter` 为什么只能估？它参与判定吗？
31. `session_before_compact` 与 `session_compact` 有何不同？后者为什么传"已保存的条目"？

---

> **接下来**：`generateSummaryWithUsage` 内部（摘要提示词长什么样、`reserveTokens` 如何变成 `maxTokens`、重试如何接入）、消息序列化的 `TOOL_RESULT_MAX_CHARS` 截断、手动 `/compact` 的 `customInstructions` 路径，以及 `branch-summarization.ts`（431 行，与压缩共用基础设施）。
