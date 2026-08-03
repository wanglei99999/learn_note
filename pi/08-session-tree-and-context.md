# 08 — 会话树与上下文管理：从一个 JSONL 文件到 LLM 上下文

> 学习系列第 8 篇（全景地图见第 0 篇，agent 运行时见第 1 篇）。本篇沿着一次真实的动手实验，完整走通 pi 的会话持久化链路：**磁盘上的 JSONL 文件 → 内存投影 → 会话树 → 当前路径 → 发给 LLM 的上下文**，覆盖分支、标签、压缩（compaction）、`!` 命令注入等全部会话机制。
>
> 所有 `文件:行号` 基于 commit `c728df8dc`（v0.83.0），核心文件是 `packages/coding-agent/src/core/session-manager.ts`（约 1850 行）。注意它与第 1 篇讲的 `packages/agent/src/harness/session/` 是两套平行实现——本篇讲的是 `pi` CLI 实际使用的这套。

## 目录

- 第 1 章 三层视图：一张图看懂全部
- 第 2 章 磁盘层：JSONL 文件格式与条目类型
- 第 3 章 加载：流式解析器的四个讲究
- 第 4 章 内存投影：四个结构，一次重放
- 第 5 章 树的重建：两遍 + Map，O(n) 搞定
- 第 6 章 上下文组装：路径回溯与压缩边界
- 第 7 章 分支：移动一个指针
- 第 8 章 压缩：有损的是路径，无损的是树
- 第 9 章 `!` 命令与自定义消息类型
- 第 10 章 工程模式清单
- 第 11 章 复习自测

---

## 第 1 章 三层视图：一张图看懂全部

pi 的会话机制可以压缩成一句话：**磁盘上是只追加的事件日志，内存里是重放日志得到的投影，LLM 看到的是投影上一条路径的（可能被摘要过的）切片。**

```text
┌─────────────────────────────────────────────────────────┐
│ 磁盘：JSONL 文件（append-only，全量历史，永不改写）        │
│   每行一个条目，靠 id + parentId 连成树                    │
└──────────────────┬──────────────────────────────────────┘
                   │ 打开会话时流式解析一次（之后不再读）
┌──────────────────▼──────────────────────────────────────┐
│ 内存：fileEntries[] + byId Map + labels + leafId         │
│   /tree 视图、分支切换、标签全在这层，毫秒级               │
└──────────────────┬──────────────────────────────────────┘
                   │ 每次调用 LLM 前组装
┌──────────────────▼──────────────────────────────────────┐
│ 上下文：leaf → root 回溯出一条路径，                       │
│   遇到压缩条目则替换为 [摘要 + 保留尾段 + 之后的新消息]     │
└─────────────────────────────────────────────────────────┘
```

三层各自回答一个问题：

| 层 | 回答的问题 | 特点 |
| --- | --- | --- |
| 磁盘 JSONL | "发生过什么" | 全量、只追加、崩溃安全 |
| 内存树 | "历史长什么形状" | 全量、O(1) 查找、含废弃分支 |
| LLM 上下文 | "模型现在需要知道什么" | 单条路径、可被压缩截断 |

## 第 2 章 磁盘层：JSONL 文件格式与条目类型

会话文件在 `~/.pi/agent/sessions/`（按工作目录组织），文件名形如 `<时间戳>_<会话UUID>.jsonl`。每行一个 JSON 对象。

### 2.1 唯一的结构规则

除首行外，**每个条目都有 `id`（8 位十六进制短 ID）和 `parentId`**。整棵树就靠这两个字段。id 由 `generateId()`（`session-manager.ts:251`）生成：`randomUUID()` 截前 8 位，与 `byId` 碰撞检查，撞了重试最多 100 次后回退完整 UUID。

### 2.2 条目类型一览

| type | 作用 | 备注 |
| --- | --- | --- |
| `session` | 首行文件头：版本、会话 ID、cwd | 无 id/parentId，严格校验 |
| `message` | 对话消息 | role 可为 user / assistant / toolResult / **bashExecution**（见第 9 章）等 |
| `model_change` | 切换模型 | **改设置也是树上的节点** |
| `thinking_level_change` | 调整思考等级 | 同上 |
| `label` | 给某节点打标签（Shift+L） | 指向 `targetId`，见 4.2 |
| `compaction` | 压缩摘要 | 顶层条目而非普通消息，见第 8 章 |
| `branch_summary` | 分支摘要 | `/tree` 跳转时选 "Summarize" 产生 |

一次真实会话的树（来自动手实验，`★` 处有两个孩子即分支点）：

```text
根(thinking_level_change, parentId=null)
 → model_change → thinking_level_change
 → user"nihao" → assistant → model_change
 → user"看一下 packages..."
 → assistant[3×toolCall] → 3×toolResult
 → assistant[9×toolCall] → 9×toolResult → …
 → assistant 最终长回答
 → bashExecution "git log --online"（打错，exitCode 128）
 → bashExecution "git log --oneline"（成功）★
     ├─ user"[! 是什么命令" ← label「测试A」指向此节点
     │   └─ assistant → user → assistant
     └─ user"你刚刚执行命令了吗..." ← /tree 开出的新分支
         └─ assistant → …
```

几个观察：

- 打错的命令、报错的工具调用（`isError: true`）全部留在树上——**一切都进树，一切可回溯**；
- assistant 条目携带 `usage`（token 与成本），底部状态栏的总成本就是逐条累加；
- OpenAI 系模型的条目里有巨大的 `encrypted_content` 加密推理块，恢复会话时须原样传回 provider 以延续思考链——这是文件"看起来乱"的主因，人读时可无视。

### 2.3 一轮对话的链条形状：调用在消息里，结果是独立条目

容易误解的一点：模型"发起工具调用"**不产生独立节点**——`toolCall` 是嵌在 assistant 消息内部的内容块（一条 assistant 可带多个）；每个工具的**执行结果**才是独立的 `toolResult` 条目。"用户输入 a，模型带四个调用回复 b，最终回复 g"的真实链条：

```text
user a → assistant b（内含 c/d/e/f 四个 toolCall 块）
       → toolResult c → toolResult d → toolResult e → toolResult f
       → assistant g
```

若一轮结果不够，模型会再发一条 assistant 继续调用：`assistant → results → assistant → results → … → assistant 终答`——这就是 agent loop 的 turn 在文件里的形状。正常对话永远是单链（每个节点一个孩子），只有 `/tree` 跳转后发言才会分叉。

一个保证确定性的细节：pi 默认**并行**执行同批工具，但**落盘的 toolResult 顺序严格按 assistant 消息里的声明顺序**（`packages/agent` README："persisted toolResult messages still follow assistant source order"）——执行乱序、记录有序，同一文件无论重放多少次，树形都一样。

## 第 3 章 加载：流式解析器的四个讲究

入口 `loadEntriesFromFile()`（`session-manager.ts:564`）。不是 `readFileSync().split("\n")`，而是 `openSync` + 1 MiB 复用缓冲区（`:540`）循环 `readSync`，有四个值得学的细节：

1. **`StringDecoder` 处理多字节边界（`:571`）**。UTF-8 中文占 3 字节，缓冲区边界可能切在字符中间；StringDecoder 把残缺字节留到下一块拼接。没有它，长会话中文消息会随机乱码。
2. **`pending` 尾行接力（`:573-588`）**。每块末尾不完整的半行 JSON 存入 `pending`，与下一块开头拼接；文件最后一行没有换行符也能通过 `decoder.end()` 收尾（`:591-593`）。
3. **坏行静默跳过（`:555-560`）**。`JSON.parse` 失败返回 null，不中断加载——文件中间损坏一行，其余历史照常可用。
4. **文件头严格校验（`:600-604`）**。第一条必须是 `type: "session"` 且 id 为字符串，否则整个文件拒收——防止把任意 JSONL 误当会话。

### 3.1 会话发现的快速路径：只读一行

`pi -r` 列出历史会话时**不解析全文**。`readSessionHeader()`（`:622`）用 4 KiB 缓冲区只扫到第一条可解析的行即返回，且封顶扫 1 MiB（`:630`），超限抛 `SessionHeaderScanLimitError`；发现流程是 best-effort（`:666-674`），单个损坏文件返回 null，不影响其他会话被列出。**不打开的会话连一次解析都不付。**

### 3.2 懒刷盘：第一条 assistant 消息之前，磁盘上没有文件

`_persist()`（`:1079`）的精妙之处：

- 首条 assistant 消息出现前，条目只攒在内存——打开 pi 敲两行字就退出，不留垃圾文件；
- 首条 assistant 消息到达时，以 `"wx"` 模式（独占创建）一次性写出全部攒下的条目（`:1094-1103`），置 `flushed = true`；
- 此后每次追加是一行同步 `appendFileSync`（`:1105`）。**同步 IO 是刻意的**：相对 LLM 秒级延迟，一行写盘的开销可忽略，换来崩溃安全——进程死在任何时刻，已追加的行都完整在盘。

另有 `_rewriteFile()`（`:1043`）全量重写，仅用于版本迁移等罕见场景，正常路径永不触发。

## 第 4 章 内存投影：四个结构，一次重放

`SessionManager` 的核心字段（`:923-925`）与 `_buildIndex()`（`:1022`）：

```text
fileEntries: FileEntry[]            条目数组（含文件头），事实来源
byId: Map<string, SessionEntry>     id → 条目，O(1) 查找
labelsById / labelTimestampsById    重放 label 条目得到的标签表
leafId: string | null               当前叶指针 = "你在树上的位置"
```

`_buildIndex` 对 `fileEntries` 做**一次线性重放**：逐条塞进 `byId`、把 `leafId` 推进到文件序最后一条、按序处理 label 条目。

### 4.1 追加路径：五行核心

`_appendEntry()`（`:1109`）：

```typescript
this.fileEntries.push(entry);   // 数组
this.byId.set(entry.id, entry); // 索引
this.leafId = entry.id;         // 叶指针前进
this._persist(entry);           // 落盘
```

新条目的 `parentId` 取自当前 `leafId`（`appendMessage`，`:1127`）——**整个树形分支模型就是这一个赋值**。文件与内存增量同步维护，运行中永不从磁盘重建。

### 4.2 leafId 的本质：树上的 HEAD 指针

leafId 不是"上一级节点"，也不只是"上一条消息"——它是**你此刻站在树上的位置**（当前活动分支的叶尖），与 git 的 HEAD 完全同构：

```text
leafId    = HEAD
新消息     = commit    （parentId 指向 HEAD，然后 HEAD 前移，:1131 → :1112）
/tree 跳转 = checkout  （branch() 只改指针，不动历史，:1469）
跳转后发言 = 在旧节点上再提交 → 分叉
恢复会话   = 加载时把 HEAD 指到文件最后一行（:1030）
```

静止时它是当前对话的最后一条记录；追加瞬间它是新条目的未来父节点——"上一条消息"与"树上的上一级"在这一瞬间是同一个条目。任何条目类型都遵守此规则，包括 label：标签条目的 `targetId` 可指向树上任意节点，`parentId` 却挂在按下 Shift+L 那一刻的 leafId 下。

### 4.3 label：只追加文件里的"修改"与"删除"

打标签**不修改目标条目**——追加一条 `type: "label"` 指向 `targetId`；取消标签也是追加，label 字段为空的条目在重放时执行 `delete`（`:1031-1038`）。**在只追加的日志里，删除也是一次追加。** 这是事件溯源最典型的手法。

## 第 5 章 树的重建：两遍 + Map，O(n) 搞定

`/tree` **不读文件**，`getTree()`（`:1409`）对内存条目做教科书级的两遍建树：

```text
第一遍：每条建一个 { entry, children: [], label } 节点放进 nodeMap   O(n)
第二遍：每条用 nodeMap.get(parentId) 找父节点，push 进其 children     O(n)
收尾：  显式栈迭代遍历，按时间戳给每层 children 排序（避免递归爆栈）
```

两个防御性细节：

- **孤儿即根（`:1433`）**：`parentId` 断链的条目不丢弃，直接作为根节点显示——文件损坏一行，其余历史照样可见；
- **多根合法**：`resetLeaf()`（`:1484`）把叶指针置 null 后，下一条追加成为新根（用于重新编辑第一条消息），所以 `getTree()` 返回的是根**数组**。

几万行的会话建树也是毫秒级。"文件长了会慢"只在首次加载时成立。

## 第 6 章 上下文组装：路径回溯与压缩边界

发给 LLM 的上下文不需要整棵树，只需要**当前叶子到根的一条链**。

### 6.1 路径回溯：O(树深)

`buildSessionPath()`（`:375`）从 `leafId` 沿 `parentId` 逐级向上走到根，再反转。复杂度 O(路径深度)而非 O(全部节点)——**被抛弃的分支根本不会被访问**。

### 6.2 压缩感知：三段拼接

`buildContextEntries()`（`:465`）在路径上找**最新**的 `compaction` 条目：

- 没有 → 原样返回整条路径（`:479-481`）；
- 有 → 上下文变为三段拼接（`:488-499`）：

```text
[压缩摘要条目] + [firstKeptEntryId 起保留的近期原文] + [压缩点之后的全部新消息]
```

比 `firstKeptEntryId` 更早的条目直接跳过；多次压缩只认路径上最后一次——上一轮摘要本身会被下一轮吞掉（分界线如何画出、快照语义见第 8 章）。

## 第 7 章 分支：移动一个指针

`branch()`（`:1469`）全文：

```typescript
branch(branchFromId: string): void {
  if (!this.byId.has(branchFromId)) throw new Error(...);
  this.leafId = branchFromId;
}
```

`/tree` 跳转执行的就是它：不读文件、不写文件、不复制，只移动内存指针；下一条消息自然以新位置为 `parentId`，岔路就此形成。文件里的表现：**同一个节点出现第二个孩子**。

配套机制对比：

| 操作 | 本质 | 产物 |
| --- | --- | --- |
| `/tree` 跳转 | `branch()` 移动 leafId | 同文件内新分支 |
| `/tree` 跳转 + Summarize | 同上，另追加 `branch_summary` 条目把被离开分支的收获带进新分支 | 同文件 |
| `/fork` | 复制活动路径到某消息为止 | **新文件** |
| `/clone` | 复制整条活动路径 | **新文件** |

跳转时的 "Summarize branch?" 三选项：`No summary`（干净重来）/ `Summarize`（自动总结被抛弃段落，适合"此路不通但教训值钱"）/ `Summarize with custom prompt`（自定义总结角度）。

## 第 8 章 压缩：有损的是路径，无损的是树

压缩（手动 `/compact [自定义指令]` 或自动触发）**不删除任何内容**：`appendCompaction()`（`:1168`）只是往树上追加一个 `type: "compaction"` 顶层条目，携带摘要文本与 `firstKeptEntryId`。三层视图各自的变化：

| 层 | 压缩后 |
| --- | --- |
| 磁盘 JSONL | 全量历史，一行没少（多了一条 compaction） |
| 内存树 / `/tree` | 全量历史，压缩条目只是树上普通一员 |
| LLM 上下文 | 摘要 + 保留尾段 + 新消息 |

**压缩是路径局部的，因此可逆**：用 `/tree` 跳回压缩点**之前**的节点开分支，新路径不经过压缩条目，`buildContextEntries` 找不到 compaction，自动回退全量原文。文档里 "Compaction is lossy. The full history remains in the JSONL" 的代码级含义即：**有损的是经过压缩节点的那条路径视图，无损的是树本身。**

### 8.1 分界线怎么画：findCutPoint（`compaction.ts:421`）

`firstKeptEntryId` 是压缩算法的分界线：**线后原文保留，线前只活在摘要里**。画线算法从最新往回累加估算 token，达到 `keepRecentTokens`（默认 20000，`compaction.ts:142`）后就近选一个**合法切点**：

- 只能切在 user 或 assistant 消息上，**永远不切在 toolResult 上**（`:408-409`）——避免保留区开头出现没有对应调用的孤儿工具结果；切在带工具调用的 assistant 上时，其结果都在后面、一并保留；
- 切点确定后会向前捎带紧邻的非上下文元数据条目（model_change 等），但不跨越可见消息或旧压缩边界（`:459-464`）；
- 用 id 而非数组下标记录（正是 v1→v2 迁移的内容，`session-manager.ts:277-279`）：树会分叉，**下标在不同路径上没有稳定含义，id 才有**，且可在 `byId` 中 O(1) 定位。

组装上下文时摘要被**提到最前**：压缩条目在树上挂在保留区之后（它是追加时的新叶子），但模型先读"前情摘要"再读近期原文——按叙事逻辑而非文件顺序。

### 8.2 快照语义与锯齿曲线

分界线是**压缩时刻的快照，不是滑动窗口**：画线后新消息持续追加，线不挪。任意时刻的上下文 = `[摘要] + [画线时定格的保留区] + [线后持续增长的新消息]`，第三段涨到阈值 → 触发下一次压缩 → 画一条新线。上下文占用因此呈**锯齿状**：涨→压→涨→压。

再压缩时**旧摘要被新摘要吞并，不叠罗汉**：下一轮的处理范围从上一条压缩的 `firstKeptEntryId` 起算（`compaction.ts:760`），新摘要的原料 = 旧摘要 + 旧保留区 + 新增消息中被划出的部分，产出**一条**新摘要取而代之。无论压缩多少轮，上下文里永远只有一个摘要块。

### 8.3 切在轮中间：唯一的例外

"保留区内绝不压缩"有一个边角情况：若按预算画线正好落在某一轮（turn）内部——比如一轮 20 个工具调用切在第 10 个——`findCutPoint` 会记录 `turnStartIndex` / `isSplitTurn`（`:413-419`），把该轮被切掉的前半段**单独摘要**后接回保留的后半段，保证保留区开头语义完整，不从半截工具循环开始。

## 第 9 章 `!` 命令与自定义消息类型

交互模式中 `!command` 直接在本地 shell 执行（不经过模型、零 token），输出进入上下文；`!!command` 执行但**不**进入上下文。

落盘形态是 `role: "bashExecution"` 的消息条目——**既不是 user 也不是 assistant**，而是 coding-agent 通过声明合并（declaration merging）扩展 `AgentMessage` 得到的自定义消息类型（机制见 `packages/agent` README "Custom Message Types"）。条目带 `excludeFromContext` 字段：`!` 为 false，`!!` 为 true。

这类消息进入 LLM 前经过第 1 篇讲过的管道过滤转换：

```text
AgentMessage[] → transformContext() → convertToLlm() → Message[] → LLM
```

动手实验中还抓到两个"活样本"，值得记住：

- **模型对自身框架的描述可能自信地出错**：会话内模型声称 bash 输出"不会写入 session 文件"，而正在读的 JSONL 里明明躺着 bashExecution 条目——**session 文件才是地面真相**；
- **agent 自我纠错**：一条 `rg` 命令因引号错误报 `unexpected EOF`，`isError: true` 的 toolResult 回传后，模型下一轮换写法重试——这就是 agent loop 处理工具失败的标准动作。

## 第 10 章 工程模式清单

本篇涉及的可迁移设计模式：

1. **事件溯源（event sourcing）**：磁盘只追加事件日志，内存是重放得到的投影，修改一律表达为新事件（label 的增删皆追加）。Kafka、Redux、git 同源。
2. **只追加 + 崩溃安全**：条目永不改写 → 内存与磁盘永远一致，无缓存失效问题；同步逐行 append → 任意时刻崩溃不丢已写数据。
3. **懒刷盘**：首条 assistant 消息前不建文件，避免垃圾会话；`"wx"` 独占创建防覆盖。
4. **两遍 + Map 建树**：O(n) 线性建树的标准算法；显式栈迭代排序避免深树递归爆栈。
5. **路径局部性**：上下文组装 O(树深)，废弃分支零开销；压缩、分支摘要都只作用于路径而非全局。
6. **有界扫描**：会话发现只读文件头，扫描字节数封顶并显式抛错，坏文件 best-effort 跳过。
7. **防御性解析**：坏行跳过、孤儿当根、文件头严格校验——单点损坏不放大。
8. **架构选对，功能免费**：恢复 = 重放；分支 = 移动指针；标签 = 追加事件；压缩 = 路径上插一个节点。每个"功能"的核心实现都在 10 行以内。

## 第 11 章 复习自测

尝试不看正文回答（答案都在上文）：

1. `/tree` 打开时读了几次磁盘？树是用什么算法、什么复杂度建出来的？
2. 一个条目成为"分支点"在文件里的表现是什么？`branch()` 的实现有几行？
3. 压缩之后，比 `firstKeptEntryId` 更早的消息去哪了？磁盘、内存树、LLM 上下文三层各自的答案是什么？
4. 如何"取消"一个标签？为什么说这体现了事件溯源？
5. 为什么打开 pi 又立刻退出不会产生会话文件？首次落盘为什么用 `"wx"` 模式？
6. `!` 和 `!!` 的区别在条目的哪个字段上体现？bashExecution 为什么能作为合法的消息 role 存在？
7. 中文消息为什么需要 `StringDecoder`？`pending` 变量解决什么问题？
8. 跳回压缩点之前的节点开分支，上下文是摘要还是全量原文？为什么？
9. `pi -r` 列出 500 个长会话为什么很快？扫描的安全上限是多少？
10. 会话恢复（`pi -c`）的本质是什么操作？
11. leafId 在"静止时"和"追加瞬间"分别扮演什么角色？它与 git 的哪个概念同构？
12. 为什么 `firstKeptEntryId` 永远不会指向一条 toolResult？为什么它是 id 而不是数组下标？
13. 连续压缩三次后，上下文里有几个摘要块？为什么？
14. 同批工具并行执行时，toolResult 的落盘顺序由什么决定？

---

*基于 2026-08-02 的动手实验与源码走读整理。配套阅读：`docs-zh/coding-agent/session-format.md`（文件格式）、`docs-zh/coding-agent/sessions.md`（用户侧操作）、`docs-zh/coding-agent/compaction.md`（压缩细节）、第 1 篇第 8 章（agent 包的平行实现）。*
