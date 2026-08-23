> **译文** | 原文：[`packages/telemetry/README.md`](https://github.com/earendil-works/pi/blob/main/packages/telemetry/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# @earendil-works/pi-telemetry

面向 pi 包、与供应商无关的 telemetry 契约和类型化 schema 工具。

该包提供：

- 显式、基于回调的 `TelemetryContext` / `TelemetrySpan` 契约；
- 共享的 `NOOP_TELEMETRY_CONTEXT`；
- 参考实现 `InMemoryTelemetryContext`；
- 可序列化的 schema 定义及由其推导的 TypeScript 类型；
- 不包含 exporter、全局 current-span 状态，也不依赖 telemetry 后端。

应用可以使用内存参考实现，也可以为 OpenTelemetry、Sentry、日志或其他后端提供 adapter。Pi 包显式传递 telemetry context，并分别定义自己的领域 schema。

## 目录

- [安装](#安装)
- [Telemetry 概念](#telemetry-概念)
- [核心 Context API](#核心-context-api)
- [Adapter 契约](#adapter-契约)
- [No-op Context](#no-op-context)
- [内存参考 Adapter](#内存参考-adapter)
- [Adapter 一致性](#adapter-一致性)
- [类型化 Schema](#类型化-schema)
  - [开始与完成属性](#开始与完成属性)
- [Schema 元信息](#schema-元信息)
- [Pi 包集成](#pi-包集成)
- [安全性与可移植性](#安全性与可移植性)
- [API 参考](#api-参考)
- [开发](#开发)
- [License](#license)

## 安装

```bash
npm install @earendil-works/pi-telemetry
```

## Telemetry 概念

Telemetry 描述程序运行期间做了什么。该包使用 span、attribute、event、status 和显式 context 对这些工作建模：

| 概念 | 通俗含义 |
|---|---|
| **Span** | 一次操作的计时记录，例如加载账号或发起 AI 请求。工作开始前创建，工作完成时结束。 |
| **父子 span** | 操作可以包含更小的操作。一个请求 span 可能包含缓存查询和数据库查询；它们共同形成一棵展示时间花费位置的树。 |
| **Attribute** | 附加到 span 的命名事实，例如 `provider: "openai"`、`cache.hit: true` 或 `item_count: 12`。Attribute 描述操作及其结果。 |
| **Event** | Span 期间某个时点发生的命名事件，例如 `retry.scheduled` 或 `cache.lookup`。Event 没有持续时间，可以带自己的 attribute。 |
| **Status** | 操作结果：`ok` 或 `error`。错误状态可以包含错误名称和消息。 |
| **Context** | 标识新工作在 span 树中归属位置的句柄。从 context 启动的 span 会成为该 context 的子节点。 |

例如，加载账号可以产生以下 telemetry：

```text
example.account.load                         span
├─ attributes: account.id=123, found=true   关于 span 的事实
├─ event: example.cache.lookup              span 期间发生的事件
│  └─ attribute: cache.hit=false            关于 event 的事实
└─ status: ok                               最终结果
```

Span 是诊断数据，不是业务状态。记录 span 不得改变账号加载是否运行、成功、失败或持久化。Adapter 把这些通用概念转换成 OpenTelemetry、Sentry、日志或其他后端使用的对应概念。

## 核心 Context API

`TelemetryContext` 围绕一个回调启动 span。回调接收 `TelemetrySpan`，它同时也是子 span 的显式 parent context。

```typescript
import {
  NOOP_TELEMETRY_CONTEXT,
  type TelemetryContext,
} from '@earendil-works/pi-telemetry';

async function loadAccount(
  accountId: string,
  telemetryContext: TelemetryContext = NOOP_TELEMETRY_CONTEXT,
) {
  return telemetryContext.startSpan(
    {
      name: 'example.account.load',
      attributes: { 'example.account.id': accountId },
    },
    async (span) => {
      const account = await readAccount(accountId);
      span.setAttributes({ 'example.account.found': account !== undefined });
      return account;
    },
  );
}
```

把回调 span 传给底层工作，以创建显式嵌套：

```typescript
return telemetryContext.startSpan({ name: 'example.parent' }, async (parentSpan) => {
  return parentSpan.startSpan({ name: 'example.child' }, async (childSpan) => {
    childSpan.addEvent('example.cache.lookup', { 'example.cache.hit': true });
    return performWork();
  });
});
```

没有公开的 `end()` 方法。`startSpan()` 负责 settlement，并让 span 保持打开，直到回调值或 promise settle。对于以正常返回值表示的预期失败，需要显式设置 status：

```typescript
return telemetryContext.startSpan({ name: 'example.save' }, async (span) => {
  const result = await save();
  if (!result.ok) {
    span.setStatus({
      status: 'error',
      error: { name: 'SaveError', message: result.reason },
    });
  }
  return result;
});
```

## Adapter 契约

Adapter 实现 `TelemetryContext`，并把通用 API 桥接到自己的后端。它必须：

- 创建子 span，并且同步、恰好一次地调用回调；
- 保留回调的返回值和 rejection 值；同步 throw 后返回以相同值 reject 的 promise；
- 让原生 span 保持打开，直到返回的 promise settle；
- 除非显式设置 status，否则将正常完成视为 `ok`，将 throw/rejection 视为错误；
- 重复调用 `setStatus()` 时以后写入者为准；
- 合并 `setAttributes()` 调用，后续已定义的值替换早先的值，忽略 `undefined`；
- 让记录方法保持同步、被动且不抛异常；
- 忽略 settlement 后的调用；
- 以原子方式忽略失败的记录调用、抑制后端失败，同时仍恰好执行一次业务回调。

Adapter 可以在内部激活后端原生 ambient context 以支持自动 instrumentation，但 pi 代码始终通过 `TelemetryContext` 参数传播 parent。Exporter 缓冲、flush、sampling、后端 ID 和后端专用 context 对象都由 adapter 负责。使用 [adapter 一致性 suite](#adapter-一致性)检查这些可观察语义。

## No-op Context

Telemetry 可选时使用 `NOOP_TELEMETRY_CONTEXT`：

```typescript
import { NOOP_TELEMETRY_CONTEXT } from '@earendil-works/pi-telemetry';

const result = await NOOP_TELEMETRY_CONTEXT.startSpan(
  { name: 'example.operation' },
  () => runOperation(),
);
```

No-op context：

- 同步调用回调；
- 保留返回值和异步 rejection，并把同步 throw 转换成以相同值 reject 的 promise；
- 包括嵌套 span 在内，使用同一个共享、冻结且惰性的 span；
- 不检查或保留名称、attribute、event 或 status。

## 内存参考 Adapter

`InMemoryTelemetryContext` 是与后端无关的参考实现，适用于测试、本地诊断，以及有意在没有 exporter 的情况下进行进程内捕获的应用：

```typescript
import { InMemoryTelemetryContext } from '@earendil-works/pi-telemetry';

const telemetry = new InMemoryTelemetryContext();

await telemetry.startSpan(
  { name: 'example.operation', attributes: { input: 'demo' } },
  async (span) => {
    span.addEvent('example.started');
    span.setAttributes({ output_count: 3 });
  },
);

console.log(telemetry.getSpans());
```

`getSpans()` 按 span 启动顺序返回相互分离的 snapshot。每个 `RecordedTelemetrySpan` 包含确定性数字 ID、parent ID、合并后的 attribute、有序 event、最终 status、settlement 状态和确定性结束序列。它不记录时间戳。

该 adapter 可以安全地用作普通 `TelemetryContext`，但其存储无界且只存在于进程内。创建新实例以隔离测试或记录作用域；除非调用方的数据策略允许，否则不要捕获敏感 attribute。

## Adapter 一致性

`@earendil-works/pi-telemetry/testing` 导出与 runner 无关、按组建模的一致性 suite。Fixture 提供新 context，并把后端已完成的 span 转换为规范化 `RecordedTelemetrySpan` snapshot：

```typescript
import {
  createTelemetryAdapterConformance,
  type TelemetryAdapterFixture,
} from '@earendil-works/pi-telemetry/testing';
import { describe, it } from 'vitest';

const conformance = createTelemetryAdapterConformance(async () => {
  const adapter = createMyTelemetryAdapter();
  return {
    context: adapter.context,
    getSpans: async () => adapter.normalizedSpans(),
    async [Symbol.asyncDispose]() {
      await adapter.close();
    },
  } satisfies TelemetryAdapterFixture;
});

for (const group of new Set(conformance.map((testCase) => testCase.group))) {
  describe(group, () => {
    for (const testCase of conformance.filter((candidate) => candidate.group === group)) {
      it(testCase.name, () => testCase.run());
    }
  });
}
```

Suite 检查同步单次 admission、结果和 rejection identity、自动和显式 status、attribute 合并、event 顺序、settlement 后调用无效、嵌套和并发 parent 关系，以及无法读取的 telemetry payload 失败被抑制。`getSpans()` 可以在返回前 flush 异步 exporter。Testing 子路径使用 Node assertion API；telemetry 根包保持 runtime-neutral。

## 类型化 Schema

底层 span API 有意接受开放名称和 attribute bag，让 adapter 保持通用。领域包可以定义封闭、可序列化的 schema，并由其推导精确的 TypeScript 类型。

```typescript
import {
  createTypedSpanStarter,
  defineTelemetrySchema,
} from '@earendil-works/pi-telemetry';

export const EXAMPLE_TELEMETRY_SCHEMA = defineTelemetrySchema({
  version: 1,
  spans: {
    'example.read': {
      description: 'Read one resource',
      parents: { kind: 'any' },
      startAttributes: {
        'example.resource': {
          type: 'string',
          required: true,
          values: ['account', 'project'],
          description: 'Resource kind',
        },
      },
      endAttributes: {
        'example.item_count': {
          type: 'number',
          description: 'Number of returned items',
        },
      },
      events: {
        'example.cache': {
          description: 'Cache lookup result',
          attributes: {
            'example.cache.hit': {
              type: 'boolean',
              required: true,
              description: 'Whether the cache contained the resource',
            },
          },
        },
      },
      status: {
        default: 'ok',
        errorWhen: 'The read throws or returns an error result',
      },
    },
  },
} as const);

const startSpan = createTypedSpanStarter(
  telemetryContext,
  [EXAMPLE_TELEMETRY_SCHEMA],
);
```

Starter 为每个 span 暴露一个 overload，并在编译期检查名称和 attribute。Union-valued 名称必须在调用前收窄，从而保留每个运行时名称与其 attribute schema 的关系。回调接收基于相同 schema 的 child starter，它已经绑定到回调 span：

```typescript
await startSpan(
  'example.read',
  { 'example.resource': 'account' },
  async (span, startChildSpan) => {
    span.addEvent('example.cache', { 'example.cache.hit': true });
    const accounts = await readAccounts();
    span.setAttributes({ 'example.item_count': accounts.length });

    await startChildSpan(
      'example.read',
      { 'example.resource': 'project' },
      async (childSpan) => {
        const projects = await readProjects();
        childSpan.setAttributes({ 'example.item_count': projects.length });
      },
    );

    return accounts;
  },
);
```

### 开始与完成属性

`startAttributes` 和 `endAttributes` 描述 attribute 通常在何时已知，并非不同的运行时存储：

| Schema 字段 | 值的记录方式 | 必填性 |
|---|---|---|
| `startAttributes` | 创建 span 时，通过 typed starter 的 `attributes` 参数传入 | 每个定义显式设置 `required: true` 或 `false` |
| `endAttributes` | 之后通过 schema-scoped span 的 `setAttributes()` 方法添加 | 始终可选 |

两组值都会成为同一后端 span 上的普通 attribute。不存在单独的结束 attribute payload 或结束回调。上例中，`example.resource` 在 `example.read` 启动时已知，`example.item_count` 则要到 `readAccounts()` 返回后才知道：

```typescript
await startSpan(
  'example.read',
  { 'example.resource': 'account' }, // 必填的开始 attribute
  async (span) => {
    const accounts = await readAccounts();
    span.setAttributes({
      'example.item_count': accounts.length, // 可选的完成 attribute
    });
    return accounts;
  },
); // 回调 resolve 时 span settle
```

“End”表示完成阶段补充：只要回调仍处于活动状态，end attribute 可以在任何时点设置；不可用时也可以省略。零次调用 `setAttributes()` 是有效的。这对提前失败、取消，以及并非每条路径都存在的 provider 专用数据很重要。

重复调用 `setAttributes()` 会合并到同一个 attribute bag。对于相同 key，后续已定义值替换早先值，`undefined` 被忽略。Schema-scoped 方法只接受当前 span 已声明的 end attribute。

Attribute 不会结束 span。回调的 return、resolve、throw 或 reject 控制 settlement；`startSpan()` 执行实际的结束操作。Settlement 后的 adapter 调用不起作用。

Starter 可以组合多个独立版本化的 schema：

```typescript
import { AGENT_TELEMETRY_SCHEMAS } from '@earendil-works/pi-agent-core';

const startAgentSpan = createTypedSpanStarter(
  telemetryContext,
  AGENT_TELEMETRY_SCHEMAS,
);
```

内联 schema 数组会自动保留 tuple 类型。单独声明的数组应使用 `as const`。数组中按字面值重复的 span 名称会在编译期被拒绝；schema 不会在运行时被合并、检查或保留。

Schema 派生类型会拒绝缺失的必填 attribute、未知 key、无效的封闭集合值、未声明 event，以及空 schema 上的 attribute。End attribute 始终是可选补充；类型系统不要求必须调用 `setAttributes()`。

`defineTelemetrySchema()` 是类型化 identity function。它返回普通、可 JSON 序列化的数据，不执行运行时验证或 parent rule 强制。

## Schema 元信息

支持的 attribute 类型：

- `string`、`number` 和 `boolean`；
- `string[]`、`number[]` 和 `boolean[]`。

Attribute 定义支持：

- `values`：标量值的封闭集合；
- `elementValues`：数组元素的封闭集合；
- `examples`：文档示例；
- `sensitive`：标记需要特殊处理的数据；
- `cardinality`：记录预期的 `low` 或 `high` 基数。

Start 和 event attribute 声明 `required`，end attribute 不声明；参见[开始与完成属性](#开始与完成属性)。

Parent 元信息是描述性 schema 数据：

- `{ kind: 'any' }`：根或任意调用方 span；
- `{ kind: 'root_or_external' }`：根或 schema 之外由调用方拥有的 span；
- `{ kind: 'spans', spans: [...] }`：仅列出的 schema span。

Adapter 不需要理解 schema 对象。Instrumentation helper 和测试使用它们保持发出的名称及 attribute 一致。

## Pi 包集成

包所有权有意拆分：

- `@earendil-works/pi-telemetry` 拥有与供应商无关的契约、no-op 和内存参考 context、schema 工具与 adapter 一致性 suite；
- `@earendil-works/pi-ai` 在 provider 请求选项中接受并传播 `telemetryContext`，但不拥有 telemetry schema；
- `@earendil-works/pi-agent-core` 拥有并导出 pi AI 请求和 harness schema、它们组合后的 readonly schema tuple，以及类型化 span helper。

```typescript
import {
  AGENT_TELEMETRY_SCHEMAS,
  AI_TELEMETRY_SCHEMA,
  HARNESS_TELEMETRY_SCHEMA,
  startAiSpan,
  startHarnessSpan,
} from '@earendil-works/pi-agent-core';
```

Pi schema 使用 pi 自有的 `pi.ai.*`、`pi.harness.*` 和 `pi.session.*` 名称。Adapter 可以将它们转换为后端惯例，但不能改变发出的 pi 词汇。

## 安全性与可移植性

Telemetry 是进程内诊断信息，不是持久应用状态。不要把 `TelemetryContext`、`TelemetrySpan` 或后端原生 trace 对象持久化到 record、message、snapshot 或 deferred handle 中。

Attribute 值有意限制为原始标量和数组。除非 schema 和数据策略明确允许，否则领域 instrumentation 应避免记录 prompt、completion、工具参数或输出、文件内容、provider payload、header、凭据和自由格式错误细节。

该包不使用 `AsyncLocalStorage` 或其他 runtime 专用 ambient context API。它适用于 Node.js、Bun、浏览器和 worker；后端 adapter 仍需负责自己的 runtime 兼容性。

## API 参考

### 核心类型和值

| 导出 | 用途 |
|---|---|
| `TelemetryContext` | 启动由回调管理的子 span |
| `TelemetrySpan` | 记录 attribute、event 和 status；也充当子 context |
| `SpanOptions` | Span 名称和可选开始 attribute |
| `SpanAttributes` / `AttributeValue` | 开放的 adapter 层 attribute bag 和支持的值 |
| `SpanStatus` | 显式 `ok` 或 `error` status |
| `NOOP_TELEMETRY_CONTEXT` | Telemetry 禁用时使用的共享被动 context |
| `InMemoryTelemetryContext` | 具有确定性进程内记录的参考 adapter |
| `RecordedTelemetrySpan` | 规范化的已捕获 span snapshot |
| `RecordedTelemetryEvent` | 规范化的已捕获 event snapshot |

### Schema 定义与推导

| 导出 | 用途 |
|---|---|
| `defineTelemetrySchema()` | 可序列化 schema 数据的类型化 identity helper |
| `createTypedSpanStarter()` | 将 parent context 绑定到一个或多个 schema 词汇表 |
| `TypedSpanStarter` | 回调递归绑定 child 的精确 starter 类型 |
| `TelemetrySchemaDefinition` | 顶层 schema 结构 |
| `TelemetrySpanDefinition` | Span 元信息、parent、attribute、event 和 status rule |
| `TelemetryAttributeType` | 支持的标量与数组类型名称 |
| `TelemetryAttributeMetadata` | 描述、敏感性和基数元信息 |
| `TelemetryAttributeDefinition` | Attribute 类型、允许值、示例和元信息 |
| `TelemetryStartAttributeDefinition` | 带必填性的开始 attribute 定义 |
| `TelemetryEventAttributeDefinition` | 带必填性的 event attribute 定义 |
| `TelemetryEventDefinition` | Event 描述和 attribute 定义 |
| `TelemetryParentDefinition` | 开放、外部根或有限 schema parent rule |
| `TelemetrySchemaSpanName` | 已声明 span 名称的 union |
| `TelemetrySchemaSpanStartAttributes` | 为一个 span 精确推导的开始 attribute |
| `TelemetrySchemaSpanEndAttributes` | 为一个 span 推导的可选结束 attribute |
| `TelemetrySchemaSpanEventName` | 一个 span 声明的 event union |
| `TelemetrySchemaSpanEventAttributes` | 为一个 event 精确推导的 attribute |
| `SchemaTelemetrySpan` | 限制为一个 schema span 的 span view |
| `TelemetrySchemaSpanUnion` | Schema 中所有 span 的 discriminated union |
| `InferStartAttributes` | 从开始定义推导的必填与可选值 |
| `InferOptionalAttributes` | 从结束定义推导的可选值 |
| `InferEventAttributes` | 从 event 定义推导的必填与可选值 |
| `InferRequiredAndOptionalAttributes` | 具有必填性的定义所共用的推导工具 |
| `ExactTelemetryAttributes` | 拒绝预期 attribute 集之外的 key |

### Testing 子路径

| 导出 | 用途 |
|---|---|
| `createTelemetryAdapterConformance()` | 创建与 runner 无关的 adapter 一致性 case |
| `TelemetryAdapterFixture` | 单个 case 的新 context 和规范化 snapshot reader |
| `TelemetryAdapterFixtureFactory` | 创建隔离 fixture |
| `TelemetryAdapterConformanceCase` | 由 test runner 执行的分组 case |

## 开发

在该包目录中：

```bash
npm test
npm run build
```

仓库级类型检查、格式化、lint 和 smoke check 使用：

```bash
npm run check
```

## License

MIT
