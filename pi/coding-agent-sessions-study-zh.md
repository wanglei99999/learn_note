# Pi Coding Agent：会话与上下文带读笔记

这份笔记从 `sessions.md` 开始，记录会话、会话文件格式与上下文压缩相关文档的带读内容。

目前读过：

- `sessions.md`
- `session-format.md`

## 1. sessions.md：Pi 如何保存和分叉对话

Pi 的 Session 不是一条线性的聊天记录，而是一棵可以回退、分叉和继续生长的对话树。

### Session 保存在哪里

Session 默认保存到：

```text
~/.pi/agent/sessions/
```

它们按工作目录组织，因此同一个项目的历史会话通常放在一起，`/resume` 默认浏览当前项目的会话。

每个 Session 是一个 JSONL 文件。文件里的条目通过 `id` 和 `parentId` 连接成树，而不是简单地认为下一行就是上一行的子节点。文件保存完整历史，当前活动叶节点决定 Pi 正处于哪条分支。

### 启动时选择 Session

```bash
pi -c
```

继续当前项目最近一次会话，适合立即接着上次工作。

```bash
pi -r
```

启动时打开历史会话选择器。

```bash
pi --session <path|id>
```

明确打开某个 Session，可以传文件路径或部分 Session ID。

```bash
pi --fork <path|id>
```

基于已有 Session 创建一个新的 Session 文件。

```bash
pi --no-session
```

当前运行不保存为 Session 文件，适合一次性临时任务。

```bash
pi --name "my task"
```

启动时设置便于识别的显示名称。名称不是文件名，也不代替 Session ID。

### `/resume` 选择器

`/resume` 和 `pi -r` 打开的是同一个选择器，只是进入时机不同：

- `pi -r`：启动 Pi 时选择。
- `/resume`：已经进入 Pi 后切换。

选择器支持搜索、显示路径、切换排序、只看已命名会话、重命名和删除。在系统提供 `trash` 命令时，Pi 会优先把删除的 Session 移到回收站，而不是直接永久删除。

### `/tree`：移动活动叶节点

假设当前 Session 是：

```text
问题
└─ 回答
   ├─ 方案 A
   │  └─ A 的回答
   │     └─ A 成功了       ← 当前活动叶节点
   └─ 方案 B
      └─ B 的回答
```

历史中的 A 和 B 都保存在同一个 Session 文件里，但 Pi 当前只沿着活动叶节点所在的路径构造对话上下文。

使用 `/tree` 跳到旧节点，不会删除后面的记录。它只是改变当前位置，然后从那里长出一条新分支。因此可以在同一个 Session 中尝试多种方案，而不必复制多份完整聊天记录。

### 选择不同节点时的行为

选择用户消息时，Pi 会：

1. 把活动叶节点移动到该消息的父节点。
2. 将原用户消息放回编辑器。
3. 允许修改后重新提交，创建新的同级分支。

例如，把原消息：

```text
请用 Redis 实现缓存
```

改成：

```text
请只用进程内 LRU 缓存
```

提交后，Redis 分支仍然保留，同时产生一条新的 LRU 分支。

选择 Assistant 消息、工具结果或其他非用户条目时，Pi 会把活动叶节点移动到该条记录，保持编辑器为空，让用户从该位置继续输入。

选择根用户消息时，叶节点会回到空对话，最初的 Prompt 会放回编辑器，允许用户从头修改任务。

### `/tree`、`/fork` 与 `/clone`

| 命令 | 是否新建文件 | 从哪里继续 |
|---|---:|---|
| `/tree` | 否 | 当前 Session 中的任意节点 |
| `/fork` | 是 | 选中的较早用户消息 |
| `/clone` | 是 | 当前活动分支 |

`/tree` 适合在同一项任务里比较多个方案，所有路线保留在同一棵树中。

`/fork` 适合发现旧问题值得变成独立任务时，从较早的用户消息创建新的 Session 文件。

`/clone` 会把当前活动分支复制为新的 Session，适合在继续高风险尝试前保留一个独立副本。

可以简单记成：

```text
/tree  = 同一个文件里换路线
/fork  = 从旧问题分出去
/clone = 复制当前路线
```

### 分支摘要

当用户离开方案 A，返回较早节点尝试方案 B 时，A 分支不在 B 的祖先路径上，模型通常看不到 A 中得到的重要结论。

Pi 可以把被放弃的 A 分支压缩成摘要，再将摘要附加到新位置：

```text
方案 A 的完整过程
        ↓ 摘要
“已经确认问题来自数据库连接池，不是缓存。”
        ↓
方案 B 从这里继续
```

这不是合并两个分支，而是选择性地把旧分支的重要发现带到新分支。切换时可以不生成摘要、使用默认 Prompt，或者指定希望摘要关注的内容。

### Session 历史不等于模型当前上下文

```text
Session 文件
保存完整历史树
        ↓ 选择活动分支
当前分支历史
        ↓ 必要时 Compaction
真正发给模型的上下文
```

因此：

- `/tree` 切换活动分支。
- Session 文件仍然保存其他分支。
- Compaction 缩短发给模型的上下文。
- 完整旧历史仍可保留在 JSONL 文件中。

下一篇 `session-format.md` 将继续说明这棵树如何写入 JSONL、有哪些条目类型，以及 `SessionManager` 如何重建活动分支。

## 2. session-format.md：Session 文件内部如何工作

`sessions.md` 讲的是用户如何使用 Session；`session-format.md` 讲的是 Session 在磁盘上的数据模型，以及程序如何从数据重建当前对话。

### 文件位置与基本结构

Session 默认保存在：

```text
~/.pi/agent/sessions/--<path>--/<timestamp>_<uuid>.jsonl
```

工作目录路径经过转换后成为目录名。每个 `.jsonl` 文件保存一个 Session，每行都是一个带 `type` 的独立 JSON 对象。

第一行固定为 `SessionHeader`：

```json
{"type":"session","version":3,"id":"uuid","timestamp":"...","cwd":"/project"}
```

Header 只描述整个 Session，不是树节点，因此没有条目使用的 `id` 和 `parentId`。通过 `/fork`、`/clone` 或 API 创建的派生 Session，还可以在 Header 中记录原文件路径：

```json
{"type":"session","version":3,"id":"uuid","cwd":"/project","parentSession":"/old/session.jsonl"}
```

`parentSession` 表示来源关系；新 Session 仍然是独立文件。

### Session 是追加的事实记录，不只是消息列表

Header 后面的每一行都是 `SessionEntry`。除了聊天消息，模型切换、思考等级、压缩、分支摘要、名称和标签也会成为条目。

例如，用户中途把模型改成 GPT，Pi 不需要回头修改 Header，而是追加：

```json
{"type":"model_change","id":"d4e5f6g7","parentId":"c3d4e5f6","provider":"openai","modelId":"gpt-4o"}
```

这意味着 Session 保存的是会话过程中发生过的事实。程序沿当前分支回放这些条目，就能重建当时的消息、模型和思考等级。

### 条目基类与树关系

除 Header 外，所有条目都有：

```typescript
interface SessionEntryBase {
  type: string;
  id: string;
  parentId: string | null;
  timestamp: string;
}
```

- `id` 是当前条目的 8 位十六进制标识。
- `parentId` 指向父条目。
- 第一条树节点的 `parentId` 为 `null`。
- 当前叶节点代表用户现在所在的位置。

JSONL 中的物理行序表示条目的写入顺序，真正的对话关系由 `parentId` 决定。解析器不能只把所有行按顺序当成一条聊天记录。

```text
user ─ assistant ─ user ─ assistant ─┬─ user A  ← 一条分支
                                     └─ summary ─ user B ← 当前分支
```

构造当前对话时，Pi 从当前叶节点沿 `parentId` 一直回溯到根，再把这条路径恢复成正序。其他兄弟分支仍在文件中，但不会直接进入当前模型上下文。

### SessionEntry 与 AgentMessage 不同

需要区分两层对象：

```text
SessionEntry
└─ 负责持久化、树关系和会话状态
   └─ 某些 Entry 内部包含 AgentMessage
      └─ 负责真正的对话内容
```

普通对话使用 `SessionMessageEntry`：

```json
{"type":"message","id":"a1b2c3d4","parentId":null,"message":{"role":"user","content":"Hello"}}
```

外层 `type: "message"` 表示这是一个会话消息条目；内层 `message.role` 才说明它是用户、Assistant、工具结果还是其他消息。

### 消息内容块

消息内容不是永远只有字符串。主要内容块包括：

| 内容块 | 用途 |
|---|---|
| `text` | 普通文本 |
| `image` | Base64 图片和 MIME 类型 |
| `thinking` | Assistant 的思考内容 |
| `toolCall` | 工具名称、调用 ID 和参数 |

基础消息包括：

- `UserMessage`：字符串，或文本与图片内容块。
- `AssistantMessage`：文本、思考和工具调用，并记录 provider、model、用量、费用和停止原因。
- `ToolResultMessage`：通过 `toolCallId` 对应工具调用，保存结果和 `isError`。

Coding Agent 另外增加：

- `BashExecutionMessage`：记录用户直接执行的 Bash 命令。
- `CustomMessage`：Extension 注入的上下文消息。
- `BranchSummaryMessage`：离开旧分支时产生的摘要。
- `CompactionSummaryMessage`：上下文压缩后代替旧前缀的摘要。

`BashExecutionMessage.excludeFromContext` 可以把命令记录留在 Session 中，但不发送给模型。`!!` 前缀命令会使用这一行为。这再次说明“保存在历史中”和“进入模型上下文”是两个不同决定。

### 主要条目类型

| Entry 类型 | 保存的内容 | 是否影响模型上下文 |
|---|---|---|
| `message` | AgentMessage | 通常会 |
| `model_change` | Provider 和模型 | 决定后续使用的模型 |
| `thinking_level_change` | 思考等级 | 决定当前推理设置 |
| `compaction` | 旧上下文摘要和保留位置 | 会转换为压缩摘要消息 |
| `branch_summary` | 被离开分支的摘要 | 会转换为分支摘要消息 |
| `custom` | Extension 私有状态 | 不会 |
| `custom_message` | Extension 注入的消息 | 会 |
| `label` | 某个条目的标签 | 不会直接成为消息 |
| `session_info` | Session 显示名称 | 不会直接成为消息 |

### `custom` 与 `custom_message` 的关键区别

`custom` 用于 Extension 保存自己的状态：

```json
{"type":"custom","customType":"my-extension","data":{"count":42}}
```

它可以重新加载和自定义渲染，但不会进入 LLM 上下文。适合计数器、缓存标记和 UI 状态。

`custom_message` 则是 Extension 有意注入给模型的消息：

```json
{"type":"custom_message","customType":"my-extension","content":"Injected context...","display":true}
```

它会进入 LLM 上下文。`display` 只决定是否在 TUI 中显示，不决定是否发送给模型；`details` 是 Extension 元数据，也不会发送给模型。

因此，隐藏显示不等于隐藏于模型，持久化也不等于进入模型上下文。

### 模型和思考等级也是分支状态

`model_change` 和 `thinking_level_change` 与消息一样带有 `parentId`，所以它们属于树中的某条路径。

切换到另一条分支时，Pi 要从该分支路径中提取最后生效的模型和思考等级，而不是简单采用文件最后一行记录的设置。不同分支可以保留各自当时的运行配置。

### CompactionEntry

上下文压缩条目主要保存：

```typescript
{
  summary: string;
  firstKeptEntryId: string;
  tokensBefore: number;
}
```

- `summary`：被压缩的旧历史摘要。
- `firstKeptEntryId`：从哪个较新的条目开始继续保留原文。
- `tokensBefore`：压缩前的 Token 数。

有效上下文可以理解为：

```text
旧历史前缀                  较新的保留内容        压缩后的新消息
     ↓ 摘要代替                  ↓ 原文保留             ↓ 原文保留
[CompactionSummary] + [firstKeptEntryId ...] + [later entries ...]
```

压缩条目还可以记录读过和修改过的文件，供默认实现延续工作状态；Extension 也可以提供自己的 `details`。

### BranchSummaryEntry

分支摘要记录：

- `fromId`：被离开分支原来所在的位置。
- `parentId`：摘要被接到新路线的哪个位置。
- `summary`：需要带到新路线的旧分支结论。

它不是旧分支的完整复制，而是一条新的上下文消息，用较少 Token 携带旧路线中的重要信息。

### 两阶段构建上下文

Pi 不会把 Session 文件里的所有条目直接交给模型，而是分两步处理。

第一步，`buildContextEntries()`：

1. 从当前叶节点回溯到根，只选择当前分支。
2. 应用 Compaction 规则，用摘要替代旧前缀，并保留指定的新内容。
3. 保留必要的非消息条目，供 TUI 和状态恢复使用。

第二步，`buildSessionContext()`：

1. 从当前路径提取最终生效的模型和思考等级。
2. 把 `message` 转为原始 AgentMessage。
3. 把 `compaction` 转为 `CompactionSummaryMessage`。
4. 把 `branch_summary` 转为 `BranchSummaryMessage`。
5. 把 `custom_message` 转为 `CustomMessage`。
6. 忽略不会进入上下文的 `custom` 等条目。

最终得到的才是发送给 LLM 的消息列表及运行配置。

### Session 版本

- v1：线性条目序列。
- v2：使用 `id` 和 `parentId` 的树结构。
- v3：把旧的 `hookMessage` 角色统一重命名为 `custom`。

旧会话加载时会自动迁移到当前 v3。自己编写解析器时，应读取 Header 的 `version`，并为缺失版本字段的旧文件做好兼容，而不能假定所有文件天然都是 v3。

### SessionManager 的职责

`SessionManager` 把底层格式封装成几组 API：

- 创建和打开：`create()`、`open()`、`continueRecent()`、`inMemory()`、`forkFrom()`。
- 列举：`list()`、`listAll()`。
- 写入：`appendMessage()`、`appendModelChange()`、`appendCompaction()`、`appendCustomEntry()` 等。
- 树导航：`getBranch()`、`getTree()`、`getChildren()`、`branch()`、`resetLeaf()`、`branchWithSummary()`。
- 上下文构建：`buildContextEntries()`、`buildSessionContext()`。
- 元数据：获取 Session 名称、目录、ID、文件路径，以及是否已经持久化。

如果只是使用 Pi，不需要直接操作这些 API。开发 Extension、SDK 集成、Session 查看器或迁移工具时，应该优先使用 `SessionManager`，避免自己重复实现树导航、版本迁移和 Compaction 规则。

这一篇可以归结为：

```text
JSONL 负责保存全部事实
parentId 负责形成会话树
当前 leaf 负责选择活动路线
Compaction 负责缩短有效上下文
buildSessionContext() 负责生成真正发给模型的内容
```
