# 06 — 压缩：一次压缩的完整生命

> 学习系列第 6 篇。01 篇跟了压缩的**一半**——切点怎么算（`findCutPoint` / `isSplitTurn` / `boundaryStart` 接力）；本篇跟另一半：**什么时候压、谁来压、摘要怎么生成、压完怎么生效**。
>
> 压缩是 pi 里唯一会**主动改写历史**的机制。别处都是只读会话树、追加新条目；只有它会说"这段以后就用摘要代替了"。也因此它同时用到前五篇的东西：
>
> ```
> 它要读会话树       → 01
> 它要重组上下文     → 02
> 它自己发一次请求   → 03
> 扩展能接管它       → 04
> 压完 Context 变了  → 05
> ```
>
> **本篇的主路径是「一次压缩的生命」**：上下文快满 → 判定 → 编排 → 生成摘要 → 落盘 → 新上下文生效。第 1 章先解决"它到底在哪儿发生"——这是理解其余一切的前提。
>
> 所有 `文件:行号` 基于 commit `859bd29bd`。核心文件三个：`core/agent-session.ts`（触发与编排）、`core/compaction/compaction.ts`（切点与生成）、`core/compaction/utils.ts`（文件操作与序列化）。
>
> ⬜ **本篇尚未覆盖**：`prepareBranchEntries` 的 `tokenBudget` 裁剪策略（见 7.2 末尾）。

## 目录

- 第 1 章 全景：压缩到底在哪一层发生
- 第 2 章 触发段：什么时候压
- 第 3 章 编排段：`_runAutoCompaction` 七步
- 第 4 章 生成段：从消息到一段摘要
- 第 5 章 旁路：文件操作追踪
- 第 6 章 生效段：压完怎么让新上下文起作用
- 第 7 章 同一套机制的另外两个入口
- 第 8 章 工程模式清单
- 第 9 章 复习自测

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
agent-loop.ts            03 篇讲的 T0–T6 全在这
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

> ⚠️ 03 篇 6.5 原先写「自动压缩挂在 `prepareNextTurn` 上、落在 T4–T5 之间」，**那是错的**，已于 2026-08-19 更正。`prepareNextTurn`（`agent-session.ts:584`）只刷 `systemPrompt` / `tools` / `model` / `thinkingLevel`（05 篇 6.1）。

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
agent-session.ts   .jsonl 文件 + 内存索引       永久、只增不删、树状     （01 篇）
                        ↓ buildSessionPath → buildContextEntries → convertToLlm （02 篇）
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
	keepRecentTokens: 20000,   // 01 篇学过：保留区大小
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

注意 `cacheRead` **算进去了**——那些内容虽然命中缓存、很便宜，但**仍然占着窗口**。**省钱和省窗口是两回事**（05 篇第 4 章讲的前缀缓存管前者，这里管后者）。

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
压缩前的消息  usage = 190k    ← 保留区里还留着它（01 篇：保留区原样保留）
压缩发生
压缩后的消息  529 错误，无 usage
                  ↓
          往回找 → 找到那条 190k → 以为还满着 → 又压一次 ❌
```

**保留区里的老消息带着老 usage，是压缩的固有副作用**：01 篇学的"保留区原样留下"意味着它们的 `usage` 字段也原样留下，而那些数字描述的是压缩前的世界。

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

压缩是一次**独立的** LLM 调用，得自己取密钥，不能复用对话那次的——与 02 篇"最后一刻才解析密钥"同源。

### 3.2 ③ `prepareCompaction` = 01 篇的全部内容

```typescript
const preparation = prepareCompaction(pathEntries, settings);
if (!preparation) return false;
```

01 篇学的 `findCutPoint`、`boundaryStart` 接力、`isSplitTurn`、`firstKeptEntryIndex`，全在 `prepareCompaction`（`compaction.ts:738`）里面。

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

这是 04 篇钩子体系里**最重量级的一个**：

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

**摘要走的是和正常对话完全相同的那条管线**（03 篇学的 SSE 解析、状态机全部适用），不是另起一套。

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

## 第 4 章 生成段：从消息到一段摘要

本章分两半：4.1–4.5 讲 `compact()` 这个**调度器**（发几次请求、覆盖哪些消息）；4.6–4.11 讲 `generateSummaryWithUsage` 这个**执行者**（摘要长什么样、请求怎么造）。

`compact()`（`compaction.ts:849`）本身几乎没有逻辑，只决定**发几次请求、怎么拼结果**。

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
	messagesToSummarize,      // ★ 要摘要的那段（01 篇算出来的）
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

**两个接力，各管一头**：01 篇的 `boundaryStart` 接力保证"每条原始记录最多被摘要一次"（管输入范围）；`previousSummary` 保证"已被摘要的内容不会因再次压缩而丢失"（管信息传承）。

**`reserveTokens` 在这里换了用途**：阈值判定里它是"什么时候压"，这里是"摘要能写多长"。同一个配置项，两处含义。

### 4.2 复习：什么是"切在轮中间"

先把 01 篇的概念补回来。会话里的消息是**成组**的，一组 = 一轮：

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

01 篇学过"存 id，算 index"——`firstKeptEntryId` 是要持久化的 uuid。老会话文件可能没有，这里**直接抛错要求迁移，而不是编一个**。

但它抛在**所有请求都发完之后**——摘要白生成了。**判断**：放在函数开头更省钱，现有位置是可改进点。

### 4.6 摘要长什么样：一个七段模板

前面几节讲的都是"发几次请求、覆盖哪些消息"。但要看懂 `generateSummaryWithUsage`（`compaction.ts:642`）里那些参数为什么长那样，得先看**产物**——**摘要不是"随便总结一下"，而是往一个固定模板里填**。

`SUMMARIZATION_PROMPT`（`compaction.ts:486`）要求 `Use this EXACT format`：

```markdown
## Goal
[用户想达成什么？会话涉及多个任务时可以多条]

## Constraints & Preferences
- [用户提过的约束、偏好、要求]
- [或者 "(none)"]

## Progress
### Done
- [x] [已完成的任务/改动]
### In Progress
- [ ] [正在做的]
### Blocked
- [卡住的问题]

## Key Decisions
- **[决策]**: [简要理由]

## Next Steps
1. [接下来该做什么，有序]

## Critical Context
- [继续工作所需的数据、示例、引用]
```

末尾一句是硬约束：

> Keep each section concise. **Preserve exact file paths, function names, and error messages.**

摘要的定位写在提示词第一句：

> Create a structured context checkpoint summary that **another LLM will use to continue the work**.

**不是给人看的会议纪要，是给另一个模型的交接文档。** 所以要有 `Next Steps`、要保留精确路径和函数名——那是"接着干"必需的，不是"读懂"必需的。

**这也解释了第 5 章那条旁路为什么还要存在**：提示词虽然要求"保留精确路径"，但那只是**对模型的请求**，不是保证。文件清单是**代码保证**的那一份，不依赖模型听话。

有了模板，`maxTokens` 那行也就好懂了：

```typescript
const maxTokens = Math.min(
	Math.floor(0.8 * reserveTokens),                                    // 16384 × 0.8 = 13107
	model.maxTokens > 0 ? model.maxTokens : Number.POSITIVE_INFINITY,
);
```

> 摘要输出上限取 `reserveTokens` 的 **80%** 与模型 `maxTokens` 的较小值，**给调用协议和后续上下文留出余量**。

**13k token 要装下这七段**，所以提示词里反复说 `Keep each section concise`。留 20% 是因为 `reserveTokens` 本是"给下一次回答留的空间"，摘要占掉一部分后，模型还得有地方回答用户的问题。

`model.maxTokens > 0 ? … : Infinity` 是防御：有些模型配置里没填 `maxTokens`（为 0），不能拿 0 当上限。

对比之下，轮前缀摘要（4.3）用的是**第三套提示词**：

```typescript
// compaction.ts:826
const TURN_PREFIX_SUMMARIZATION_PROMPT = `This is the PREFIX of a turn that was too large to keep. The SUFFIX (recent work) is retained. …`;
```

**它不填七段模板**，只需交代"这一轮前半截发生了什么"——所以预算是一半。

### 4.7 两套提示词：同一模板的两种模式

```typescript
let basePrompt = previousSummary ? UPDATE_SUMMARIZATION_PROMPT : SUMMARIZATION_PROMPT;
if (customInstructions) {
	basePrompt = `${basePrompt}\n\nAdditional focus: ${customInstructions}`;
}
```

> 有旧摘要时执行**增量合并**，确保多次压缩不会遗失更早阶段的目标、约束与决策。

**两套提示词的七个标题一模一样，只是每段下的指示不同：**

| 段落 | 首次版 | 增量版 |
|---|---|---|
| Goal | `[用户想达成什么]` | `[保留已有目标，任务扩展了就加新的]` |
| Progress / Done | `[x] [已完成的]` | `[x] [包含之前已完成的 AND 新完成的]` |
| Progress / In Progress | `[ ] [正在做的]` | `[ ] [根据进展更新]` |
| Blocked | `[卡住的问题]` | `[当前的阻塞——已解决的要删掉]` |
| Key Decisions | `**[决策]**: [理由]` | `**[决策]**: [理由] (保留全部旧的，加新的)` |

增量版开头还多五条规则：`PRESERVE` 旧摘要全部信息 / `ADD` 新进展与决策 / `UPDATE` 完成项从 In Progress 挪到 Done / `UPDATE` Next Steps / 不再相关的可删。

**"增量"的实质是让模型做一次结构化 merge，而不是重新总结。**

#### 为什么必须换提示词，不能只是把旧摘要塞进去

假设只塞不换，用首次版的提示词，输入是 `<conversation>新 50 条</conversation>` + `<previous-summary>旧摘要</previous-summary>`，而开场白仍是：

> The messages above are a conversation to summarize.

模型会理解成"**上面是一段对话，总结它**"——去总结那 50 条新消息，把 `<previous-summary>` 当成对话的一部分或干脆忽略。**结果是旧信息丢失。**

增量版的开场白重新定义了角色：

> The messages above are **NEW** conversation messages to incorporate into the existing summary provided in `<previous-summary>` tags.

```text
首次版：  对话 ──► 摘要
增量版：  旧摘要 + 新对话 ──► 新摘要
             ↑ 主体      ↑ 增量
```

**4.1 说的 `previousSummary` 接力，代码只负责把旧摘要传过来；真正保证"信息不丢"的是这套提示词。**

`customInstructions` 是**追加而非替换**——手动 `/compact 重点关注数据库部分` 会在提示词末尾加一行 `Additional focus: 重点关注数据库部分`。

### 4.8 `serializeConversation`：一举解决两个问题

`generateSummaryWithUsage` 里这两行看着平平无奇：

```typescript
const llmMessages = convertToLlm(currentMessages);            // 先归一化（02 篇那个投影函数）
const conversationText = serializeConversation(llmMessages);  // 再拍平成文本
```

但 `serializeConversation`（`utils.ts:125`）同时解决了两个**互不相干**的问题。

#### 问题一：防止模型接着聊

> This prevents the model from treating it as a conversation to continue.

结构化的 `messages` 数组被拍成一段带前缀标签的**纯文本**：

```text
[User]: 帮我重构认证模块
[Assistant thinking]: 先看看现有结构…
[Assistant]: 好的，我先读一下相关文件
[Assistant tool calls]: read(path="src/auth.ts"); read(path="src/token.ts")
[Tool result]: export class Auth { … }
[Assistant]: 我看到 TokenValidator 和 Auth 耦合了…
```

**这就不是对话了，是对话的转录稿。** 模型没有"轮到我了"的信号可循。

若把那 50 条消息原样当作 `messages` 发过去，最后一条可能是 `user` 或 `toolResult`——那正是"该你说话了"的信号，模型会接着往下干活。

这与另外两处构成**同一目的的三道防线**：

```text
① serializeConversation      拍平成转录稿              ← 形式上不像对话
② 装进一条 user 消息          整段包进 <conversation>   ← 结构上是"材料"
③ SUMMARIZATION_SYSTEM_PROMPT  Do NOT continue…        ← 指令上明令禁止
```

系统提示词（`utils.ts:174`）三句话堵同一个洞：

```typescript
export const SUMMARIZATION_SYSTEM_PROMPT = `You are a context summarization assistant. …

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary.`;
```

**三道都做，因为这个失败模式代价大**：模型不输出摘要而接着干活，压缩彻底失败，且要到解析结果时才发现。

#### 问题二：摘要请求自身不能爆

这里有个自指的难题：

```text
要摘要的这批消息，本身就是因为【太大】才要被压缩的
                ↓
原样塞进摘要请求 → 摘要请求自己就爆了
```

解法是**工具结果截断**：

```typescript
const TOOL_RESULT_MAX_CHARS = 2000;

function truncateForSummary(text: string, maxChars: number): string {
	if (text.length <= maxChars) return text;
	const truncatedChars = text.length - maxChars;
	return `${text.slice(0, maxChars)}\n\n[... ${truncatedChars} more characters truncated]`;
}
// …
} else if (msg.role === "toolResult") {
	parts.push(`[Tool result]: ${truncateForSummary(content, TOOL_RESULT_MAX_CHARS)}`);
}
```

> 工具结果会被截断，以便将摘要请求控制在合理的 token 预算内。**生成摘要不需要工具结果的完整内容。**

**为什么单挑工具结果开刀**：它是上下文膨胀的主要来源——一次 `read` 可能返回几万字符，而 `[User]`/`[Assistant]` 通常几百字。

**为什么截断不伤质量**：摘要要记的是"读了 auth.ts、发现耦合、决定提取 TokenValidator"，**不是文件内容本身**。前 2000 字符足够判断"这次调用干了什么、结果是什么性质"。

`[... N more characters truncated]` 这个标记也必要——**告诉模型此处被截过**，免得它以为文件就这么长、据此做出错误结论。

工具调用参数则被压成一行，且**不截断**：

```typescript
const argsStr = Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
toolCalls.push(`${block.name}(${argsStr})`);
// →  [Assistant tool calls]: read(path="src/auth.ts"); grep(pattern="TokenValidator")
```

因为参数短，而且**正是摘要最需要精确保留的东西**（模板里那句 `Preserve exact file paths, function names`）。

#### 取舍梯度：判据不是长度，是"对接着干有多重要"

| 内容 | 处理 | 理由 |
|---|---|---|
| 工具**参数** | 完整保留 | 短，且是"做了什么"的精确记录 |
| 用户/助手**文本** | 完整保留 | 短，且是意图与决策所在 |
| **thinking** | 完整保留 | 决策理由在这里 |
| 工具**结果** | 截到 2000 字符 | 长，且摘要不需要内容本身 |

工具结果最长、也恰好最不需要——这不是巧合：**工具结果本来就是"原始数据"，而摘要要的是"结论"。**

#### `thinking` 为什么单独一行

```typescript
if (thinkingParts.length > 0) parts.push(`[Assistant thinking]: ${thinkingParts.join("\n")}`);
if (msg.content.some((b) => b.type === "text")) parts.push(`[Assistant]: ${contentText(msg.content)}`);
if (toolCalls.length > 0) parts.push(`[Assistant tool calls]: ${toolCalls.join("; ")}`);
```

**一条 assistant 消息可能拆成三行输出。** 保留 thinking 是因为模板里 `## Key Decisions` 要求 `**[决策]**: [简要理由]`——**理由往往只在 thinking 里**：模型对外说"我来提取 TokenValidator"，而"为什么"在思考块中。

**模板需要什么，序列化就保留什么**——这是产物格式反过来决定输入格式的地方。

### 4.9 发请求：三个刻意的选择

```typescript
// compaction.ts:581
export async function completeSummarization(model, context, options, streamFn, retry, callbacks) {
	// Summaries are standalone requests, so isolate routing and avoid cache writes that cannot be reused.
	const requestOptions: SimpleStreamOptions = { ...options, cacheRetention: "none", sessionId: uuidv7() };
	const produce = async () => streamFn ? (await streamFn(model, context, requestOptions)).result()
	                                     : completeSimple(model, context, requestOptions);
	return retryAssistantCall(produce, retry, requestOptions.signal, callbacks);
}
```

**`cacheRetention: "none"`** —— 摘要请求的前缀独一无二（那一大坨 `<conversation>`），下次压缩内容完全不同，**缓存百分之百命中不了**。写缓存要花钱（cacheWrite 1.25×），读却永远读不到——纯亏。接 05 篇第 4 章的前缀缓存：**知道命中不了就别写**。

**`sessionId: uuidv7()`** —— `isolate routing`，让路由层把它当独立请求，不与主对话混在一起。

**`retryAssistantCall`** —— 函数注释：

> 把这唯一一次 LLM 调用包进 `retryAssistantCall`，使**瞬时流中断**（`terminated`、socket 关闭）按配置的重试策略处理，而不是第一次失败就让整个压缩告吹。确定性错误和中断立即返回。

**压缩是昂贵操作**——切点已算完，split turn 时可能已发过一次轮前缀请求。为一次 socket 抖动全盘放弃代价太大。但确定性错误不重试（重试也是一样结果），这是 `generated/robustness-and-cost` 讲的"重试四层主权"在压缩路径上的体现。

另外，思考等级会被继承（`createSummarizationOptions`，`:558`）：

```typescript
if (model.reasoning && thinkingLevel && thinkingLevel !== "off") options.reasoning = thinkingLevel;
```

摘要是需要理解全局的任务，让模型先想一想是合理的——代价是更慢更贵。

### 4.10 失败就抛，不折成数据

```typescript
if (response.stopReason === "error") {
	throw new Error(`Summarization failed: ${response.errorMessage || "Unknown error"}`);
}
```

对比 03 篇学的工具执行——工具失败会变成一条 `toolResult` 回到对话里让模型自己纠正（"错误即数据"）。**摘要失败不能这么办**：没有摘要就没法压缩，没法压缩就没法继续，**这不是模型能处理的问题**。

这个 `throw` 一路冒到 `_runAutoCompaction` 的 `try`，变成 `compaction_end` 事件 + `errorMessage`，最终显示给用户。

### 4.11 一次摘要请求的完整形态

```json
{
  "system": "You are a context summarization assistant… Do NOT continue the conversation…",
  "messages": [{ "role": "user", "content": [{ "type": "text", "text":
      "<conversation>\n[User]: 帮我重构认证模块\n[Assistant tool calls]: read(path=\"src/auth.ts\")\n[Tool result]: …前 2000 字符…\n[... 8421 more characters truncated]\n…\n</conversation>\n\n
       <previous-summary>\n## Goal\n重构认证模块…\n</previous-summary>\n\n
       The messages above are NEW conversation messages to incorporate…\n…七段模板…\n\n
       Additional focus: …（若有）"
  }]}],
  "max_tokens": 13107,
  "reasoning": "medium"
}
```

**一条 user 消息包打天下。** 没有多轮、没有工具、没有缓存——一次纯粹的"给你材料，输出总结"。

返回的七段 Markdown 原样存进 `compaction` 条目的 `summary`；下一轮组装上下文时（02 篇第 4 章）被 `COMPACTION_SUMMARY_PREFIX` 包成一条 user 消息：

```text
The conversation history before this point was compacted into the following summary:

<summary>
## Goal
重构认证模块…
## Progress
### Done
- [x] 提取了 TokenValidator
…
</summary>
```

**闭环：模板填出来 → 存进树 → 下次组装时包上标签 → 变成新对话的开头。**

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
第 2 行  重跑 02 篇那条组装链
         buildSessionPath → buildContextEntries → convertToLlm
         （这次会走 02 篇第 4 章那个"摘要放回坑位"的分支）
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

## 第 7 章 同一套机制的另外两个入口

前六章跟的是**自动压缩**这条主路径。同一套核心还被另外两处调用，看它们**差在哪、为什么差**，比重复核心逻辑更有价值。

### 7.1 手动 `/compact`：同一机制，两种交互契约

`agent-session.ts:2018` 的 `compact(customInstructions?)`。把它和 `_runAutoCompaction()` 并排，**中间一大段几乎逐行相同**：

```text
取密钥   _getSummarizationRequestAuth          ← 一样
读会话树 sessionManager.getBranch()             ← 一样
算切点   prepareCompaction(pathEntries, …)      ← 一样
问扩展   session_before_compact，三种结局        ← 一样
生成摘要 compact(preparation, …)                ← 一样（compaction.ts 那个）
中断检查 signal.aborted                          ← 一样
落盘刷新 appendCompaction → buildSessionContext → state.messages  ← 一样
通知扩展 session_compact                         ← 一样
```

**差异全部来自一件事：调用者是谁、在等什么。**

```text
自动：调用者是 agent 循环刚结束的会话层
      它在 _runAgentPrompt 的 while 里，等一个 boolean 决定要不要 continue
手动：调用者是用户敲的 /compact
      agent 可能正在跑，用户盯着屏幕等结果
```

#### 差异一：开场要先把 agent 停掉

```typescript
async compact(customInstructions?: string): Promise<CompactionResult> {
	this._disconnectFromAgent();          // ★ 断开事件连接
	await this.abort();                   // ★ 中止正在跑的 agent
	this._compactionAbortController = new AbortController();
	this._emit({ type: "compaction_start", reason: "manual" });
	try {
		…
	} finally {
		this._compactionAbortController = undefined;
		this._reconnectToAgent();           // ★ 成对恢复
	}
}
```

自动压缩没有这两行——**它天然发生在 agent 已停下的时刻**（循环刚返回，见 1.2）。手动则可能在模型答到一半时被敲下：压缩要改 `agent.state.messages`，而 agent 正拿着它的快照在跑（1.3），不先停就会撞车。

`_disconnectFromAgent` / `_reconnectToAgent` 一个在 `try` 之外、一个在 `finally` 里，保证成功、失败、取消三条路径都恢复连接。

#### 差异二：两个独立的中断控制器

```typescript
private _compactionAbortController: AbortController | undefined;      // 手动
private _autoCompactionAbortController: AbortController | undefined;  // 自动
```

不共用，是因为**两者可能同时存在**（自动压缩正跑，用户又敲了 `/compact`），共用则说不清谁 abort 了谁。

但取消时一起打：

```typescript
this._compactionAbortController?.abort();
this._autoCompactionAbortController?.abort();
```

**建的时候分开，取消的时候一起**——用户按 Esc 的意思是"全停"，不区分类型。`isCompacting` 同理，是三个控制器或起来的。

#### 差异三：失败要抛，而且要分类

这是最能体现"谁在等"的一处。同样是"压不动"：

```typescript
// 自动
const preparation = prepareCompaction(pathEntries, settings);
if (!preparation) return false;                      // ★ 静默放弃

// 手动
const preparation = prepareCompaction(pathEntries, settings);
if (!preparation) {
	const lastEntry = pathEntries[pathEntries.length - 1];
	if (lastEntry?.type === "compaction") throw new Error("Already compacted");   // ★ 还要诊断原因
	throw new Error("Nothing to compact (session too small)");
}
```

**自动静默返回是对的**——后台行为，"这次没压"不必打扰用户。**手动必须抛**——用户主动按了按钮，什么都不发生是最糟的反馈；而且它多做一步诊断，回头看最后一条是不是 compaction 条目，好区分"刚压过"和"内容太少"。

同样的分歧贯穿全函数：

| 场景 | 自动 | 手动 |
|---|---|---|
| 没得压 | `return false` | `throw` + 区分两种原因 |
| 扩展 cancel | `emit` + `return false` | `throw new Error("Compaction cancelled")` |
| 中断 | `emit` + `return false` | `throw new Error("Compaction cancelled")` |
| 没有模型 | `return false` | `throw new Error(formatNoModelSelectedMessage())` |

**返回类型本身就说明了差异：**

```typescript
_runAutoCompaction(…): Promise<boolean>        // 回答"接下来怎么办"
compact(…): Promise<CompactionResult>          // 交付"这是压缩的成果"
```

#### 差异四：`customInstructions` 只有手动才有

自动那边写死 `customInstructions: undefined`。回到 4.7：它会被追加到摘要提示词末尾（`Additional focus: …`）。

**只有用户知道这次压缩想侧重什么**；自动压缩是无人值守的，没有"意图"可传。

#### 差异五：取消不算失败

```typescript
} catch (error) {
	const message = error instanceof Error ? error.message : String(error);
	const aborted = message === "Compaction cancelled" || (error instanceof Error && error.name === "AbortError");
	this._emit({
		type: "compaction_end", reason: "manual", result: undefined, aborted,
		errorMessage: aborted ? undefined : `Compaction failed: ${message}`,   // ★ 取消时不填错误
	});
	throw error;                                                               // ★ 事件之外还要继续抛
}
```

**"被取消"和"失败了"要分开**：前者是用户自己的选择，不该弹错误；后者才需要显示原因。判据有两个来源——自己抛的 `"Compaction cancelled"`，以及底层的 `AbortError`。

最后那句 `throw error` 表明：**事件只是通知，异常才是控制流**，两条都要走。

### 7.2 分支摘要：解决的是"离开"而不是"太满"

`compaction/branch-summarization.ts`（431 行）。它和压缩是同目录的兄弟，共用大量基础设施，但**触发原因根本不同**：

```text
压缩      上下文太满了     →  同一条路径上，把前半截换成摘要
分支摘要  你要跳到别处去   →  离开当前分支，把这一段的成果记下来
```

01 篇学过：`/tree` 跳转、fork、切换会话，本质都是移动 `leafId`。指针一移，刚才那一路干的活就**不在新路径上**了——不是被删除（树上永远留着），是不可见。

```text
        ┌─ C ─ D ─ E ←── 你现在在这（干了一堆活）
   A ─ B
        └─ F ─ G     ←── 你要跳到这
```

文件头注释：

> 会话树导航到其他位置时，为**即将离开的分支**生成摘要，避免上下文丢失。

#### 独有的第一步：找共同祖先

压缩不需要这一步——它在一条直线上切一刀即可。分支摘要必须先算出两条路径的分岔点（`:131`）：

```typescript
export function collectEntriesForBranchSummary(session, oldLeafId, targetId): CollectEntriesResult {
	if (!oldLeafId) return { entries: [], commonAncestorId: null };

	const oldPath = new Set(session.getBranch(oldLeafId).map((e) => e.id));
	const targetPath = session.getBranch(targetId);

	let commonAncestorId: string | null = null;
	for (let i = targetPath.length - 1; i >= 0; i--) {     // targetPath 从根排列，反向找最深的
		if (oldPath.has(targetPath[i].id)) { commonAncestorId = targetPath[i].id; break; }
	}

	const entries: SessionEntry[] = [];
	let current: string | null = oldLeafId;
	while (current && current !== commonAncestorId) {       // ★ 又是那个父链遍历
		const entry = session.getEntry(current);
		if (!entry) break;
		entries.push(entry);
		current = entry.parentId;
	}
	entries.reverse();                                      // 转成时间顺序
	return { entries, commonAncestorId };
}
```

用上图走一遍：

```text
oldPath    = { A, B, C, D, E }
targetPath = [A, B, F, G]        ← 从根排列
反向遍历：G ∉ oldPath → F ∉ oldPath → B ∈ oldPath ✓  →  commonAncestorId = B
从 E 回溯到 B（不含）：[E, D, C] → reverse → [C, D, E]
```

**这就是"要摘要的那一段"。** 02 篇 3.1 讲的那个 `while (current)` 父链遍历，在这里又出现一次——只是终点从 `undefined` 换成了 `commonAncestorId`。

#### 同一个问题，两个相反的答案

注释特意点出：

> 遇到压缩边界时**不会停止**，因为这些边界也会被纳入，其摘要将成为上下文的一部分。

对比压缩自己的处理（`compaction.ts:87`）：

```typescript
function getMessageFromEntryForCompaction(entry: SessionEntry): AgentMessage | undefined {
	if (entry.type === "compaction") return undefined;    // ★ 压缩条目不参与再摘要
	// 压缩条目本身只是历史边界，不能再次作为普通消息并入下一轮摘要。
}
```

而分支摘要的版本（`branch-summarization.ts:187`，注释写着 `but also handles compaction entries`）会把它转成 `compactionSummary` 消息一并摘要。

| | 压缩 | 分支摘要 |
|---|---|---|
| 压缩条目怎么办 | **跳过** | **纳入** |
| 理由 | 它是当前路径的**活边界**，再摘要会套娃 | 离开之后这条边界也失效，它只是这段历史的一部分 |

**同一条压缩摘要，是"活的边界"还是"一段历史"，取决于你打算留在这条路上还是离开。**

#### 工具结果：截断 vs 直接丢弃

```typescript
case "message":
	if (entry.message.role === "toolResult") return undefined;   // 直接丢
	// 跳过工具结果，其上下文已包含在助手的工具调用中。
```

对比 4.8：压缩把工具结果**截到 2000 字符保留**。

**因为两者要回答的问题不同：**

```text
压缩摘要   ——  同一条路上要接着干  ——  需要"依据"（上次读那个文件看到了什么）
分支摘要   ——  离开这条路          ——  只需要"结论"（试了什么、行不行）
```

工具调用本身（`read(path="x")`）已经说明做过什么，结果内容对"日后回来看一眼"没有价值。

#### 复用了什么、独有什么

看 import 就一目了然：

```typescript
import { completeSummarization, estimateTokens } from "./compaction.ts";
import { computeFileLists, createFileOps, extractFileOpsFromMessage,
         formatFileOperations, SUMMARIZATION_SYSTEM_PROMPT, serializeConversation } from "./utils.ts";
```

| 共用 | 独有 |
|---|---|
| `completeSummarization`（无缓存 / 新 sessionId / 可重试） | `collectEntriesForBranchSummary`（找共同祖先） |
| `SUMMARIZATION_SYSTEM_PROMPT`（`Do NOT continue`） | `getMessageFromEntry`（对压缩条目与工具结果的不同处理） |
| `serializeConversation`（拍平成转录稿） | `BRANCH_SUMMARY_PROMPT`（第四套模板） |
| 文件操作那一整套 | `prepareBranchEntries`（带 `tokenBudget` 的裁剪） |
| `convertToLlm` | |

**`utils.ts` 存在的意义就在这一栏**——它装的正是"压缩与分支摘要都要用"的东西。这也回答了 4.8 的一个小疑问：`serializeConversation` 为什么在 `utils.ts` 而不在 `compaction.ts`。

#### 第四套提示词

```typescript
// branch-summarization.ts:306
const BRANCH_SUMMARY_PROMPT = `Create a structured summary of this conversation branch for context when returning later. …`;
```

至此摘要提示词共四套：

| 提示词 | 用在哪 | 回答什么 |
|---|---|---|
| `SUMMARIZATION_PROMPT` | 首次压缩 | 这段历史干了什么（七段模板） |
| `UPDATE_SUMMARIZATION_PROMPT` | 后续压缩 | 把新进展合并进旧摘要 |
| `TURN_PREFIX_SUMMARIZATION_PROMPT` | split turn | 被切断那半轮发生了什么 |
| `BRANCH_SUMMARY_PROMPT` | 分支摘要 | 这条分支试了什么，**以便日后回来** |

`for context when returning later` 这句定位是关键——**它假设你可能会回来**，所以侧重"试过什么、结果如何"，而不是压缩摘要那种"接着干的交接文档"。

**四套提示词，四种读者处境。** 同样是让模型总结，期待的产物形态完全不同。

#### 一个多出来的参数

```typescript
export function prepareBranchEntries(entries: SessionEntry[], tokenBudget: number = 0): BranchPreparation
```

分支摘要多了 `tokenBudget`——**要摘要的分支可能任意长**（你在上面干了一整天），而压缩至少有 `keepRecentTokens` 划出的范围。有预算就要裁剪。

⬜ 裁剪策略（裁哪头、怎么取舍）本篇未跟。

---

## 第 8 章 工程模式清单

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
25. **先定产物格式，再倒推输入格式。** 摘要是七段固定模板，于是 `maxTokens`（13k 装七段）、序列化保留 thinking（`Key Decisions` 需要理由）、保留工具参数（`Preserve exact file paths`）全都由模板反推而来。
26. **"要求"不等于"保证"。** 提示词里写了 `Preserve exact file paths` 只是对模型的请求；真要保证就得像文件清单那样用代码提取。
27. **同一模板的两种模式，靠换提示词而非换数据。** 首次填空 vs 增量 merge，七个标题不变、每段指示不同；只把旧摘要塞进输入而不换开场白，模型会当成普通对话去总结，旧信息就丢了。
28. **一个失败模式值得三道防线。** 防"模型接着聊"：拍平成转录稿（形式）+ 装进一条 user 消息（结构）+ `Do NOT continue`（指令）——因为失败要到解析结果时才发现。
29. **自指难题靠有损压缩输入来解。** 摘要请求自身也会爆，故截断工具结果；判据不是长度而是"对接着干有多重要"——工具结果最长且最不需要，因为它是原始数据而摘要要的是结论。
30. **截断要留痕。** `[... N more characters truncated]` 防止模型据不完整内容作出错误结论。
31. **知道缓存命中不了就别写。** 摘要请求前缀独一无二，`cacheRetention: "none"`——写缓存要花钱，读却永远读不到。
32. **昂贵操作值得重试，但只重试瞬时失败。** 压缩已算完切点、可能已发过轮前缀请求，不该因一次 socket 抖动全废；确定性错误立即返回。
33. **不是所有错误都能折成数据。** 工具失败变 `toolResult` 让模型自纠，摘要失败只能 `throw`——没有摘要就无法继续，这不是模型能处理的问题。
34. **核心一份，外壳按调用者的期待包。** 自动与手动压缩共用九成代码；差异全来自"谁在等"——无人值守则静默返回 boolean，用户在等则抛出带诊断的错误并交付结果对象。
35. **控制器按来源分设，取消时一起打。** 自动与手动压缩可能并存，故各有各的 `AbortController`；但用户按 Esc 的意思是"全停"。
36. **"被取消"不是"失败了"。** 事件里分成 `aborted` 与 `errorMessage` 两个字段，取消不填错误——用户自己的选择不该弹报错。
37. **事件是通知，异常是控制流。** 手动压缩 `emit` 之后仍要 `throw`，两条路各走各的。
38. **同一份数据的取舍取决于读者处境。** 压缩条目在压缩里被跳过（活边界，再摘要会套娃），在分支摘要里被纳入（离开后只是一段历史）；工具结果在压缩里截断保留（还要接着干，需要依据），在分支摘要里直接丢弃（只需结论）。
39. **共用的东西沉到公共文件。** `utils.ts` 装的正是压缩与分支摘要都要用的部分——这是判断"该不该抽出来"的现成标准。
40. **同一动作、多套提示词。** 四套摘要提示词对应四种读者处境；模板的差别不在措辞而在"读它的人接下来要干什么"。

---

## 第 9 章 复习自测

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
24. 摘要的产物是什么形态？七段分别是什么？为什么说它"不是给人看的纪要"？
25. `maxTokens` 为什么取 `reserveTokens` 的 80%？为什么还要和 `model.maxTokens` 取小？
26. 两套摘要提示词是什么关系？只把旧摘要塞进输入而不换提示词，会发生什么？
27. 防止"模型接着聊"有哪三道防线？为什么值得做三道？
28. 摘要请求自身也可能超窗——代码怎么解？为什么单挑工具结果截断，且不伤摘要质量？
29. 序列化时哪些内容完整保留、哪个被截断？判据是什么？
30. `thinking` 为什么要单独一行保留？（提示：回到模板的哪一段）
31. `cacheRetention: "none"` 的理由是什么？这和 05 篇讲的前缀缓存怎么接上？
32. 摘要失败为什么 `throw` 而不是折成一条消息交给模型？
33. `previousSummary` 解决什么问题？它和 `boundaryStart` 接力分别管什么？
34. 文件操作追踪只认哪三个工具、哪个参数？`grep` 为什么不算？
35. 读过又改过的文件会出现在哪个清单里？为什么？
36. 文件清单为什么要同时存成文本和结构化两种形态？
37. 上一次压缩若由扩展接管，这次的文件清单会怎样？为什么 pi 宁可这样？
38. 压缩生效的三行代码分别做了什么？之后靠什么让 agent-loop 拿到新上下文？
39. `estimatedTokensAfter` 为什么只能估？它参与判定吗？
40. `session_before_compact` 与 `session_compact` 有何不同？后者为什么传"已保存的条目"？
41. 手动 `/compact` 与自动压缩共用哪些步骤？差异全部源于什么？
42. 手动压缩开场为什么要 `_disconnectFromAgent()` + `abort()`？自动压缩为什么不用？
43. 为什么两种压缩各有一个 `AbortController`，取消时却一起打？
44. 同样是"压不动"，两条路的反应为何相反？手动那边还多做了什么？
45. 两个函数的返回类型分别是什么？这说明了什么？
46. `customInstructions` 为什么只有手动才有？
47. 事件里为什么要把 `aborted` 和 `errorMessage` 分开？判据有哪两个来源？
48. 分支摘要解决的问题和压缩有何根本不同？
49. `collectEntriesForBranchSummary` 怎么找共同祖先？用 A-B-C-D-E / A-B-F-G 那棵树走一遍。
50. 压缩条目在两种摘要里被区别对待——分别怎么处理、理由是什么？
51. 工具结果在压缩里截断保留、在分支摘要里直接丢弃，判据是什么？
52. `utils.ts` 里放的是哪一类东西？这给"该不该抽公共文件"提供了什么标准？
53. 四套摘要提示词分别用在哪、回答什么问题？它们的差别本质上是什么差别？

---

> **压缩这条线到此走完。** 仅剩 `prepareBranchEntries` 的 `tokenBudget` 裁剪策略未跟（7.2 末尾已标注）。
