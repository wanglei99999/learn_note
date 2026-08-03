> **译文** | 原文：[`packages/coding-agent/docs/rpc.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# RPC 模式

RPC 模式通过 stdin/stdout 上的 JSON 协议实现编码 agent 的无界面（headless）运行。这对于将 agent 嵌入其它应用、IDE 或自定义 UI 非常有用。

**Node.js/TypeScript 用户注意**：如果你在构建 Node.js 应用，建议直接使用 `@earendil-works/pi-coding-agent` 中的 `AgentSession`，而不是启动子进程。API 参见 [`src/core/agent-session.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/agent-session.ts)。若需要基于子进程的 TypeScript 客户端，参见 [`src/modes/rpc/rpc-client.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/modes/rpc/rpc-client.ts)。

## 启动 RPC 模式

```bash
pi --mode rpc [options]
```

常用选项：
- `--provider <name>`：设置 LLM provider（anthropic、openai、google 等）
- `--model <pattern>`：模型匹配模式或 ID（支持 `provider/id` 以及可选的 `:<thinking>` 后缀）
- `--name <name>` / `-n <name>`：在启动时设置会话（session）显示名称
- `--no-session`：禁用会话持久化
- `--session-dir <path>`：自定义会话存储目录

## 协议概览

- **命令（Commands）**：发送到 stdin 的 JSON 对象，每行一个
- **响应（Responses）**：`type: "response"` 的 JSON 对象，表示命令成功/失败
- **事件（Events）**：以 JSON 行的形式流式输出到 stdout 的 agent 事件

所有命令都支持可选的 `id` 字段，用于请求/响应关联。如果提供了 `id`，对应的响应会包含相同的 `id`。

### 帧格式（Framing）

RPC 模式使用严格的 JSONL 语义，仅以 LF（`\n`）作为记录分隔符。

这对客户端很重要：
- 只以 `\n` 分割记录
- 兼容 `\r\n` 输入：剥掉行尾的 `\r` 即可
- 不要使用会把 Unicode 分隔符当作换行的通用行读取器

尤其要注意，Node 的 `readline` 对 RPC 模式而言并不符合协议，因为它还会在 `U+2028` 和 `U+2029` 处分行，而这两个字符在 JSON 字符串内是合法的。

## 命令

### 提示（Prompting）

#### prompt

向 agent 发送用户 prompt。当 prompt 被接受、入队或处理后即发出命令响应。接受之后，事件会继续异步流式输出。

```json
{"id": "req-1", "type": "prompt", "message": "Hello, world!"}
```

带图片：
```json
{"type": "prompt", "message": "What's in this image?", "images": [{"type": "image", "data": "base64-encoded-data", "mimeType": "image/png"}]}
```

**streaming 期间**：如果 agent 已在 streaming，你必须指定 `streamingBehavior` 才能将消息入队：

```json
{"type": "prompt", "message": "New instruction", "streamingBehavior": "steer"}
```

- `"steer"`：在 agent 运行期间将消息入队。它会在当前助手回合执行完其工具调用之后、下一次 LLM 调用之前被投递。
- `"followUp"`：等 agent 结束再投递。消息仅在 agent 停止后才会被投递。

如果 agent 正在 streaming 且未指定 `streamingBehavior`，该命令返回错误。

**Extension 命令**：如果消息是 extension 命令（例如 `/mycommand`），即便在 streaming 期间也会立即执行。Extension 命令通过 `pi.sendMessage()` 自行管理其与 LLM 的交互。

**输入展开**：skill 命令（`/skill:name`）和提示词模板（`/template`）会在发送/入队之前被展开。

响应：
```json
{"id": "req-1", "type": "response", "command": "prompt", "success": true}
```

`success: true` 表示 prompt 已被接受、入队或立即处理。`success: false` 表示 prompt 在被接受之前遭到拒绝。被接受之后发生的失败会通过正常的事件与消息流上报，而不会针对同一请求 id 发出第二个 `response`。

`images` 字段是可选的。每张图片使用 `ImageContent` 格式：`{"type": "image", "data": "base64-encoded-data", "mimeType": "image/png"}`。

#### steer

在 agent 运行期间将一条 steering 消息入队。它会在当前助手回合执行完其工具调用之后、下一次 LLM 调用之前被投递。skill 命令和提示词模板会被展开。不允许 extension 命令（请改用 `prompt`）。

```json
{"type": "steer", "message": "Stop and do this instead"}
```

带图片：
```json
{"type": "steer", "message": "Look at this instead", "images": [{"type": "image", "data": "base64-encoded-data", "mimeType": "image/png"}]}
```

`images` 字段是可选的。每张图片使用 `ImageContent` 格式（与 `prompt` 相同）。

响应：
```json
{"type": "response", "command": "steer", "success": true}
```

关于如何控制 steering 消息的处理方式，参见 [set_steering_mode](#set_steering_mode)。

#### follow_up

将一条后续消息入队，在 agent 结束后处理。仅当 agent 不再有工具调用或 steering 消息时才会投递。skill 命令和提示词模板会被展开。不允许 extension 命令（请改用 `prompt`）。

```json
{"type": "follow_up", "message": "After you're done, also do this"}
```

带图片：
```json
{"type": "follow_up", "message": "Also check this image", "images": [{"type": "image", "data": "base64-encoded-data", "mimeType": "image/png"}]}
```

`images` 字段是可选的。每张图片使用 `ImageContent` 格式（与 `prompt` 相同）。

响应：
```json
{"type": "response", "command": "follow_up", "success": true}
```

关于如何控制后续消息的处理方式，参见 [set_follow_up_mode](#set_follow_up_mode)。

#### abort

中止当前的 agent 操作。

```json
{"type": "abort"}
```

响应：
```json
{"type": "response", "command": "abort", "success": true}
```

#### new_session

开始一个全新会话。可以被 `session_before_switch` extension 事件处理器取消。

```json
{"type": "new_session"}
```

可选地记录父会话：
```json
{"type": "new_session", "parentSession": "/path/to/parent-session.jsonl"}
```

响应：
```json
{"type": "response", "command": "new_session", "success": true, "data": {"cancelled": false}}
```

如果某个 extension 取消了操作：
```json
{"type": "response", "command": "new_session", "success": true, "data": {"cancelled": true}}
```

### 状态

#### get_state

获取当前会话状态。

```json
{"type": "get_state"}
```

响应：
```json
{
  "type": "response",
  "command": "get_state",
  "success": true,
  "data": {
    "model": {...},
    "thinkingLevel": "medium",
    "isStreaming": false,
    "isCompacting": false,
    "steeringMode": "all",
    "followUpMode": "one-at-a-time",
    "sessionFile": "/path/to/session.jsonl",
    "sessionId": "abc123",
    "sessionName": "my-feature-work",
    "autoCompactionEnabled": true,
    "messageCount": 5,
    "pendingMessageCount": 0
  }
}
```

`model` 字段是完整的 [Model](#model) 对象或 `null`。`sessionName` 字段是通过 `set_session_name` 设置的显示名称，未设置时省略。

#### get_messages

获取对话中的所有消息。

```json
{"type": "get_messages"}
```

响应：
```json
{
  "type": "response",
  "command": "get_messages",
  "success": true,
  "data": {"messages": [...]}
}
```

消息是 `AgentMessage` 对象（参见[类型](#类型)）。

### 模型

#### set_model

切换到指定模型。

```json
{"type": "set_model", "provider": "anthropic", "modelId": "claude-sonnet-4-20250514"}
```

响应包含完整的 [Model](#model) 对象：
```json
{
  "type": "response",
  "command": "set_model",
  "success": true,
  "data": {...}
}
```

#### cycle_model

循环切换到下一个可用模型。如果只有一个可用模型，`data` 返回 `null`。

```json
{"type": "cycle_model"}
```

响应：
```json
{
  "type": "response",
  "command": "cycle_model",
  "success": true,
  "data": {
    "model": {...},
    "thinkingLevel": "medium",
    "isScoped": false
  }
}
```

`model` 字段是完整的 [Model](#model) 对象。

#### get_available_models

列出所有已配置的模型。

```json
{"type": "get_available_models"}
```

响应包含完整 [Model](#model) 对象的数组：
```json
{
  "type": "response",
  "command": "get_available_models",
  "success": true,
  "data": {
    "models": [...]
  }
}
```

### 思考（Thinking）

#### set_thinking_level

为支持推理/思考的模型设置思考级别。

```json
{"type": "set_thinking_level", "level": "high"}
```

级别：`"off"`、`"minimal"`、`"low"`、`"medium"`、`"high"`、`"xhigh"`、`"max"`

`"xhigh"` 与 `"max"` 仅在所选模型支持时才会暴露。某些模型（包括 GPT-5.6）两者都支持。

响应：
```json
{"type": "response", "command": "set_thinking_level", "success": true}
```

#### cycle_thinking_level

循环切换可用的思考级别。如果模型不支持思考，`data` 返回 `null`。

```json
{"type": "cycle_thinking_level"}
```

响应：
```json
{
  "type": "response",
  "command": "cycle_thinking_level",
  "success": true,
  "data": {"level": "high"}
}
```

### 队列模式

#### set_steering_mode

控制 steering 消息（来自 `steer`）的投递方式。

```json
{"type": "set_steering_mode", "mode": "one-at-a-time"}
```

模式：
- `"all"`：在当前助手回合执行完其工具调用之后，投递所有 steering 消息
- `"one-at-a-time"`：每完成一个助手回合投递一条 steering 消息（默认）

响应：
```json
{"type": "response", "command": "set_steering_mode", "success": true}
```

#### set_follow_up_mode

控制后续消息（来自 `follow_up`）的投递方式。

```json
{"type": "set_follow_up_mode", "mode": "one-at-a-time"}
```

模式：
- `"all"`：agent 结束时投递所有后续消息
- `"one-at-a-time"`：agent 每次完成投递一条后续消息（默认）

响应：
```json
{"type": "response", "command": "set_follow_up_mode", "success": true}
```

### 上下文压缩

#### compact

手动压缩对话上下文以降低 token 用量。

```json
{"type": "compact"}
```

带自定义指令：
```json
{"type": "compact", "customInstructions": "Focus on code changes"}
```

响应：
```json
{
  "type": "response",
  "command": "compact",
  "success": true,
  "data": {
    "summary": "Summary of conversation...",
    "firstKeptEntryId": "abc123",
    "tokensBefore": 150000,
    "estimatedTokensAfter": 32000,
    "details": {}
  }
}
```

`estimatedTokensAfter` 是对压缩后立即重建的消息上下文的启发式估算，并非 provider 精确的 token 计数。

#### set_auto_compaction

启用或禁用上下文接近占满时的自动压缩。

```json
{"type": "set_auto_compaction", "enabled": true}
```

响应：
```json
{"type": "response", "command": "set_auto_compaction", "success": true}
```

### 重试

#### set_auto_retry

启用或禁用瞬时错误（过载、限流、5xx）时的自动重试。

```json
{"type": "set_auto_retry", "enabled": true}
```

响应：
```json
{"type": "response", "command": "set_auto_retry", "success": true}
```

#### abort_retry

中止正在进行的重试（取消延迟等待并停止重试）。

```json
{"type": "abort_retry"}
```

响应：
```json
{"type": "response", "command": "abort_retry", "success": true}
```

### Bash

#### bash

执行一条 shell 命令，并将输出加入对话上下文。

```json
{"type": "bash", "command": "ls -la"}
```

响应：
```json
{
  "type": "response",
  "command": "bash",
  "success": true,
  "data": {
    "output": "total 48\ndrwxr-xr-x ...",
    "exitCode": 0,
    "cancelled": false,
    "truncated": false
  }
}
```

如果输出被截断，会包含 `fullOutputPath`：
```json
{
  "type": "response",
  "command": "bash",
  "success": true,
  "data": {
    "output": "truncated output...",
    "exitCode": 0,
    "cancelled": false,
    "truncated": true,
    "fullOutputPath": "/tmp/pi-bash-abc123.log"
  }
}
```

**bash 结果如何进入 LLM：**

`bash` 命令立即执行并返回 `BashResult`。在内部会创建一个 `BashExecutionMessage` 并存入 agent 的消息状态。这条消息**不会**发出事件。

当下一个 `prompt` 命令发出时，所有消息（包括 `BashExecutionMessage`）在发送给 LLM 之前会被转换。`BashExecutionMessage` 会被转换成如下格式的 `UserMessage`：

````
Ran `ls -la`
```
total 48
drwxr-xr-x ...
```
````

这意味着：
1. bash 输出会在**下一个 prompt** 时进入 LLM 上下文，而不是立即进入
2. 在一次 prompt 之前可以执行多条 bash 命令；所有输出都会被包含
3. `BashExecutionMessage` 本身不会发出任何事件

#### abort_bash

中止正在运行的 bash 命令。

```json
{"type": "abort_bash"}
```

响应：
```json
{"type": "response", "command": "abort_bash", "success": true}
```

### 会话

#### get_session_stats

获取 token 用量、费用统计以及当前上下文窗口占用。

```json
{"type": "get_session_stats"}
```

响应：
```json
{
  "type": "response",
  "command": "get_session_stats",
  "success": true,
  "data": {
    "sessionFile": "/path/to/session.jsonl",
    "sessionId": "abc123",
    "userMessages": 5,
    "assistantMessages": 5,
    "toolCalls": 12,
    "toolResults": 12,
    "totalMessages": 22,
    "tokens": {
      "input": 50000,
      "output": 10000,
      "cacheRead": 40000,
      "cacheWrite": 5000,
      "total": 105000
    },
    "cost": 0.45,
    "contextUsage": {
      "tokens": 60000,
      "contextWindow": 200000,
      "percent": 30
    }
  }
}
```

`tokens` 包含当前会话状态下助手用量的累计值。`contextUsage` 包含实际的当前上下文窗口估算，用于上下文压缩判断与页脚显示。

没有可用模型或上下文窗口时，`contextUsage` 会被省略。上下文压缩刚完成后，在压缩后的新助手响应提供有效用量数据之前，`contextUsage.tokens` 和 `contextUsage.percent` 为 `null`。

#### export_html

将会话导出为 HTML 文件。

```json
{"type": "export_html"}
```

带自定义路径：
```json
{"type": "export_html", "outputPath": "/tmp/session.html"}
```

响应：
```json
{
  "type": "response",
  "command": "export_html",
  "success": true,
  "data": {"path": "/tmp/session.html"}
}
```

#### switch_session

加载另一个会话文件。可以被 `session_before_switch` extension 事件处理器取消。

```json
{"type": "switch_session", "sessionPath": "/path/to/session.jsonl"}
```

响应：
```json
{"type": "response", "command": "switch_session", "success": true, "data": {"cancelled": false}}
```

如果某个 extension 取消了切换：
```json
{"type": "response", "command": "switch_session", "success": true, "data": {"cancelled": true}}
```

#### fork

从活动分支上的某条历史用户消息创建一个新分叉。可以被 `session_before_fork` extension 事件处理器取消。返回分叉起点消息的文本。

```json
{"type": "fork", "entryId": "abc123"}
```

响应：
```json
{
  "type": "response",
  "command": "fork",
  "success": true,
  "data": {"text": "The original prompt text...", "cancelled": false}
}
```

如果某个 extension 取消了分叉：
```json
{
  "type": "response",
  "command": "fork",
  "success": true,
  "data": {"text": "The original prompt text...", "cancelled": true}
}
```

#### clone

将当前活动分支在当前位置复制为一个新会话。可以被 `session_before_fork` extension 事件处理器取消。

```json
{"type": "clone"}
```

响应：
```json
{
  "type": "response",
  "command": "clone",
  "success": true,
  "data": {"cancelled": false}
}
```

如果某个 extension 取消了复制：
```json
{
  "type": "response",
  "command": "clone",
  "success": true,
  "data": {"cancelled": true}
}
```

#### get_fork_messages

获取可用于分叉的用户消息。

```json
{"type": "get_fork_messages"}
```

响应：
```json
{
  "type": "response",
  "command": "get_fork_messages",
  "success": true,
  "data": {
    "messages": [
      {"entryId": "abc123", "text": "First prompt..."},
      {"entryId": "def456", "text": "Second prompt..."}
    ]
  }
}
```

#### get_entries

按追加顺序获取所有会话条目（不含会话头）。会话是一棵只追加（append-only）的条目树，条目 id 稳定，因此条目 id 可以充当持久化游标：把你已见过的最后一个条目 id 作为 `since` 传入，即可只获取严格位于其后的条目，即使客户端重启也依然有效。与 `get_messages` 不同，这里包含压缩前的历史以及被放弃的分支。

```json
{"type": "get_entries"}
```

带游标：
```json
{"type": "get_entries", "since": "abc123"}
```

响应：
```json
{
  "type": "response",
  "command": "get_entries",
  "success": true,
  "data": {
    "entries": [
      {"type": "message", "id": "def456", "parentId": "abc123", "timestamp": "...", "message": {"role": "user", "...": "..."}}
    ],
    "leafId": "def456"
  }
}
```

`leafId` 是当前叶子条目的 id（空会话时为 `null`），因此客户端一次往返即可判断活动分支是否发生了移动。如果 `since` 不匹配任何条目 id，响应为 `success: false`。

#### get_tree

以条目树的形式获取会话。每个节点为 `{entry, children, label?, labelTimestamp?}`。结构良好的会话只有一个根；孤儿条目（父链断裂）也会作为根出现。

```json
{"type": "get_tree"}
```

响应：
```json
{
  "type": "response",
  "command": "get_tree",
  "success": true,
  "data": {
    "tree": [
      {
        "entry": {"type": "message", "id": "abc123", "parentId": null, "...": "..."},
        "children": [
          {"entry": {"type": "message", "id": "def456", "parentId": "abc123", "...": "..."}, "children": []}
        ]
      }
    ],
    "leafId": "def456"
  }
}
```

#### get_last_assistant_text

获取最后一条助手消息的文本内容。

```json
{"type": "get_last_assistant_text"}
```

响应：
```json
{
  "type": "response",
  "command": "get_last_assistant_text",
  "success": true,
  "data": {"text": "The assistant's response..."}
}
```

如果不存在助手消息，返回 `{"text": null}`。

#### set_session_name

为当前会话设置显示名称。该名称会出现在会话列表中，便于识别会话。

```json
{"type": "set_session_name", "name": "my-feature-work"}
```

响应：
```json
{
  "type": "response",
  "command": "set_session_name",
  "success": true
}
```

当前会话名称可通过 `get_state` 的 `sessionName` 字段获取。要在启动 RPC 模式时设置初始名称，向 `pi --mode rpc` 进程传入 `--name <name>` 或 `-n <name>`。

### 命令列表

#### get_commands

获取可用命令（extension 命令、提示词模板和 skill）。这些命令都可以通过 `prompt` 命令以 `/` 前缀调用。

```json
{"type": "get_commands"}
```

响应：
```json
{
  "type": "response",
  "command": "get_commands",
  "success": true,
  "data": {
    "commands": [
      {"name": "session-name", "description": "Set or clear session name", "source": "extension", "path": "/home/user/.pi/agent/extensions/session.ts"},
      {"name": "fix-tests", "description": "Fix failing tests", "source": "prompt", "location": "project", "path": "/home/user/myproject/.pi/agent/prompts/fix-tests.md"},
      {"name": "skill:brave-search", "description": "Web search via Brave API", "source": "skill", "location": "user", "path": "/home/user/.pi/agent/skills/brave-search/SKILL.md"}
    ]
  }
}
```

每个命令包含：
- `name`：命令名（以 `/name` 调用）
- `description`：人类可读的描述（extension 命令可省略）
- `source`：命令的种类：
  - `"extension"`：由 extension 中的 `pi.registerCommand()` 注册
  - `"prompt"`：从提示词模板 `.md` 文件加载
  - `"skill"`：从 skill 目录加载（名称带 `skill:` 前缀）
- `location`：加载来源（可选，extension 命令没有此字段）：
  - `"user"`：用户级（`~/.pi/agent/`）
  - `"project"`：项目级（`./.pi/agent/`）
  - `"path"`：通过 CLI 或设置指定的显式路径
- `path`：命令来源文件的绝对路径（可选）

**注意**：内置的 TUI 命令（`/settings`、`/hotkeys` 等）不包含在内。它们只在交互模式下处理，通过 `prompt` 发送并不会执行。

## 事件

在 agent 运行期间，事件以 JSON 行的形式流式输出到 stdout。事件**不**包含 `id` 字段（只有响应才有）。

### 事件类型

| 事件 | 描述 |
|-------|-------------|
| `agent_start` | agent 开始处理 |
| `agent_end` | 一次底层 agent 运行完成（其后仍可能有重试、上下文压缩或队列中的后续消息） |
| `agent_settled` | agent 运行完全落定；不再有自动重试、压缩后重试或队列中的后续任务 |
| `turn_start` | 新回合开始 |
| `turn_end` | 回合结束（包含助手消息和工具结果） |
| `message_start` | 消息开始 |
| `message_update` | 流式更新（文本/思考/工具调用增量） |
| `message_end` | 消息完成 |
| `tool_execution_start` | 工具开始执行 |
| `tool_execution_update` | 工具执行进度（流式输出） |
| `tool_execution_end` | 工具执行完成 |
| `queue_update` | 待处理的 steering/后续消息队列发生变化 |
| `compaction_start` | 上下文压缩开始 |
| `compaction_end` | 上下文压缩完成 |
| `auto_retry_start` | 自动重试开始（在瞬时错误之后） |
| `auto_retry_end` | 自动重试结束（成功或最终失败） |
| `extension_error` | extension 抛出错误 |

### agent_start

agent 开始处理 prompt 时发出。

```json
{"type": "agent_start"}
```

### agent_end

一次底层 agent 运行完成时发出。包含本次运行中生成的所有消息。如果 `willRetry` 为 true，随后会进行一次自动重试。

```json
{
  "type": "agent_end",
  "messages": [...],
  "willRetry": false
}
```

### agent_settled

整个会话级运行落定之后发出。此时 Pi 不会再通过重试、压缩后重试或队列中的后续消息自动继续。

```json
{"type": "agent_settled"}
```

### turn_start / turn_end

一个回合由一条助手响应及其引发的所有工具调用和结果组成。

```json
{"type": "turn_start"}
```

```json
{
  "type": "turn_end",
  "message": {...},
  "toolResults": [...]
}
```

### message_start / message_end

消息开始与完成时发出。`message` 字段包含一个 `AgentMessage`。

```json
{"type": "message_start", "message": {...}}
{"type": "message_end", "message": {...}}
```

### message_update（streaming）

在助手消息流式输出期间发出。同时包含部分消息和一个流式增量事件。

```json
{
  "type": "message_update",
  "message": {...},
  "assistantMessageEvent": {
    "type": "text_delta",
    "contentIndex": 0,
    "delta": "Hello ",
    "partial": {...}
  }
}
```

`assistantMessageEvent` 字段包含以下增量类型之一：

| 类型 | 描述 |
|------|-------------|
| `start` | 消息生成开始 |
| `text_start` | 文本内容块开始 |
| `text_delta` | 文本内容片段 |
| `text_end` | 文本内容块结束 |
| `thinking_start` | 思考块开始 |
| `thinking_delta` | 思考内容片段 |
| `thinking_end` | 思考块结束 |
| `toolcall_start` | 工具调用开始 |
| `toolcall_delta` | 工具调用参数片段 |
| `toolcall_end` | 工具调用结束（包含完整的 `toolCall` 对象） |
| `done` | 消息完成（原因：`"stop"`、`"length"`、`"toolUse"`） |
| `error` | 发生错误（原因：`"aborted"`、`"error"`） |

流式输出一段文本响应的示例：
```json
{"type":"message_update","message":{...},"assistantMessageEvent":{"type":"text_start","contentIndex":0,"partial":{...}}}
{"type":"message_update","message":{...},"assistantMessageEvent":{"type":"text_delta","contentIndex":0,"delta":"Hello","partial":{...}}}
{"type":"message_update","message":{...},"assistantMessageEvent":{"type":"text_delta","contentIndex":0,"delta":" world","partial":{...}}}
{"type":"message_update","message":{...},"assistantMessageEvent":{"type":"text_end","contentIndex":0,"content":"Hello world","partial":{...}}}
```

### tool_execution_start / tool_execution_update / tool_execution_end

工具开始执行、流式报告进度、执行完成时发出。

```json
{
  "type": "tool_execution_start",
  "toolCallId": "call_abc123",
  "toolName": "bash",
  "args": {"command": "ls -la"}
}
```

执行期间，`tool_execution_update` 事件流式输出部分结果（例如陆续到达的 bash 输出）：

```json
{
  "type": "tool_execution_update",
  "toolCallId": "call_abc123",
  "toolName": "bash",
  "args": {"command": "ls -la"},
  "partialResult": {
    "content": [{"type": "text", "text": "partial output so far..."}],
    "details": {"truncation": null, "fullOutputPath": null}
  }
}
```

完成时：

```json
{
  "type": "tool_execution_end",
  "toolCallId": "call_abc123",
  "toolName": "bash",
  "result": {
    "content": [{"type": "text", "text": "total 48\n..."}],
    "details": {...}
  },
  "isError": false
}
```

使用 `toolCallId` 来关联事件。`tool_execution_update` 中的 `partialResult` 包含到目前为止累积的输出（而不仅是增量），因此客户端只需在每次更新时整体替换显示内容即可。

### queue_update

待处理的 steering 或后续消息队列发生变化时发出。

```json
{
  "type": "queue_update",
  "steering": ["Focus on error handling"],
  "followUp": ["After that, summarize the result"]
}
```

### compaction_start / compaction_end

上下文压缩运行时发出，无论手动还是自动。

```json
{"type": "compaction_start", "reason": "threshold"}
```

`reason` 字段为 `"manual"`、`"threshold"` 或 `"overflow"`。

```json
{
  "type": "compaction_end",
  "reason": "threshold",
  "result": {
    "summary": "Summary of conversation...",
    "firstKeptEntryId": "abc123",
    "tokensBefore": 150000,
    "estimatedTokensAfter": 32000,
    "details": {}
  },
  "aborted": false,
  "willRetry": false
}
```

如果 `reason` 是 `"overflow"` 且压缩成功，则 `willRetry` 为 `true`，agent 会自动重试该 prompt。

如果压缩被中止，`result` 为 `null` 且 `aborted` 为 `true`。

如果压缩失败（例如 API 配额耗尽），`result` 为 `null`，`aborted` 为 `false`，`errorMessage` 包含错误描述。

### auto_retry_start / auto_retry_end

在瞬时错误（过载、限流、5xx）之后触发自动重试时发出。

```json
{
  "type": "auto_retry_start",
  "attempt": 1,
  "maxAttempts": 3,
  "delayMs": 2000,
  "errorMessage": "529 {\"type\":\"error\",\"error\":{\"type\":\"overloaded_error\",\"message\":\"Overloaded\"}}"
}
```

```json
{
  "type": "auto_retry_end",
  "success": true,
  "attempt": 2
}
```

最终失败时（超出最大重试次数）：
```json
{
  "type": "auto_retry_end",
  "success": false,
  "attempt": 3,
  "finalError": "529 overloaded_error: Overloaded"
}
```

### extension_error

extension 抛出错误时发出。

```json
{
  "type": "extension_error",
  "extensionPath": "/path/to/extension.ts",
  "event": "tool_call",
  "error": "Error message..."
}
```

## Extension UI 协议

Extension 可以通过 `ctx.ui.select()`、`ctx.ui.confirm()` 等方法请求用户交互。在 RPC 模式下，这些调用会被翻译成叠加在基础命令/事件流之上的请求/响应子协议。

Extension UI 方法分为两类：

- **对话框方法**（`select`、`confirm`、`input`、`editor`）：在 stdout 上发出 `extension_ui_request`，并阻塞等待客户端从 stdin 发回带匹配 `id` 的 `extension_ui_response`。
- **即发即弃（fire-and-forget）方法**（`notify`、`setStatus`、`setWidget`、`setTitle`、`set_editor_text`）：在 stdout 上发出 `extension_ui_request`，但不期待响应。客户端可以展示这些信息，也可以忽略。

如果对话框方法带有 `timeout` 字段，超时到期时 agent 侧会以默认值自动解析。客户端无需跟踪超时。

部分 `ExtensionUIContext` 方法在 RPC 模式下不受支持或功能降级，因为它们需要直接访问 TUI：
- `custom()` 返回 `undefined`
- `setWorkingMessage()`、`setWorkingIndicator()`、`setFooter()`、`setHeader()`、`setEditorComponent()`、`setToolsExpanded()` 是空操作（no-op）
- `getEditorText()` 返回 `""`
- `getToolsExpanded()` 返回 `false`
- `pasteToEditor()` 委托给 `setEditorText()`（没有粘贴/折叠处理）
- `getAllThemes()` 返回 `[]`
- `getTheme()` 返回 `undefined`
- `setTheme()` 返回 `{ success: false, error: "..." }`

注意：RPC 模式下 `ctx.mode` 是 `"rpc"`，且 `ctx.hasUI` 是 `true`，因为对话框方法和即发即弃方法都可以通过 extension UI 子协议正常工作。对于像 `custom()` 这样需要真实终端的 TUI 专属功能，请用 `ctx.mode === "tui"` 加以判断。

### Extension UI 请求（stdout）

所有请求都有 `type: "extension_ui_request"`、唯一的 `id` 以及一个 `method` 字段。

#### select

提示用户从列表中选择。带 `timeout` 字段的对话框方法会包含以毫秒为单位的超时时间；如果客户端未及时响应，agent 会自动以 `undefined` 解析。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-1",
  "method": "select",
  "title": "Allow dangerous command?",
  "options": ["Allow", "Block"],
  "timeout": 10000
}
```

期望的响应：带 `value`（所选选项字符串）或 `cancelled: true` 的 `extension_ui_response`。

#### confirm

提示用户进行是/否确认。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-2",
  "method": "confirm",
  "title": "Clear session?",
  "message": "All messages will be lost.",
  "timeout": 5000
}
```

期望的响应：带 `confirmed: true/false` 或 `cancelled: true` 的 `extension_ui_response`。

#### input

提示用户输入自由文本。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-3",
  "method": "input",
  "title": "Enter a value",
  "placeholder": "type something..."
}
```

期望的响应：带 `value`（输入的文本）或 `cancelled: true` 的 `extension_ui_response`。

#### editor

打开一个多行文本编辑器，可选预填内容。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-4",
  "method": "editor",
  "title": "Edit some text",
  "prefill": "Line 1\nLine 2\nLine 3"
}
```

期望的响应：带 `value`（编辑后的文本）或 `cancelled: true` 的 `extension_ui_response`。

#### notify

显示一条通知。即发即弃，不期待响应。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-5",
  "method": "notify",
  "message": "Command blocked by user",
  "notifyType": "warning"
}
```

`notifyType` 字段为 `"info"`、`"warning"` 或 `"error"`。省略时默认为 `"info"`。

#### setStatus

设置或清除页脚/状态栏中的一个状态条目。即发即弃。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-6",
  "method": "setStatus",
  "statusKey": "my-ext",
  "statusText": "Turn 3 running..."
}
```

发送 `statusText: undefined`（或省略该字段）可清除对应 key 的状态条目。

#### setWidget

设置或清除一个显示在编辑器上方或下方的 widget（若干行文本组成的块）。即发即弃。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-7",
  "method": "setWidget",
  "widgetKey": "my-ext",
  "widgetLines": ["--- My Widget ---", "Line 1", "Line 2"],
  "widgetPlacement": "aboveEditor"
}
```

发送 `widgetLines: undefined`（或省略该字段）可清除该 widget。`widgetPlacement` 字段为 `"aboveEditor"`（默认）或 `"belowEditor"`。RPC 模式下只支持字符串数组；组件工厂会被忽略。

#### setTitle

设置终端窗口/标签页标题。即发即弃。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-8",
  "method": "setTitle",
  "title": "pi - my project"
}
```

#### set_editor_text

设置输入编辑器中的文本。即发即弃。

```json
{
  "type": "extension_ui_request",
  "id": "uuid-9",
  "method": "set_editor_text",
  "text": "prefilled text for the user"
}
```

### Extension UI 响应（stdin）

仅对话框方法（`select`、`confirm`、`input`、`editor`）需要发送响应。`id` 必须与请求匹配。

#### 值响应（select、input、editor）

```json
{"type": "extension_ui_response", "id": "uuid-1", "value": "Allow"}
```

#### 确认响应（confirm）

```json
{"type": "extension_ui_response", "id": "uuid-2", "confirmed": true}
```

#### 取消响应（任意对话框）

关闭任意对话框方法。extension 会收到 `undefined`（select/input/editor）或 `false`（confirm）。

```json
{"type": "extension_ui_response", "id": "uuid-3", "cancelled": true}
```

## 错误处理

失败的命令返回 `success: false` 的响应：

```json
{
  "type": "response",
  "command": "set_model",
  "success": false,
  "error": "Model not found: invalid/model"
}
```

解析错误：

```json
{
  "type": "response",
  "command": "parse",
  "success": false,
  "error": "Failed to parse command: Unexpected token..."
}
```

## 类型

源码文件：
- [`packages/ai/src/types.ts`](https://github.com/earendil-works/pi/blob/main/packages/ai/src/types.ts) - `Model`、`UserMessage`、`AssistantMessage`、`ToolResultMessage`
- [`packages/agent/src/types.ts`](https://github.com/earendil-works/pi/blob/main/packages/agent/src/types.ts) - `AgentMessage`、`AgentEvent`
- [`src/core/messages.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/messages.ts) - `BashExecutionMessage`
- [`src/modes/rpc/rpc-types.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/modes/rpc/rpc-types.ts) - RPC 命令/响应类型、extension UI 请求/响应类型

### Model

```json
{
  "id": "claude-sonnet-4-20250514",
  "name": "Claude Sonnet 4",
  "api": "anthropic-messages",
  "provider": "anthropic",
  "baseUrl": "https://api.anthropic.com",
  "reasoning": true,
  "input": ["text", "image"],
  "contextWindow": 200000,
  "maxTokens": 16384,
  "cost": {
    "input": 3.0,
    "output": 15.0,
    "cacheRead": 0.3,
    "cacheWrite": 3.75
  }
}
```

### UserMessage

```json
{
  "role": "user",
  "content": "Hello!",
  "timestamp": 1733234567890,
  "attachments": []
}
```

`content` 字段可以是字符串，也可以是 `TextContent`/`ImageContent` 块的数组。

### AssistantMessage

```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "Hello! How can I help?"},
    {"type": "thinking", "thinking": "User is greeting me..."},
    {"type": "toolCall", "id": "call_123", "name": "bash", "arguments": {"command": "ls"}}
  ],
  "api": "anthropic-messages",
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "usage": {
    "input": 100,
    "output": 50,
    "cacheRead": 0,
    "cacheWrite": 0,
    "cost": {"input": 0.0003, "output": 0.00075, "cacheRead": 0, "cacheWrite": 0, "total": 0.00105}
  },
  "stopReason": "stop",
  "timestamp": 1733234567890
}
```

停止原因：`"stop"`、`"length"`、`"toolUse"`、`"error"`、`"aborted"`

### ToolResultMessage

```json
{
  "role": "toolResult",
  "toolCallId": "call_123",
  "toolName": "bash",
  "content": [{"type": "text", "text": "total 48\ndrwxr-xr-x ..."}],
  "isError": false,
  "timestamp": 1733234567890
}
```

### BashExecutionMessage

由 `bash` RPC 命令创建（并非 LLM 工具调用创建）：

```json
{
  "role": "bashExecution",
  "command": "ls -la",
  "output": "total 48\ndrwxr-xr-x ...",
  "exitCode": 0,
  "cancelled": false,
  "truncated": false,
  "fullOutputPath": null,
  "timestamp": 1733234567890
}
```

### Attachment

```json
{
  "id": "img1",
  "type": "image",
  "fileName": "photo.jpg",
  "mimeType": "image/jpeg",
  "size": 102400,
  "content": "base64-encoded-data...",
  "extractedText": null,
  "preview": null
}
```

## 示例：基础客户端（Python）

```python
import subprocess
import json

proc = subprocess.Popen(
    ["pi", "--mode", "rpc", "--no-session"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

def send(cmd):
    proc.stdin.write(json.dumps(cmd) + "\n")
    proc.stdin.flush()

def read_events():
    for line in proc.stdout:
        yield json.loads(line)

# 发送 prompt
send({"type": "prompt", "message": "Hello!"})

# 处理事件
for event in read_events():
    if event.get("type") == "message_update":
        delta = event.get("assistantMessageEvent", {})
        if delta.get("type") == "text_delta":
            print(delta["delta"], end="", flush=True)

    if event.get("type") == "agent_end":
        print()
        break
```

## 示例：交互式客户端（Node.js）

完整的交互式示例参见 [`test/rpc-example.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/test/rpc-example.ts)；带类型的客户端实现参见 [`src/modes/rpc/rpc-client.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/modes/rpc/rpc-client.ts)。

处理 extension UI 协议的完整示例参见 [`examples/rpc-extension-ui.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/rpc-extension-ui.ts)，它与 [`examples/extensions/rpc-demo.ts`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/rpc-demo.ts) extension 配套使用。

```javascript
const { spawn } = require("child_process");
const { StringDecoder } = require("string_decoder");

const agent = spawn("pi", ["--mode", "rpc", "--no-session"]);

function attachJsonlReader(stream, onLine) {
    const decoder = new StringDecoder("utf8");
    let buffer = "";

    stream.on("data", (chunk) => {
        buffer += typeof chunk === "string" ? chunk : decoder.write(chunk);

        while (true) {
            const newlineIndex = buffer.indexOf("\n");
            if (newlineIndex === -1) break;

            let line = buffer.slice(0, newlineIndex);
            buffer = buffer.slice(newlineIndex + 1);
            if (line.endsWith("\r")) line = line.slice(0, -1);
            onLine(line);
        }
    });

    stream.on("end", () => {
        buffer += decoder.end();
        if (buffer.length > 0) {
            onLine(buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer);
        }
    });
}

attachJsonlReader(agent.stdout, (line) => {
    const event = JSON.parse(line);

    if (event.type === "message_update") {
        const { assistantMessageEvent } = event;
        if (assistantMessageEvent.type === "text_delta") {
            process.stdout.write(assistantMessageEvent.delta);
        }
    }
});

// 发送 prompt
agent.stdin.write(JSON.stringify({ type: "prompt", message: "Hello" }) + "\n");

// Ctrl+C 时中止
process.on("SIGINT", () => {
    agent.stdin.write(JSON.stringify({ type: "abort" }) + "\n");
});
```
