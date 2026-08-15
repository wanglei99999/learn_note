# 09 — 从会话历史到 LLM 请求：上下文组装链路

> 学习系列第 9 篇（全景地图见第 0 篇，会话树见第 8 篇）。第 8 篇讲清了会话在磁盘与内存里长什么**形状**——一棵 append-only 的事件树。本篇接着问下一个问题：**这棵树上的一条路径，是怎么一步步变成发给 LLM 的那串消息的？**
>
> 这是一条分工明确的流水线，本篇**从头走到尾**：前半段（第 1–8 章）是 `packages/coding-agent/src/core/session-manager.ts` 里 6 个**纯函数**如何把「当前 leaf 路径」组装成 `AgentMessage[]`；后半段（第 9–12 章）是 `transformContext()` / `convertToLlm()` 如何把 `AgentMessage` 塌缩成中立的 `Message`，再由各家 provider 译成真正的 HTTP 报文。
>
> 只覆盖**"出去"的方向**。响应流回来之后（SSE 解析 → `AssistantMessage` → 落盘成新条目 → 下一轮）属于第 1、2 篇的范围，本篇不重走。
>
> 所有 `文件:行号` 基于 commit `859bd29bd`。核心文件三个：`session-manager.ts`（约 1850 行，前半段）、`core/messages.ts`（后半段的塌缩逻辑）、`packages/agent/src/agent-loop.ts`（两段之间的交接点）。与第 8 篇同一套代码，本篇聚焦其"读侧"——从树到上下文的组装，而非第 8 篇的"写侧"——落盘与建树。

## 目录

- 第 1 章 全景：一条从 leaf 到 LLM 请求的流水线
- 第 2 章 `buildEntryIndex`：把数组变成 O(1) 查找表
- 第 3 章 `buildSessionPath`：选出当前路径
- 第 4 章 `buildContextEntries`：按压缩边界裁剪（位置维度）
- 第 5 章 `sessionEntryToContextMessages`：按类型投影成消息（类型维度）
- 第 6 章 `getSessionContextSettings`：设置靠重放
- 第 7 章 `buildSessionContext`：总装配线
- 第 8 章 一个漂亮的设计：两层正交
- 第 9 章 交接点：`agent-loop` 的二十行
- 第 10 章 `convertToLlm`：七种 role 塌缩成三种
- 第 11 章 `Context`：把翻译推迟到最后一刻
- 第 12 章 全链路回望：三种形态与唯一不可逆的一步
- 第 13 章 工程模式清单
- 第 14 章 复习自测

---

## 第 1 章 全景：一条从 leaf 到 LLM 请求的流水线

一句话立骨架：**发给模型的上下文不是某个字段里存着的，而是每次调用 LLM 之前，从会话树上现算出来的。**

输入是全量事实（内存里的 `entries[]` 数组 + 当前 `leafId` 指针），输出是一个 `SessionContext`：

```typescript
SessionContext = {
  messages: AgentMessage[]     // 发给模型的消息序列
  thinkingLevel: string        // 当前思考等级
  model: { provider, modelId } // 当前模型
}
```

中间是一条六站流水线：

```text
entries[] (磁盘 JSONL 的内存投影，全量事实) + leafId
  │
  ├─① buildSessionPath         选出 leaf→root 的正序路径              [选路径]
  │      └─ buildEntryIndex     （内部）id→条目 的 O(1) 查找表
  │
  ├─② getSessionContextSettings(path)  重放出当前 model + thinkingLevel [解析设置]
  │
  ├─③ buildContextEntries       沿路径按压缩边界裁剪（位置维度）        [裁条目]
  │
  └─④ .flatMap(sessionEntryToContextMessages)  每条按类型投影 0~N 消息（类型维度）[变消息]
         │
         ▼
   SessionContext { messages, thinkingLevel, model }
         │
         ▼  （下篇）transformContext() → convertToLlm()
   provider 报文 → LLM
```

六个函数各管一件事，职责表：

| 函数 | 职责 | 关键维度 | 行号 |
| --- | --- | --- | --- |
| `buildEntryIndex` | 数组 → `id→条目` 查找表 | 性能 | 363 |
| `buildSessionPath` | 选出当前 leaf→root 正序路径 | — | 372 |
| `getSessionContextSettings` | 沿路径重放出当前 model / thinkingLevel | — | 400 |
| `buildContextEntries` | 沿路径按压缩边界裁条目 | **位置** | 465 |
| `sessionEntryToContextMessages` | 单个条目投影成 0~N 条消息 | **类型** | 423 |
| `buildSessionContext` | 总装配线，串起以上 | — | 508 |

一个贯穿全篇、也贯穿整个系列的心智模型（从第 8 篇延续）：

> **事实层 vs 投影层。** `entries[]` 是事实——全量、不可变、只追加。`SessionContext` 是投影——当前这条路径的一个可裁剪切片。这条流水线，本质就是一个把「事实」算成「投影」的**纯函数**。改 leaf、压缩、分支，都只是"换一种投影方式"，事实本身一个字节不动。

这也决定了本篇 6 个函数的一个共同特征：**它们全是模块级纯函数**（不依赖 `SessionManager` 实例状态，输入全靠参数进），`SessionManager` 上的同名方法只是薄薄一层转发（例如 `session-manager.ts:1366`）。纯函数好测试、好复用，这是整套设计能保持简单的根基。

---

## 第 2 章 `buildEntryIndex`：把数组变成 O(1) 查找表

流水线第一站，8 行，却是后面"路径回溯"能做到 O(路径深度) 的前提。

```typescript
function buildEntryIndex(entries: SessionEntry[], byId?: Map<string, SessionEntry>): Map<string, SessionEntry> {
	if (byId) return byId;                          // 364
	const index = new Map<string, SessionEntry>();  // 365
	for (const entry of entries) {                  // 366
		index.set(entry.id, entry);
	}
	return index;                                   // 369
}
```

**作用**：把 `entries` 这个只能顺序遍历的数组，变成一张 `id → 条目` 的 Map。

**为什么需要**：下一站的路径回溯，核心动作是"拿着 `parentId` 找到父条目"。数组里按 id 找只能 `entries.find(...)`，是 **O(n)** 线性扫；回溯 D 层就是 O(n×D)。有了 Map，`.get(id)` 是 **O(1)**，回溯整体降到 O(D)。

**最值得学的是 364 行 `if (byId) return byId`**——这是"可选注入 + 惰性回退（lazy fallback）"模式：

- 传了 `byId` → 直接返回，一个字不建。运行时 `SessionManager` 总把维护好的 `this.byId` 递进来，于是这里**零重建**。
- 没传 → 才现场遍历 `entries` 建一张。这条路径是给**单元测试 / 外部调用**用的：手头只有数组、没有现成索引，函数自给自足照样能跑。

一个安全细节：传入 `byId` 时返回的是**同一个引用**（不拷贝）。之所以无害，是因为下游只对它做 `.get`（只读），从不写，不会污染调用方的表。

---

## 第 3 章 `buildSessionPath`：选出当前路径

```typescript
function buildSessionPath(
	entries: SessionEntry[],
	leafId?: string | null,
	byId?: Map<string, SessionEntry>,
): SessionEntry[] {
	const index = buildEntryIndex(entries, byId);   // 377
	let leaf: SessionEntry | undefined;
	if (leafId === null) {                           // 379
		return [];
	}
	if (leafId) {                                    // 382
		leaf = index.get(leafId);
	}
	leaf ??= entries[entries.length - 1];            // 385
	if (!leaf) {                                     // 386
		return [];
	}

	const path: SessionEntry[] = [];
	let current: SessionEntry | undefined = leaf;
	while (current) {                                // 392
		path.push(current);
		current = current.parentId ? index.get(current.parentId) : undefined;
	}
	path.reverse();                                  // 396
	return path;
}
```

**一句话概括：它是 pi 版的 `git log --reverse`——从当前 HEAD（`leafId`）沿 `parentId` 链走到根，再倒过来，只吐出当前这一条分支线。**

拿一棵有分叉的小树走一遍，抽象立刻落地。设文件里追加顺序是 `[A, B, C, D]`：

```text
A (root, parentId=null)
└─ B (parentId=A)
   ├─ C (parentId=B)   ← 假设 leafId 指这里
   └─ D (parentId=B)   ← 另一条分支
```

调 `buildSessionPath(entries, "C")`：

```text
377  index = { A, B, C, D }
382  "C" truthy → leaf = index.get("C") = C
392  循环：
       current=C → push C, parentId=B → index.get(B)=B
       current=B → push B, parentId=A → index.get(A)=A
       current=A → push A, parentId=null → 三元取 false → undefined，停
     path = [C, B, A]
396  reverse → [A, B, C]
     返回 [A, B, C]
```

**注意 D**：它在 `entries` 数组里、在 `index` 里，却从头到尾没被 `push` 一次——**"在索引里 ≠ 在你走的路上"**。把 `leafId` 换成 `"D"`，path 就变 `[A, B, D]`，C 不碰。同一棵树，只换指针，就是换一条上下文——这正是 `/tree` 跳转（`branch()` 改 `leafId`，第 8 章）之后，下一次组装自动走新路径的原理。`branch()` 是"写这个指针"，`buildSessionPath` 是"读这个指针"，`leafId` 是它俩共享的 HEAD。

三个"讲究"：

**① `leafId` 是三态，不是布尔（379–385）。** 这三行在分诊三种情况：

| `leafId` 传入 | 命中的行 | 结果 | 语义 |
| --- | --- | --- | --- |
| `null` | 379 `=== null` | 返回 `[]` | **明确没有叶子**（`resetLeaf()` 重编第一条消息） |
| 有效 id | 382 `if(leafId)` | 从该节点上溯 | 正常指定位置 |
| `undefined` / 查不到的 id | 385 `??=` 回退 | 用文件最后一条 | "没说站哪 → 站最新"（恢复会话） |

关键在 379 用的是严格 `=== null`，而非 `if (!leafId)`。若写成后者，`null`（重置）和 `undefined`（没传）会被抹成同一种，重置态就丢了。边角自测：传空字符串 `""` 会怎样？——`=== null` 不成立，`if("")` falsy 跳过查找，最后被 385 的 `??=` 回退到最后一条，即被当成"没传"。

**② 上溯循环有三种停法，且不需要防环（392–395）。** `current.parentId ? index.get(...) : undefined` 会在：根节点（`parentId=null`）、断链（`parentId` 指向不存在的 id，`get` 返回 undefined）、正常到根——三种情况下让 `current` 变 undefined，`while` 收工。**没写 `visited` 集合防环**，因为 append-only 保证 `parentId` 永远指向一个**已存在的、更早的**节点（追加时 `parentId = 当时的 leafId`）——环在这套数据结构里构造不出来。不变量替你省了防御代码。

**③ `reverse` 是为下游服务的（396）。** 循环收集出的是 `[leaf…root]` 倒序，396 翻成 `[root…leaf]` 正序。为什么下游非要正序？见下一章的 `getSessionContextSettings`——它靠"后者覆盖前者"取最新设置，只有正序才对；LLM 上下文本身也要求旧消息在前。所以 `reverse` 不是顺手，是刚需。

定性：复杂度 **O(路径深度)**，与会话总条数无关；纯函数，不改 `entries`、不改 `index`、返回全新的 `path` 数组。

### 3.1 同一段遍历的三份实现：校验强度跟着信任边界走

仓库里"沿 parentId 爬到根"这段逻辑写了三遍，处理异常的态度**一次比一次严**：

| 实现 | 断链（parentId 指向不存在的条目） | 父链成环 |
| --- | --- | --- |
| `session-manager.ts:392`（本章） | 静默停止，返回残缺路径 | 不防（会死循环） |
| `array-session-reader.ts:99-101` | `throw SessionError("invalid_session")` | 不防 |
| `sqlite-node/.../storage/index.ts:237-245` | `throw SessionError("invalid_session")` | `visited` 集合，成环即 `throw` |

```typescript
// array-session-reader.ts:99-101 —— 把"到根"和"断链"拆成两种结局
if (!current.parentId) break;                       // 到根：正常收工
const parent = byId.get(current.parentId);
if (!parent) throw new SessionError("invalid_session", `Entry ${current.parentId} not found`);
```

```typescript
// sqlite/storage/index.ts:237-240 —— 多防一手环
const visited = new Set<string>();
while (current) {
	if (visited.has(current.id)) throw invalidSession(`cycle in parent chain at entry ${current.id}`);
	visited.add(current.id);
```

差异不是随手写的，而是**数据来源的可信度不同**：

- `session-manager` 的 `index` 是它自己刚从 `.jsonl` 一次性重放建起来的，append-only 不变量在同一个进程里刚被它亲手维护过——上面"不需要防环"的论证在这里成立。
- SQLite 那份面对的是一个**可能被外部进程改写**的数据库文件。append-only 不变量在进程外不受它控制，于是不变量降级成"待验证的假设"，防御代码就必须补回来。

**一句话：不变量能省掉防御代码，但只在不变量的作用域之内。跨过信任边界，省掉的都要还回来。**

---

## 第 4 章 `buildContextEntries`：按压缩边界裁剪（位置维度）

这一站是**选择器**：拿到上一站的完整路径，决定"这条路径上**哪些条目真正进上下文**"，核心只干一件事——**处理压缩边界**。它不碰消息内容、不生成摘要文本，只挑条目。

```typescript
export function buildContextEntries(
	entries: SessionEntry[],
	leafId?: string | null,
	byId?: Map<string, SessionEntry>,
): SessionEntry[] {
	const path = buildSessionPath(entries, leafId, byId);   // 470
	let compaction: CompactionEntry | null = null;

	for (const entry of path) {                              // 473 找"最新"compaction
		if (entry.type === "compaction") compaction = entry;
	}

	if (!compaction) return path;                            // 479 短路①：没压缩

	const compactionIdx = path.findIndex((e) => e.id === compaction.id);
	if (compactionIdx < 0) return path;                      // 484 短路②：防御

	const contextEntries: SessionEntry[] = [compaction];     // 488 第一段：摘要提到最前
	let foundFirstKept = false;
	for (let i = 0; i < compactionIdx; i++) {                // 490 第二段：保留区
		const entry = path[i];
		if (entry.id === compaction.firstKeptEntryId) foundFirstKept = true;
		if (foundFirstKept) contextEntries.push(entry);
	}
	contextEntries.push(...path.slice(compactionIdx + 1));   // 499 第三段：压缩后新消息
	return contextEntries;
}
```

摆一个具体例子。设一段压缩过一次的对话，`buildSessionPath` 返回的正序 path 是 9 条：

```text
idx  条目                          说明
 0   u1  (user)                   很旧
 1   a1  (assistant)              很旧
 2   u2  (user)                   很旧
 3   a2  (assistant)   ←──────── firstKeptEntryId 指向这里（保留区起点）
 4   u3  (user)
 5   a3  (assistant)
 6   COMP (compaction)  ←──────── compactionIdx = 6；带着 firstKeptEntryId = a2.id
 7   u4  (user)                   压缩之后新说的
 8   a4  (assistant)   ← leaf     压缩之后新说的
```

一个**关键前提**：`firstKeptEntryId` 不是这个函数算的。它是**上一次压缩发生时**由压缩算法（`findCutPoint`，见第 8 篇第 8 章）定下的"分界线 id"——线后保留原文，线前进摘要。`buildContextEntries` 只**消费**这条线，不计算它。分清"谁画线（压缩时）"和"谁用线（组装时）"很重要。

再记住一处错位：**`COMP` 在 path 里排在 idx 6（保留区之后）**，因为它是压缩那一刻**追加**上去的、较晚的节点。这解释了 488 行。

逐块走：

- **① 找"最新"compaction（473–477）**：正向遍历，每遇到一个就覆盖 `compaction` 变量，所以最后拿到的是**路径上最靠后（最新）的**那个。
- **② 短路①：没压缩就原样返回（479）**：**这一行就是第 8 篇说的"可逆性"落点**。你 `/tree` 跳回压缩点**之前**开分支，新路径不经过任何 compaction，走这个 `return`，全量原文自动回来——可逆不是额外写的功能，是这个 `if` 的自然结果。
- **③ 定位 + 防御（483–486）**：`compactionIdx = 6`。`< 0` 理论上不可能（COMP 就是从 path 里挑出来的），仍写防御——"不信任上一步结果"的风格。
- **④ 第一段：摘要提到最前（488）**：`[COMP]`。树上 COMP 在 idx 6，这里却提到数组第 0 位——**让模型先读"前情提要"再读近期原文，按叙事逻辑排，不按文件顺序排**。
- **⑤ 第二段：挑保留区（490–498）**：用开关 `foundFirstKept` 扫 idx 0–5。对着例子：

  ```text
  i=0 u1 : id≠a2 → 开关 false → 不收
  i=1 a1 : 不收
  i=2 u2 : 不收          ← 分界线之前 → 丢弃，只活在 COMP 的摘要里
  i=3 a2 : id==firstKeptEntryId → 开关翻 true → 同一轮就收 a2  ← "第一个保留的"
  i=4 u3 : 收
  i=5 a3 : 收
  ```

  命中分界线那条（a2）**先翻开关、紧接着就被 push**，所以 `firstKeptEntry` 本身是被保留的，名副其实。
- **⑥ 第三段：压缩后新消息（499）**：`path.slice(7) = [u4, a4]`，无条件收。

产出：

```text
contextEntries = [COMP, a2, u3, a3, u4, a4]
= [摘要] + [保留区 a2,u3,a3] + [压缩后新消息 u4,a4]
丢弃：u1, a1, u2（分界线之前，只存在于摘要文本里）
```

两个"为什么"点睛：

- **⑤ 为何用开关而不是 `findIndex + slice`**：正常两者等价。区别在脏数据下——`firstKeptEntryId` 在路径里找不到时，开关写法全程 `false`，保留区为空，优雅降级成 `[摘要] + [新消息]`，**这个结论一眼可见，不需要推理**。而 `findIndex` 返回 `-1` 后 `path.slice(-1, compactionIdx)` 的行为要绕一圈才能算清：负下标被折成 `length - 1 = 8`，起点 8 大于终点 6，结果同样是空数组——**碰巧也安全，但安全性依赖 `slice` 的负下标语义，而不是依赖代码本身写得明白**。开关版本把"找不到就什么都不收"直接写在控制流里，是**不需要注释就能验证**的写法。
- **多次压缩为什么只有一个摘要块**：473 只认**最新**的 compaction，上一轮的旧 compaction 条目落在新的 `firstKeptEntryId` **之前**，于是在第二段 `foundFirstKept=false` 阶段被跳过——**旧摘要被自然吞掉**，不叠罗汉。

串回三层视图：磁盘上 u1/a1/u2 一条没删，内存树里它们也还在，**只有这里、只在当前这条路径上，它们被 `foundFirstKept` 挡在了上下文之外**。"有损的是路径，无损的是树"——损失恰好发生在 490 那个 `if (foundFirstKept)` 上。

### 4.1 摘要是"替身"，488 行是把它放回坑位

上面 ④ 说的"错位"值得单独拎出来，因为它是这个函数最容易看岔的地方。要分清两件事：

| | 位置 |
| --- | --- |
| compaction **记录**在哪 | 路径末尾（它是压缩那一刻追加的新叶子） |
| compaction **内容**讲的是哪 | 路径开头（它替换掉的那段历史） |

**记录躺在末尾，内容指向开头。** 矛盾感全部来自这里——"压缩发生在 idx 6"说的是**时刻**，"被压掉的是 idx 0–2"说的是**范围**，两句都对。

于是 `buildContextEntries` 要做的不是"过滤"，而是**顶替**：COMP 顶掉了 u1/a1/u2，就该站到它们原来站的位置去。

```text
path:      [u1 a1 u2] [a2 u3 a3] [COMP] [u4 a4]
             ↓ 被顶替
context:   [  COMP  ] [a2 u3 a3]        [u4 a4]
              ↑ 占的是 u1/a1/u2 腾出的坑位
```

推论：**"删"和"搬"必须一起做，光 filter 不够**。只删不搬的话 COMP 还留在尾巴上，模型会先读完近期原文、最后才读到"以上省略，前情提要是……"——先看细节再看背景，读起来是反的。488 行那个 `[compaction]` 初始值就是"搬"，490 那个 `if (foundFirstKept)` 才是"删"。

由此得到这个函数真正在守的东西：**输出永远是时间有序的，摘要顶替谁就站在谁的位置上**。模型看不出中间动过手脚。

### 4.2 三段是拼图，不是图层

第二个容易看岔的地方：摘要覆盖的范围和保留区**在时间上不相交**，所以摘要提到最前不会和保留区"内容交叉"。

保证来自压缩那一侧（`compaction.ts:782`，详见第 8 篇 8.1）：摘要范围是 `[boundaryStart, historyEnd)`，保留区是 `[firstKeptEntryIndex, ...)`，**前者的开区间上界正好是后者的下界**，半开区间一刀两断。多轮压缩靠 `boundaryStart = 上一次的 firstKeptEntryIndex` 接力（`compaction.ts:761`），于是：

```text
[摘要① 覆盖 0-2][摘要② 覆盖 3-7][原文尾巴 8-]
```

首尾相接，不重不漏。**任何一条原始记录最多只会被摘要一次**——要么还是原文（在保留区），要么已经进了某一段摘要，然后永久退出，不会被第二段摘要再盖一遍。

所以上下文里的几段是**拼图**（各管一段，拼起来是完整历史），不是**图层**（同一段内容的多个版本叠在一起）。这也解释了上面"多次压缩为什么只有一个摘要块"——不是新摘要盖住了旧摘要，是新摘要**吞并**了旧摘要的原料，旧摘要条目随即落到分界线之前被丢弃。

### 4.3 另一份实现：`retainedTail`

`array-session-reader.ts:95-98` 处理压缩边界的方式和本章不同，值得对照记一笔：

```typescript
if (current.type === "compaction") {
	if (current.retainedTail) break;
	stopAtEntryId = current.firstKeptEntryId ?? null;
}
```

它是**边爬树边处理压缩边界**（自 leaf 向根走，撞见 compaction 就把停止点设成 `firstKeptEntryId`），而本章是**先爬完整条路径、再裁剪**。`retainedTail` 这个字段在 `session-manager.ts` 那份实现里没有对应分支——两份实现对压缩边界的建模不完全一致，具体差异待查。

---

## 第 5 章 `sessionEntryToContextMessages`：按类型投影成消息（类型维度）

上一站产出的还是**条目**（`SessionEntry`）。把条目变成真正的**消息**（`AgentMessage`），是这一站干的。

```typescript
export function sessionEntryToContextMessages(entry: SessionEntry): AgentMessage[] {
	if (entry.type === "message") {
		const message = entry.message;
		if ((role 是 user/assistant/toolResult) && message.content == null) {
			return [{ ...message, content: [] }];   // 428–435 null 防御：补空数组
		}
		return [message];                            // 普通消息，原样
	}
	if (entry.type === "custom_message") {
		return [createCustomMessage(...)];           // bashExecution（`!` 命令）走这
	}
	if (entry.type === "branch_summary" && entry.summary) {
		return [createBranchSummaryMessage(...)];
	}
	if (entry.type === "compaction") {
		return [createCompactionSummaryMessage(entry.summary, entry.tokensBefore, ...)];  // 摘要文本→一条消息
	}
	return [];                                       // 449 其它一律空
}
```

**先看整体形状**：四个 `if` 分支，落点却是**三种命运**——

| entry | 分支写法 | 命运 |
| --- | --- | --- |
| `message` | `return [message]` | **剥离**：载荷本身就是现成消息，掏出来即可 |
| `custom_message` / `branch_summary` / `compaction` | `return [create*Message(…)]` | **重建**：载荷是散字段，得现场拼成消息对象 |
| `custom` / `model_change` / `label` / `session_info` / … | 没有分支，掉到 `:449` | **丢弃**：压根不对应任何消息 |

为什么同样是会话记录，命运差这么多？因为**它们在磁盘上的存储结构就不同**——根因见 5.1。这里先记住结论：**第三档才是"什么东西不进上下文"的唯一判决点。**

四个要点：

- **`message` 的 null 防御（428–435）**：会话文件解析时不做完整校验，旧版本 / fork / 手改文件可能出现 `content` 为 null 的消息，这里补成 `content: []`，不让下游拿到 null 崩。典型的"边界不信任外部数据"。
- **`compaction` → 一条摘要消息（446–448）**：还记得上一站把 compaction 提到数组第 0 位吗？到这里它被 `createCompactionSummaryMessage` 变成**一条真正的消息**——所以 LLM 收到的**第一条消息就是这段前情摘要**。上一站和这一站在这里接上了。
- **`custom_message`**：`!` 命令的 `bashExecution` 从这条路变成消息（`content ?? []` 又是一处 null 防御）。
- **兜底 `return []`（449）**：`model_change`、`thinking_level_change`、`label` 这些**全部落到这，投影成空数组**。

**`flatMap` 才是"进不进上下文"的最终执行点。** 在总装配线里（下一章 515 行）：

```typescript
buildContextEntries(...).flatMap(sessionEntryToContextMessages)
```

每个条目投影成 0~N 条消息的数组，`flatMap` 把它们拍平成一条连续 message 流。**返回 `[]` 的条目贡献 0 条，直接从消息流里蒸发。** 这就解开了一个迟早会问的现象：`model_change` 明明还在 `buildContextEntries` 的输出数组里，为什么不占 LLM 上下文？——它没被裁掉，是**被投影成了空**。

### 5.1 三种命运的根因：存储结构不同

看两条真实的 `.jsonl`（第二条是学扩展时 test06 自己写进去的）：

```json
{"type":"message","id":"6fbb1cd6","parentId":"d27f0567","timestamp":"2026-08-10T04:47:27.015Z",
 "message":{"role":"user","content":[{"type":"text","text":"看看 AGENTS.md 的前 20 行写了什么"}],"timestamp":1786337247013}}

{"type":"custom_message","customType":"test06-inject","content":"[系统注入] 现在是本会话第 1 次提问……",
 "display":true,"id":"43ac450f","parentId":"62b17225","timestamp":"2026-08-10T11:23:19.993Z"}
```

**存储结构根本不同**：前者是「元数据 + 一个完整的内层 `message` 对象」，后者是「元数据与载荷字段平铺混在一起」。所以前者只需**剥壳**，后者必须**重建**。

嵌套还是平铺不是随手定的，规律是——**载荷是"外来对象"就整体存，是"自家字段"就拆开存**：

| | 载荷归属 | 存法 | 代价 / 收益 |
| --- | --- | --- | --- |
| `message` | `packages/ai` 定义、要原样发给 provider | 整体嵌套 | `AssistantMessage` 有 `usage`/`stopReason`/`diagnostics` 等十几个字段且还会加，整体存**不丢字段、不用改持久化逻辑**；读时 `return [message]` 一行 |
| `custom_message` / `branch_summary` / `compaction` | pi 自己定义，形状它说了算 | 字段平铺 | 直观、好 `grep`；代价是读时要拼回对象，`create*Message` 就是这笔账的还款 |

`create*Message` 本身几乎不干活——套个对象字面量、把 role 标签贴上，唯一的实际操作是 `new Date(iso).getTime()`：磁盘上是 ISO 字符串（给树排序、给人读），`Message` 类型要求毫秒 `number`。顺带注意 `message` 条目里**两个 timestamp 并存**（外层 ISO 给树，内层毫秒给消息），正是同一件事的另一面。

**第三档（丢弃）的根因也是存储结构**：`model_change`、`label`、`session_info` 这些条目的字段本身就是元数据——"这里换了模型"、"这里打了个标签"——**没有任何字段是给模型看的载荷**，自然无从投影。它们不是"被过滤掉的消息"，而是**从来就不是消息**。

`custom` 尤其值得看，因为它和 `custom_message` 长得几乎一样。对照 test06 留下的两条数据，区别就写在字段名上：

```json
{"type":"custom_message","customType":"test06-inject","content":"…"}   ← content：给模型看的
{"type":"custom",        "customType":"test06-count", "data":{"count":1}}  ← data：给扩展自己用的
```

**差一个后缀，命运完全不同**：前者有分支、进上下文；后者掉到 `:449`、永不进上下文。扩展用 `appendEntry` 存的状态之所以能安全地待在 session 里而不污染模型，全靠这一行。

### 5.2 返回数组而不是 `AgentMessage | null`

每个分支实际只返回 0 或 1 条，签名却是数组，有两处收益。

**① 调用处不需要 `filter`。** `flatMap` 让 0 / 1 / N 三种情况用同一套写法，空数组自动蒸发；若返回 `AgentMessage | undefined`，调用处得写成 `.map(...).filter(m => m !== undefined)`，还要额外做类型收窄。**用空数组表示"没有"，比用 `null` 表示"没有"更好组合。**

**② 压缩算法白捡三个判定。** 因为"不可见"被统一表达成"空数组"，`compaction.ts` 直接拿它当探针，问了三个不同的问题：

```typescript
// :439  这条占多少 token？   → model_change 投影成空 → 0 → continue，不参与倒数
const messageTokens = sessionEntryToContextMessages(entry).reduce((s, m) => s + estimateTokens(m), 0);

// :464  这条在上下文里可见吗？ → 长度 0 才允许被切点顺手捎带
if (prevEntry.type === "compaction" || sessionEntryToContextMessages(prevEntry).length > 0) break;

// :373  这条能当切点吗？     → 投影出来的消息交给 isCutPointMessage 判断
if (sessionEntryToContextMessages(entry).some(isCutPointMessage)) cutPoints.push(i);
```

关键在于压缩**没有自己重新判断一遍 `entry.type`**。它算的是 token **预算**，而预算属于"投影之后的世界"——一条 `model_change` 在文件里占几十字节，在上下文里占 0 token，**只有投影函数知道这件事**。若压缩自己维护一份"哪些类型不占 token"的清单，新增 entry 类型时两处都要改，漏一处切点就偏了。

**一句话：投影函数是"entry 在上下文里长什么样"这个知识的唯一持有者，谁想知道就来问它，而不是自己猜。**（对照第 8 篇 8.1 —— 那三处调用正是切点算法的地基。）

---

## 第 6 章 `getSessionContextSettings`：设置靠重放

上下文不只有消息，还有"此刻该用哪个模型、哪个思考等级"。这也是从历史里推出来的。

```typescript
function getSessionContextSettings(path: SessionEntry[]): Pick<SessionContext, "thinkingLevel" | "model"> {
	let thinkingLevel = "off";
	let model: { provider: string; modelId: string } | null = null;

	for (const entry of path) {                                    // 404
		if (entry.type === "thinking_level_change") {
			thinkingLevel = entry.thinkingLevel;
		} else if (entry.type === "model_change") {
			model = { provider: entry.provider, modelId: entry.modelId };
		} else if (entry.type === "message" && entry.message.role === "assistant") {
			model = { provider: entry.message.provider, modelId: entry.message.model };
		}
	}
	return { thinkingLevel, model };
}
```

遍历整条 path，**后者覆盖前者**，拿到"最后生效的"设置。这正是第 3 章说 `buildSessionPath` 必须返回**正序**的原因——倒序的话"取最新"就反了。

两个细节：`model` 有两个来源——显式的 `model_change` 条目，以及 assistant 消息**自带**的 `provider/model`；都会更新 `model`，取路径上最后一个。所以即便没有 `model_change` 条目，最后一条 assistant 用的模型也会被认作"当前模型"。

这又是一个"**配置即事件、状态靠重放**"的实例——和第 8 篇里 label 的重放、leafId 的推进同源。设置不是存在某个字段里，而是散落在树上的一串 change 事件，用的时候重放路径取最新。

---

## 第 7 章 `buildSessionContext`：总装配线

前面六个部件，在这里汇合。

```typescript
export function buildSessionContext(entries, leafId?, byId?): SessionContext {
	const path = buildSessionPath(entries, leafId, byId);                                    // 513 ① 选路径
	const { thinkingLevel, model } = getSessionContextSettings(path);                        // 514 ② 解析设置
	const messages = buildContextEntries(entries, leafId, byId).flatMap(sessionEntryToContextMessages); // 515 ③ 裁剪+投影
	return { messages, thinkingLevel, model };
}
```

三步：选路径 → 解析设置 → 裁剪并投影，产出 `SessionContext = { messages, thinkingLevel, model }`。

一个小观察：`buildSessionPath` 在这条线里被**算了两次**——514 的 `getSessionContextSettings` 用一次，515 的 `buildContextEntries` 内部又调一次（`buildContextEntries` 第一行就是 `buildSessionPath`）。看似重复，但因为是纯函数、且 `byId` 被复用、单次开销只有 O(路径深度)，实际成本可忽略——用"多算一次的确定性"换"少一个共享中间变量的简单性"，是划算的取舍。

**最后划一道边界，别搞混**：这里产出的 `messages` 还是 **`AgentMessage[]`**，不是最终发给 provider 的 HTTP body。它离真正上路还差下篇要讲的 `transformContext() → convertToLlm()`——那一步才把 `AgentMessage` 翻译成各家 provider 的 `Message` 格式。`buildSessionContext` 负责"**装配出会话视图**"，翻译成 provider 方言是下一棒的事。

---

## 第 8 章 一个漂亮的设计：两层正交

把第 4 章和第 5 章并排看，会发现一个干净的关注点分离：

```text
buildContextEntries           →  只按【位置】裁（压缩边界），完全不看条目类型
sessionEntryToContextMessages →  只按【类型】投影，完全不看条目在哪个位置
```

一个管"位置维度留哪些条目"，一个管"类型维度变成什么消息"，**两个维度正交、各管一件事**。所以"一个 `model_change` 会不会进上下文"，是两层**共同**决定的：先看它在不在压缩保留区（位置），再看它投影成啥（类型 = `[]`）。

这种正交分解的好处是每一层都能独立推理、独立测试：改压缩算法不用碰投影逻辑，加一种新消息类型（如 `bashExecution`）只需在投影层加一个 `if`，裁剪层无感。

---

## 第 9 章 交接点：`agent-loop` 的二十行

前八章的终点是 `buildSessionContext` 产出的 `AgentMessage[]`。它怎么变成 HTTP 请求体？全部交接动作压缩在 `packages/agent/src/agent-loop.ts:303-338` 一个函数里——`streamAssistantResponse`，**每轮要向模型要一次回复就跑一遍**：

```typescript
async function streamAssistantResponse(context, config, signal, emit, streamFunction) {
	// ① AgentMessage[] → AgentMessage[]
	let messages = context.messages;
	if (config.transformContext) {                       // 313
		messages = await config.transformContext(messages, signal);
	}

	// ② AgentMessage[] → Message[]
	const llmMessages = await config.convertToLlm(messages);   // 319

	// ③ 三条支流汇合
	const llmContext: Context = {                        // 323
		systemPrompt: context.systemPrompt,
		messages: llmMessages,
		tools: context.tools,
	};

	// ④ 最后一刻才解析密钥
	const resolvedApiKey =
		(config.getApiKey ? await config.getApiKey(config.model.provider) : undefined) || config.apiKey;

	const response = await streamFunction(config.model, llmContext, { ...config, apiKey: resolvedApiKey, signal });
```

四个要点：

**① `convertToLlm` 是注入进来的，不是 `agent` 包自己的。**

```typescript
// agent.ts:223
this.convertToLlm = runtimeOptions.convertToLlm ?? defaultConvertToLlm;
```

`packages/agent` 压根不知道 `compactionSummary` / `bashExecution` 这些 role 存在——它只在配置里挖了个**洞**，由 coding-agent 在 `sdk.ts` 填自己的实现。这解释了一个乍看奇怪的位置：处理自定义 role 的 `convertToLlm` 住在 `coding-agent/src/core/messages.ts`，而不是定义 `AgentMessage` 的 `agent` 包里。**谁定义的自定义类型，谁负责把它翻译回标准形态。**

**② `transformContext` 排在 `convertToLlm` 之前，是刻意的。** 扩展的 `context` 钩子挂在这一层，因此它拿到的是**结构完好的 `AgentMessage`**——还看得见 `customType`、还能按 role 筛选。等过了 ②，四种自定义 role 全塌成 `user`，就再也分不出谁是谁了。**能插手的地方必须在不可逆的一步之前。**

**③ 两级取密钥，动态优先、静态兜底。**

| | 形态 | 何时确定 |
| --- | --- | --- |
| `config.getApiKey` | **函数**，每轮现取 | 调用时（可能顺带刷新 token） |
| `config.apiKey` | **字符串** | 装配 Agent 时定死 |

动态那级是为 OAuth 准备的：access token 有有效期，可能这轮开始时还好、要发请求时已过期，所以不能装配阶段取一次存着。pi 填进去的实现在 `model-registry.ts:125`，`await this.runtime.getAuth(provider)` 里面藏着刷新逻辑——**那一下 `await` 可能真的发了一次 HTTP 请求**。

两个细节值得记：用 `||` 而非 `??`，因为 `getApiKey` 返回空字符串时应当继续兜底（`"" ?? x` 会得到 `""`，拿着空串去发请求只会 401）；`getApiKeyForProvider` 内部 `catch { return undefined }` 而不抛错，正是为了**把决定权让给这个 `||`**——刷新失败还能退回静态密钥，抛出去则整轮直接崩。

**④ `Context` 是 `packages/ai` 的统一入口**，详见第 11 章。

---

## 第 10 章 `convertToLlm`：七种 role 塌缩成三种

`packages/coding-agent/src/core/messages.ts:161`。一个 `switch` 干完全部工作：

```typescript
export function convertToLlm(messages: AgentMessage[]): Message[] {
	return messages
		.map((m): Message | undefined => {
			switch (m.role) {
				case "bashExecution": …          // → user（文本化），excludeFromContext 则丢弃
				case "custom": …                 // → user
				case "branchSummary": …          // → user + <summary> 包装
				case "compactionSummary": …      // → user + <summary> 包装
				case "user":
				case "assistant":
				case "toolResult":
					return m;                    // 原样放行
				default: {
					const _exhaustiveCheck: never = m;
					return undefined;
				}
			}
		})
		.filter((m) => m !== undefined);
}
```

`AgentMessage` 有 7 种 role（3 标准 + 4 个 coding-agent 通过声明合并加进去的），`Message` 只有 3 种。**这一步就是把多出来的 4 种压平。**

| 输入 role | 输出 | 永久丢失的字段 |
| --- | --- | --- |
| `user` / `assistant` / `toolResult` | 原样 | — |
| `bashExecution` | `user`，结构揉成文本 | `command` / `exitCode` / `cancelled` / `truncated` 的结构形态 |
| `custom` | `user` | **`customType`、`display`、`details`** |
| `branchSummary` | `user` + `<summary>` 包装 | **`fromId`** |
| `compactionSummary` | `user` + `<summary>` 包装 | **`tokensBefore`** |

**在模型眼里没有"这是压缩摘要"这种东西，只有一个用户说了段话。**

### 10.1 role 区分没了，就靠文本说明

既然塌缩后无法用 role 表达"这是什么"，只能把说明写进内容。这就是 `messages.ts:12-25` 那几个常量的用途：

```typescript
export const COMPACTION_SUMMARY_PREFIX = `The conversation history before this point was compacted into the following summary:

<summary>
`;
export const COMPACTION_SUMMARY_SUFFIX = `
</summary>`;
```

模型实际收到的是：

```text
The conversation history before this point was compacted into the following summary:

<summary>
（摘要正文）
</summary>
```

`branchSummary` 同款，前缀换成 `The following is a summary of a branch that this conversation came back from:`。

**用 XML 风格标签而非裸文本，是因为模型对成对标签的边界识别准得多**——它能清楚知道摘要从哪开始到哪结束，不至于把摘要里的内容误当成用户的新指令。这也是第 4 章"摘要提到最前"能成立的前提：既然它排在第 0 位，就更需要一个明确的边界标记把它和后面的真实对话隔开。

`bashExecution` 的文本化最复杂，有专门的 `bashExecutionToText`（`:90`）：命令、输出、退出码、是否取消、是否截断、完整输出路径，一个结构化对象拼成一段自然语言。**这些诊断信息不能省**——模型必须能区分"命令失败了"和"用户按了 Ctrl+C"，两种情况后续处理完全不同。

### 10.2 两个过滤点，语义不同

```typescript
case "bashExecution":
	if (m.excludeFromContext) return undefined;   // `!!` 前缀
```

配合末尾的 `.filter((m) => m !== undefined)` 清走。注意它和第 5 章那个 `return []` 是**两个不同的闸门**：

| 闸门 | 位置 | 挡掉什么 | 语义 |
| --- | --- | --- | --- |
| `return []` | `sessionEntryToContextMessages` | `custom` / `model_change` / `label` | **压根不是消息** |
| `return undefined` | `convertToLlm` | `!!` 执行记录 | **是消息，但这条不给模型看** |

两层各挡一类，都不越界。

### 10.3 `never` 穷尽检查：用类型系统强制人做事

```typescript
default: {
	const _exhaustiveCheck: never = m;
	return undefined;
}
```

所有 `case` 都覆盖到时，`m` 在 `default` 分支被收窄成 `never`，赋值合法、编译通过。**一旦有人往 `CustomAgentMessages` 里加了第八种 role 却忘了在这里加 `case`，`m` 就不再是 `never`，编译当场报错。**

源码注释挑明了意图：

> 穷尽检查确保新增自定义消息角色时必须同步更新模型转换逻辑。

这是 TypeScript 里把"别忘了改这里"从**口头约定**变成**编译期强制**的标准手法。声明合并让扩展消息类型变得很容易加，这个 `never` 就是配套的刹车——**开了口子，就得在出口处设卡。**

---

## 第 11 章 `Context`：把翻译推迟到最后一刻

`packages/ai/src/types.ts:553`，三个字段：

```typescript
export interface Context {
	systemPrompt?: string;
	messages: Message[];
	tools?: Tool[];
}
```

**它是"这次要发给模型的全部输入"**，`convertToLlm` 的产物只占其中一个字段。模型需要知道的不止对话内容：少了 `tools` 它不知道自己能调工具，少了 `systemPrompt` 它不知道自己是谁。

### 11.1 为什么不把三样直接拼在一起

因为**各家 API 放的位置不一样**。同一个 `systemPrompt`：

```typescript
// Anthropic：顶层独立字段（anthropic-messages.ts:1037）
params.system = [{ type: "text", text: sanitizeSurrogates(context.systemPrompt), … }];
```

```typescript
// OpenAI：塞进消息数组第一条（openai-completions.ts:1050）
params.push({ role: role, content: sanitizeSurrogates(context.systemPrompt) });
```

```json
// Anthropic 的 body                     // OpenAI 的 body
{ "system": [...], "messages": [...] }   { "messages": [{"role":"system",…}, …] }
```

**在 Anthropic 眼里系统提示词不是消息，在 OpenAI 眼里它就是第一条消息。**

如果 pi 内部提前把 systemPrompt 塞进 `messages`，到 Anthropic 那边还得捞出来——而捞的时候拿什么区分"这是系统提示词"和"这是一条普通用户消息"？信息已经丢了。

所以 `Context` 的全部理由是：**保留区分，把翻译推迟到最后一刻。** 这和第 5 章 `create*Message` 保留结构、第 10 章才拼文本，是同一条原则在不同尺度上的复用。

### 11.2 provider 层做什么：看一家就够

`packages/ai/src/api/` 下有十几个 provider 文件，都在干同一件事的不同方言。以 Anthropic 的 `buildParams`（`anthropic-messages.ts:981`）为样本，四件必需品先就位：

```typescript
const params: MessageCreateParamsStreaming = {
	model: model.id,
	messages: convertMessages(transformedMessages, …),
	max_tokens: options?.maxTokens ?? model.maxTokens,
	stream: true,
};
```

然后往上挂可选字段。三处值得一提：

**① OAuth 时硬插一条 Claude Code 身份**（`:1019`）：

```typescript
if (isOAuthToken) {
	params.system = [{ type: "text", text: "You are Claude Code, Anthropic's official CLI for Claude.", … }];
	if (context.systemPrompt) params.system.push({ type: "text", text: sanitizeSurrogates(context.systemPrompt), … });
}
```

用 Claude 订阅（OAuth）而非 API key 时，**pi 必须把自己报成 Claude Code**，用户的 systemPrompt 只能排第二条。这是订阅授权的要求，不是可选项。

**② `cache_control` 挂在 system 上**——提示词缓存的锚点。系统提示词每轮内容相同，标记成可缓存能显著省钱。

**③ 能力差异靠 compat 表兜**：

```typescript
if (options?.temperature !== undefined && !options?.thinkingEnabled && compat.supportsTemperature) {
	params.temperature = options.temperature;
}
```

注释给了两条排除理由：**`temperature` 与扩展推理互斥，Claude Opus 4.7+ 也不支持该参数**。同一 provider 下不同型号能力不同，靠 `getAnthropicCompat(model)` 查表决定发不发某个字段。**发错字段 API 直接 400，所以这些判断不是洁癖，是必需品。**

再往下（`convertMessages` 逐条把 `toolResult` 译成 `tool_result` block、`toolCallId` 译成 `tool_use_id`，`convertTools` 译工具定义）是纯粹的字段对照工作，**看一家就能推知其余，不必逐个走读**。

---

## 第 12 章 全链路回望：三种形态与唯一不可逆的一步

```text
.jsonl 各行
   │ 解析 + 重放（第 8 篇）
   ▼
SessionEntry[]                    树，全量事实
   │ buildSessionPath             选路径          （第 3 章）
   │ buildContextEntries          挑条目（位置）   （第 4 章）
   │ sessionEntryToContextMessages 变消息（类型）  （第 5 章）
   ▼
AgentMessage[]                    7 种 role，结构完好
   │ transformContext             扩展钩子插手     （第 9 章）
   │ convertToLlm                 塌缩成 3 种 role （第 10 章）
   ▼
Message[]                         中立形态
   │ Context { systemPrompt, messages, tools }    （第 11 章）
   │ buildParams（各家 provider 各译各的）
   ▼
HTTP body
```

三种形态各自的定位：

| 形态 | 谁定义 | 特点 |
| --- | --- | --- |
| `SessionEntry` | coding-agent | 带 `id`/`parentId`，**是树的节点**，只追加不修改 |
| `AgentMessage` | agent 包 + coding-agent 声明合并 | 7 种 role，**结构还在**（TUI 渲染、扩展钩子都靠它） |
| `Message` | ai 包 | 3 种 role，**中立**，是所有 provider 的共同输入 |

**每一层只负责一次转换，且都是纯函数**——所以你能在任何一层插手：压缩改 `SessionEntry`、`context` 钩子改 `AgentMessage`、provider 层改报文。

### 12.1 全链路唯一不可逆的一步

是 `convertToLlm`。结构塌成文本、7 种 role 塌成 3 种、`tokensBefore` / `fromId` / `customType` / `display` 全部丢失。

**在它之前，一切都还能按结构操作；在它之后，只剩字符串。**

这一条决定了整个扩展点的布局：`transformContext` 必须排在它前面（第 9 章 ②），`create*Message` 必须保留结构到那之前（第 5 章 5.1），`Context` 必须把三条支流分开存到那之后（第 11 章）。**知道哪一步不可逆，就知道所有的口子该开在哪。**

---

## 第 13 章 工程模式清单

本篇涉及的可迁移设计模式：

1. **纯函数核心 + 薄状态包装**：核心逻辑是 6 个模块级纯函数（输入全靠参数），`SessionManager` 的同名方法只转发（`:1366`）。好测试、好复用。
2. **事实层 vs 投影层分离**：上下文是每次调用前从事实**现算的投影**，不是存着的字段。分支、可逆压缩、审计因此全是"换一种投影"，免费得到。
3. **可选注入 + 惰性回退**：`buildEntryIndex` 的 `if (byId) return byId`——能复用就复用（高性能路径），没有就自给自足（好测试）。
4. **O(1) 查找表预处理**：把只能顺序遍历的数组，预处理成能按 id 瞬间跳转的 Map，让回溯从 O(n×深度) 降到 O(深度)。
5. **路径局部性**：组装只走 leaf→root 一条链，O(路径深度)，废弃分支零访问。
6. **关注点正交分解**：裁剪（位置）与投影（类型）两个维度彻底解耦，各层独立演化。
7. **防御式投影**：null content 补空数组、`compactionIdx < 0` 兜底、`firstKeptEntryId` 找不到时优雅降级——单点脏数据不放大成崩溃。
8. **配置即事件 + 重放取最新**：模型 / 思考等级不存字段，而是树上一串 change 事件，用时重放路径取最后生效。
9. **不变量的作用域就是防御的省略范围**：同一段父链遍历，`session-manager` 靠 append-only 不变量省掉防环，SQLite 存储层跨进程信任边界就必须把 `visited` 补回来（3.1）。省防御前先问一句：**这个不变量是谁在什么范围内保证的？**
10. **替身要占坑，不能只删不搬**：摘要顶替一段历史，就必须站到那段历史的位置上（4.1）。凡是"用 A 代表一批 B"的场景，删 B 之后都要把 A 放回 B 的坑位，否则顺序语义会断。
11. **用半开区间表达分界线**：一个 `firstKeptEntryIndex` 同时是"摘要终点"和"保留区起点"，天然不重不漏（4.2）。**用两个数表示一条边界，迟早会对不齐。**
12. **降级路径要一眼可见，而不是碰巧安全**：开关扫描 vs `findIndex + slice`，脏数据下结果相同，但前者的正确性写在控制流里，后者依赖 `slice` 的负下标语义（第 4 章 ⑤）。
13. **外来对象整体存，自家字段拆开存**：`message` 嵌套持久化（不丢字段、免维护），pi 自己的条目平铺（直观、好 grep，代价是读时重建）。**判据是 schema 归谁所有**（5.1）。
14. **用空数组表示"没有"，而不是 `null`**：`[]` 能被 `flatMap` 直接吞掉，`null` 则强迫每个调用处补一次 `filter` 和类型收窄（5.2）。
15. **知识只存一处，其余来问**：压缩算法不自己维护"哪些类型不占 token"，而是跑一遍投影函数拿答案——新增 entry 类型时只改一处（5.2）。
16. **把不可逆的一步推到最后**：结构保留到 `convertToLlm` 才拍成文本，`systemPrompt`/`tools`/`messages` 分开存到 provider 层才合并。**先塌缩就再也分不开了**（第 10、11 章）。
17. **扩展点必须开在不可逆之前**：`transformContext` 排在 `convertToLlm` 前一行，所以钩子拿到的是结构完好的 `AgentMessage`（第 9 章 ②）。**想让人插手，就得在信息还没丢的时候给机会。**
18. **依赖注入解开分层循环**：`agent` 包只挖 `convertToLlm` 的洞，coding-agent 填自己的实现——**谁定义的自定义类型，谁负责翻译回标准形态**（第 9 章 ①）。
19. **开了口子就在出口设卡**：声明合并让加 role 很容易，`never` 穷尽检查保证漏改必然编译失败（10.3）。
20. **兜底链要允许失败下坠**：`getApiKeyForProvider` 内部 `catch → undefined` 而非抛错，`||` 而非 `??`，两处配合才让"动态取不到就退回静态密钥"真正成立（第 9 章 ③）。

---

## 第 14 章 复习自测

尝试不看正文回答（答案都在上文）：

1. 发给 LLM 的上下文是"存"出来的还是"算"出来的？输入和输出各是什么？
2. `buildEntryIndex` 的 `if (byId) return byId` 解决了什么？运行时它到底建不建索引？
3. `buildSessionPath` 为什么最后要 `reverse`？不 reverse 会让哪个下游出错？
4. `leafId` 传 `null`、传有效 id、传 `undefined` 分别走哪条分支、得到什么？为什么用 `=== null` 而非 `!leafId`？
5. 上溯循环为什么不需要 `visited` 防环？
6. `buildContextEntries` 里，路径上没有 compaction 时返回什么？这一行和"压缩可逆"有什么关系？
7. 三段拼接的顺序是什么？为什么摘要 `COMP` 在树上排 idx 6，却出现在上下文第 0 位？
8. 第二段为什么用 `foundFirstKept` 开关而不是 `findIndex + slice`？两者在什么情况下行为不同？
9. 连续压缩三次后，上下文里有几个摘要块？代码在哪一步把旧摘要吞掉？
10. `model_change` 在路径上、也在 `buildContextEntries` 的输出里，为什么不占 LLM 上下文？最终裁决在哪一行？
11. "两层正交"指哪两层？各按什么维度工作？
12. `getSessionContextSettings` 靠什么机制拿到"当前模型"？`model` 的两个来源是什么？
13. `buildSessionContext` 产出的 `messages` 是最终发给 provider 的报文吗？还差哪一步？
14. `AgentMessage` 有几种 role，`Message` 有几种？多出来的几种在哪一步、变成了什么？
15. `transformContext` 为什么必须排在 `convertToLlm` 之前？换个顺序会失去什么能力？
16. `convertToLlm` 住在 coding-agent 而不是 agent 包，为什么？`agent` 包怎么保证它一定会被提供？
17. 压缩摘要为什么要套 `<summary>` 标签？不套会有什么风险？
18. 本篇出现了三个"丢弃"闸门（`return []`、`return undefined`、以及 `!!` 的 `excludeFromContext`），分别在哪一层、语义有何不同？
19. `never` 穷尽检查防的是什么场景？它在什么时刻报错——运行时还是编译时？
20. 同一个 `systemPrompt`，Anthropic 和 OpenAI 分别放在报文的什么位置？这解释了 `Context` 为什么要把它单独拎出来？
21. 取 API key 那一行为什么用 `||` 而不是 `??`？`getApiKeyForProvider` 里的 `catch { return undefined }` 和它是什么关系？
22. 全链路唯一不可逆的一步是哪一步？说出至少两个"因为它不可逆所以才那样设计"的例子。

---

*基于 2026-08-14 / 08-15 的源码精读整理（对话式逐行走读）。上承第 8 篇（会话树的形状）。本篇只覆盖"出去"的方向；响应流回来之后（SSE 解析 → `AssistantMessage` → 落盘 → 下一轮）见第 1、2 篇。`systemPrompt` 与 `tools` 这两条支流各自怎么攒出来，见第 3 篇（提示词六道关卡）与第 5 篇（扩展注册工具）。配套阅读：`docs-zh/coding-agent/compaction.md`（压缩细节）。*
