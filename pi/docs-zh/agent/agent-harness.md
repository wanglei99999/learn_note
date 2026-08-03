> **译文** | 原文：[`packages/agent/docs/agent-harness.md`](https://github.com/earendil-works/pi/blob/main/packages/agent/docs/agent-harness.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# AgentHarness 生命周期

`AgentHarness` 是位于底层 agent 循环之上的编排层。它负责 session（会话）持久化、运行时配置、资源解析、操作锁定，以及面向 extension（扩展）的变更语义。

本文档描述当前的方向与已实现的行为。部分 extension/session 门面（facade）细节尚在规划中，文中会明确指出。

## 最终生命周期目标

harness 的监听器与 hook 应当能够闭包捕获 `AgentHarness` 实例，并在任何文档声明允许的事件中调用公开的 harness API。这些调用不得破坏进行中的回合快照、不得打乱已持久化的转录条目顺序、不得丢失待写入数据、不得使结算（settlement）死锁，也不得让 harness 停留在错误的阶段。

预期的规则是：

- 结构性操作在忙碌期间仍被拒绝
- 队列操作在文档声明的回合安全点被接受
- 运行时配置 setter 更新未来的快照，而不修改当前的 provider 请求
- 忙碌期间发起的 session 写入会被持久化排队，并按确定性顺序刷出
- getter 返回最新的 harness 配置，而不是进行中的快照
- 监听器/hook 目前没有门面可用；如果它们闭包捕获原始 harness，并在活动运行期间调用 `waitForIdle()` 之类的结算 API，可能会死锁。未来的门面应改为暴露 `runWhenIdle()`。

`AssistantMessageStream` 已经将 provider 传输层的 streaming（如 SSE 或 websocket 读取）与下游事件消费解耦。因此 harness 可以等待（await）监听器、extension hook、持久化和保存点工作，而不会阻塞 provider 传输读取器，也不会重新引入临时的事件队列。生命周期代码在 harness 边界处应优先采用显式的、逐一 await 的顺序执行，而不是「发出即忘」的 hook/事件结算方式。

最终的生命周期加固工作应通过一套覆盖广泛的监听器/hook 重入测试套件来证明这些保证。

## 错误处理

当前的划分方式是：

- 底层能力和辅助函数使用 `Result<TValue, TError>`，预期内的失败被包含在结果中且不得抛出异常，例如 `ExecutionEnv`、文件系统/shell 操作、shell 输出捕获、资源加载和上下文压缩辅助函数
- 高层变更/编排 API（如 `Session` 与 `AgentHarness`）采用 reject/throw，而不是返回可能被忽略的裸结果
- 公开的 `AgentHarness` 失败在可行的情况下统一规范化为 `AgentHarnessError`；子系统错误保留为 `cause`

harness 事件观察的是已提交的状态。公开的变更方法在可行时会先校验必需输入并完成持久化再提交，然后 await 通知。如果 hook 或订阅者在提交后失败，状态变更不会回滚，公开方法以 code 为 `"hook"` 的 `AgentHarnessError` reject。

## 状态模型

harness 将状态分为四类。

### harness 配置

harness 配置是应用或 extension 设置的最新运行时配置：

- 模型
- 思考等级（thinking level）
- 工具
- 激活的工具名
- 资源
- 流选项（stream options）
- 系统提示词或系统提示词 provider

getter 返回 harness 配置。它们不返回进行中的 provider 请求所用的快照。

setter 立即更新 harness 配置，包括回合进行期间。变更影响下一个回合快照，而不是当前正在运行的 provider 请求。

`setResources()` 接受具体的资源，并在每次调用时发出 `resources_update` 事件，携带浅拷贝的当前与之前的资源。资源从磁盘或其它来源的加载/重新加载由应用负责，应用应以新值调用 `setResources()`。

`getResources()` 返回浅拷贝的当前资源。它是对实时配置的读取，而不是上一个回合快照。

### 回合快照

回合快照是一次 LLM 回合所使用的具体状态。它由 `createTurnState()` 创建，包含：

- 已持久化的 session 消息
- 已解析的资源
- 已解析的系统提示词
- 模型
- 思考等级
- 全部工具
- 激活的工具
- 流选项
- 派生的 session id

静态选项值被直接使用。系统提示词 provider 回调在每次 `createTurnState()` 调用时被调用一次。该回合的所有逻辑都使用同一个快照。

快照创建时会浅拷贝资源数组。单个 skill 与提示词模板对象不做深拷贝。

快照创建时会浅拷贝流选项。`headers` 与 `metadata` 映射会被浅拷贝；其值不做深拷贝。来自 `getApiKeyAndHeaders()` 的凭据按每次 provider 请求解析，以便会过期的 token 能够刷新，但配置的流选项与派生的 session id 来自当前的回合快照。

### session

session 仅包含已持久化的条目。session 读取返回已持久化的状态，不包含排队中的写入。

`Session.buildContextEntries()` 返回用于构建模型上下文的、感知上下文压缩的条目序列。`Session.buildContext()` 从完整的活动分支派生运行时状态，然后将这些上下文条目投影为 `AgentMessage[]`。自定义条目默认不进入模型上下文；应用可以向 `Session` 构造函数或 `buildContext()` 传入 `entryProjectors`，将选定的自定义条目投影为消息。应用还可以传入可叠加的 `entryTransforms`，它们在默认的上下文压缩变换之后运行，用于在投影前过滤或重排上下文条目。

session 存储实现必须将叶子（leaf）变更持久化为 `leaf` 条目。`setLeafId()` 不是仅在内存中更新游标；它会追加一条持久化条目，其 `targetId` 为活动树的叶子，根节点则为 `null`。重新打开存储时必须从最新持久化的影响叶子的条目重建当前叶子。

### 待处理的 session 写入

操作进行期间发起的 session 写入会作为待处理的 session 写入排队。待写入基于不含生成字段（`id`、`parentId`、`timestamp`）的 session 条目形状。

待处理的 session 写入总会被持久化。它们在保存点、操作结算时以及失败清理时被刷出。

公开的待写入/session 门面 API 已在规划中，但尚未实现。

## 操作阶段

harness 有一个显式的阶段（phase）：

```ts
type AgentHarnessPhase = "idle" | "turn" | "compaction" | "branch_summary" | "retry";
```

结构性操作要求 `phase === "idle"`，并在第一个 `await` 之前同步设置阶段：

- `prompt`
- `skill`
- `promptFromTemplate`
- `compact`
- `navigateTree`

在 harness 非空闲时启动另一个结构性操作，会以 code 为 `"busy"` 的 `AgentHarnessError` reject。

以下操作在回合期间的适当时机是允许的：

- `steer`
- `followUp`
- `nextTurn`
- `abort`
- 运行时配置 setter

阶段/结算语义仍是临时性的，需要一次完整的生命周期梳理。

## 回合执行

`prompt`、`skill` 与 `promptFromTemplate` 遵循相同的流程：

1. 断言空闲并将阶段设置为 `"turn"`。
2. 用 `createTurnState()` 创建回合快照。
3. 从该快照派生调用文本。
4. 用 `executeTurn()` 执行该回合。

`skill` 与 `promptFromTemplate` 从传给该回合的同一个快照中解析其资源。它们不会单独解析资源。

`steer`、`followUp` 与 `nextTurn` 接受文本加可选图片，并在内部创建用户消息。`nextTurn` 的消息会在下一个由用户发起的回合中，插入到新的用户消息之前。

队列模式是实时的，不进入回合快照：

- `getSteeringMode()` / `setSteeringMode()`
- `getFollowUpMode()` / `setFollowUpMode()`

运行期间更改队列模式会影响下一次队列排空。队列排空发生在安全点。

## 保存点

保存点出现在一个助手回合及其工具结果消息完成之后。

在保存点，harness 会：

1. 在该回合由 agent 发出的消息之后，刷出待处理的 session 写入
2. 如果底层循环可能继续，则创建一个新的回合快照
3. 在下一次 provider 请求之前，应用新的上下文/模型/思考等级/流选项/session id 状态

这使得回合期间做出的模型、思考等级、工具、资源、流选项和系统提示词变更能够影响同一次运行中的下一个回合，同时永远不会修改进行中的 provider 请求。由于 provider 传输读取已被 `AssistantMessageStream` 解耦，保存点工作与 hook 结算可以被直接 await，以保持转录/session 顺序的确定性。循环回调不会在保存点被重新创建。

底层循环在 provider 边界将 harness 的 `ThinkingLevel` 转换为 provider 的 `reasoning`：

- `"off"` -> `undefined`
- 其它所有思考等级原样透传

`agent_end` 时不需要刷新状态，只需刷出遗留的待处理 session 写入并清除操作阶段。确切的 `settled` 事件时机仍在审查中。

如果系统提示词回调在启动 `prompt`、`skill` 或 `promptFromTemplate` 时抛出异常，该操作以 `AgentHarnessError` reject，harness 回到空闲状态。如果它是在 `prepareNextTurn` 创建的保存点快照中抛出，底层 agent 运行会记录一条助手错误消息。

## hook 与事件

目标 hook 系统在 [hooks.md](./hooks.md) 中描述。

概要：

- `AgentHarness` 发出带类型的 hook 事件并消费带类型的结果。
- 由单一的 hooks 实现负责注册、清理、来源（provenance）和结果归约器（reducer）。
- 观察型与变更型 hook 使用同一个按事件区分的 `on()` API；事件的结果类型决定处理器是否可以返回结果。
- 产生结果的事件由带类型的归约器表归约；应用特有的 hook 只为应用特有的产生结果的事件添加归约器。
- hook 注册的来源信息是注册上的附属（sidecar）元数据。资源与工具的来源信息属于应用特有的具体值类型。
- hook 上下文应是一个由门面组成的普通对象，而不是原始内部结构或层层延迟绑定的 getter 迷宫。

事件负载描述正在发生的事情。harness 的 getter 描述用于未来快照的最新配置。hook 与监听器的结算应尽可能按生命周期顺序 await；传输层背压由 harness 之下的 `AssistantMessageStream` 处理，因此 harness 不需要仅仅为了维持 SSE 或 websocket 读取流动而设置单独的异步事件队列。

## 规划中的 session 门面

extension 最终应通过一个 harness 作用域的 `HarnessSession` 门面与 session 交互，而不是直接操作原始 session。该门面应包装内部 session，并强制执行 harness 的待写入排序语义。一旦它存在，hook 与事件监听器就可以收到一个上下文，暴露完整的 `AgentHarness` 加 session 门面，而不给予对无序原始 session 写入的直接访问。

规划中的读语义：

- 读取委托给已持久化的 session 状态
- 读取不包含排队中的待写入

规划中的写语义：

- 空闲时：立即持久化
- 忙碌时：作为待处理的 session 写入排队

规划中的诊断 API 可能会显式暴露待写入：

```ts
getPendingWrites(): readonly PendingSessionWrite[]
```

agent 发出的消息在 `message_end` 时持久化，以保持转录顺序。extension/session 的待写入在保存点、在这些消息之后刷出。

## 中止（abort）

回合期间允许中止。中止会终止底层运行并清空 steering/后续消息队列。

中止不会清除 `nextTurn` 消息。用 `nextTurn()` 排队的消息在中止后依然保留，并在下一个由用户发起的回合中插入到用户消息之前。

中止不会丢弃待处理的 session 写入。待写入会在下一个到达的保存点、在 `agent_end` 时、或在操作失败清理时刷出。

中止的屏障（barrier）语义仍需审计。

## 上下文压缩与树导航

上下文压缩和树导航是结构性的 session 变更。

它们仅在空闲时被允许且不会排队。它们作用于已持久化的 session 状态。下一次 prompt 会创建一个新的回合快照。

分支摘要的生成是树导航操作的一部分。

自动上下文压缩与重试决策点尚未在 `AgentHarness` 中实现。

## 测试组织

harness 测试应按领域保持聚焦，而不是膨胀为一个巨大的大杂烩文件。

当前结构：

- `packages/agent/test/harness/agent-harness.test.ts`：核心生命周期与公开 API 行为。
- `packages/agent/test/harness/agent-harness-stream.test.ts`：流选项与 provider hook 语义。

期望的未来结构：

- `agent-harness-resources.test.ts`：资源快照/加载语义。
- `agent-harness-tools.test.ts`：工具注册表 getter、激活工具语义和更新事件。
- `agent-harness-lifecycle.test.ts`：阶段/保存点/settled/重入行为。

请使用 `pi-ai` 的 faux provider（`registerFauxProvider`、`fauxAssistantMessage`）进行确定性的 harness/provider 测试。faux 响应工厂可以检查 `StreamOptions`、调用 `options.onPayload`，并返回预先编排的助手消息，而无需真实的 provider API 或网络访问。

harness 覆盖率与默认的包测试运行是分开配置的：

```bash
npm run test:harness
npm run coverage:harness
```

`coverage:harness` 运行 `test/harness/**/*.test.ts`，并将 `src/harness/**/*.ts` 加上它直接触及的非 harness 运行时文件（`src/agent.ts` 与 `src/agent-loop.ts`）的覆盖率报告输出到 `coverage/harness`。仅类型的依赖（如 `src/types.ts`）不包含在内，因为它们没有有意义的运行时覆盖率。

## 实现待办

此列表跟踪在将 `AgentHarness` 视为可迁移之前剩余的工作。活动/规划中的条目按从易到难排序。已完成条目归档在底部。

### 1. 添加显式的工具注册表读取/更新语义

状态：进行中

已完成：

- 添加了 `setTools(tools, activeToolNames?)`。
- 添加了 `setActiveTools(toolNames)`。
- 无效的激活工具名以 `AgentHarnessError` reject。
- 通过 `AgentHarness<TSkill, TPromptTemplate, TTool>` 添加了泛型的应用工具形状。
- 从核心类型导出了 `QueueMode`。
- 添加了 `AgentHarnessOptions.steeringMode` 与 `followUpMode`。
- 添加了实时的 `getSteeringMode()` / `setSteeringMode()` 与 `getFollowUpMode()` / `setFollowUpMode()`。
- 添加了 `getTools()` 与 `getActiveTools()`。
- 添加了 `tools_update` 可观测性事件，包括仅激活工具的更新。
- 激活工具变更被持久化为分支作用域的 `active_tools_change` 条目。
- 重复的工具名与重复的激活工具名会被 reject。

剩余：

- 无。

备注：

- 可观测性设计：[observability.md](./observability.md)

### 2. 设计按 `AgentHarness` 实例的模型注册表

状态：规划中

已完成：

- 保留了当前 `setModel()` 的行为。

剩余：

- 决定应用如何提供模型注册表。
- 决定 harness 存储具体的 `Model` 对象、模型引用，还是两者兼有。
- 根据注册表校验模型选择。
- 定义活动回合和保存点期间的模型变更语义。

### 3. 完整的 `AgentHarness` 生命周期/状态梳理

状态：进行中

已完成：

- 移除了构造函数中的 `void syncFromTree()`、`syncFromTree()`、`liveOperationId` 与 `shell()`。
- 添加了 `createTurnState()`、`applyTurnState()` 与 `executeTurn()`。
- 用显式的 `phase` 替代布尔型空闲状态。
- 保存点会刷新上下文、模型、思考等级、流选项和 session 快照状态。
- 待处理的 session 写入使用不含生成字段的 session 条目形状。
- 待处理的 session 写入在保存点、结算和失败清理时刷出。
- `steer`、`followUp` 与 `nextTurn` 从文本加可选图片创建用户消息。
- `nextTurn` 消息插入到新的用户 prompt 之前。
- 结构性的压缩/树操作用 `finally` 恢复阶段。
- 公开的 harness 失败将子系统原因规范化为 `AgentHarnessError`。
- 待处理的 session 写入逐条刷出，失败时不会被丢弃。
- 如果队列更新通知失败，队列排空会回滚。
- `message_end` 的持久化发生在订阅者通知之前。
- `abort()` 在通知之前先发出取消信号，并在通知出错时仍等待到空闲。
- 空闲时的模型/思考/工具更新在提交内存状态之前先校验并持久化。
- `setLeafId()` 持久化持久的 `leaf` 条目，使树导航在存储重新打开后依然有效。

剩余：

- 敲定阶段/空闲语义。
- 审计 `settled` 是否可能触发过早。
- 使 `settled` 回调内的 session 写入具有确定性。
- 审计 `agent_end` 前后的后续消息行为。
- 实现自动上下文压缩决策点。
- 实现重试处理。
- 对照 coding-agent 验证 `before_agent_start` hook 语义。
- 决定 `before_agent_start` 是否需要更多回合信息，如工具/工具片段。
- 记录或更改忙碌时运行时配置事件的时机。
- 审计 `abort()` 屏障语义。

### 4. 实现通用的 hook/事件 extension 机制

状态：已在 [hooks.md](./hooks.md) 中设计，尚未实现

已完成：

- 移除了 `AgentHarnessContext`。
- hook 只接收事件负载。
- `emitHook(event)` 从 `event.type` 推导 hook 类型。
- provider 请求/负载 hook 具有有序的变换语义。

剩余：

- 添加 `HookEvent`、`ResultOf`、带泛型来源元数据的注册选项，以及单一的 `AgentHarnessHooks` 实现。
- 将结果链式处理从 `AgentHarness` 移入归约器函数。
- 对基础 harness 归约器做类型检查，确保每个产生结果的 `AgentHarnessEvent` 都有归约器语义。
- 让 `AgentHarness` 接受并暴露具体的 hooks 实例，并通过构造函数推断支持应用特有的 hook。
- 定义通过 hook 上下文暴露的初始 harness/上下文门面。
- 保留当前的 provider hook 行为，包括流选项补丁的删除语义。
- 为归约器语义添加对等测试：变换链式处理、补丁链式处理、提前 block/cancel、清理、来源元数据，以及带类型的应用特有归约器覆盖。

备注：

- hook 设计：[hooks.md](./hooks.md)

### 5. 探索（spike）半持久化的 harness/session 恢复

状态：规划中

已完成：

- 撰写了持久化设计：[durable-harness.md](./durable-harness.md)

剩余：

- 决定是由 session 拥有全部持久化的 harness 状态，还是大型二进制数据需要附属存储（sidecar）。
- 为队列、待写入、操作、回合、provider 请求和工具调用定义持久化条目。
- 为应用提供的工具、模型、extension、资源、hook 和认证 provider 定义恢复要求。
- 为未完成的 agent 回合、provider 请求、工具调用、上下文压缩和树导航定义保守的恢复策略。
- 基于 session 条目原型验证基于归约器的恢复。
- 决定被中断的操作是追加用户可见的消息，还是仅追加内部操作条目。

备注：

- provider 流不可恢复；恢复应从持久化边界重新开始，或将操作标记为已中断。
- 未完成的工具调用不能安全重试，除非工具声明了幂等/可安全重试的行为。

### 6. 最终生命周期加固套件

状态：规划中

已完成：

- 无。

剩余：

- 跨相关事件添加覆盖广泛的监听器/hook 重入测试。
- 测试从底层生命周期事件和 harness 事件中调用运行时配置 setter。
- 测试模型、思考、资源、工具、激活工具和流选项的运行时配置可观测性。
- 测试活动回合和保存点期间的资源/工具/模型/思考/流选项更新。
- 测试来自监听器和 hook 的 session 写入，包括 `settled` 中的写入。
- 测试从回合事件、工具事件和 provider hook 发起的队列操作。
- 测试忙碌时被拒绝的结构性操作。
- 测试从监听器/hook 发起的中止。
- 测试活动操作期间的 getter 行为。
- 测试 agent 发出的消息与待处理监听器写入的确定性顺序。
- 测试异步监听器调用并 await harness API 时不发生死锁。
- 测试成功、provider 错误、hook 错误、中止、上下文压缩和树导航各路径下的阶段清理。

### 7. 后续的 coding-agent 迁移计划

状态：规划中

已完成：

- 无。

剩余：

- 将 coding-agent 的资源映射到带来源的加载器。
- 将应用层的资源去重/来源信息保持在 harness 之外。
- 使 extension 加载适配未来的 hook/session 门面。
- 将 UI/session 行为保持在核心之外。
- 将 coding-agent 的流/认证/重试/header 行为迁移到 harness 的流配置和 provider hook 上。

---

## 已完成的实现待办

### 8. 移除 `AgentHarness` 对 `Agent` 的依赖

状态：已完成

已完成：

- `AgentHarness` 直接调用 `runAgentLoop()`。
- harness 拥有运行生命周期、abort controller、队列排空、provider 流配置、事件归约、session 持久化、待写入刷出和保存点快照。
- harness 测试覆盖 prompt 构建、队列排空、中止行为、保存点刷新、待写入排序、awaited 监听器结算、工具 hook 和 provider 流包装。

剩余：

- 无。

备注：

- 更广泛的监听器/hook 重入覆盖在条目 6 中跟踪。

### 9. 完成精选的 provider/流配置

状态：已完成

已完成：

- 添加了精选的 `AgentHarnessOptions.streamOptions`、`getStreamOptions()` 与 `setStreamOptions()`。
- 流选项、headers、metadata 和派生的 session id 按回合快照。
- harness 拥有的流包装器调用 `streamSimple()`，并保留由生命周期拥有的、来自底层循环的 `signal` 与 `reasoning`。
- `getApiKeyAndHeaders()` 按每次 provider 请求解析凭据。
- 实现了 `before_provider_request`、`before_provider_payload` 与 `after_provider_response` hook。
- 流选项补丁支持显式字段删除和有序的 hook 链式处理。
- `agent-harness-stream.test.ts` 覆盖转发、认证合并、hook 补丁/删除/链式处理、负载 hook，以及忙碌/保存点快照行为。

剩余：

- 无。

### 10. 完成底层的 `Result` 清理

状态：已完成

已完成：

- 添加了泛型 `Result<TValue, TError>` 及辅助函数。
- 更新了 `ExecutionEnv` 与 `NodeExecutionEnv`，使文件系统/进程操作返回带类型的结果。
- 拆分了文件系统与 shell 能力。
- 将 JSONL session 存储/仓库迁移到文件系统能力选择（picks）上，而不是直接导入 Node 模块。
- 为流式追加用例添加了 `ExecutionEnv.appendFile()`。
- 更新了 skill 与提示词模板加载器以消费 `ExecutionEnv` 结果。
- 更新了 shell 输出捕获以返回结果并使用 `ExecutionEnv`，包括通过 `appendFile()` 溢写完整输出。
- 从浏览器安全的根导出中移除了 `NodeExecutionEnv`。
- 用运行时中立的 UTF-8 处理替换了通用截断工具中的 `Buffer` 用法。
- 将上下文压缩和分支摘要辅助函数改为带类型的结果返回。
- 添加了 `readTextLines()`，使 JSONL 元数据加载只读取头部行。
- 从取消没有意义的 Node 文件系统方法中移除了无操作的中止处理。
- 将跨越 session 边界的文件系统错误映射为带类型的 `SessionError`。
- 添加了带类型的分支摘要错误和感知 cause 的公开 harness 错误规范化。
- 资源加载器为非 `not_found` 的文件系统失败报告结构化诊断。
- 扩展了 `NodeExecutionEnv` 的测试，覆盖文件操作、exec 错误、中止、回调、超时和 shell 输出溢写。

剩余：

- 无。

备注：

- 底层能力/辅助 API 在返回 `Result` 时保持不抛出异常。
- session 存储/仓库/session API 保持抛出带类型的 `SessionError`。
- 公开的结构性 harness 失败保持规范化为 `AgentHarnessError`。
- Node 特有的 API 保持隔离在 `src/harness/env/nodejs.ts`、由 Node 支持的存储/session 实现，或显式的 Node 专用入口点中。
- 随着 API 增加，审计通用 harness 工具中的 Node 全局对象使用。
- 审计包导出，确保浏览器/通用导入不会引入 Node 专用模块。
- 随着 API 演进，持续扩展 `ExecutionEnv` 与 shell 输出契约测试。
