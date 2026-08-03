> **译文** | 原文：[`packages/coding-agent/docs/json.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/json.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# JSON 事件流模式

```bash
pi --mode json "Your prompt"
```

将 session 的全部事件以 JSON 行的形式输出到 stdout。适合把 pi 集成进其它工具或自定义 UI。

## 事件类型

事件定义见 [`AgentSessionEvent`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/agent-session.ts#L102)：

```typescript
type AgentSessionEvent =
  | AgentEvent
  | { type: "queue_update"; steering: readonly string[]; followUp: readonly string[] }
  | { type: "compaction_start"; reason: "manual" | "threshold" | "overflow" }
  | { type: "compaction_end"; reason: "manual" | "threshold" | "overflow"; result: CompactionResult | undefined; aborted: boolean; willRetry: boolean; errorMessage?: string }
  | { type: "auto_retry_start"; attempt: number; maxAttempts: number; delayMs: number; errorMessage: string }
  | { type: "auto_retry_end"; success: boolean; attempt: number; finalError?: string };
```

`queue_update` 会在待处理的 steering 与后续消息队列发生变化时输出完整队列内容。`compaction_start` 和 `compaction_end` 同时覆盖手动与自动的上下文压缩。

基础事件来自 [`AgentEvent`](https://github.com/earendil-works/pi-mono/blob/main/packages/agent/src/types.ts#L179)：

```typescript
type AgentEvent =
  // Agent 生命周期
  | { type: "agent_start" }
  | { type: "agent_end"; messages: AgentMessage[] }
  // 轮次（turn）生命周期
  | { type: "turn_start" }
  | { type: "turn_end"; message: AgentMessage; toolResults: ToolResultMessage[] }
  // 消息生命周期
  | { type: "message_start"; message: AgentMessage }
  | { type: "message_update"; message: AgentMessage; assistantMessageEvent: AssistantMessageEvent }
  | { type: "message_end"; message: AgentMessage }
  // 工具执行
  | { type: "tool_execution_start"; toolCallId: string; toolName: string; args: any }
  | { type: "tool_execution_update"; toolCallId: string; toolName: string; args: any; partialResult: any }
  | { type: "tool_execution_end"; toolCallId: string; toolName: string; result: any; isError: boolean };
```

## 消息类型

基础消息来自 [`packages/ai/src/types.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/ai/src/types.ts#L134)：
- `UserMessage`（第 134 行）
- `AssistantMessage`（第 140 行）
- `ToolResultMessage`（第 152 行）

扩展消息来自 [`packages/coding-agent/src/core/messages.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/messages.ts#L29)：
- `BashExecutionMessage`（第 29 行）
- `CustomMessage`（第 46 行）
- `BranchSummaryMessage`（第 55 行）
- `CompactionSummaryMessage`（第 62 行）

## 输出格式

每一行是一个 JSON 对象。第一行是 session 头：

```json
{"type":"session","version":3,"id":"uuid","timestamp":"...","cwd":"/path"}
```

后面跟随实时产生的事件：

```json
{"type":"agent_start"}
{"type":"turn_start"}
{"type":"message_start","message":{"role":"assistant","content":[],...}}
{"type":"message_update","message":{...},"assistantMessageEvent":{"type":"text_delta","delta":"Hello",...}}
{"type":"message_end","message":{...}}
{"type":"turn_end","message":{...},"toolResults":[]}
{"type":"agent_end","messages":[...]}
```

## 示例

```bash
pi --mode json "List files" 2>/dev/null | jq -c 'select(.type == "message_end")'
```
