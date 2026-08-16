# 10 — 从 LLM 响应到会话历史：一轮的完整时间线

> 学习系列第 10 篇，与第 9 篇配成一对：**09 讲"出去"，10 讲"回来"**。
>
> 第 9 篇把一条数据从磁盘送到了 HTTP 请求体里——树 → 路径 → 消息 → 报文，一路塌缩。本篇反过来问：**模型开始吐字之后，发生了什么？** 字节流怎么变回结构、工具什么时候执行、循环凭什么继续、新内容怎么长回树上。
>
> 两篇合起来是一个闭环：`磁盘 → 模型 → 磁盘`。第 9 篇的关键词是**塌缩**（丢信息、不可逆），本篇的关键词是**累积**（攒信息、可中断）。
>
> 所有 `文件:行号` 基于 commit `859bd29bd`。核心文件：`packages/ai/src/types.ts`（事件协议与消息类型）、`packages/agent/src/agent-loop.ts`（循环与工具执行）。
>
> **本篇状态**：第 1–2 章已完成，第 3–7 章待写。

## 目录

- 第 1 章 全景：一轮的完整时间线
- 第 2 章 事件协议：模型吐字的切分规则
- 第 3 章 T1 段：SSE 解析器怎么把字节变成事件（待写）
- 第 4 章 T2 段：`AssistantMessage` 怎么攒出来（待写）
- 第 5 章 T3 段：工具执行（待写）
- 第 6 章 T4–T5 段：结果入上下文与循环条件（待写）
- 第 7 章 T6 段：落盘成条目，回到第 9 篇的起点（待写）

---

## 第 1 章 全景：一轮的完整时间线

先把整条时间轴摆出来。后面每一章都是在放大它的某一段。

设用户问了个问题，模型决定读两个文件：

```text
T0   ── HTTP 请求 ① 发出 ────────────────────────────────────
        body: { system, messages: [用户提问], tools: [read, bash, …] }

T1   ── SSE 流开始，事件逐个到达 ─────────────────────────────
        start
        thinking_start  idx 0
        thinking_delta  idx 0  "让我"          ┐
        thinking_delta  idx 0  "看看"          │ pi 这期间只做两件事：
        thinking_end    idx 0                  │   ① 拿 partial 刷新界面
        text_start      idx 1                  │   ② 往 content 数组里攒
        text_delta      idx 1  "我读一下"       │
        text_end        idx 1                  │ 不执行任何工具
        toolcall_start  idx 2                  │
        toolcall_delta  idx 2  '{"pa'          │ ← 参数还没流完，
        toolcall_delta  idx 2  'th":"A.md"}'   │   此刻根本不知道要读哪个文件
        toolcall_end    idx 2  { id:"c1", name:"read", arguments:{ path:"A.md" } }
        toolcall_start  idx 3
        toolcall_delta  idx 3  '{"path":"B.md"}'
        toolcall_end    idx 3  { id:"c2", … }
        done            reason: "toolUse"      ┘

T2   ── 连接结束，AssistantMessage 完整 ──────────────────────

T3   ── agent-loop 醒过来（agent-loop.ts:217）────────────────
        filter 出 2 个 toolCall
        executeToolCalls(…)          ← 这里才真正干活
          ├─ read("A.md")   ┐ 默认并行（:456）
          └─ read("B.md")   ┘ 带 sequential 标记的工具才串行（:454）

T4   ── 结果包成 toolResult 消息（:235）─────────────────────
        { role:"toolResult", toolCallId:"c1", content:[…] }
        { role:"toolResult", toolCallId:"c2", content:[…] }
        currentContext.messages.push(result)

T5   ── while 循环回到顶部，HTTP 请求 ② 发出 ─────────────────
        body: { system,
                messages: [用户提问, assistant①, toolResult, toolResult],
                tools: […] }
                          ↑ 全部历史重新发一遍

T6   ── 新一轮 SSE 流…… 直到某次 done 的 reason 是 "stop" ────
```

### 1.1 三条必须记住的规则

**① 工具不是流到一半就执行的。**

```typescript
// agent-loop.ts:217
const toolCalls = message.content.filter((c) => c.type === "toolCall");
```

`message` 是**完整的** `AssistantMessage`——`done` 之后才存在。T1 全程 pi 只做渲染和攒状态，一个工具都不碰。三个理由：

- **参数没流完就不知道调什么**：`'{"pa'` 这时候连文件名都没有；
- **要等全部调用到齐才能并行**：只有拿到完整消息才知道"一共 2 个"，才能一起发出去。边流边执行只能串行，慢一倍；
- **`stopReason` 最后才知道**，而它会改变处理方式（见下）。

**② `length` 截断时，所有工具调用一律不执行。**

```typescript
// agent-loop.ts:227-230
const executedToolBatch =
	message.stopReason === "length"
		? await failToolCallsFromTruncatedMessage(toolCalls, emit)   // 全部判失败
		: await executeToolCalls(currentContext, message, config, signal, emit);
```

源码注释说得直白：撞到 token 上限意味着输出被砍断，**消息里每个工具调用都可能携带不完整参数**（`{"path": "AGE` 这种），执行下去后果不可控。宁可全部失败，也不执行可能损坏的调用。

**③ 每一轮都把全部历史重发一遍。**

```text
请求① messages: [u]
请求② messages: [u, a①, tr, tr]
请求③ messages: [u, a①, tr, tr, a②, tr]
```

**没有"中间追加"这回事**——每次都是一个干净、完整、越来越长的请求。

### 1.2 这条时间线解释了什么

很多零散知识点只有摆在这条轴上才对得上号：

| 现象 | 时间线上的原因 |
| --- | --- |
| 上下文会涨、需要压缩（第 8 篇） | 每轮重发全部历史，messages 数组只增不减 |
| 第 9 篇那六个纯函数**每轮都跑一遍** | T0 和 T5 各是一次完整的"树 → 报文"组装，所以复杂度必须是 O(路径深度) 而非 O(全部条目) |
| 提示词缓存为什么值钱 | 第 N 轮请求的前 90% 与第 N−1 轮**逐字节相同**，`cache_control` 挂在系统提示词上（`anthropic-messages.ts:1041`）就是为了让这部分按 0.1 倍计费 |
| 模型为什么"记不住" | 它是**无状态**的——不是记得你说过什么，而是每轮被重新告知一遍。想让它记住某件事，唯一办法是让那件事出现在 messages 数组里 |
| 按 Esc 中断为什么还能留下内容 | `error` 事件同样携带 `AssistantMessage`（`types.ts:584`），已攒进 `content` 的部分不丢 |
| 界面上"一次回答"，账单上好几次调用 | 一次 `agent_start` 到 `agent_end` 之间，可能有十几个 T0→T6 循环 |

**判断：这条时间线是整个 agent 的心跳。** 单看任何一个模块都能读懂代码，但"为什么这样设计"的答案几乎都在这条轴上。

---

## 第 2 章 事件协议：模型吐字的切分规则

模型回话不是一次性到达的，是一个字一个字流过来的。**事件协议就是把这个连续过程切成离散事件的规则**：会发出哪些事件、按什么顺序、每个带什么数据。

`packages/ai/src/types.ts:572`：

```typescript
export type AssistantMessageEvent =
	| { type: "start"; partial: AssistantMessage }
	| { type: "text_start"; contentIndex: number; partial: AssistantMessage }
	| { type: "text_delta"; contentIndex: number; delta: string; partial: AssistantMessage }
	| { type: "text_end"; contentIndex: number; content: string; partial: AssistantMessage }
	| { type: "thinking_start"; contentIndex: number; partial: AssistantMessage }
	| { type: "thinking_delta"; contentIndex: number; delta: string; partial: AssistantMessage }
	| { type: "thinking_end"; contentIndex: number; content: string; partial: AssistantMessage }
	| { type: "toolcall_start"; contentIndex: number; partial: AssistantMessage }
	| { type: "toolcall_delta"; contentIndex: number; delta: string; partial: AssistantMessage }
	| { type: "toolcall_end"; contentIndex: number; toolCall: ToolCall; partial: AssistantMessage }
	| { type: "done"; reason: Extract<StopReason, "stop" | "length" | "toolUse">; message: AssistantMessage }
	| { type: "error"; reason: Extract<StopReason, "aborted" | "error">; error: AssistantMessage };
```

12 个事件，别被数量吓到——**规律是 3×3 + 3**：

```text
          start      delta      end
text        ●          ●         ●
thinking    ●          ●         ●
toolcall    ●          ●         ●

外加：start（整条消息开始）、done（成功终结）、error（失败终结）
```

三类内容，每类都是"开始 → 若干增量 → 结束"。**认识一类就认识全部。**

它保证三件事：

- **顺序**：`start` 一定最先，`done` 或 `error` 一定最后（源码注释：*Streams should emit `start` before partial updates, then terminate with either `done` … or `error` …*）；
- **完整性**：`xxx_end` 携带这一块的完整内容，`done` 携带整条消息。**完全不管 delta、只等 end 和 done，照样拿到全部数据**——delta 是给"要实时显示"的人用的（TUI 的打字机效果），`-p` 一次性模式直接等 `done` 即可；
- **有且只有一个终结事件**：不会两个都来，也不会一个都不来。

### 2.1 `partial`：每个事件都带一份完整快照

```typescript
| { type: "text_delta"; contentIndex: number; delta: string; partial: AssistantMessage }
//                                            ↑ 这次新增的     ↑ 到目前为止的完整状态
```

**不是只给增量，而是"增量 + 当前完整快照"一起给。** 好处是消费者不必自己攒状态：

```typescript
// ❌ 只给 delta，消费者被迫维护状态，还得担心漏事件、乱序
let text = "";
on("text_delta", (e) => { text += e.delta; render(text); });

// ✅ 给 partial，消费者完全无状态
on("text_delta", (e) => render(e.partial));
```

TUI 收到任何一个事件，直接拿 `partial` 重画即可。

**这个模式在 pi 里是一以贯之的**：写扩展工具时 `execute` 收到的 `onUpdate` 回调，约定同样是"每次传一份完整的半成品结果"，而非只传增量。看似浪费，实则把"状态一致性"这件麻烦事从每个消费者身上收归到生产者一处。

### 2.2 `contentIndex`：`content` 数组的下标

一条 assistant 消息的 `content` 是数组（`types.ts:463`）：

```typescript
content: (TextContent | ThinkingContent | ToolCall)[];
//   下标   0             1                2
```

`contentIndex: 2` 就是"这个事件属于 `content[2]`"。**只有一个编号系统**——三种类型共用同一串连续下标，不各数各的：

```text
content[0]  thinking     contentIndex 0
content[1]  text         contentIndex 1
content[2]  toolCall     contentIndex 2
content[3]  toolCall     contentIndex 3
```

第 2 块是 toolCall，编号就是 2，不会因为"这是第 0 个 toolCall"而变成 0。

**分块的依据是类型切换，不是句子边界。** 模型连说十句话中间没干别的，那也只有 1 块——`text_start` → 几十个 `delta` → `text_end`，`contentIndex` 全程是 0。顺序也不固定，`text → toolCall → text → toolCall` 完全合法。**`contentIndex` 只表示"在数组的第几格"，不表示类型顺序。**

它最要紧的用途是**给交错到达的增量归位**：

```text
toolcall_delta  contentIndex 2   delta '{"pa'
toolcall_delta  contentIndex 3   delta '{"pat'
toolcall_delta  contentIndex 2   delta 'th":"AGENTS'      ← 接回第 2 块
toolcall_delta  contentIndex 4   delta '{"path"'
```

三个工具调用的参数 JSON 同时在流，没有 index 就全糊成一团。**这与工具执行时用 `toolCallId` 把界面更新分派到对应组件，是同一个问题的同一种解法：并发的多路更新，靠一个 key 各归各位。**

### 2.3 三种内容类型：为什么 `toolCall` 不能塞进 `text`

一个自然的疑问：工具调用不就是模型输出的一段文本吗，为什么要单列一种类型？看结构就明白了。

```typescript
// types.ts:417
export interface ToolCall {
	type: "toolCall";
	id: string;                       // ← 身份证
	name: string;                     // ← 调哪个
	arguments: Record<string, any>;   // ← 已解析好的对象
}

// types.ts:391
export interface TextContent {
	type: "text";
	text: string;                     // ← 就一坨字符串
}
```

**放进 `text` 的话，这三个字段就得自己从字符串里抠出来。** 早期（ReAct 那一代）确实这么干过——让模型输出 `Action: read` / `Action Input: {…}` 再用正则解析。三个问题：

- **分不清"提及"和"执行"**：模型说"你可以用 read 工具读这个文件"，正则一匹配工具就跑了。类型分开之后，**说 read 是文本，调 read 是 toolCall**，语义彻底隔开；
- **格式随时会歪**：少个引号、JSON 写成单引号，解析就炸。现在 provider 侧有受限采样兜底（`packages/ai/src/api/constrained-sampling.ts`），从生成阶段就保证 JSON 合法；
- **没有 id，结果配不回去**——这是最硬的理由。

模型一次可发起多个工具调用，结果回来时靠 `id` 认领：

```text
assistant:   toolCall { id: "c1", name: "read", … }
             toolCall { id: "c2", name: "read", … }
             toolCall { id: "c3", name: "bash", … }

toolResult:  { toolCallId: "c2", … }    ← 靠 id 认领，
toolResult:  { toolCallId: "c1", … }      顺序可以是乱的
toolResult:  { toolCallId: "c3", … }
```

到 Anthropic 报文里就是 `tool_use_id` ↔ `tool_use.id` 配对（`anthropic-messages.ts:1155` 的 `convertToolResult`）。**纯文本没地方挂这个 id**——要么自己发明一套编号约定，要么只能串行调用，三个文件三个来回，慢三倍。

`ThinkingContent` 同理（`types.ts:398`），它带着 `thinkingSignature`（provider 返回的不透明推理标识，下一轮要原样回传才能维持推理连续性）和 `redacted`（是否被安全过滤器遮蔽）。**混进 `text` 里这些字段就没地方放了。**

**结论：分成三种类型，是因为它们各自带着不同的结构化元数据，而这些元数据都有硬用途（配对、回传、执行）。挤进一个 `text: string` 就全丢了。**

### 2.4 `done` / `error`：用类型收窄堵死非法组合

```typescript
| { type: "done";  reason: Extract<StopReason, "stop" | "length" | "toolUse">; message: AssistantMessage }
| { type: "error"; reason: Extract<StopReason, "aborted" | "error">;           error: AssistantMessage };
```

`StopReason` 全集有 6 个（`types.ts:453`）：

```typescript
export type StopReason = "pending" | "stop" | "length" | "toolUse" | "error" | "aborted";
```

`Extract<T, U>` 是 TypeScript 内置工具类型，**从联合类型 T 里只挑出属于 U 的成员**。于是：

- `done` 的 reason **只可能**是 `stop` / `length` / `toolUse`；
- `error` 的 reason **只可能**是 `aborted` / `error`；
- `pending` 一个都不在里面——它是"还没结束"的中间态，不可能出现在终结事件上。

**写一个 `{ type: "done", reason: "aborted" }` 会当场编译报错。** "成功不可能带失败原因"这条协议规则，不靠注释、不靠运行时检查，靠类型定义堵死。

### 2.5 `reason` 其实是在说"接下来谁动"

| reason | 含义 | agent 接下来 |
| --- | --- | --- |
| `toolUse` | 模型要调工具 | **执行工具 → 再问一轮**（回到 T3） |
| `stop` | 模型说完了 | 停，控制权交回用户 |
| `length` | 撞到 `max_tokens` 上限 | 停；且本轮所有工具调用一律判失败（1.1 ②） |
| `aborted` | 用户中断 | 停，保留已收到的部分 |
| `error` | 出错 | 停（`agent-loop.ts:209` 直接 `turn_end` + `agent_end` 返回） |

**`toolUse` 就是那个"再来一轮"的信号**，`agent-loop.ts:180` 那个 `while (true)` 转不转，全看它。所以一次完整的用户交互可能是：

```text
用户提问
  → assistant① (toolUse)  → 执行工具 → toolResult
  → assistant② (toolUse)  → 执行工具 → toolResult
  → assistant③ (toolUse)  → 执行工具 → toolResult
  → assistant④ (stop)     → 结束，等用户
```

四条 assistant 消息、四次 HTTP 请求。**界面上的"一次回答"，底下是十几个来回。**

---

*基于 2026-08-16 的源码精读整理（对话式逐行走读）。与第 9 篇配对：09 讲"出去"（会话历史 → LLM 请求），本篇讲"回来"（LLM 响应 → 会话历史）。第 3–7 章待写。*
