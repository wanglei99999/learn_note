# pi 中文文档

[earendil-works/pi](https://github.com/earendil-works/pi) 官方文档的简体中文翻译，自包含、可整体迁移。翻译版本与约定见 [TRANSLATION-NOTES.md](./TRANSLATION-NOTES.md)。

## 包之间的关系

pi 是一个由多个 npm 包组成的 monorepo：

```text
pi-tui ──┐
pi-ai ───┴─→ pi-agent-core ─→ pi-coding-agent（pi CLI）─→ pi-orchestrator（实验性）
```

| 目录 | npm 包 | 用途 |
| --- | --- | --- |
| [`ai`](./ai/README.md) | `@earendil-works/pi-ai` | 统一封装不同大模型服务，负责模型发现、Provider 配置和流式响应。 |
| [`agent`](./agent/README.md) | `@earendil-works/pi-agent-core` | 基于 pi-ai 的通用 Agent 运行时：状态管理、工具调用、生命周期。 |
| [`tui`](./tui/README.md) | `@earendil-works/pi-tui` | 终端 UI 组件与差分渲染。 |
| [`coding-agent`](./coding-agent/README.md) | `@earendil-works/pi-coding-agent` | 组合以上三者，形成可直接使用的终端编程助手（`pi` 命令）。 |
| [`orchestrator`](./orchestrator/README.md) | `@earendil-works/pi-orchestrator` | 基于 coding-agent 的实验性任务编排工具。 |

## Agent Core 设计文档（`agent/`）

记录 Agent 运行时的内部设计，适合改底层框架或排查运行机制时阅读。

| 译文 | 内容 |
| --- | --- |
| [AgentHarness 生命周期](./agent/agent-harness.md) | Agent 状态模型、执行阶段、保存点、错误处理、钩子和事件。 |
| [持久化 AgentHarness 与会话设计](./agent/durable-harness.md) | 持久化状态、会话恢复、运行时配置和故障恢复策略。 |
| [钩子设计](./agent/hooks.md) | Hook 接口、默认实现、上下文和状态修改语义。 |
| [模型架构](./agent/models.md) | Models、Provider、模型列表、流式调用及 API 实现结构。 |
| [可观测性设计](./agent/observability.md) | 日志、追踪、异步上下文、运行时适配器和埋点位置。 |

## Coding Agent 文档（`coding-agent/`）

### 入门与日常使用

| 译文 | 内容 |
| --- | --- |
| [文档首页](./coding-agent/index.md) | 文档总入口和推荐阅读路径。 |
| [快速开始](./coding-agent/quickstart.md) | 安装、认证和第一次会话。 |
| [使用指南](./coding-agent/usage.md) | 交互模式、斜杠命令、消息队列、上下文文件和 CLI 参数。 |
| [设置](./coding-agent/settings.md) | 全局设置、项目设置和项目信任机制。 |
| [安全](./coding-agent/security.md) | 项目信任、沙箱边界及运行不可信代码时的注意事项。 |

### 模型与 Provider

| 译文 | 内容 |
| --- | --- |
| [Provider](./coding-agent/providers.md) | API key、订阅认证和云服务商配置。 |
| [自定义模型](./coding-agent/models.md) | 自定义模型文件格式、API 类型及模型参数。 |
| [自定义 Provider](./coding-agent/custom-provider.md) | 注册、覆盖、移除 Provider 以及 OAuth 支持。 |
| [llama.cpp](./coding-agent/llama-cpp.md) | 使用 llama.cpp 路由器运行本地模型。 |

### 扩展与个性化

| 译文 | 内容 |
| --- | --- |
| [Extensions](./coding-agent/extensions.md) | TypeScript extension 的位置、接口、事件和 UI 能力。 |
| [Skills](./coding-agent/skills.md) | Skill 的目录、加载方式、命令和文件结构。 |
| [pi 包](./coding-agent/packages.md) | 扩展包的安装、来源、管理和发布格式。 |
| [提示词模板](./coding-agent/prompt-templates.md) | 提示词模板的位置、格式、参数和加载规则。 |
| [主题](./coding-agent/themes.md) | 主题选择、自定义主题和颜色令牌。 |
| [快捷键](./coding-agent/keybindings.md) | 按键格式、可配置操作和快捷键配置。 |
| [Shell 别名](./coding-agent/shell-aliases.md) | 在 shell 中为 pi 配置快捷别名。 |

### 会话与上下文管理

| 译文 | 内容 |
| --- | --- |
| [会话](./coding-agent/sessions.md) | 会话存储、恢复、删除、命名、分支和克隆。 |
| [会话文件格式](./coding-agent/session-format.md) | JSONL 会话文件、版本和消息条目类型。 |
| [上下文压缩与分支摘要](./coding-agent/compaction.md) | 长会话压缩、分支摘要及摘要格式。 |

### SDK 与外部集成

| 译文 | 内容 |
| --- | --- |
| [SDK](./coding-agent/sdk.md) | 在代码中创建 coding agent 会话及配置资源加载器。 |
| [RPC 模式](./coding-agent/rpc.md) | RPC 命令、事件、extension UI 协议和错误处理。 |
| [JSON 事件流模式](./coding-agent/json.md) | JSON 输出格式、事件类型和消息类型。 |
| [TUI 组件](./coding-agent/tui.md) | 组件接口、焦点管理、覆盖层、键盘输入和内置组件。 |

### 开发与运行环境

| 译文 | 内容 |
| --- | --- |
| [开发指南](./coding-agent/development.md) | 本地开发、调试、测试、路径解析和项目结构。 |
| [容器化](./coding-agent/containerization.md) | Gondolin、Docker 和 OpenShell 等隔离运行方式。 |
| [终端配置](./coding-agent/terminal-setup.md) | 常见终端模拟器的按键和协议配置。 |
| [Windows 配置](./coding-agent/windows.md) | Windows 下的 shell 路径配置。 |
| [Termux 配置](./coding-agent/termux.md) | Android Termux 环境的安装步骤。 |
| [tmux 配置](./coding-agent/tmux.md) | tmux 推荐设置及 `csi-u` 键盘协议说明。 |

## 推荐阅读顺序

如果目标是**使用 pi**：

1. [Coding Agent README](./coding-agent/README.md)
2. [快速开始](./coding-agent/quickstart.md) 和 [使用指南](./coding-agent/usage.md)
3. 按需查看 Provider、设置、快捷键、主题或 Skills 文档

如果目标是**参与开发**：

1. [开发指南](./coding-agent/development.md)
2. [AgentHarness 生命周期](./agent/agent-harness.md)
3. [会话文件格式](./coding-agent/session-format.md) 和 [Extensions](./coding-agent/extensions.md)
4. 根据修改范围继续阅读模型架构、SDK、RPC 或 TUI 文档
