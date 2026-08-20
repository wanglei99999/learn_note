> **译文** | 原文：[`packages/coding-agent/docs/session-format.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/session-format.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 会话文件格式

Session（会话）以 JSONL（JSON Lines）文件存储。每一行是一个带 `type` 字段的 JSON 对象。会话条目通过 `id`/`parentId` 字段构成树结构，从而支持在同一文件内就地分支，无需创建新文件。

## 文件位置

```
~/.pi/agent/sessions/--<path>--/<timestamp>_<uuid>.jsonl
```

其中 `<path>` 是把 `/` 替换为 `-` 后的工作目录路径。

## 删除会话

删除 `~/.pi/agent/sessions/` 下对应的 `.jsonl` 文件即可移除会话。

Pi 也支持在 `/resume` 中交互式删除会话（选中一个会话并按 `Ctrl+D`，然后确认）。在可用时，pi 会使用 `trash` CLI 以避免永久删除。

## 会话版本

会话头（header）中带有版本字段：

- **版本 1**：线性条目序列（历史遗留，加载时自动迁移）
- **版本 2**：通过 `id`/`parentId` 链接的树结构
- **版本 3**：将 `hookMessage` 角色重命名为 `custom`（extension 体系统一）

现有会话在加载时会自动迁移到当前版本（v3）。

## 源码文件

GitHub 上的源码（[pi-mono](https://github.com/earendil-works/pi-mono)）：
- [`packages/coding-agent/src/core/session-manager.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/session-manager.ts) - 会话条目类型与 SessionManager
- [`packages/coding-agent/src/core/messages.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/messages.ts) - 扩展消息类型（BashExecutionMessage、CustomMessage 等）
- [`packages/ai/src/types.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/types.ts) - 基础消息类型（UserMessage、AssistantMessage、ToolResultMessage）
- [`packages/agent/src/types.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/agent/src/types.ts) - AgentMessage 联合类型

如需在你的项目中查看 TypeScript 类型定义，请查阅 `node_modules/@earendil-works/pi-coding-agent/dist/` 和 `node_modules/@earendil-works/pi-ai/dist/`。

## 消息类型

会话条目包含 `AgentMessage` 对象。理解这些类型对解析会话和编写 extension 至关重要。

### 内容块

消息包含带类型的内容块数组：

```typescript
interface TextContent {
  type: "text";
  text: string;
}

interface ImageContent {
  type: "image";
  data: string;      // base64 编码
  mimeType: string;  // 例如 "image/jpeg"、"image/png"
}

interface ThinkingContent {
  type: "thinking";
  thinking: string;
}

interface ToolCall {
  type: "toolCall";
  id: string;
  name: string;
  arguments: Record<string, any>;
}
```

### 基础消息类型（来自 pi-ai）

```typescript
interface UserMessage {
  role: "user";
  content: string | (TextContent | ImageContent)[];
  timestamp: number;  // Unix 毫秒时间戳
}

interface AssistantMessage {
  role: "assistant";
  content: (TextContent | ThinkingContent | ToolCall)[];
  api: string;
  provider: string;
  model: string;
  usage: Usage;
  stopReason: "stop" | "length" | "toolUse" | "error" | "aborted";
  errorMessage?: string;
  timestamp: number;
}

interface ToolResultMessage {
  role: "toolResult";
  toolCallId: string;
  toolName: string;
  content: (TextContent | ImageContent)[];
  details?: any;      // tool 特有的元数据
  isError: boolean;
  timestamp: number;
}

interface Usage {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  totalTokens: number;
  cost: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
    total: number;
  };
}
```

### 扩展消息类型（来自 pi-coding-agent）

```typescript
interface BashExecutionMessage {
  role: "bashExecution";
  command: string;
  output: string;
  exitCode: number | undefined;
  cancelled: boolean;
  truncated: boolean;
  fullOutputPath?: string;
  excludeFromContext?: boolean;  // !! 前缀命令为 true
  timestamp: number;
}

interface CustomMessage {
  role: "custom";
  customType: string;            // extension 标识符
  content: string | (TextContent | ImageContent)[];
  display: boolean;              // 是否在 TUI 中显示
  details?: any;                 // extension 特有的元数据
  timestamp: number;
}

interface BranchSummaryMessage {
  role: "branchSummary";
  summary: string;
  fromId: string;                // 分支出发时所在的条目
  timestamp: number;
}

interface CompactionSummaryMessage {
  role: "compactionSummary";
  summary: string;
  tokensBefore: number;
  timestamp: number;
}
```

### AgentMessage 联合类型

```typescript
type AgentMessage =
  | UserMessage
  | AssistantMessage
  | ToolResultMessage
  | BashExecutionMessage
  | CustomMessage
  | BranchSummaryMessage
  | CompactionSummaryMessage;
```

## 条目基类

所有条目（除 `SessionHeader` 外）都继承自 `SessionEntryBase`：

```typescript
interface SessionEntryBase {
  type: string;
  id: string;           // 8 位十六进制 ID
  parentId: string | null;  // 父条目 ID（首个条目为 null）
  timestamp: string;    // ISO 时间戳
}
```

## 条目类型

### SessionHeader

文件的第一行。仅包含元数据，不参与树结构（没有 `id`/`parentId`）。

```json
{"type":"session","version":3,"id":"uuid","timestamp":"2024-12-03T14:00:00.000Z","cwd":"/path/to/project"}
```

对于带父会话的会话（通过 `/fork`、`/clone` 或 `newSession({ parentSession })` 创建）：

```json
{"type":"session","version":3,"id":"uuid","timestamp":"2024-12-03T14:00:00.000Z","cwd":"/path/to/project","parentSession":"/path/to/original/session.jsonl"}
```

### SessionMessageEntry

对话中的一条消息。`message` 字段包含一个 `AgentMessage`。

```json
{"type":"message","id":"a1b2c3d4","parentId":"prev1234","timestamp":"2024-12-03T14:00:01.000Z","message":{"role":"user","content":"Hello"}}
{"type":"message","id":"b2c3d4e5","parentId":"a1b2c3d4","timestamp":"2024-12-03T14:00:02.000Z","message":{"role":"assistant","content":[{"type":"text","text":"Hi!"}],"provider":"anthropic","model":"claude-sonnet-4-5","usage":{...},"stopReason":"stop"}}
{"type":"message","id":"c3d4e5f6","parentId":"b2c3d4e5","timestamp":"2024-12-03T14:00:03.000Z","message":{"role":"toolResult","toolCallId":"call_123","toolName":"bash","content":[{"type":"text","text":"output"}],"isError":false}}
```

### ModelChangeEntry

用户在会话中途切换模型时写入。

```json
{"type":"model_change","id":"d4e5f6g7","parentId":"c3d4e5f6","timestamp":"2024-12-03T14:05:00.000Z","provider":"openai","modelId":"gpt-4o"}
```

### ThinkingLevelChangeEntry

用户更改思考/推理等级时写入。

```json
{"type":"thinking_level_change","id":"e5f6g7h8","parentId":"d4e5f6g7","timestamp":"2024-12-03T14:06:00.000Z","thinkingLevel":"high"}
```

### CompactionEntry

上下文压缩时创建。存储较早消息的摘要。

```json
{"type":"compaction","id":"f6g7h8i9","parentId":"e5f6g7h8","timestamp":"2024-12-03T14:10:00.000Z","summary":"User discussed X, Y, Z...","firstKeptEntryId":"c3d4e5f6","tokensBefore":50000}
```

可选字段：
- `details`：具体实现自定义的数据（默认实现为 `{ readFiles: string[], modifiedFiles: string[] }`，extension 可使用自定义数据）
- `fromHook`：由 extension 生成时为 `true`，由 pi 生成时为 `false`/`undefined`（历史遗留字段名）

### BranchSummaryEntry

通过 `/tree` 切换分支时创建，包含由 LLM 生成的、从被离开分支到共同祖先为止的总结。它保留了被放弃路径中的上下文。

```json
{"type":"branch_summary","id":"g7h8i9j0","parentId":"a1b2c3d4","timestamp":"2024-12-03T14:15:00.000Z","fromId":"f6g7h8i9","summary":"Branch explored approach A..."}
```

可选字段：
- `details`：文件跟踪数据（默认为 `{ readFiles: string[], modifiedFiles: string[] }`），extension 可使用自定义数据
- `fromHook`：由 extension 生成时为 `true`，由 pi 生成时为 `false`/`undefined`（历史遗留字段名）

### CustomEntry

Extension 的状态持久化。**不**参与 LLM 上下文。

```json
{"type":"custom","id":"h8i9j0k1","parentId":"g7h8i9j0","timestamp":"2024-12-03T14:20:00.000Z","customType":"my-extension","data":{"count":42}}
```

重新加载时可通过 `customType` 识别属于你的 extension 的条目。交互模式可以通过 `pi.registerEntryRenderer(customType, renderer)` 渲染自定义条目，但它们仍然不参与 LLM 上下文。

### CustomMessageEntry

由 extension 注入、**会**参与 LLM 上下文的消息。

```json
{"type":"custom_message","id":"i9j0k1l2","parentId":"h8i9j0k1","timestamp":"2024-12-03T14:25:00.000Z","customType":"my-extension","content":"Injected context...","display":true}
```

字段：
- `content`：字符串或 `(TextContent | ImageContent)[]`（与 UserMessage 相同）
- `display`：`true` 表示在 TUI 中以特殊样式显示，`false` 表示隐藏
- `details`：可选的 extension 特有元数据（不发送给 LLM）

### LabelEntry

用户在某个条目上定义的书签/标记。

```json
{"type":"label","id":"j0k1l2m3","parentId":"i9j0k1l2","timestamp":"2024-12-03T14:30:00.000Z","targetId":"a1b2c3d4","label":"checkpoint-1"}
```

将 `label` 设为 `undefined` 可清除标签。

### SessionInfoEntry

会话元数据（例如用户定义的显示名称）。通过 `/name`、`--name` / `-n` 或 extension 中的 `pi.setSessionName()` 设置。

```json
{"type":"session_info","id":"k1l2m3n4","parentId":"j0k1l2m3","timestamp":"2024-12-03T14:35:00.000Z","name":"Refactor auth module"}
```

设置后，会话名称会在会话选择器（`/resume`）中代替第一条消息显示。

## 树结构

条目构成一棵树：
- 首个条目的 `parentId` 为 `null`
- 后续每个条目通过 `parentId` 指向其父条目
- 分支即从更早的条目派生出新的子条目
- 「叶子」（leaf）是树中的当前位置

```
[user msg] ─── [assistant] ─── [user msg] ─── [assistant] ─┬─ [user msg] ← current leaf
                                                            │
                                                            └─ [branch_summary] ─── [user msg] ← alternate branch
```

## 上下文构建

`buildContextEntries()` 从当前叶子回溯到根，生成当前生效的条目列表，并遵循上下文压缩的规则：

1. 收集路径上的所有条目
2. 如果路径上存在 `CompactionEntry`：
   - 先包含该压缩条目
   - 然后是从 `firstKeptEntryId` 到压缩条目之间的条目
   - 然后是压缩条目之后的条目
3. 保留所选范围内的非消息条目，以便交互模式渲染它们

`buildSessionContext()` 在该条目列表的基础上生成发送给 LLM 的消息列表：

1. 从完整路径中提取当前的模型和思考等级设置
2. 将选中的条目转换为消息：
   - `message` -> 存储的 `AgentMessage`
   - `compaction` -> `compactionSummary`
   - `branch_summary` -> `branchSummary`
   - `custom_message` -> `CustomMessage`
   - `custom` -> 不产生上下文消息

## 解析示例

```typescript
import { readFileSync } from "fs";

const lines = readFileSync("session.jsonl", "utf8").trim().split("\n");

for (const line of lines) {
  const entry = JSON.parse(line);

  switch (entry.type) {
    case "session":
      console.log(`Session v${entry.version ?? 1}: ${entry.id}`);
      break;
    case "message":
      console.log(`[${entry.id}] ${entry.message.role}: ${JSON.stringify(entry.message.content)}`);
      break;
    case "compaction":
      console.log(`[${entry.id}] Compaction: ${entry.tokensBefore} tokens summarized`);
      break;
    case "branch_summary":
      console.log(`[${entry.id}] Branch from ${entry.fromId}`);
      break;
    case "custom":
      console.log(`[${entry.id}] Custom (${entry.customType}): ${JSON.stringify(entry.data)}`);
      break;
    case "custom_message":
      console.log(`[${entry.id}] Extension message (${entry.customType}): ${entry.content}`);
      break;
    case "label":
      console.log(`[${entry.id}] Label "${entry.label}" on ${entry.targetId}`);
      break;
    case "model_change":
      console.log(`[${entry.id}] Model: ${entry.provider}/${entry.modelId}`);
      break;
    case "thinking_level_change":
      console.log(`[${entry.id}] Thinking: ${entry.thinkingLevel}`);
      break;
  }
}
```

## SessionManager API

以编程方式操作会话的关键方法。

### 静态创建方法
- `SessionManager.create(cwd, sessionDir?)` - 新建会话
- `SessionManager.open(path, sessionDir?)` - 打开已有的会话文件
- `SessionManager.continueRecent(cwd, sessionDir?)` - 继续最近的会话，若无则新建
- `SessionManager.inMemory(cwd?)` - 不做文件持久化
- `SessionManager.forkFrom(sourcePath, targetCwd, sessionDir?)` - 从另一个项目 fork 会话

### 静态列举方法
- `SessionManager.list(cwd, sessionDir?, onProgress?)` - 列出某个目录的会话
- `SessionManager.listAll(onProgress?)` - 列出所有项目的全部会话

### 实例方法 - 会话管理
- `newSession(options?)` - 开始新会话（options：`{ parentSession?: string }`）
- `setSessionFile(path)` - 切换到另一个会话文件
- `createBranchedSession(leafId)` - 将分支提取为新的会话文件

### 实例方法 - 追加条目（均返回条目 ID）
- `appendMessage(message)` - 添加消息
- `appendThinkingLevelChange(level)` - 记录思考等级变更
- `appendModelChange(provider, modelId)` - 记录模型变更
- `appendCompaction(summary, firstKeptEntryId, tokensBefore, details?, fromHook?)` - 添加上下文压缩条目
- `appendCustomEntry(customType, data?)` - extension 状态（不进入上下文）
- `appendSessionInfo(name)` - 设置会话显示名称
- `appendCustomMessageEntry(customType, content, display, details?)` - extension 消息（进入上下文）
- `appendLabelChange(targetId, label)` - 设置/清除标签

### 实例方法 - 树导航
- `getLeafId()` - 当前位置
- `getLeafEntry()` - 获取当前叶子条目
- `getEntry(id)` - 按 ID 获取条目
- `getBranch(fromId?)` - 从条目回溯到根
- `getTree()` - 获取完整树结构
- `getChildren(parentId)` - 获取直接子条目
- `getLabel(id)` - 获取条目的标签
- `branch(entryId)` - 将叶子移动到更早的条目
- `resetLeaf()` - 将叶子重置为 null（位于所有条目之前）
- `branchWithSummary(entryId, summary, details?, fromHook?)` - 带上下文总结的分支

### 实例方法 - 上下文与信息
- `buildContextEntries()` - 获取应用上下文压缩后当前分支的生效条目
- `buildSessionContext()` - 获取发送给 LLM 的消息、thinkingLevel 和模型
- `getEntries()` - 所有条目（不含 header）
- `getHeader()` - 会话头元数据
- `getSessionName()` - 从最新的 session_info 条目获取显示名称
- `getCwd()` - 工作目录
- `getSessionDir()` - 会话存储目录
- `getSessionId()` - 会话 UUID
- `getSessionFile()` - 会话文件路径（内存会话为 undefined）
- `isPersisted()` - 会话是否已保存到磁盘
