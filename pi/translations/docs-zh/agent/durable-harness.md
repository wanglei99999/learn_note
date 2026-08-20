> **译文** | 原文：[`packages/agent/docs/durable-harness.md`](https://github.com/earendil-works/pi/blob/main/packages/agent/docs/durable-harness.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 持久化 AgentHarness 与 session 设计

<!-- 从 jot zmnps2zu 同步而来。今后请在仓库内编辑本文件。 -->

持久化 AgentHarness / session 设计笔记。

## 问题界定

单靠自身实现一个完全持久化的 `AgentHarness` 并不现实，因为重要的依赖是由宿主应用提供的运行时 JS：

- 工具实现
- 模型/认证 provider
- extension 与 hook 处理器
- 资源加载器
- 系统提示词回调/修改器

工具注册表是运行时依赖。harness 应当持久化可序列化的工具配置（如激活的工具名），但不持久化具体的工具实现。

务实的目标是半持久化的 harness：

- session 是持久化的、只追加的状态树
- harness 将自己拥有的状态持久化为 session 条目
- 宿主应用负责在恢复时重建兼容的、不可持久化的依赖
- 恢复从持久化边界重新开始，而不是从进行中的 provider 流

## session 拥有持久化状态

把 session 视为全部持久化的 agent 状态，而不仅仅是转录历史。

现有的 session 状态已经包含 harness 状态：

- 模型变更
- 思考等级变更
- 激活工具变更
- 叶子（leaf）条目
- 标签
- 上下文压缩与分支摘要
- 自定义消息与自定义条目

这表明应继续使用单一的持久化 session 日志，而不是为 harness 添加附属存储（sidecar）。附属存储对大型二进制数据可能仍有用，但 session 条目应保持为权威来源的引用。

## 应用在恢复时必须提供什么

应用必须重建兼容的运行时依赖：

- 模型注册表 / 模型对象
- 工具注册表
- extension 集合、版本与顺序
- 资源加载器
- 系统提示词 provider/hook
- 认证 provider
- 应用特有的 hook

在可用时，harness 可以校验稳定的 ID/版本/哈希，但它无法自行序列化这些依赖。

## 运行时配置与恢复

构造函数选项保持为显式的运行时配置，不读取 session 状态。在构造函数中隐藏异步恢复会使失败处理变得含糊。

未来的异步 builder/工厂应负责持久化恢复：

```ts
const harness = await AgentHarness.builder()
  .env(env)
  .session(session)
  .model(defaultModel)
  .tools(runtimeTools)
  .defaultActiveTools(["read", "edit"])
  .restore({ missingActiveTools: "fail" });
```

`restore()` 应读取活动分支、归约持久化的 harness 配置、为缺失条目应用默认值、对照应用提供的运行时依赖进行校验、构造 harness，并可选地在构造后发出 `source: "restore"` 更新事件。

对于激活工具：

- `active_tools_change` 条目是分支作用域的持久化配置。
- 如果分支上不存在 `active_tools_change`，恢复使用 builder 默认值；如果没有提供默认激活名，则使用全部已注册工具。
- 激活工具名必须唯一。
- 工具注册表中的名字必须唯一。
- 恢复出的激活工具名如有缺失，默认应使恢复失败；宽容的丢弃/禁用策略之后可以显式添加。
- 具体工具永远不会从 session 恢复；宿主应用必须提供兼容的工具。

## harness 应持久化什么

最低限度有用的持久化条目：

- 分支作用域的激活工具名
- 排队的 steer/followUp/nextTurn 消息
- 与某个回合绑定的队列消费记录
- 活动操作期间接受的待处理 session 写入
- 待写入的应用状态
- 操作的开始/结束/中断
- 回合的开始/结束
- provider 请求的开始/结束（如果恢复诊断需要）
- 工具调用的开始/结束（如果我们想要安全的工具恢复）

可能的条目：

```ts
type DurableHarnessEntry =
  | QueueEnqueuedEntry
  | QueueConsumedEntry
  | PendingWriteEnqueuedEntry
  | PendingWriteAppliedEntry
  | OperationStartedEntry
  | OperationFinishedEntry
  | OperationInterruptedEntry
  | TurnStartedEntry
  | TurnFinishedEntry
  | ProviderRequestStartedEntry
  | ProviderRequestFinishedEntry
  | ToolCallStartedEntry
  | ToolCallFinishedEntry;
```

每个被接受的变更都必须在公开 API resolve 之前完成持久化。

## 恢复模型

启动时：

1. 宿主应用注册工具/模型/extension/资源/认证/hook。
2. harness 打开 session。
3. harness 将 session 条目归约为：
   - 当前叶子
   - 会话分支
   - harness 配置，包括激活的工具名
   - 队列
   - 待写入
   - 活动的操作/回合/工具状态
4. harness 校验所需的运行时依赖，包括对照应用提供的工具注册表校验恢复出的激活工具名。
5. harness 调和（reconcile）未完成的操作状态。

provider 流不可恢复。恢复只能从持久化边界重试，或将操作标记为已中断。

## 恢复策略

默认的保守策略：

- 未完成的 agent 回合：标记为中断，保留持久化的队列/待写入，返回空闲
- 未完成的 provider 请求：标记为中断；不自动重试
- 未完成的工具调用：追加中断/错误的工具结果；仅当工具声明可安全重试/幂等时才重试
- 未完成的上下文压缩：如果不存在压缩条目则重新运行
- 未完成的分支摘要/树导航：在安全的情况下重新运行/补上缺失的摘要或叶子条目

可选策略：

```ts
recovery: "mark_interrupted" | "retry_unfinished"
```

`retry_unfinished` 必须对非幂等的工具调用加以防护。

## 关键场景

### 队列

- `queue_enqueued` 之前崩溃：消息未被接受。
- `queue_enqueued` 之后崩溃：消息会被恢复。
- 队列排空之后、持久化的回合记录之前崩溃：有丢失/重复的风险。
- 必需的不变量：已消费的队列 ID 必须先记录在 `turn_started` 或等价条目中，才能视为已消费。

### 待写入

- `pending_write_enqueued` 之前崩溃：写入未被接受。
- 入队之后、应用之前崩溃：恢复时会应用它。
- 应用之后、已应用标记之前崩溃：确定性的目标条目 ID 让恢复能够检测到该条目已存在，并将其标记为已应用。

### agent 循环回合

- provider 请求之前崩溃：重试或标记为中断。
- provider 请求进行中崩溃：默认标记为中断。
- provider 响应之后、助手消息持久化之前崩溃：除非 provider 结果已被记入日志（journal），否则响应丢失。
- 助手消息持久化之后崩溃：从持久化的消息恢复。

### 工具调用

- 工具调用开始之后、结果产生之前崩溃：外部副作用可能已经发生。
- 默认恢复不应重新运行非幂等的工具。
- 工具调用需要稳定的 ID 和可安全重试的元数据才能自动恢复。

### 上下文压缩

- 摘要生成之前崩溃：重新运行准备/摘要。
- 摘要已生成、压缩条目写入之前崩溃：除非摘要已记入日志，否则重新运行。
- 压缩条目写入之后崩溃：操作已完成；如缺失则追加结束标记。

### 分支摘要 / 树导航

- 摘要之前崩溃：重新运行或标记为中断。
- 摘要条目之后、叶子条目之前崩溃：追加缺失的叶子条目。
- 叶子条目之后崩溃：操作已完成；如缺失则追加结束标记。

## 最小可行探索（spike）

1. 添加持久化的队列条目。
2. 添加带确定性目标 ID 的持久化待写入条目。
3. 添加操作开始/结束/中断条目。
4. 添加带已消费队列 ID 的回合开始条目。
5. 通过归约 session 日志进行恢复。
6. 默认将未完成的 agent 回合标记为中断。
7. 仅在不存在最终条目时重新运行未完成的压缩/树操作。
8. 除非工具元数据声明可安全重试，否则不重试未完成的工具调用。

## 未决问题

- 剩余的 harness 配置条目中，哪些应最先移入 session：资源、流选项、系统提示词引用？
- 是否应按回合快照已解析的系统提示词文本，用于审计/调试？
- 恢复时是否要求严格的依赖 ID/版本匹配？
- 应记入日志多少 provider 请求数据？
- 恢复时是追加用户可见的助手中断消息，还是仅追加内部操作条目？
- 存储是否应支持在恢复时截断最后一行不完整的 JSONL？
