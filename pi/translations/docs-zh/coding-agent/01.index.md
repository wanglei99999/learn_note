> **译文** | 原文：[`packages/coding-agent/docs/index.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/index.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# Pi 文档

Pi 是一个极简的终端编码 harness（运行框架）。它的设计理念是保持核心尽量小，通过 TypeScript extension（扩展）、skill（技能）、提示词模板、主题以及 pi 包来进行扩展。

## 快速开始

使用 npm 安装 Pi：

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
```

`--ignore-scripts` 会在安装期间禁用依赖的生命周期脚本。常规的 npm 安装并不需要 Pi 运行任何安装脚本。

在 Linux 或 macOS 上，也可以使用安装脚本：

```bash
curl -fsSL https://pi.dev/install.sh | sh
```

要卸载 pi 本体，curl 与 npm 两种安装方式都使用 npm：

```bash
npm uninstall -g @earendil-works/pi-coding-agent
```

如果是通过 pnpm、Yarn 或 Bun 安装的，请使用对应的全局卸载命令：`pnpm remove -g @earendil-works/pi-coding-agent`、`yarn global remove @earendil-works/pi-coding-agent` 或 `bun uninstall -g @earendil-works/pi-coding-agent`。

然后在一个项目目录中运行它：

```bash
pi
```

订阅制 provider 通过 `/login` 认证，或者在启动 pi 之前设置 API key（例如 `ANTHROPIC_API_KEY`）。

完整的首次运行流程请参见[快速上手](quickstart.md)。

## 从这里开始

- [快速上手](quickstart.md) - 安装、认证并运行第一个 session。
- [使用 Pi](usage.md) - 交互模式、斜杠命令、上下文文件与 CLI 参考。
- [Provider](providers.md) - 内置 provider 的订阅与 API key 配置。
- [llama.cpp](llama-cpp.md) - 运行本地路由器并通过 `/llama` 管理模型。
- [安全](security.md) - 项目信任、沙箱边界与漏洞报告。
- [容器化](containerization.md) - 通过 Gondolin、Docker 或 OpenShell 为 pi 提供沙箱。
- [设置](settings.md) - 全局与项目设置。
- [快捷键](keybindings.md) - 默认快捷键与自定义按键绑定。
- [会话](sessions.md) - session 管理、会话分支与树状导航。
- [上下文压缩](compaction.md) - 上下文压缩与分支摘要。

## 自定义

- [Extension](extensions.md) - 用于工具、命令、事件与自定义 UI 的 TypeScript 模块。
- [Skill](skills.md) - 可复用、按需加载能力的 Agent Skills。
- [提示词模板](prompt-templates.md) - 通过斜杠命令展开的可复用提示词。
- [主题](themes.md) - 内置与自定义终端主题。
- [Pi 包](packages.md) - 打包并分享 extension、skill、提示词与主题。
- [自定义模型](models.md) - 为受支持的 provider API 添加模型条目。
- [自定义 provider](custom-provider.md) - 实现自定义 API 与 OAuth 流程。

## 编程方式使用

- [SDK](sdk.md) - 在 Node.js 应用中嵌入 pi。
- [RPC 模式](rpc.md) - 通过 stdin/stdout JSONL 集成。
- [JSON 事件流模式](json.md) - 输出结构化事件的 print 模式。
- [TUI 组件](tui.md) - 为 extension 构建自定义终端 UI。

## 参考

- [Session 格式](session-format.md) - JSONL session 文件格式、条目类型与 SessionManager API。

## 平台配置

- [Windows](windows.md)
- [Android 上的 Termux](termux.md)
- [tmux](tmux.md)
- [终端配置](terminal-setup.md)
- [Shell 别名](shell-aliases.md)

## 开发

- [开发](development.md) - 本地环境搭建、项目结构与调试。
