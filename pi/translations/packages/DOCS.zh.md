# Pi Packages 中文文档导览

本文档用于快速了解 `packages` 目录中的各个包，并找到对应的详细文档。

## 包之间的关系

Pi 是一个由多个 npm 包组成的 monorepo：

```text
pi-ai ──> pi-agent-core ──┐
pi-ai ───────────────────┼──> pi-coding-agent ──> pi-orchestrator
pi-tui ──────────────────┘
pi-ai ──────────────────────> pi-telemetry
```

| 目录 | npm 包 | 用途 |
| --- | --- | --- |
| [`ai`](../docs-zh/ai/README.md) | `@earendil-works/pi-ai` | 统一封装不同大模型服务，负责模型发现、Provider 配置和流式响应。 |
| [`agent`](../docs-zh/agent/README.md) | `@earendil-works/pi-agent-core` | 基于 `pi-ai` 提供通用 Agent 运行时、状态管理、工具调用和生命周期管理。 |
| [`tui`](../docs-zh/tui/README.md) | `@earendil-works/pi-tui` | 提供终端用户界面组件和增量渲染能力。 |
| [`coding-agent`](../docs-zh/coding-agent/README.md) | `@earendil-works/pi-coding-agent` | 组合 AI、Agent 和 TUI，形成可直接使用的终端编程助手。 |
| [`orchestrator`](../docs-zh/orchestrator/README.md) | `@earendil-works/pi-orchestrator` | 基于 Coding Agent 的实验性任务编排工具。 |
| [`telemetry`](../docs-zh/telemetry/README.md) | `@earendil-works/pi-telemetry` | 提供类型化、默认无内容的 telemetry 接口与适配器。 |

## 中文入口

- [Agent Core 中文 README](../docs-zh/agent/README.md)
- [AI 中文 README](../docs-zh/ai/README.md)
- [Coding Agent 中文 README](../docs-zh/coding-agent/README.md)
- [Orchestrator 中文 README](../docs-zh/orchestrator/README.md)
- [TUI 中文 README](../docs-zh/tui/README.md)
- [Telemetry 中文 README](../docs-zh/telemetry/README.md)
- [Client 中文 README](../docs-zh/client/README.md)
- [Protocol 中文 README](../docs-zh/protocol/README.md)
- [Server 中文 README](../docs-zh/server/README.md)
- [Evals 中文 README](../docs-zh/evals/README.md)
- [SQLite Node Session Backend](../docs-zh/session-backends/sqlite-node/README.md)
- [Windows 原生预构建](../docs-zh/tui/native/win32/README.md)
- [Darwin 原生预构建](../docs-zh/tui/native/darwin/README.md)

初次接触项目时，建议先阅读 Coding Agent 中文 README。它包含安装、认证、基本使用、命令行参数和配置说明。

## Agent Core 设计文档

`agent/docs` 主要记录 Agent 运行时的内部设计，适合维护底层框架或排查运行机制时阅读。

| 原文 | 内容 |
| --- | --- |
| [AgentHarness 生命周期](../docs-zh/agent/agent-harness.md) | Agent 状态模型、执行阶段、保存点、错误处理、钩子和事件。 |
| [持久化 AgentHarness 与会话设计](../docs-zh/agent/durable-harness.md) | 持久化状态、会话恢复、运行时配置和故障恢复策略。 |
| [钩子设计](../docs-zh/agent/hooks.md) | 钩子接口、默认实现、上下文和状态修改语义。 |
| [模型架构](../docs-zh/agent/models.md) | Models、Provider、模型列表、流式调用及 API 实现结构。 |
| [可观测性设计](../docs-zh/agent/observability.md) | 日志、追踪、异步上下文、运行时适配器和埋点位置。 |
| [持久化 Harness 规范](../docs-zh/agent/harness.md) | 存储、状态机、恢复、公开 API、迁移与测试规范。 |
| [会话搜索](../docs-zh/agent/search.md) | 搜索索引同步、查询与一致性语义。 |
| [Telemetry Schema](../docs-zh/agent/telemetry-schema.md) | Agent telemetry span、属性和内容安全约束。 |

## Coding Agent 使用文档

### 入门与日常使用

| 原文 | 内容 |
| --- | --- |
| [文档首页](../docs-zh/coding-agent/01.index.md) | 文档总入口和推荐阅读路径。 |
| [快速开始](../docs-zh/coding-agent/quickstart.md) | 安装、认证和第一次会话。 |
| [使用指南](../docs-zh/coding-agent/02.usage.md) | 交互模式、斜杠命令、消息队列、上下文文件和 CLI 参数。 |
| [设置](../docs-zh/coding-agent/11.settings.md) | 全局设置、项目设置和项目信任机制。 |
| [安全](../docs-zh/coding-agent/05.security.md) | 项目信任、沙箱边界及运行不可信代码时的注意事项。 |

### 模型与 Provider

| 原文 | 内容 |
| --- | --- |
| [Provider](../docs-zh/coding-agent/03.providers.md) | API Key、订阅认证和云服务商配置。 |
| [自定义模型](../docs-zh/coding-agent/12.models.md) | 自定义模型文件格式、API 类型及模型参数。 |
| [自定义 Provider](../docs-zh/coding-agent/13.custom-provider.md) | 注册、覆盖、移除 Provider 以及 OAuth 支持。 |
| [llama.cpp](../docs-zh/coding-agent/04.llama-cpp.md) | 使用 llama.cpp 路由器运行本地模型。 |

### 扩展与个性化

| 原文 | 内容 |
| --- | --- |
| [Extensions](../docs-zh/coding-agent/19.extensions.md) | TypeScript 扩展的位置、接口、事件和 UI 能力。 |
| [Skills](../docs-zh/coding-agent/14.skills.md) | Skill 的目录、加载方式、命令和文件结构。 |
| [Pi Packages](../docs-zh/coding-agent/18.packages.md) | 扩展包的安装、来源、管理和发布格式。 |
| [Prompt 模板](../docs-zh/coding-agent/15.prompt-templates.md) | 提示词模板的位置、格式、参数和加载规则。 |
| [主题](../docs-zh/coding-agent/16.themes.md) | 主题选择、自定义主题和颜色令牌。 |
| [快捷键](../docs-zh/coding-agent/17.keybindings.md) | 按键格式、可配置操作和快捷键配置。 |
| [Shell 别名](../docs-zh/coding-agent/shell-aliases.md) | 在 Shell 中为 Pi 配置快捷别名。 |

### 会话与上下文管理

| 原文 | 内容 |
| --- | --- |
| [会话](../docs-zh/coding-agent/08.sessions.md) | 会话存储、恢复、删除、命名、分支和克隆。 |
| [会话文件格式](../docs-zh/coding-agent/09.session-format.md) | JSONL 会话文件、版本和消息条目类型。 |
| [上下文压缩与分支摘要](../docs-zh/coding-agent/10.compaction.md) | 长会话压缩、分支摘要及摘要格式。 |

### SDK 与外部集成

| 原文 | 内容 |
| --- | --- |
| [SDK](../docs-zh/coding-agent/sdk.md) | 在代码中创建 Coding Agent 会话及配置资源加载器。 |
| [RPC 模式](../docs-zh/coding-agent/rpc.md) | RPC 命令、事件、扩展 UI 协议和错误处理。 |
| [JSON 事件流模式](../docs-zh/coding-agent/07.json.md) | JSON 输出格式、事件类型和消息类型。 |
| [TUI 组件](../docs-zh/coding-agent/tui.md) | 组件接口、焦点管理、覆盖层、键盘输入和内置组件。 |

### 开发与运行环境

| 原文 | 内容 |
| --- | --- |
| [开发指南](../docs-zh/coding-agent/development.md) | 本地开发、调试、测试、路径解析和项目结构。 |
| [容器化](../docs-zh/coding-agent/06.containerization.md) | Gondolin、Docker 和 OpenShell 等隔离运行方式。 |
| [环境变量](../docs-zh/coding-agent/environment-variables.md) | Pi 支持的环境变量、优先级与运行时行为。 |
| [终端配置](../docs-zh/coding-agent/terminal-setup.md) | 常见终端模拟器的按键和协议配置。 |
| [Windows 配置](../docs-zh/coding-agent/windows.md) | Windows 下的 Shell 路径配置。 |
| [Termux 配置](../docs-zh/coding-agent/termux.md) | Android Termux 环境的安装步骤。 |
| [tmux 配置](../docs-zh/coding-agent/tmux.md) | tmux 推荐设置及 `csi-u` 键盘协议说明。 |

### 示例与测试

| 原文 | 内容 |
| --- | --- |
| [示例总览](../docs-zh/coding-agent/examples/README.md) | SDK、extension 与 provider 示例入口。 |
| [SDK 示例](../docs-zh/coding-agent/examples/sdk/README.md) | 编程方式创建和管理 agent session。 |
| [Extension 示例](../docs-zh/coding-agent/examples/extensions/README.md) | Extension 示例目录与常用模式。 |
| [Subagent 示例](../docs-zh/coding-agent/examples/extensions/subagent/README.md) | 隔离 subagent、并行与链式工作流。 |
| [Plan mode 示例](../docs-zh/coding-agent/examples/extensions/plan-mode/README.md) | 只读探索、计划编辑与执行模式。 |
| [DOOM Overlay 示例](../docs-zh/coding-agent/examples/extensions/doom-overlay/README.md) | 实时 overlay 渲染示例。 |
| [测试 Suite](../docs-zh/coding-agent/test/suite/README.md) | coding-agent 测试 suite 的组织与运行方式。 |

## 推荐阅读顺序

如果目标是使用 Pi：

1. 阅读 [Coding Agent 中文 README](../docs-zh/coding-agent/README.md)。
2. 阅读[快速开始](../docs-zh/coding-agent/quickstart.md)和[使用指南](../docs-zh/coding-agent/02.usage.md)。
3. 根据需要查看 Provider、设置、快捷键、主题或 Skills 文档。

如果目标是参与开发：

1. 阅读[开发指南](../docs-zh/coding-agent/development.md)。
2. 了解[持久化 Harness 规范](../docs-zh/agent/harness.md)。
3. 阅读[会话文件格式](../docs-zh/coding-agent/09.session-format.md)和[扩展开发](../docs-zh/coding-agent/19.extensions.md)。
4. 根据修改范围继续阅读模型架构、SDK、RPC 或 TUI 文档。

> 上述链接均指向完整简体中文译文。
