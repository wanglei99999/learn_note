> **译文** | 原文：[`packages/evals/README.md`](https://github.com/earendil-works/pi/blob/main/packages/evals/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# Pi evals

Pi evals 是由模型支持、用于检查 Pi 工作流行为的评估。它们把真实 `AgentSession` 适配到 `vitest-evals`，在隔离的临时项目目录和 agent 目录中运行，并附带 Pi 原生 session artifact。使用它们可以衡量端到端行为，比较 prompt、工具、skill、模型或其他 harness 配置。

## 运行 eval

在仓库根目录使用默认 provider 和模型运行：

```bash
npm run eval -- --provider openai --model gpt-5.6-sol
```

等价的环境变量是：

```bash
PI_PROVIDER=openai PI_MODEL=gpt-5.6-sol npm run eval
```

CLI 值优先，并成为没有显式选择模型的 harness 的默认值。Provider 和模型必须一起提供。如果每个执行的 harness 都配置了自己的模型，runner 也允许不提供默认值。认证来自 Pi 正常的 `ModelRuntime`，包括 Pi 订阅凭据和 provider API key 环境变量。

其他参数会转发给 Vitest：

```bash
npm run eval -- src/extensions.eval.ts
npm run eval -- -t "creates, reloads, and uses"
```

每次调用都会打印一个被忽略的 `.eval/` artifact 目录。`runs.jsonl` 为已完成的 harness run 及其位于 `sessions/` 下的 Pi 原生 session JSONL 附件建立索引。这些文件可能包含 prompt、响应、源代码和工具输出。

## 编写 eval

通用 suite、judge、断言和规范化 trace 指南请遵循 [`vitest-evals`](https://github.com/getsentry/vitest-evals)。Pi 专用 eval 使用 `src/pi-harness.ts` 的 `createPiCodingAgentHarness(...)`，每个 `describeEval(...)` suite 绑定一个 harness：

```ts
import { expect } from "vitest";
import { describeEval } from "vitest-evals";
import { createPiCodingAgentHarness } from "./pi-harness.ts";

const harness = createPiCodingAgentHarness({ noTools: "all" });

describeEval("Pi smoke", { harness }, (it) => {
	it("answers a factual question", async ({ run }) => {
		const result = await run("What is the capital of France? Reply with only the city name.");
		expect(result.output).toBe("Paris");
	});
});
```

### 配置 Pi harness

`createPiCodingAgentHarness(...)` 接受：

- `name`：报告和比较使用的稳定 harness 标识。
- `model`：可选的 `{ provider, id }` 选择，覆盖 runner 的默认模型。
- `noTools`：Pi 的工具禁用配置。
- `transformSystemPrompt`：在 eval 开始前转换完整的默认 prompt。
- `output`：将最终响应和 `AgentSession` 转换为 JSON-safe 领域结果。

显式选择模型可让模型比较 harness 不依赖 runner 默认值：

```ts
const harness = createPiCodingAgentHarness({
	name: "claude-opus-4-6",
	model: { provider: "anthropic", id: "claude-opus-4-6" },
});
```

一次 run 接受单条 prompt，也接受由 prompt 和 reload 步骤组成的序列。如果上一条 prompt 创建或更改了 Pi 资源，reload 步骤会很有用：

```ts
const result = await run([
	{ type: "prompt", content: "Create a Pi extension." },
	{ type: "reload" },
	{ type: "prompt", content: "Use the extension." },
]);
```

### 转换 harness 输出

使用 `output` 暴露特定场景的 JSON-safe 行为，而不把这些行为加入通用 Pi adapter：

```ts
const harness = createPiCodingAgentHarness({
	output: ({ response, session }) => ({
		response,
		activeTools: session.getActiveToolNames(),
		extensionErrors: session.resourceLoader.getExtensions().errors,
	}),
});
```

在 `result.output` 上断言应用行为。在 `result.session` 上断言模型和工具 trace，并使用 `toolCalls(...)` 等 `vitest-evals` helper。

### 编写比较 eval 集

使用 `evalHarnessTable(...)` 配合 Vitest 原生的 `describe.for(...)`，让同一组输入在多个 harness 上运行。Harness 可以在 prompt、工具、skill、模型或任何其他 Pi 配置上有所不同：

```ts
import { describe } from "vitest";
import { createJudge, describeEval } from "vitest-evals";
import { evalHarnessTable } from "./vitest-evals/harness-table.ts";

const TargetTaskJudge = createJudge<string, string>("TargetTaskJudge", ({ output }) => ({
	score: output === "expected result" ? 1 : 0,
}));

const harnessTable = evalHarnessTable(
	"target skill effectiveness",
	{
		baseline: withoutTargetSkillHarness,
		candidate: withTargetSkillHarness,
		repetitions: 6,
	},
);

describe.for(harnessTable)("$name repetition $repetition", ({ harness }) => {
	describeEval("target skill effectiveness", { harness, judges: [TargetTaskJudge], judgeThreshold: null }, (it) => {
		it("completes the target task", async ({ run }) => {
			await run("Complete the target task.");
		});
	});
});
```

比较 suite 应使用确定性或模型支持的 judge 记录正确性，并设置 `judgeThreshold: null`。这样，低分会作为观测结果，而不会导致 Vitest 调用失败。硬断言只应用于 suite invariant 和基础设施契约。`expect.soft(...)` 仍会让测试失败，不是评分机制。

Pi harness 会在删除临时 workspace 前为原生 session JSONL 创建 snapshot。仅用于 eval 的 `afterEach` hook 会在 reporter 运行前，把该 snapshot 注册到显式 Vitest test task。

Harness 名称在一个 eval 集中必须稳定且唯一。分组 key 会组合 repetition 与非空字符串 `input.id`；没有后者时，则组合 strict canonical JSON 输入的 SHA-256 hash。一个 treatment 使用 `candidate`，多个 treatment 使用 `candidates`。每个 candidate 只与声明的 baseline 比较。对于每组匹配的输入和 repetition，reporter 根据每次 run 记录的 judge 平均分计算通过率提升，并将至少为 `1` 的得分视为通过。提升值是 candidate 通过率减去 baseline 通过率，以百分点表示。缺失 judge 得分会报告为不完整观测。Token、延迟和估算费用仍是相互独立的 candidate-minus-baseline 配对差值；缺失的 telemetry 仍标记为不可用。如果需要随机化执行顺序，请使用 Vitest 内置的 sequence shuffle。

比较 eval 的方法、重复策略、可信 judge 和 telemetry 解读请参见 [`skill-eval-harness`](https://github.com/adewale/skill-eval-harness/) 指南。
