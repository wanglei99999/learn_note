> **译文** | 原文：[`packages/agent/docs/telemetry-schema.md`](https://github.com/earendil-works/pi/blob/main/packages/agent/docs/telemetry-schema.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# Pi Agent Telemetry Schema

<!-- 由 generate-telemetry-docs.ts 生成。请勿手动编辑。 -->

## AI 请求 schema

Schema 版本：1

### `pi.ai.request`

对 AI provider 的一次逻辑请求

- Parent：根 span 或任意调用方 span
- 默认状态：`ok`
- 错误条件：操作抛出异常或返回错误结果

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.ai.operation` | `string` | 是 | stream, fetch_deferred, cancel_deferred, generate_images |  | 逻辑 provider 操作 |
| `pi.ai.provider` | `string` | 是 |  |  | 选定的 provider ID |
| `pi.ai.model` | `string` | 是 |  |  | 请求的模型 ID |
| `pi.ai.api` | `string` | 是 |  |  | Provider API ID |
| `pi.ai.streaming` | `boolean` | 是 |  |  | 该操作是否返回 stream |
| `pi.ai.deferred` | `boolean` | 否 |  |  | 该操作是否请求或参与延迟执行 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.ai.response.model` | `string` |  |  | 实际响应模型 |
| `pi.ai.response.id` | `string` |  | 高基数 | Provider 响应 ID |
| `pi.ai.response.stop_reason` | `string` | stop, length, tool_use, error, aborted, deferred |  | 规范化的终止响应原因 |
| `pi.ai.http.status_code` | `number` |  |  | 最终 HTTP 状态码 |
| `pi.ai.usage.input_tokens` | `number` |  |  | 报告的输入 token 数 |
| `pi.ai.usage.output_tokens` | `number` |  |  | 报告的输出 token 数 |
| `pi.ai.usage.cache_read_tokens` | `number` |  |  | 报告的缓存读取 token 数 |
| `pi.ai.usage.cache_write_tokens` | `number` |  |  | 报告的缓存写入 token 数 |
| `pi.ai.usage.reasoning_tokens` | `number` |  |  | 报告的推理 token 数 |
| `pi.ai.usage.total_tokens` | `number` |  |  | 报告的总 token 数 |
| `pi.ai.usage.cost` | `number` |  |  | 报告的总费用 |
| `pi.ai.stream.chunk_count` | `number` |  |  | 流式更新的数据块数量 |
| `pi.ai.stream.time_to_first_chunk_ms` | `number` |  |  | 距离第一个更新数据块的耗时，单位毫秒 |
| `pi.ai.error.type` | `string` |  | 低基数 | Provider 或 transport 错误类别 |

#### Event

未声明 span event。

## Harness schema

Schema 版本：1

### `pi.harness.run`

一次获准进入的进程内 run 调用

- Parent：根 span 或调用方拥有的外部 span
- 默认状态：`ok`
- 错误条件：run 失败或抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.session.id` | `string` | 是 |  | 高基数 | Session ID |
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.operation.recovery` | `boolean` | 是 |  |  | 该调用是否恢复持久化工作 |
| `pi.operation.kind` | `string` | 是 | run |  | Run operation 类型 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.operation.outcome` | `string` | completed, aborted, failed, suspended |  | Run 调用结果 |
| `pi.error.code` | `string` |  | 低基数 | 稳定的 operation 错误码 |
| `pi.error.type` | `string` |  | 低基数 | 低基数的 operation 错误类别 |

#### Event

未声明 span event。

### `pi.harness.compaction`

一次获准进入的进程内手动上下文压缩调用

- Parent：根 span 或调用方拥有的外部 span
- 默认状态：`ok`
- 错误条件：上下文压缩失败或抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.session.id` | `string` | 是 |  | 高基数 | Session ID |
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.operation.recovery` | `boolean` | 是 |  |  | 该调用是否恢复持久化工作 |
| `pi.operation.kind` | `string` | 是 | compaction |  | 上下文压缩 operation 类型 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.operation.outcome` | `string` | completed, declined, aborted, failed |  | 上下文压缩调用结果 |
| `pi.error.code` | `string` |  | 低基数 | 稳定的 operation 错误码 |
| `pi.error.type` | `string` |  | 低基数 | 低基数的 operation 错误类别 |

#### Event

未声明 span event。

### `pi.harness.navigation`

一次获准进入的进程内 navigation 调用

- Parent：根 span 或调用方拥有的外部 span
- 默认状态：`ok`
- 错误条件：navigation 失败或抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.session.id` | `string` | 是 |  | 高基数 | Session ID |
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.operation.recovery` | `boolean` | 是 |  |  | 该调用是否恢复持久化工作 |
| `pi.operation.kind` | `string` | 是 | navigation |  | Navigation operation 类型 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.operation.outcome` | `string` | completed, declined, aborted, failed |  | Navigation 调用结果 |
| `pi.error.code` | `string` |  | 低基数 | 稳定的 operation 错误码 |
| `pi.error.type` | `string` |  | 低基数 | 低基数的 operation 错误类别 |

#### Event

未声明 span event。

### `pi.harness.checkpoint`

一个 run checkpoint

- Parent：`pi.harness.run`
- 默认状态：`ok`
- 错误条件：checkpoint 工作抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.checkpoint.kind` | `string` | 是 | normal, failure_drain, abort_reconcile |  | Checkpoint 用途 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| _无_ | | | | |

#### Event

未声明 span event。

### `pi.harness.turn`

一次助手响应及其工具批次

- Parent：`pi.harness.run`
- 默认状态：`ok`
- 错误条件：turn 工作抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.turn.id` | `string` | 是 |  | 高基数 | 调用内局部 turn ID |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| _无_ | | | | |

#### Event

未声明 span event。

### `pi.harness.step`

一次持久化重试 attempt

- Parent：`pi.harness.turn`、`pi.harness.checkpoint`、`pi.harness.compaction`、`pi.harness.navigation`
- 默认状态：`ok`
- 错误条件：attempt 发生重试、失败或抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.step.kind` | `string` | 是 | assistant, compaction, branch_summary |  | 可重试 step 类型 |
| `pi.step.attempt` | `number` | 是 |  |  | 从一开始计数的持久化 attempt 编号 |
| `pi.compaction.reason` | `string` | 否 | manual, threshold, overflow |  | 上下文压缩触发原因 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.step.outcome` | `string` | succeeded, retry, failed, aborted, deferred, overflow |  | Attempt 结果 |

#### Event

未声明 span event。

### `pi.harness.tool`

一次原始 phase-2 工具执行

- Parent：`pi.harness.turn`、`pi.harness.run`
- 默认状态：`ok`
- 错误条件：原始 phase-2 执行返回错误

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.turn.id` | `string` | 否 |  | 高基数 | 调用内局部 live turn ID |
| `pi.tool.name` | `string` | 是 |  |  | 工具名称 |
| `pi.tool.call_id` | `string` | 是 |  | 高基数 | 工具调用 ID |
| `pi.tool.replay` | `string` | 是 | never, safe |  | 声明的 replay 策略 |
| `pi.tool.recovery` | `boolean` | 是 |  |  | 是否为恢复执行 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.tool.is_error` | `boolean` |  |  | 原始 phase-2 执行是否返回错误 |

#### Event

未声明 span event。

### `pi.harness.hook`

一次已注册 hook handler 调用

- Parent：根 span 或任意调用方 span
- 默认状态：`ok`
- 错误条件：handler 抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 否 |  | 高基数 | 获准进入后的持久化 operation ID |
| `pi.hook.name` | `string` | 是 | before_run, before_resume, before_run_end, transform_context, before_request, before_payload, after_response, before_tool, after_tool, before_compaction, before_navigation |  | Hook 名称 |
| `pi.hook.registration_id` | `string` | 否 |  |  | 稳定的 hook 注册 ID |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.hook.outcome` | `string` | completed, skipped, blocked, failed |  | Handler 结果 |

#### Event

未声明 span event。

### `pi.harness.sleep`

一次重试延迟

- Parent：`pi.harness.step`、`pi.harness.run`
- 默认状态：`ok`
- 错误条件：sleep 工作抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.operation.id` | `string` | 是 |  | 高基数 | 持久化 operation ID |
| `pi.sleep.delay_ms` | `number` | 是 |  |  | 请求的延迟毫秒数 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.sleep.outcome` | `string` | elapsed, aborted |  | 延迟结果 |

#### Event

未声明 span event。

### `pi.harness.event_handler`

一次被动 event listener 调用

- Parent：根 span 或任意调用方 span
- 默认状态：`ok`
- 错误条件：listener 抛出异常

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.event.type` | `string` | 是 | run_start, run_resume, run_suspend, run_abort, run_end, fault, handler_error, turn_start, turn_end, retry_scheduled, retry_start, retry_end, message_start, message_update, message_end, tool_start, tool_update, tool_end, entry_added, write_pending, queue_update, fact_update, config_update, compaction_start, compaction_end, navigation_start, navigation_end, lane_created, usage | 低基数 | 投递的 harness event 类型 |
| `pi.lane.name` | `string` | 否 |  | 高基数 | Lane 作用域 event 的 lane 名称 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| _无_ | | | | |

#### Event

未声明 span event。

### `pi.session.write`

一次已提交的 session 变更

- Parent：根 span 或任意调用方 span
- 默认状态：`ok`
- 错误条件：storage 拒绝变更

#### 开始属性

| 名称 | 类型 | 必填 | 可选值 | 备注 | 描述 |
|---|---|---:|---|---|---|
| `pi.lane.name` | `string` | 是 |  | 高基数 | Lane 名称 |
| `pi.operation.id` | `string` | 否 |  | 高基数 | 获准进入后的持久化 operation ID |
| `pi.session.mutation` | `string` | 是 | entry, record, lane, fact |  | Session 变更类型 |
| `pi.session.item_type` | `string` | 否 |  |  | Entry、record、lane 或 fact 子类型 |

#### 结束属性

所有结束属性都是可选的完成阶段补充信息。

| 名称 | 类型 | 可选值 | 备注 | 描述 |
|---|---|---|---|---|
| `pi.session.seq` | `number` |  |  | 暴露时的已提交 session sequence |

#### Event

未声明 span event。
