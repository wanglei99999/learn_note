# 10 — 从 LLM 响应到会话历史：一轮的完整时间线

> 学习系列第 10 篇，与第 9 篇配成一对：**09 讲"出去"，10 讲"回来"**。
>
> 第 9 篇把一条数据从磁盘送到了 HTTP 请求体里——树 → 路径 → 消息 → 报文，一路塌缩。本篇反过来问：**模型开始吐字之后，发生了什么？** 字节流怎么变回结构、工具什么时候执行、循环凭什么继续、新内容怎么长回树上。
>
> 两篇合起来是一个闭环：`磁盘 → 模型 → 磁盘`。第 9 篇的关键词是**塌缩**（丢信息、不可逆），本篇的关键词是**累积**（攒信息、可中断）。
>
> 所有 `文件:行号` 基于 commit `859bd29bd`。核心文件三个：`packages/ai/src/types.ts`（事件协议与消息类型）、`packages/ai/src/api/anthropic-messages.ts`（SSE 解析与状态机，以 Anthropic 为样本）、`packages/agent/src/agent-loop.ts`（循环与工具执行）。

## 目录

- 第 1 章 全景：一轮的完整时间线
- 第 2 章 T1 段：SSE 解析器怎么把字节变成事件
- 第 3 章 T2 段：`AssistantMessage` 怎么攒出来
- 第 4 章 事件协议：模型吐字的切分规则（路旁参照表）
- 第 5 章 T3 段：工具执行
- 第 6 章 T4–T5 段：循环怎么转
- 第 7 章 T6 段：落回会话树
- 第 8 章 工程模式清单
- 第 9 章 复习自测

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

## 第 2 章 T1 段：SSE 解析器怎么把字节变成事件

### 2.1 线上流过来的是什么

Anthropic 的响应体是一串**文本**，长这样：

```text
event: content_block_start
data: {"type":"content_block_start","index":1,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"我读"}}

event: content_block_stop
data: {"type":"content_block_stop","index":1}
```

SSE（Server-Sent Events）的规则极简：**每行是 `字段名: 值`；空行表示一个事件结束；`:` 开头的行是注释**。解析器要干的事，就是把字节流切成行、把行攒成事件。

### 2.2 三层生成器叠起来

```text
ReadableStream<Uint8Array>            原始字节
   │ iterateSseMessages(:414)          切行、攒事件      ← 通用 SSE，不认识 Anthropic
   ▼
ServerSentEvent { event, data, raw }
   │ iterateAnthropicEvents(:473)      过滤 + JSON 解析   ← Anthropic 专属
   ▼
RawMessageStreamEvent                 Anthropic 的事件对象
   │ stream(:514)                      翻译成中立事件      ← 变成 12 种之一（第 3 章）
   ▼
AssistantMessageEvent
```

每层只干一件事，且都是 `async function*`（异步生成器）——**上游一有数据下游就能拿到，不必等全部收完**。

### 2.3 核心工程点：一个事件可能被切成两半

网络不保证按行送达。某次 `read()` 拿到的可能是：

```text
event: content_block_delta\ndata: {"text":"我
```

后半截 `读"}` 在下一个 chunk 里。所以有 `buffer`（`:421`）：

```typescript
let buffer = "";
while (true) {
	const { value, done } = await reader.read();
	if (done) break;

	buffer += decoder.decode(value, { stream: true });   // 追加：新来的接在零头后面
	let consumed = consumeLine(buffer);
	while (consumed) {                                    // 切得动就一直切
		buffer = consumed.rest;                           // 切剩的放回桶里
		const event = decodeSseLine(consumed.line, state);
		if (event) yield event;                           // 只有空行那次会进这里
		consumed = consumeLine(buffer);
	}
}
```

三个角色分工明确：

| 角色 | 职责 |
| --- | --- |
| `reader` | 水龙头：每次给一坨字节 |
| `decoder` | 翻译官：字节 → 字符串 |
| `buffer` | 水桶：接住还不够一行的零头 |

**外层循环管"收"，内层循环管"切"**：收一坨，能切几行切几行，切不动了回去再收一坨。

`consumeLine` 一次只切一行——找到**第一个**换行符，切一刀返回 `{ line, rest }`；没有换行符就返回 `null`，这正是内层循环的退出条件。

用真实数据走一遍。设服务器要发的事件被切成两坨：

**第一坨** `'event: content_block_delta\ndata: {"text":"我'`（JSON 从中间断了）

| 轮次 | `consumeLine(buffer)` | 动作 |
| --- | --- | --- |
| 1 | `{ line: "event: content_block_delta", rest: 'data: {"text":"我' }` | `decodeSseLine` 记下 `state.event`，返回 `null` |
| 2 | `null`（余下部分无换行符） | **内层循环结束** |

此刻 `buffer = 'data: {"text":"我'`，半截 JSON 留在桶里，**一个事件都没 yield**。

**第二坨** `'读"}\n\n'` 到达，拼接后 `buffer = 'data: {"text":"我读"}\n\n'`：

| 轮次 | `consumeLine(buffer)` | 动作 |
| --- | --- | --- |
| 1 | `{ line: 'data: {"text":"我读"}', rest: "\n" }` | 塞进 `state.data`，返回 `null` |
| 2 | `{ line: "", rest: "" }` | **空行！** 触发 `flushSseEvent` → **`yield event`** |
| 3 | `null` | 内层循环结束 |

**`buffer` 的作用只有一个：跨越两次 `read()` 把断掉的行接起来。** 没有它，第一坨结尾那半截 JSON 就会被当成完整一行去解析，直接炸。

`decoder.decode(value, { stream: true })` 的 `stream: true` 是同一道理的**字符级**版本：一个中文字 UTF-8 占 3 字节，chunk 边界可能切在中间。加了这个标记，`TextDecoder` 会把半个字符留着等下一块；不加则解出 `�`，且再也补不回来。**`buffer` 管半行，`stream: true` 管半个字，两层保险。**

### 2.4 `decodeSseLine`：攒事件的状态机

分工要分清：**`consumeLine` 把字符流切成行（语法层，只认换行符），`decodeSseLine` 把行攒成事件（语义层，认识 SSE 协议）**。

它一次只吃一行，反应视行的内容而定：

| 输入行 | 动作 | 返回 |
| --- | --- | --- |
| `event: content_block_delta` | `state.event = "content_block_delta"` | `null` |
| `data: {"text":"我读"}` | `state.data.push(...)` | `null` |
| `data: 第二行` | 再 push 一个（**一个事件可以有多行 data**） | `null` |
| `: keep-alive` | 忽略（注释行） | `null` |
| `""`（空行） | **打包 `state` 成事件并清空** | **事件对象** |

```typescript
function decodeSseLine(line: string, state: SseDecoderState): ServerSentEvent | null {
	if (line === "") {
		return flushSseEvent(state);      // 空行：把攒的东西打包吐出去
	}

	state.raw.push(line);
	if (line.startsWith(":")) return null;

	const delimiterIndex = line.indexOf(":");
	const fieldName = delimiterIndex === -1 ? line : line.slice(0, delimiterIndex);
	let value = delimiterIndex === -1 ? "" : line.slice(delimiterIndex + 1);
	if (value.startsWith(" ")) value = value.slice(1);   // 冒号后的一个空格是分隔符，不是内容

	if (fieldName === "event") state.event = value;
	else if (fieldName === "data") state.data.push(value);

	return null;                          // 非空行一律返回 null，只攒不吐
}
```

**函数本身无记忆，记忆全在 `state` 里**——它在循环外创建、反复传入。解析开头那个事件实际调了三次：

```text
第 1 次  decodeSseLine("event: content_block_delta", state)  →  null    记进 state
第 2 次  decodeSseLine('data: {"text":"我读"}',      state)  →  null    记进 state
第 3 次  decodeSseLine("",                           state)  →  事件!   凑齐，打包
```

这样写的好处是**函数小到一眼能验**：给一行、给一个 state，检查 state 变成什么样即可，不必构造整条流。复杂度全交给外面那个 while。

于是整条链路上有两处"攒不够就先存着"，只是粒度不同：

```text
字节  ──decoder──►  字符  ──consumeLine──►  行  ──decodeSseLine──►  事件
                            ↑ buffer 兜半行         ↑ state 兜半个事件
```

### 2.5 边界与健壮性

**三种换行都要认**（`:385-412`）。`nextLineBreakIndex` 同时找 `\r` 和 `\n` 取较小者，`consumeLine` 里再补一句让 CRLF 算一个：

```typescript
if (text[lineBreakIndex] === "\r" && text[nextIndex] === "\n") nextIndex += 1;
```

`\n`、`\r\n`、`\r` 规范都允许，那就都得认。

**收尾四连**（`:446-467`）。流 `done` 之后还有四步：冲掉 decoder 里残留的半个字符（`decoder.decode()` 无参调用）、处理 buffer 里剩下的完整行、把最后没有换行符的残余也当一行、最后 `flushSseEvent` 手动收尾。**服务器不保证最后给一个规规矩矩的空行**，这四步是在兜"流断在任何位置"的底。

**保留原始行只为报错**。`ServerSentEvent` 有个 `raw: string[]` 字段平时没用，只在解析失败时派上用场（`:504`）：

```typescript
throw new Error(
	`Could not parse Anthropic SSE event ${sse.event}: ${message}; data=${sse.data}; raw=${sse.raw.join("\\n")}`,
);
```

**报错时把原始报文一起给出来**——调试流式协议时这个太重要，否则只知道"JSON 解析失败"，不知道服务器究竟发了什么。

**检测被截断的流**（`:481-511`）：

```typescript
let sawMessageStart = false;
let sawMessageEnd = false;
// …
if (sawMessageStart && !sawMessageEnd) {
	throw new Error("Anthropic stream ended before message_stop");
}
```

连接中途断掉（网络抖动、服务端崩），**HTTP 层面看起来是"正常结束"**——`reader.read()` 返回 `done: true`，不报错。只有靠协议层的配对检查才能发现"开始了但没结束"。不检查的话，上层会拿到一条内容不全的消息，还以为是完整的。

**白名单挡住未知事件**（`:334`、`:489`）：

```typescript
const ANTHROPIC_MESSAGE_EVENTS: ReadonlySet<string> = new Set([
	"message_start", "message_delta", "message_stop",
	"content_block_start", "content_block_delta", "content_block_stop",
]);
// …
if (!ANTHROPIC_MESSAGE_EVENTS.has(sse.event ?? "")) continue;
```

Anthropic 还会发 `ping` 保活事件，将来也可能新增类型。**白名单让新增事件不会把老客户端搞崩。**（`event: error` 例外，在白名单检查之前就直接 `throw`，`:485`。）

---

## 第 3 章 T2 段：`AssistantMessage` 怎么攒出来

`stream()` 函数里那台状态机**同时干两件事**：

```text
Anthropic 的 6 种事件  ──►  ① 翻译成中立的 12 种事件（push 给下游）
                       └──►  ② 往 output 这个对象上攒（拼出完整消息）
```

### 3.0 先看骨架：一个循环，一个 `output`

后面几节会拆开讲各个分支，但**先要看清它们都长在同一个循环里**——否则容易把那些 `if (event.type === …)` 看成互不相干的片段：

```typescript
export const stream = (model, context, options) => {
	const stream = new AssistantMessageEventStream();

	(async () => {
		const output: AssistantMessage = {          // ← ① 只创建一次，整条流共用
			role: "assistant",
			content: [],                             //    空的，边收边填
			api: model.api,
			provider: model.provider,
			model: model.id,
			usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { … } },
		};

		stream.push({ type: "start", partial: output });          // :595

		for await (const event of iterateAnthropicEvents(response, options?.signal)) {   // :600
			// ② 每转一圈 = 一个 Anthropic 事件
			if (event.type === "message_start") { … }            // 改 output.usage
			else if (event.type === "content_block_start") { … } // output.content.push(新块)
			else if (event.type === "content_block_delta") { … } // 已有块 += 增量
			else if (event.type === "content_block_stop") { … }  // 收尾、删脚手架
			else if (event.type === "message_delta") { … }       // 改 output.stopReason / usage
		}

		stream.push({ type: "done", reason: output.stopReason, message: output });   // ③ :792
		stream.end();
	})();

	return stream;
};
```

三件事要记住：

**① `output` 在循环外创建，只有一个。** 第 2 章那条流水线上，前面几层都是"一个接一个流过去"，到这里换成"一直在那儿、越蓄越满"：

| 层 | 一次响应里有多少个 |
| --- | --- |
| 行 | 几百上千 |
| `ServerSentEvent` | 几十上百 |
| `RawMessageStreamEvent` | 几十上百 |
| **`output`** | **1 个** |

**前面是流水，`output` 是水池。** 这也解释了为什么 `partial: output` 每次都是同一个对象——它本来就只有一个（见 3.1）。

**② 每转一圈处理一个事件，同时干两件事**：改 `output`，并向下游 `push` 一个中立事件。

```typescript
block.text += event.delta.text;                                // ← 攒进 output
stream.push({ type: "text_delta", …, partial: output });        // ← 通知下游
```

**一个进（Anthropic 的事件），两个出（改 output + 发中立事件）。**

注意对 `output` 的操作**有三种，不都是 push**：`content_block_start` 才 `output.content.push(block)`（数组多一格）、`content_block_delta` 是 `block.text += …`（往已有那格追加）、`message_start` / `message_delta` 是 `output.usage.x = …`（改顶层字段）。

**③ 循环跑完，`output` 就完整了**，作为 `done` 事件的 `message` 发出去（去向见 3.9）。

### 3.1 `partial` 不是拷贝

```typescript
stream.push({ type: "text_delta", contentIndex: index, delta: …, partial: output });
//                                                              ↑ 每次都是同一个对象
```

**每个事件带的 `partial` 都是 `output` 本人，不是快照副本。** 下游拿到的因此永远是"此刻最新状态"——`output` 一变，之前发出去的事件里的 `partial` 也跟着变。

这是有意的：TUI 只需要 `render(e.partial)`，不关心自己是不是漏了几个事件。**代价是不能把 `partial` 存起来当历史快照用**——它会变。真要留存，得等 `done` 事件里的 `message`。

### 3.2 事件对应关系

| Anthropic | pi | 干的事 |
| --- | --- | --- |
| `message_start` | —（不转发） | 记 `usage` 初值、`responseId` |
| `content_block_start` | `text_start` / `thinking_start` / `toolcall_start` | **新建一块**，push 进 `content` |
| `content_block_delta` | `text_delta` / `thinking_delta` / `toolcall_delta` | **往那块上追加** |
| `content_block_stop` | `text_end` / `thinking_end` / `toolcall_end` | **收尾**，清理临时字段 |
| `message_delta` | —（不转发） | 记 `stopReason`、最终 `usage` |
| `message_stop` | `done` | 终结 |

结构上是"消息级"和"块级"两套 start/delta/stop 嵌套：

```text
message_start
    content_block_start / delta* / stop      ← 第 0 块
    content_block_start / delta* / stop      ← 第 1 块
message_delta            ← stop_reason 在这里才揭晓
message_stop
```

新建一块（`:617`）：

```typescript
if (event.content_block.type === "text") {
	const block: Block = { type: "text", text: "", index: event.index };
	output.content.push(block);                    // 数组里多一格
	stream.push({ type: "text_start", contentIndex: output.content.length - 1, partial: output });
	//                                              ↑ 刚 push 完，长度-1 就是它的下标
}
```

往块上追加（`:659`）：

```typescript
const index = blocks.findIndex((b) => b.index === event.index);
const block = blocks[index];
if (block && block.type === "text") {
	block.text += event.delta.text;               // 就地追加
	stream.push({ type: "text_delta", contentIndex: index, delta: event.delta.text, partial: output });
}
```

`block.text += …` 改的就是 `output.content[index].text`，因为两者是同一个数组：

```typescript
const blocks = output.content as Block[];    // :598  只是换个类型视角，不是复制
```

### 3.3 两套 index 要对上

```typescript
const index = blocks.findIndex((b) => b.index === event.index);
//            ↑ pi 自己数组里的位置        ↑ Anthropic 给的编号
```

为什么不直接用 `event.index`？因为那是 **Anthropic 的编号**，pi 不假设它与自己数组的下标一致。于是每个 block 上临时挂一个 `index` 字段记住"我在 Anthropic 那边是几号"，用时查一遍。**发给下游的 `contentIndex` 始终是 pi 自己数组的下标**——上层永远不必知道 provider 的编号规则。

### 3.4 脚手架字段搭完就拆

`Block` 这个类型很有意思（`:597`）：

```typescript
type Block = (ThinkingContent | TextContent | (ToolCall & { partialJson: string })) & { index: number };
//            └────────── 正式字段 ──────────┘   └脚手架①┘     └脚手架②┘
```

在正式类型上**临时加两个字段**：`index`（对 Anthropic 编号）和 `partialJson`（攒工具参数的半截 JSON）。`content_block_stop` 时全部删掉（`:708`、`:728`）：

```typescript
delete (block as any).index;
// …
block.arguments = parseStreamingJson(block.partialJson);
delete (block as { partialJson?: string }).partialJson;
```

源码注释交代了动机：

> 原地完成工具调用并删除暂存 JSON，**保证重放数据只携带解析后的参数**。

**这条消息最后要落盘进会话历史**（第 7 章）——脚手架字段留着就会写进 `.jsonl`，污染数据、白占空间。

### 3.5 工具参数边流边解析

```typescript
block.partialJson += event.delta.partial_json;
block.arguments = parseStreamingJson(block.partialJson);      // :688
```

每来一段就**重新解析一次不完整的 JSON**：

```text
partialJson = '{"pa'                →  arguments = {}
partialJson = '{"path":"A'          →  arguments = { path: "A" }
partialJson = '{"path":"A.md"}'     →  arguments = { path: "A.md" }
```

`parseStreamingJson` 尽量解出目前已知的部分。**这样界面上能实时显示"正在读 A…"，而不是等参数全到齐才蹦出来。**

### 3.6 Anthropic 到底会返回哪些类型

三层，代码里都能查到。

**① SSE 事件类型**：白名单六种（见 3.5），外加单独拦截的 `error` 和一概跳过的其余（`ping` 等）。

**② content block 类型**（`:617-657` 那串 if）：

| Anthropic 类型 | pi 存成 |
| --- | --- |
| `text` | `TextContent` |
| `thinking` | `ThinkingContent` |
| `redacted_thinking` | `ThinkingContent` + `redacted: true` |
| `tool_use` | `ToolCall` |

**四进三出。** 注意那串 if 没有 `else`——Anthropic 若返回别的块类型（如服务端工具 `server_tool_use`），**pi 会静默丢弃**，不报错也不进 `content`。

**③ delta 类型**（`:659-703`）：

| delta 类型 | 追加到哪 | 转发事件？ |
| --- | --- | --- |
| `text_delta` | `block.text` | ✅ |
| `thinking_delta` | `block.thinking` | ✅ |
| `input_json_delta` | `block.partialJson` | ✅ |
| `signature_delta` | `block.thinkingSignature` | **❌ 不转发** |

`signature_delta` 只往 `output` 上攒，不通知任何人（`:696-702`）——**签名是给 API 回传用的，界面上没什么可显示，发事件出去只会让下游多一次无意义重绘。**

### 3.7 `redacted_thinking`：看不见但不能扔

开了扩展思考后模型的推理过程会流回来，但偶尔安全系统会判定某段推理不宜明文返回，发回来的就是一坨加密数据。`types.ts:403-407` 的注释说全了：

> 为 true 时表示思考内容被安全过滤器遮蔽；不透明的加密载荷保存在 `thinkingSignature` 中，**以便后续轮次原样回传给 API，维持多轮连续性**。

```typescript
const block: Block = {
	type: "thinking",
	thinking: "[Reasoning redacted]",              // 给人看的占位文本
	thinkingSignature: event.content_block.data,   // 加密载荷，原样收着
	redacted: true,
	index: event.index,
};
```

**你读不了，但不能扔。** 因为模型是无状态的——下一轮要把整段历史重发一遍（第 1 章）。这块思考丢了，模型就忘了自己上轮想过什么，推理链断掉，可能重新绕弯路甚至前后矛盾。对 pi 而言它就是个不透明 blob，转手而已。

为什么折进 `thinking` 而不新建类型？因为它本质就是"思考，只是看不到内容"。**照搬的话 `content` 的联合类型要从 3 种变 4 种，每个 switch、每个渲染器、`convertToLlm` 的每个分支全得加一支**——用一个 `redacted?: boolean` 字段标记划算得多。

顺带：`thinkingSignature` 不是 redacted 专属，**普通思考块也带签名，同样要原样回传**。区别只是普通思考的签名是附属品，redacted 的签名**就是全部内容**。

### 3.8 两个健壮性细节

**usage 在 `message_start` 就记**（`:606`）。注释：*在 message_start 即记录初始用量，**确保流提前中止时仍保留输入令牌统计***。按 Esc 中断时输入 token 已经花掉，必须能算出账；等流结束才记就晚了。

**`message_delta` 用"非空才覆盖"更新 usage**（`:750`）：

```typescript
if (event.usage.input_tokens != null) {
	output.usage.input = event.usage.input_tokens;
}
```

注释：*仅用非空字段更新统计，**避免代理在 message_delta 省略字段时覆盖 message_start 的输入令牌数***。有些第三方代理转发时会把 `input_tokens` 置空，无脑赋值会把先前记下的数字冲掉。

还有一处很实在的注释（`:762`）：推理令牌位于 `output_tokens_details.thinking_tokens`，**当前 SDK 类型尚未声明该字段，因此用窄类型断言读取，字段结构已通过真实 API 验证**。官方 SDK 的类型定义落后于真实 API，pi 用窄断言绕过并注明验证来源——**将来 SDK 补上类型时，一眼能看出这段可以清理**。

### 3.9 `output` 攒完之后去哪了

循环跑完（`:779`），`output` 就是一条完整的 `AssistantMessage`。它作为 `done` 事件的 `message` 字段发出去（`:792`）：

```typescript
stream.push({ type: "done", reason: output.stopReason, message: output });
stream.end();
```

异常路径走 `catch`（`:794-804`）——**中断或出错时 `output` 照样发出去**，只是装在 `error` 字段里：

```typescript
} catch (error) {
	for (const block of output.content) {
		delete (block as { index?: number }).index;
		// partialJson 仅用于流式拼接，不能进入持久化或重放数据。
		delete (block as { partialJson?: string }).partialJson;
	}
	output.stopReason = options?.signal?.aborted ? "aborted" : "error";
	output.errorMessage = error instanceof Error ? error.message : JSON.stringify(error);
	stream.push({ type: "error", reason: output.stopReason, error: output });
}
```

**这就是按 Esc 还能保留半截回复的原因**（第 1 章 1.2 那张表里的最后一条）。注意它先手动清了一遍脚手架字段：正常路径上这些是在 `content_block_stop` 里逐块删的（3.4），异常路径没走到那儿，得在这补一刀。

然后一路往上：

```text
:792  stream.push({ type: "done", message: output })
        ↓
      AssistantMessageEventStream
        ↓
      agent-loop.ts:343   for await (const event of response) { … }
        ↓
      streamAssistantResponse 返回这条 AssistantMessage
        ↓
      agent-loop.ts:206   const message = await streamAssistantResponse(…)
```

到这里它换了个名字叫 `message`，随即分三路：

```text
output 诞生（空壳）        anthropic-messages.ts:522
   ↓ 边收边攒（几十上百圈）
output 完整               :779 循环结束
   ↓ done 事件带出去 → agent-loop 收到，变成 message
   ├─► filter 出 toolCall → 执行工具                      （第 5 章，T3）
   ├─► push 进 currentContext.messages → 下一轮重发        （第 6 章，T5）
   └─► message_end → appendMessage → .jsonl              （第 7 章，T6）
```

**从一个空对象开始，攒满，然后同时成为"下一轮的输入"和"磁盘上的一行"。** 圆就是在这里合上的——后面三章都是在讲这三条支路。

---

## 第 4 章 事件协议：模型吐字的切分规则

> **这一章不是路径上的一站，是路旁的参照表。** 前两章跟着字节走完了 T1→T2，路上已经反复见到 `text_delta`、`toolcall_end`、`done` 这些名字冒出来；本章把它们系统地摆一遍——**先在路上遇见，再回头看全貌**。急着往下走可以跳过，需要时回查。

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

### 4.1 `partial`：每个事件都带一份完整快照

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

### 4.2 `contentIndex`：`content` 数组的下标

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

### 4.3 三种内容类型：为什么 `toolCall` 不能塞进 `text`

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

### 4.4 `done` / `error`：用类型收窄堵死非法组合

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

### 4.5 `reason` 其实是在说"接下来谁动"

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

## 第 5 章 T3 段：工具执行

### 5.1 先决定串行还是并行

```typescript
// agent-loop.ts:449-456
const toolCalls = assistantMessage.content.filter((c) => c.type === "toolCall");
const hasSequentialToolCall = toolCalls.some(
	(tc) => currentContext.tools?.find((t) => t.name === tc.name)?.executionMode === "sequential",
);
if (config.toolExecution === "sequential" || hasSequentialToolCall) {
	return executeToolCallsSequential(…);
}
return executeToolCallsParallel(…);
```

**只要这批里有一个工具标了 `executionMode: "sequential"`，整批都退化成串行。** 不是"那一个串行、其余并行"——**一个拖累全部**。因为串行工具的语义通常是"我在动全局状态"（改文件、跑迁移、切分支），旁边并行跑别的工具就可能读到半途状态。

### 5.2 并行版：先攒任务，再一起放

```typescript
finalizedCalls.push(async () => {          // ← 不是 push 结果，是 push 一个函数
	const executed = await executePreparedToolCall(preparation, signal, emit);
	const finalized = await finalizeExecutedToolCall(…);
	await emitToolExecutionEnd(finalized, emit);
	return finalized;
});
```

循环里只"攒任务"不 `await`，攒完一起放（`:571`）：

```typescript
const orderedFinalizedCalls = await Promise.all(
	finalizedCalls.map((entry) => (typeof entry === "function" ? entry() : Promise.resolve(entry))),
);
```

**变量名里的 `ordered` 是关键**：`Promise.all` 保证输出顺序与输入一致，与谁先跑完无关。所以后面生成的 `toolResult` 消息顺序 = **模型发起调用的顺序**，不是完成顺序。读大文件慢、小文件快，结果排列仍按原序——**上下文是确定性的，重放不会因网络快慢而不同**。

那句 `typeof entry === "function"` 在分辨数组里的两种元素：**要么是待执行的函数，要么是现成结果**。现成结果来自 `preparation.kind === "immediate"`（`:539`）——工具名不存在、参数校验失败、被扩展的 `tool_call` 钩子拦下，这类根本不用执行就有答案，不必进等待队列。

### 5.3 串行版多一件事：逐个检查中断

```typescript
if (signal?.aborted) {
	break;                    // :509
}
```

**每执行完一个就检查一次。** 按 Esc 后剩下的工具不再跑，但**已跑完的结果保留**——`messages` 数组里已有的照样返回。

并行版做不到这么细：任务都已放出去，只能靠传进去的 `signal` 让各个工具自己响应中断（写扩展工具时循环里那句 `if (signal?.aborted) break` 就是干这个的）。

### 5.4 每个工具执行发三类事件

```typescript
emit({ type: "tool_execution_start", toolCallId, toolName, args });   // 开始
// …执行中，工具自己调 onUpdate 会发 tool_execution_update
emitToolExecutionEnd(finalized, emit);                                // 结束
emitToolResultMessage(toolResultMessage, emit);                       // 结果消息生成了
```

**`tool_execution_start` 是在 `prepareToolCall` 之前发的**——所以即使工具名不存在、参数校验失败，界面上也会先出现这个工具块，再立刻变成错误状态。这解释了一个观察得到的现象：`tool_execution_start` 比扩展的 `tool_call` 钩子还早。

中间那个 `tool_execution_update` 就是工具 `onUpdate` 回调的出口——**与 3.1 的 `partial` 同一个模式：每次上报一份完整的半成品快照，消费者无需自己攒状态。**

### 5.5 `terminate`：工具可以叫停整个循环

```typescript
return { messages, terminate: shouldTerminateToolBatch(finalizedCalls) };
```

回到主循环（`:232`）：

```typescript
hasMoreToolCalls = !executedToolBatch.terminate;
```

**某些工具执行完之后 agent 不再继续问模型，直接收工。** 典型是"任务完成"类工具——模型调用它表示自己干完了，没必要再来一轮。

---

## 第 6 章 T4–T5 段：循环怎么转

### 6.0 镜头拉远：前面几章都发生在一圈之内

到这里要换个视角。前面几章是**贴着一圈走**——请求怎么发、字节怎么变消息、工具怎么执行；本章要说的是：**你刚看完的那一整套，是循环体里的一圈；它凭什么转第二圈、什么时候停。**

所以循环不是这一章才冒出来的新东西，**它从 T0 就在了**。实际是三层嵌套：

```text
runAgentLoop(…)                                      agent-loop.ts
  │
  └─ while (true) {                                  // :180  ← 本章的外层
       │
       └─ while (hasMoreToolCalls || pending…) {     // :185  ← 本章的内层
            │
            ├─ 注入 pendingMessages                   // :195
            │
            ├─ streamAssistantResponse(…)             // :206
            │    │
            │    ├─ transformContext / convertToLlm   ← 第 9 篇第 9 章
            │    ├─ 组装 Context，发 HTTP             ← T0
            │    └─ stream(…)                         ← anthropic-messages.ts:514
            │         │
            │         └─ for await (const event of iterateAnthropicEvents(…)) {
            │              …                          ← 第 2、3 章讲的就是这个循环
            │            }                            ← T1、T2
            │
            ├─ executeToolCalls(…)                    // :230  ← 第 5 章，T3
            ├─ 结果 push 进 currentContext.messages    // :235  ← T4
            └─（回到内层顶部，发下一个请求）            ← T5
          }
     }
```

**第 2、3 章那个 `for await` 是最内层**，它转几十上百圈才产出**一条** assistant 消息——而那只是内层 while 一圈里的一小段。对回第 1 章的时间线：

```text
T0 ─┬─ 内层 while 第 1 圈开始
T1  │    └─ for await 转几十上百圈（每圈一个 SSE 事件）
T2  │    └─ for await 结束，output 完整
T3  │  executeToolCalls
T4  │  结果入 context
T5 ─┴─ 内层 while 第 2 圈开始  ← 就是"回到顶部"
T6     （落盘散落在 T2 和 T4，由 message_end 触发，见第 7 章）
```

**第 1 章那条时间线，画的就是内层 while 的一圈半。**

循环是这样被进入的：

```text
用户敲回车 → AgentSession.prompt(消息) → Agent.prompt() → runAgentLoop(context, config, …)
   → while (true) → while (hasMoreToolCalls = true) → 第一次 streamAssistantResponse
```

`hasMoreToolCalls` 初值是 `true`（`:181`），**就是为了让内层 while 无条件跑第一圈**——否则第一个请求都发不出去。

### 6.1 两层循环，不是一层

```typescript
while (true) {                                              // :180 外层
	let hasMoreToolCalls = true;

	while (hasMoreToolCalls || pendingMessages.length > 0) { // :185 内层
		…
	}

	const followUpMessages = (await config.getFollowUpMessages?.()) || [];
	if (followUpMessages.length > 0) {
		pendingMessages = followUpMessages;
		continue;                                            // :286 回外层
	}
	break;                                                   // :291 真的结束
}
```

| | 管什么 | 什么时候转 |
| --- | --- | --- |
| **内层** | 工具调用来回 | 模型还要调工具、或有插话消息 |
| **外层** | 收工之后的回心转意 | agent 本来要停了，但用户又发了消息 |

**两层的分界是"agent 认为自己该收工了"**：内层退出 = 模型不再要工具、也没有插话；外层这才有机会问一句"还有后续消息吗"。

### 6.2 内层一圈的顺序

```text
① turn_start 事件                                    :188
② 注入 pendingMessages（插话）                        :195   ← 在请求之前
③ streamAssistantResponse（T0–T2）                    :206
④ 检查 error/aborted → 直接 return                    :209
⑤ filter 工具调用 → 执行 → 结果 push 进 context       :217-237
⑥ turn_end 事件                                       :240
⑦ prepareNextTurn 钩子（可换 context / model）        :249
⑧ shouldStopAfterTurn 钩子 → 可能 return              :264
⑨ 抓下一批 steering messages                          :276
```

**②在③前面**，这是"插话"能生效的原因：

```typescript
if (pendingMessages.length > 0) {
	for (const message of pendingMessages) {
		await emit({ type: "message_start", message });
		await emit({ type: "message_end", message });
		currentContext.messages.push(message);     // 塞进上下文
		newMessages.push(message);
	}
	pendingMessages = [];
}
```

模型正在干活时你打字，消息**不打断当前这轮，而是排队等下一次请求带上**。

### 6.3 三种"继续"的理由

- **模型要调工具** —— `hasMoreToolCalls = !executedToolBatch.terminate`（`:232`）
- **有 steering message** —— 每轮结束抓一次（`:276`），指"agent 干活期间说的话"
- **有 follow-up message** —— 内层已退出，外层再捞一次（`:281`），指"agent 都准备收摊了才说的话"

后两者的区别只是**时机**。coding-agent 侧两个方法在 `agent-session.ts:1725` / `:1731`。

### 6.4 三个出口

```typescript
// ① 出错或中断，立刻走
if (message.stopReason === "error" || message.stopReason === "aborted") { … return; }   // :212

// ② 钩子说停
if (await config.shouldStopAfterTurn?.({ … })) { … return; }                            // :273

// ③ 正常走完，内外层都没活了
break;                                                                                   // :291
```

①② 是 `return`，③ 是 `break` 后落到函数末尾那句 `agent_end`（`:294`）。**三条路都会发 `agent_end`。**

### 6.5 `prepareNextTurn`：每轮之间换装的机会

```typescript
const nextTurnSnapshot = await config.prepareNextTurn?.(nextTurnContext);
if (nextTurnSnapshot) {
	currentContext = nextTurnSnapshot.context ?? currentContext;    // ← 整个上下文可以被换掉
	config = {
		...config,
		model: nextTurnSnapshot.model ?? config.model,               // ← 模型可以换
		reasoning: …,                                                // ← 思考等级可以换
	};
}
```

**`currentContext` 整个可以被替换——这就是压缩的插入点。** 上一轮结束后发现 token 快满，压缩一次，把新的（短得多的）context 交回来，下一轮就用新的发请求。coding-agent 在 `agent-session.ts:584` 接管了这个钩子。

时间线上它落在 **T4 和 T5 之间**：工具结果已进上下文，下一个请求还没发出去。第 8 篇学的自动压缩（`shouldCompact`）就是从这里被触发的。

### 6.6 上下文是一路带着走的同一个数组

```typescript
currentContext.messages.push(result);      // :235
```

工具结果直接 push 进去，**下一轮的请求自然就包含了全部历史，不需要任何"重新组装"的动作**。这正是第 1 章那条"每轮重发全部历史"在代码里的样子。

---

## 第 7 章 T6 段：落回会话树

### 7.1 落盘的触发点是 `message_end`

```typescript
// agent-session.ts:694
if (event.type === "message_end") {
	if (event.message.role === "custom") {
		this.sessionManager.appendCustomMessageEntry(customType, content, display, details);
	} else if (
		event.message.role === "user" ||
		event.message.role === "assistant" ||
		event.message.role === "toolResult"
	) {
		this.sessionManager.appendMessage(event.message);
	}
}
```

**不是"一轮结束批量写"，是每条消息各自落盘。** agent 每发一个 `message_end`，coding-agent 就追加一条 entry：

```text
T2  assistant 消息完整  → message_end → appendMessage → .jsonl 多一行
T4  toolResult 生成    → message_end → appendMessage → .jsonl 多一行
T4  toolResult 生成    → message_end → appendMessage → .jsonl 多一行
```

每条消息一落地就写盘，**中途崩溃也不丢已完成的部分**。

### 7.2 写的两条路，正是第 9 篇读的两条路

| 写（本章） | 存储形态 | 读（第 9 篇 5.1） |
| --- | --- | --- |
| `appendMessage(message)` | 整个消息嵌套在 `message` 字段里 | **剥离**：`return [message]` |
| `appendCustomMessageEntry(type, content, …)` | 字段平铺 | **重建**：`createCustomMessage(…)` |

**嵌套还是平铺，是在写的这一刻决定的。** 第 9 篇那条"载荷是外来对象就整体存，是自家字段就拆开存"的规律，源头在这里。

注释还点名了三个例外：

```typescript
// 其他消息类型（bashExecution、compactionSummary、branchSummary）由别处负责持久化
```

它们不走 agent 循环，因为**不是模型产出的**：`bashExecution` 来自 `!` 命令本地执行（`agent-session.ts:3126` / `:3168`）、`compactionSummary` 来自压缩流程（`appendCompaction`，第 8 篇）、`branchSummary` 来自分支流程。**`message_end` 只管"agent 循环里流过的消息"。**

### 7.3 自动压缩在这里埋线

```typescript
// 跟踪助手消息，供 agent_end 时执行自动压缩检查
if (event.message.role === "assistant") {
	this._lastAssistantMessage = event.message;
	…
}
```

每条 assistant 消息都记一份引用，留到 `agent_end` 时判断要不要压缩。**因为 assistant 消息带着 `usage`，知道当前烧了多少 token**——判断"该不该压缩"的数据就从这条消息上取。

### 7.4 圆闭合了

```text
              ┌─────────────── 第 9 篇 ───────────────┐
              ▼                                       │
        SessionEntry[] ──► path ──► messages ──► Context ──► HTTP 请求
         （会话树）                                             │
              ▲                                                ▼
              │                                           SSE 字节流
        appendMessage                                          │
              ▲                                      SSE 解析（第 2 章）
              │                                                │
        message_end ◄── agent-loop ◄── AssistantMessage ◄── 状态机（第 3 章）
              │              │
              │              └──► 工具执行（第 5 章）──► toolResult ──┐
              │                                                       │
              └───────────────────────────────────────────────────────┘
              └─────────────── 第 10 篇 ───────────────┘
```

一轮结束，树上多了 1 条 assistant + N 条 toolResult，`leafId` 指向最新那条。下一轮第 9 篇那条链路从新 leaf 重新爬一遍——**因为树长高了，所以路径变长了，所以上下文涨了，所以迟早要压缩。**

这一圈顺带解释了几件散落的事：

| 现象 | 答案在这一圈的哪一段 |
| --- | --- |
| 为什么上下文会涨 | T6 每轮追加，第 9 篇每轮全量重读 |
| 为什么 `/new` 不是 `/clear` | T6 只追加不删，`/new` 只是把 `leafId` 挪走（第 8 篇） |
| 扩展 `appendEntry` 存的状态为什么不进上下文 | 它走第三条路（`type: "custom"`），被第 9 篇 5.1 的 `:449` 挡住 |
| 扩展的 `tool_result` 钩子在哪插手 | T3 与 T4 之间，结果生成之后、落盘之前 |
| `onUpdate` 流式上报到哪去了 | T3 里的 `tool_execution_update` 事件 → TUI 重绘 |

---

## 第 8 章 工程模式清单

本篇涉及的可迁移设计模式：

1. **两级缓冲对付流式切分**：`buffer` 兜半行、`TextDecoder` 的 `stream: true` 兜半个字符。**凡是从流里切结构，都要问"切在中间怎么办"**（2.3）。
2. **小函数 + 循环重复**：`consumeLine` 一次切一行、`decodeSseLine` 一次吃一行，复杂度交给外面的 while。**每个函数小到一眼能验对错**（2.4）。
3. **状态外置**：`decodeSseLine` 本身无记忆，`state` 由调用方持有。好测（给一行、给一个 state，检查 state）、好复位（换个空 state 就重新开始）。
4. **白名单而非黑名单**：只认六种 SSE 事件，其余跳过。**新增事件不会把老客户端搞崩**（2.5）。
5. **协议层的配对检查**：`sawMessageStart && !sawMessageEnd`。HTTP 层的"正常结束"不等于协议层的完整——**传输成功不代表内容完整**（2.5）。
6. **报错要带原始输入**：`raw: string[]` 平时无用，只在解析失败时救命。**调试流式协议时，"解析失败"四个字毫无价值**（2.5）。
7. **推送完整快照而非纯增量**：`partial` / `onUpdate(snapshot)` 同一模式。**把"状态一致性"从每个消费者身上收归到生产者一处**（3.1、5.4）。
8. **脚手架字段搭完就拆**：`index` / `partialJson` 用完 `delete`，因为这条消息要落盘（3.4）。**临时字段和持久化数据共用一个对象时，必须显式清理。**
9. **方言在边界层吃掉**：`redacted_thinking` 折进 `thinking` + `redacted` 标记，provider 编号换算成自己的 `contentIndex`。**上层永远不该知道下层的方言**（3.3、3.7）。
10. **不透明数据原样转手**：`thinkingSignature` 读不懂也不能扔，下轮要回传（3.7）。**"我看不懂"不等于"可以丢"。**
11. **一个拖累全部的降级策略**：一个 sequential 工具让整批退化成串行（5.1）。**并发安全上，保守是唯一正确的默认。**
12. **并发执行、确定性排序**：`Promise.all` 保证结果顺序等于输入顺序，与完成先后无关（5.2）。**上下文必须可重放，不能受网络快慢影响。**
13. **异常路径也要计量**：`usage` 在 `message_start` 就记，中断了也能算账（3.8）。
14. **"非空才覆盖"的防御式合并**：避免上游省略字段时把已有数据冲掉（3.8）。
15. **钩子放在状态切换的缝隙**：`prepareNextTurn` 落在"工具结果已入上下文、下个请求未发出"之间，压缩才有机会整个替换 context（6.5）。

---

## 第 9 章 复习自测

尝试不看正文回答：

1. 工具是流到一半就开始执行，还是等整条消息收完？三条理由分别是什么？
2. `stopReason` 为 `length` 时，这批工具调用会怎样处理？为什么不能照常执行？
3. 每轮请求带的是增量还是全部历史？这解释了哪三个现象？
4. 12 个事件的规律是什么？完全忽略 `delta` 事件还能不能拿到完整数据？
5. `partial` 是快照副本还是同一个对象引用？这带来什么好处和什么限制？
6. `contentIndex` 是事件编号还是数组下标？模型连说十句话中间没干别的，会产生几块内容？
7. 为什么 `toolCall` 不能塞进 `TextContent`？最硬的那条理由是什么？
8. `buffer` 和 `TextDecoder` 的 `stream: true` 分别在兜什么？少了任意一个会发生什么？
9. `decodeSseLine` 一次处理几行？它什么时候返回非 `null`？记忆存在哪里？
10. `sawMessageStart && !sawMessageEnd` 检查的是什么场景？为什么 HTTP 层发现不了？
11. `Block` 类型上那两个脚手架字段是什么？为什么必须在 `content_block_stop` 时删掉？异常路径上谁来补这一刀？
12. `redacted_thinking` 为什么折进 `thinking` 而不新建第四种内容类型？它的 `thinkingSignature` 和普通思考的有何不同？
13. 一批工具里有一个标了 `sequential`，其余会怎样？为什么这么设计？
14. 并行执行时，`toolResult` 消息的顺序由什么决定？为什么不能用完成顺序？
15. agent-loop 为什么是两层循环？各自的退出条件是什么？
16. steering message 和 follow-up message 的区别是什么？插话为什么不会打断当前这一轮？
17. 自动压缩挂在哪个钩子上？它在时间线的哪两个点之间执行？为什么必须在那里？
18. 落盘的触发事件是什么？哪三种消息类型不走这条路，为什么？
19. `appendMessage` 与 `appendCustomMessageEntry` 的存储形态有何不同？这与第 9 篇的"剥离 vs 重建"是什么关系？
20. 一次响应里，行、`ServerSentEvent`、`RawMessageStreamEvent`、`output` 各有多少个？为什么 `output` 是特殊的那一个？
21. `output` 攒完之后分几路、各去了哪？中断时它还会被发出去吗？
22. 把第 9 篇和本篇接起来，说出"上下文为什么会涨"的完整因果链。

---

*基于 2026-08-16 的源码精读整理（对话式逐行走读）。与第 9 篇配对：09 讲"出去"（会话历史 → LLM 请求），本篇讲"回来"（LLM 响应 → 会话历史）。provider 层以 Anthropic 为唯一样本，其余十余家是同一件事的不同方言。*
