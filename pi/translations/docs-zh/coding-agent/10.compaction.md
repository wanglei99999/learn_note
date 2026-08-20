> **译文** | 原文：[`packages/coding-agent/docs/compaction.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/compaction.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 上下文压缩与分支总结

LLM 的上下文窗口是有限的。当对话变得过长时，pi 会通过上下文压缩（compaction）总结较早的内容，同时保留近期的工作。本页涵盖自动上下文压缩与分支总结两部分。

**源码文件**（[pi-mono](https://github.com/earendil-works/pi-mono)）：
- [`packages/coding-agent/src/core/compaction/compaction.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/compaction.ts) - 自动上下文压缩逻辑
- [`packages/coding-agent/src/core/compaction/branch-summarization.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/branch-summarization.ts) - 分支总结
- [`packages/coding-agent/src/core/compaction/utils.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/utils.ts) - 共享工具（文件跟踪、序列化）
- [`packages/coding-agent/src/core/session-manager.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/session-manager.ts) - 条目类型（`CompactionEntry`、`BranchSummaryEntry`）
- [`packages/coding-agent/src/core/extensions/types.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/extensions/types.ts) - extension 事件类型

如需在你的项目中查看 TypeScript 类型定义，请查阅 `node_modules/@earendil-works/pi-coding-agent/dist/`。

## 概览

Pi 有两种总结机制：

| 机制 | 触发条件 | 目的 |
|-----------|---------|---------|
| 上下文压缩 | 上下文超过阈值，或执行 `/compact` | 总结旧消息以释放上下文空间 |
| 分支总结 | `/tree` 导航 | 在切换分支时保留上下文 |

两者使用相同的结构化摘要格式，并对文件操作进行累积跟踪。

## 上下文压缩

### 触发时机

满足以下条件时触发自动上下文压缩：

```
contextTokens > contextWindow - reserveTokens
```

默认情况下 `reserveTokens` 为 16384 个 token（可在 `~/.pi/agent/settings.json` 或 `<project-dir>/.pi/settings.json` 中配置）。这为 LLM 的响应留出空间。

你也可以用 `/compact [instructions]` 手动触发，可选的 instructions 用于让摘要聚焦特定内容。

### 工作原理

1. **确定切割点**：从最新消息向前回溯，累积估算 token 数，直到达到 `keepRecentTokens`（默认 20k，可在 `~/.pi/agent/settings.json` 或 `<project-dir>/.pi/settings.json` 中配置）
2. **提取消息**：收集从上一次保留边界（或会话起点）到切割点之间的消息
3. **生成摘要**：调用 LLM 按结构化格式总结，若存在上一次摘要则将其作为迭代上下文传入
4. **追加条目**：保存包含摘要和 `firstKeptEntryId` 的 `CompactionEntry`
5. **重新加载**：会话重新加载，使用摘要加上从 `firstKeptEntryId` 起的消息

```
Before compaction:

  entry:  0     1     2     3      4     5     6      7      8     9
        ┌─────┬─────┬─────┬─────┬──────┬─────┬─────┬──────┬──────┬─────┐
        │ hdr │ usr │ ass │ tool │ usr │ ass │ tool │ tool │ ass │ tool│
        └─────┴─────┴─────┴──────┴─────┴─────┴──────┴──────┴─────┴─────┘
                └────────┬───────┘ └──────────────┬──────────────┘
               messagesToSummarize            kept messages
                                   ↑
                          firstKeptEntryId (entry 4)

After compaction (new entry appended):

  entry:  0     1     2     3      4     5     6      7      8     9     10
        ┌─────┬─────┬─────┬─────┬──────┬─────┬─────┬──────┬──────┬─────┬─────┐
        │ hdr │ usr │ ass │ tool │ usr │ ass │ tool │ tool │ ass │ tool│ cmp │
        └─────┴─────┴─────┴──────┴─────┴─────┴──────┴──────┴─────┴─────┴─────┘
               └──────────┬──────┘ └──────────────────────┬───────────────────┘
                 not sent to LLM                    sent to LLM
                                                         ↑
                                              starts from firstKeptEntryId

What the LLM sees:

  ┌────────┬─────────┬─────┬─────┬──────┬──────┬─────┬──────┐
  │ system │ summary │ usr │ ass │ tool │ tool │ ass │ tool │
  └────────┴─────────┴─────┴─────┴──────┴──────┴─────┴──────┘
       ↑         ↑      └─────────────────┬────────────────┘
    prompt   from cmp          messages from firstKeptEntryId
```

再次进行上下文压缩时，被总结的范围从上一次压缩的保留边界（`firstKeptEntryId`）开始，而不是从压缩条目本身开始；若在路径中找不到该保留条目，则回退为上一次压缩条目之后的条目。这样，在上一次压缩中幸存下来的消息也会被纳入下一轮总结，从而得以保留。Pi 还会在写入新的 `CompactionEntry` 之前，基于重建后的会话上下文重新计算 `tokensBefore`，使 token 数反映实际被替换的压缩前上下文。

### 拆分轮次（Split Turns）

一个「轮次」（turn）从一条用户消息开始，包含直到下一条用户消息之前的所有 assistant 响应和工具调用。正常情况下，上下文压缩在轮次边界处切割。

当单个轮次超过 `keepRecentTokens` 时，切割点会落在轮次中间的某条 assistant 消息上。这就是「拆分轮次」：

```
Split turn (one huge turn exceeds budget):

  entry:  0     1     2      3     4      5      6     7      8
        ┌─────┬─────┬─────┬──────┬─────┬──────┬──────┬─────┬──────┐
        │ hdr │ usr │ ass │ tool │ ass │ tool │ tool │ ass │ tool │
        └─────┴─────┴─────┴──────┴─────┴──────┴──────┴─────┴──────┘
                ↑                                     ↑
         turnStartIndex = 1                  firstKeptEntryId = 7
                │                                     │
                └──── turnPrefixMessages (1-6) ───────┘
                                                      └── kept (7-8)

  isSplitTurn = true
  messagesToSummarize = []  (no complete turns before)
  turnPrefixMessages = [usr, ass, tool, ass, tool, tool]
```

对于拆分轮次，pi 会生成两份摘要并将它们合并：
1. **历史摘要**：之前的上下文（如果有）
2. **轮次前缀摘要**：被拆分轮次的前半部分

### 切割点规则

有效的切割点包括：
- 用户消息
- Assistant 消息
- BashExecution 消息
- 自定义消息（custom_message、branch_summary）

绝不能在工具结果处切割（工具结果必须与其工具调用保持在一起）。

### CompactionEntry 结构

定义于 [`session-manager.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/session-manager.ts)：

```typescript
interface CompactionEntry<T = unknown> {
  type: "compaction";
  id: string;
  parentId: string;
  timestamp: number;
  summary: string;
  firstKeptEntryId: string;
  tokensBefore: number;
  fromHook?: boolean;  // 若由 extension 提供则为 true（历史遗留字段名）
  details?: T;         // 具体实现自定义的数据
}

// 默认的上下文压缩在 details 中使用如下结构（来自 compaction.ts）：
interface CompactionDetails {
  readFiles: string[];
  modifiedFiles: string[];
}
```

Extension 可以在 `details` 中存储任意可 JSON 序列化的数据。默认的上下文压缩会跟踪文件操作，但 extension 的自定义实现可以使用自己的结构。

实现细节参见 [`prepareCompaction()`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/compaction.ts) 和 [`compact()`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/compaction.ts)。

## 分支总结

### 触发时机

当你使用 `/tree` 导航到另一个分支时，pi 会询问是否对即将离开的工作生成总结。这会把被离开分支的上下文注入到新分支中。

### 工作原理

1. **找到共同祖先**：新旧位置共享的最深节点
2. **收集条目**：从旧叶子节点回溯到共同祖先
3. **按预算准备**：在 token 预算内（从最新开始）纳入消息
4. **生成摘要**：调用 LLM 按结构化格式生成
5. **追加条目**：在导航位置保存 `BranchSummaryEntry`

```
Tree before navigation:

         ┌─ B ─ C ─ D (old leaf, being abandoned)
    A ───┤
         └─ E ─ F (target)

Common ancestor: A
Entries to summarize: B, C, D

After navigation with summary:

         ┌─ B ─ C ─ D ─ [summary of B,C,D]
    A ───┤
         └─ E ─ F (new leaf)
```

### 累积式文件跟踪

上下文压缩和分支总结都会对文件进行累积跟踪。生成摘要时，pi 会从以下来源提取文件操作：
- 被总结消息中的工具调用
- 上一次压缩或分支总结的 `details`（如果有）

这意味着文件跟踪会跨越多次上下文压缩或嵌套的分支总结不断累积，保留读取和修改过的文件的完整历史。

### BranchSummaryEntry 结构

定义于 [`session-manager.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/session-manager.ts)：

```typescript
interface BranchSummaryEntry<T = unknown> {
  type: "branch_summary";
  id: string;
  parentId: string;
  timestamp: number;
  summary: string;
  fromId: string;      // 导航出发时所在的条目
  fromHook?: boolean;  // 若由 extension 提供则为 true（历史遗留字段名）
  details?: T;         // 具体实现自定义的数据
}

// 默认的分支总结在 details 中使用如下结构（来自 branch-summarization.ts）：
interface BranchSummaryDetails {
  readFiles: string[];
  modifiedFiles: string[];
}
```

与上下文压缩相同，extension 可以在 `details` 中存储自定义数据。

实现细节参见 [`collectEntriesForBranchSummary()`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/branch-summarization.ts)、[`prepareBranchEntries()`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/branch-summarization.ts) 和 [`generateBranchSummary()`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/branch-summarization.ts)。

## 摘要格式

上下文压缩和分支总结使用相同的结构化格式：

```markdown
## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
- [Requirements mentioned by user]

## Progress
### Done
- [x] [Completed tasks]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues, if any]

## Key Decisions
- **[Decision]**: [Rationale]

## Next Steps
1. [What should happen next]

## Critical Context
- [Data needed to continue]

<read-files>
path/to/file1.ts
path/to/file2.ts
</read-files>

<modified-files>
path/to/changed.ts
</modified-files>
```

### 消息序列化

总结之前，消息会通过 [`serializeConversation()`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/compaction/utils.ts) 序列化为文本：

```
[User]: What they said
[Assistant thinking]: Internal reasoning
[Assistant]: Response text
[Assistant tool calls]: read(path="foo.ts"); edit(path="bar.ts", ...)
[Tool result]: Output from tool
```

这可以防止模型把它当作一段需要继续的对话来处理。

序列化时工具结果会被截断到 2000 个字符。超出该限制的内容会被替换成一个标记，指明有多少字符被截断。这能把总结请求控制在合理的 token 预算内，因为工具结果（尤其是来自 `read` 和 `bash` 的）通常是上下文体积的最大贡献者。

## 通过 Extension 自定义总结

Extension 可以拦截并自定义上下文压缩和分支总结。事件类型定义参见 [`extensions/types.ts`](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/src/core/extensions/types.ts)。

### session_before_compact

在自动上下文压缩或 `/compact` 之前触发。可以取消，也可以提供自定义摘要。参见类型文件中的 `SessionBeforeCompactEvent` 和 `CompactionPreparation`。

```typescript
pi.on("session_before_compact", async (event, ctx) => {
  const { preparation, branchEntries, customInstructions, reason, willRetry, signal } = event;

  // preparation.messagesToSummarize - 待总结的消息
  // preparation.turnPrefixMessages - 拆分轮次的前缀（当 isSplitTurn 时）
  // preparation.previousSummary - 上一次的压缩摘要
  // preparation.fileOps - 提取出的文件操作
  // preparation.tokensBefore - 压缩前的上下文 token 数
  // preparation.firstKeptEntryId - 保留消息的起始位置
  // preparation.settings - 上下文压缩设置

  // branchEntries - 当前分支上的所有条目（用于自定义状态）
  // reason - "manual"（/compact）、"threshold" 或 "overflow"
  // willRetry - 被中止的轮次是否会在压缩后重试（溢出恢复）
  // signal - AbortSignal（传给 LLM 调用）

  // 取消：
  return { cancel: true };

  // 自定义摘要：
  return {
    compaction: {
      summary: "Your summary...",
      firstKeptEntryId: preparation.firstKeptEntryId,
      tokensBefore: preparation.tokensBefore,
      details: { /* 自定义数据 */ },
    }
  };
});
```

#### 把消息转换为文本

如果想用你自己的模型生成摘要，可以用 `serializeConversation` 把消息转换为文本：

```typescript
import { convertToLlm, serializeConversation } from "@earendil-works/pi-coding-agent";

pi.on("session_before_compact", async (event, ctx) => {
  const { preparation } = event;

  // 先把 AgentMessage[] 转换为 Message[]，再序列化为文本
  const conversationText = serializeConversation(
    convertToLlm(preparation.messagesToSummarize)
  );
  // 返回：
  // [User]: message text
  // [Assistant thinking]: thinking content
  // [Assistant]: response text
  // [Assistant tool calls]: read(path="..."); bash(command="...")
  // [Tool result]: output text

  // 然后发送给你的模型进行总结
  const summary = await myModel.summarize(conversationText);

  return {
    compaction: {
      summary,
      firstKeptEntryId: preparation.firstKeptEntryId,
      tokensBefore: preparation.tokensBefore,
    }
  };
});
```

使用另一个模型的完整示例见 [custom-compaction.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/custom-compaction.ts)。

### session_before_tree

在 `/tree` 导航之前触发。无论用户是否选择生成总结都会触发。可以取消导航，也可以提供自定义摘要。

```typescript
pi.on("session_before_tree", async (event, ctx) => {
  const { preparation, signal } = event;

  // preparation.targetId - 导航的目标位置
  // preparation.oldLeafId - 当前位置（即将被离开）
  // preparation.commonAncestorId - 共同祖先
  // preparation.entriesToSummarize - 将被总结的条目
  // preparation.userWantsSummary - 用户是否选择生成总结

  // 完全取消导航：
  return { cancel: true };

  // 提供自定义摘要（仅当 userWantsSummary 为 true 时才会被使用）：
  if (preparation.userWantsSummary) {
    return {
      summary: {
        summary: "Your summary...",
        details: { /* 自定义数据 */ },
      }
    };
  }
});
```

参见类型文件中的 `SessionBeforeTreeEvent` 和 `TreePreparation`。

## 设置

在 `~/.pi/agent/settings.json` 或 `<project-dir>/.pi/settings.json` 中配置上下文压缩：

```json
{
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  }
}
```

| 设置项 | 默认值 | 说明 |
|---------|---------|-------------|
| `enabled` | `true` | 启用自动上下文压缩 |
| `reserveTokens` | `16384` | 为 LLM 响应预留的 token 数 |
| `keepRecentTokens` | `20000` | 保留（不总结）的近期 token 数 |

将 `"enabled"` 设为 `false` 可禁用自动上下文压缩。此时你仍可以用 `/compact` 手动压缩。
