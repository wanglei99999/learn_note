> **译文** | 原文：[`packages/coding-agent/docs/quickstart.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/quickstart.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 快速上手

本页带你从安装走到第一个有用的 pi session。

## 安装

Pi 以 npm 包的形式发布：

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
```

`--ignore-scripts` 会在安装期间禁用依赖的生命周期脚本。常规的 npm 安装并不需要 Pi 运行任何安装脚本。

### 卸载

使用当初安装 pi 的那个包管理器卸载。curl 安装脚本底层使用全局 npm，因此 curl 与 npm 两种安装方式都用 npm 卸载：

```bash
# curl 安装脚本或 npm install -g
npm uninstall -g @earendil-works/pi-coding-agent

# pnpm
pnpm remove -g @earendil-works/pi-coding-agent

# Yarn
yarn global remove @earendil-works/pi-coding-agent

# Bun
bun uninstall -g @earendil-works/pi-coding-agent
```

卸载 pi 后，设置、凭据、session 以及已安装的 pi 包仍会保留在 `~/.pi/agent/` 中。

接下来，在你希望它工作的项目目录中启动 pi：

```bash
cd /path/to/project
pi
```

## 认证

Pi 可以通过 `/login` 使用订阅制 provider，也可以通过环境变量或 auth 文件使用 API key 类 provider。

### 方式一：订阅登录

启动 pi 并运行：

```text
/login
```

然后选择一个 provider。内置的订阅登录包括 Claude Pro/Max、ChatGPT Plus/Pro（Codex）以及 GitHub Copilot。

### 方式二：API key

在启动 pi 之前设置 API key：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pi
```

也可以运行 `/login` 并选择一个 API key 类 provider，把 key 保存到 `~/.pi/agent/auth.json`。

所有受支持的 provider、环境变量以及云 provider 配置，请参见 [Provider](providers.md)。

## 第一个 session

pi 启动后，输入一个请求并按回车：

```text
Summarize this repository and tell me how to run its checks.
```

默认情况下，pi 为模型提供四个工具：

- `read` - 读取文件
- `write` - 创建或覆盖文件
- `edit` - 修补文件
- `bash` - 运行 shell 命令

其余内置的只读工具（`grep`、`find`、`ls`）可通过工具选项启用。Pi 运行在你的当前工作目录中，并且可以修改其中的文件。如果希望方便回滚，请使用 git 或其它保存点（checkpoint）工作流。

## 给 pi 项目指令

Pi 在启动时会加载上下文文件。添加一个 `AGENTS.md` 文件来告诉它如何在项目中工作：

```markdown
# Project Instructions

- Run `npm run check` after code changes.
- Do not run production migrations locally.
- Keep responses concise.
```

Pi 会加载：

- `~/.pi/agent/AGENTS.md`：全局指令
- 各上级目录以及当前目录中的 `AGENTS.md` 或 `CLAUDE.md`

修改上下文文件后，重启 pi 或运行 `/reload`。

## 常见用法

### 引用文件

在编辑器中输入 `@` 进行文件模糊搜索，或在命令行上传入文件：

```bash
pi @README.md "Summarize this"
pi @src/app.ts @src/app.test.ts "Review these together"
```

图片或文本可以用 Ctrl+V 粘贴（Windows 上为 Alt+V）；在受支持的终端里也可以直接把图片拖进来。

### 运行 shell 命令

在交互模式下：

```text
!npm run lint
```

命令的输出会发送给模型。使用 `!!command` 可以运行命令但不把输出加入模型上下文。

### 切换模型

使用 `/model` 或 Ctrl+L 选择模型。使用 Shift+Tab 循环切换思考级别。使用 Ctrl+P / Shift+Ctrl+P 在按作用域配置的模型之间循环切换。

### 稍后继续

Session 会自动保存：

```bash
pi -c                  # 继续最近的 session
pi -r                  # 浏览历史 session
pi --name "my task"    # 启动时设置 session 显示名称
pi --session <path|id> # 打开指定 session
```

在 pi 内部，使用 `/resume`、`/new`、`/tree`、`/fork` 和 `/clone` 管理 session。

### 非交互模式

一次性 prompt：

```bash
pi -p "Summarize this codebase"
cat README.md | pi -p "Summarize this text"
pi -p @screenshot.png "What's in this image?"
```

使用 `--mode json` 输出 JSON 事件，或使用 `--mode rpc` 进行进程集成。

## 下一步

- [使用 Pi](usage.md) - 交互模式、斜杠命令、session、上下文文件与 CLI 参考。
- [Provider](providers.md) - 认证与模型配置。
- [设置](settings.md) - 全局与项目配置。
- [快捷键](keybindings.md) - 快捷键与自定义。
- [Pi 包](packages.md) - 安装共享的 extension、skill、提示词与主题。

平台说明：[Windows](windows.md)、[Termux](termux.md)、[tmux](tmux.md)、[终端配置](terminal-setup.md)、[Shell 别名](shell-aliases.md)。
