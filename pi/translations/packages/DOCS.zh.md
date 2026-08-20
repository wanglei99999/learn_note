# Pi Packages 中文文档导览

本文档用于快速了解 `packages` 目录中的各个包，并找到对应的详细文档。

## 包之间的关系

Pi 是一个由多个 npm 包组成的 monorepo：

```text
pi-ai ──> pi-agent-core ──┐
pi-ai ───────────────────┼──> pi-coding-agent ──> pi-orchestrator
pi-tui ──────────────────┘
```

| 目录 | npm 包 | 用途 |
| --- | --- | --- |
| [`ai`](./ai/) | `@earendil-works/pi-ai` | 统一封装不同大模型服务，负责模型发现、Provider 配置和流式响应。 |
| [`agent`](./agent/) | `@earendil-works/pi-agent-core` | 基于 `pi-ai` 提供通用 Agent 运行时、状态管理、工具调用和生命周期管理。 |
| [`tui`](./tui/) | `@earendil-works/pi-tui` | 提供终端用户界面组件和增量渲染能力。 |
| [`coding-agent`](./coding-agent/) | `@earendil-works/pi-coding-agent` | 组合 AI、Agent 和 TUI，形成可直接使用的终端编程助手。 |
| [`orchestrator`](./orchestrator/) | `@earendil-works/pi-orchestrator` | 基于 Coding Agent 的实验性任务编排工具。 |

## 中文入口

- [Agent Core 中文 README](./agent/README.zh.md)
- [AI 中文 README](./ai/README.zh.md)
- [Coding Agent 中文 README](./coding-agent/README.zh.md)
- [Orchestrator 中文 README](./orchestrator/README.zh.md)
- [TUI 中文 README](./tui/README.zh.md)

初次接触项目时，建议先阅读 Coding Agent 中文 README。它包含安装、认证、基本使用、命令行参数和配置说明。

## Agent Core 设计文档

`agent/docs` 主要记录 Agent 运行时的内部设计，适合维护底层框架或排查运行机制时阅读。

| 原文 | 内容 |
| --- | --- |
| [AgentHarness 生命周期](./agent/docs/agent-harness.md) | Agent 状态模型、执行阶段、保存点、错误处理、钩子和事件。 |
| [持久化 AgentHarness 与会话设计](./agent/docs/durable-harness.md) | 持久化状态、会话恢复、运行时配置和故障恢复策略。 |
| [钩子设计](./agent/docs/hooks.md) | 钩子接口、默认实现、上下文和状态修改语义。 |
| [模型架构](./agent/docs/models.md) | Models、Provider、模型列表、流式调用及 API 实现结构。 |
| [可观测性设计](./agent/docs/observability.md) | 日志、追踪、异步上下文、运行时适配器和埋点位置。 |

## Coding Agent 使用文档

### 入门与日常使用

| 原文 | 内容 |
| --- | --- |
| [文档首页](./coding-agent/docs/index.md) | 文档总入口和推荐阅读路径。 |
| [快速开始](./coding-agent/docs/quickstart.md) | 安装、认证和第一次会话。 |
| [使用指南](./coding-agent/docs/usage.md) | 交互模式、斜杠命令、消息队列、上下文文件和 CLI 参数。 |
| [设置](./coding-agent/docs/settings.md) | 全局设置、项目设置和项目信任机制。 |
| [安全](./coding-agent/docs/security.md) | 项目信任、沙箱边界及运行不可信代码时的注意事项。 |

### 模型与 Provider

| 原文 | 内容 |
| --- | --- |
| [Provider](./coding-agent/docs/providers.md) | API Key、订阅认证和云服务商配置。 |
| [自定义模型](./coding-agent/docs/models.md) | 自定义模型文件格式、API 类型及模型参数。 |
| [自定义 Provider](./coding-agent/docs/custom-provider.md) | 注册、覆盖、移除 Provider 以及 OAuth 支持。 |
| [llama.cpp](./coding-agent/docs/llama-cpp.md) | 使用 llama.cpp 路由器运行本地模型。 |

### 扩展与个性化

| 原文 | 内容 |
| --- | --- |
| [Extensions](./coding-agent/docs/extensions.md) | TypeScript 扩展的位置、接口、事件和 UI 能力。 |
| [Skills](./coding-agent/docs/skills.md) | Skill 的目录、加载方式、命令和文件结构。 |
| [Pi Packages](./coding-agent/docs/packages.md) | 扩展包的安装、来源、管理和发布格式。 |
| [Prompt 模板](./coding-agent/docs/prompt-templates.md) | 提示词模板的位置、格式、参数和加载规则。 |
| [主题](./coding-agent/docs/themes.md) | 主题选择、自定义主题和颜色令牌。 |
| [快捷键](./coding-agent/docs/keybindings.md) | 按键格式、可配置操作和快捷键配置。 |
| [Shell 别名](./coding-agent/docs/shell-aliases.md) | 在 Shell 中为 Pi 配置快捷别名。 |

### 会话与上下文管理

| 原文 | 内容 |
| --- | --- |
| [会话](./coding-agent/docs/sessions.md) | 会话存储、恢复、删除、命名、分支和克隆。 |
| [会话文件格式](./coding-agent/docs/session-format.md) | JSONL 会话文件、版本和消息条目类型。 |
| [上下文压缩与分支摘要](./coding-agent/docs/compaction.md) | 长会话压缩、分支摘要及摘要格式。 |

### SDK 与外部集成

| 原文 | 内容 |
| --- | --- |
| [SDK](./coding-agent/docs/sdk.md) | 在代码中创建 Coding Agent 会话及配置资源加载器。 |
| [RPC 模式](./coding-agent/docs/rpc.md) | RPC 命令、事件、扩展 UI 协议和错误处理。 |
| [JSON 事件流模式](./coding-agent/docs/json.md) | JSON 输出格式、事件类型和消息类型。 |
| [TUI 组件](./coding-agent/docs/tui.md) | 组件接口、焦点管理、覆盖层、键盘输入和内置组件。 |

### 开发与运行环境

| 原文 | 内容 |
| --- | --- |
| [开发指南](./coding-agent/docs/development.md) | 本地开发、调试、测试、路径解析和项目结构。 |
| [容器化](./coding-agent/docs/containerization.md) | Gondolin、Docker 和 OpenShell 等隔离运行方式。 |
| [终端配置](./coding-agent/docs/terminal-setup.md) | 常见终端模拟器的按键和协议配置。 |
| [Windows 配置](./coding-agent/docs/windows.md) | Windows 下的 Shell 路径配置。 |
| [Termux 配置](./coding-agent/docs/termux.md) | Android Termux 环境的安装步骤。 |
| [tmux 配置](./coding-agent/docs/tmux.md) | tmux 推荐设置及 `csi-u` 键盘协议说明。 |

## 推荐阅读顺序

如果目标是使用 Pi：

1. 阅读 [Coding Agent 中文 README](./coding-agent/README.zh.md)。
2. 阅读[快速开始](./coding-agent/docs/quickstart.md)和[使用指南](./coding-agent/docs/usage.md)。
3. 根据需要查看 Provider、设置、快捷键、主题或 Skills 文档。

如果目标是参与开发：

1. 阅读[开发指南](./coding-agent/docs/development.md)。
2. 了解 [AgentHarness 生命周期](./agent/docs/agent-harness.md)。
3. 阅读[会话文件格式](./coding-agent/docs/session-format.md)和[扩展开发](./coding-agent/docs/extensions.md)。
4. 根据修改范围继续阅读模型架构、SDK、RPC 或 TUI 文档。

> 当前专题文档的正文仍以英文为主。本文提供中文导航和内容摘要，便于按需选择后续需要完整翻译的文档。
