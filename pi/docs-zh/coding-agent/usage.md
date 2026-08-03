> **译文** | 原文：[`packages/coding-agent/docs/usage.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/usage.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 使用 Pi

本页汇集了快速上手页面容纳不下的日常使用细节。

## 交互模式

<p align="center"><img src="https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/images/interactive-mode.png" alt="交互模式" width="600"></p>

界面分为四个主要区域：

- **启动头部** —— 快捷键、已加载的上下文文件、提示词模板、skill 和 extension
- **消息区** —— 用户消息、助手回复、工具调用、工具结果、通知、错误以及 extension UI
- **编辑器** —— 输入区域；边框颜色指示当前思考级别
- **底栏** —— 工作目录、session 名称、token/缓存用量、费用、上下文用量和当前模型

编辑器可以被内置 UI（如 `/settings`）或自定义 extension UI 临时替换。

### 编辑器功能

| 功能 | 用法 |
|---------|-----|
| 文件引用 | 输入 `@` 模糊搜索项目文件 |
| 路径补全 | 按 Tab 补全路径 |
| 多行输入 | Shift+Enter，Windows Terminal 上为 Ctrl+Enter |
| 复制回复 | Ctrl+X 复制最后一条助手消息；在 `/tree` 中复制当前选中的消息 |
| 图片 | Ctrl+V 粘贴（Windows 上为 Alt+V），或直接拖进终端 |
| Shell 命令 | `!command` 执行并把输出发送给模型 |
| 隐藏式 shell 命令 | `!!command` 执行但不把输出发送给模型 |
| 外部编辑器 | Ctrl+G 打开 `externalEditor`、`$VISUAL`、`$EDITOR`，Windows 上为记事本，其他平台为 `nano` |

所有快捷键及自定义方式参见[快捷键](keybindings.md)。

## 斜杠命令

在编辑器中输入 `/` 打开命令补全。extension 可以注册自定义命令，skill 以 `/skill:name` 形式可用，提示词模板通过 `/templatename` 展开。

| 命令 | 说明 |
|---------|-------------|
| `/login`、`/logout` | 管理 OAuth 或 API key 凭据 |
| [`/llama`](llama-cpp.md) | 下载、加载和卸载 llama.cpp 路由模型 |
| `/model` | 切换模型 |
| `/scoped-models` | 启用/禁用参与 Ctrl+P 轮换的模型 |
| `/settings` | 思考级别、主题、消息投递、传输方式 |
| `/resume` | 从历史 session 中选择 |
| `/new` | 开始新 session |
| `/name <name>` | 设置 session 显示名称 |
| `/session` | 显示 session 文件、ID、消息数、token 用量和费用 |
| `/tree` | 跳转到 session 中的任意节点并从那里继续 |
| `/trust` | 保存项目信任决定，供未来 session 使用 |
| `/fork` | 从之前的某条用户消息创建新 session |
| `/clone` | 把当前活动分支复制为新 session |
| `/compact [prompt]` | 手动进行上下文压缩，可附带自定义指令 |
| `/copy` | 复制最后一条助手消息到剪贴板 |
| `/export [file]` | 将 session 导出为 HTML 或 JSONL |
| `/import <file>` | 从 JSONL 文件导入并恢复 session |
| `/share` | 上传为私有 GitHub gist，生成可分享的 HTML 链接 |
| `/reload` | 重新加载快捷键、extension、skill、提示词、主题和上下文文件 |
| `/hotkeys` | 显示所有键盘快捷键 |
| `/changelog` | 显示版本历史 |
| `/quit` | 退出 pi |

## 消息队列

在 agent 仍在工作时，你就可以提交消息：

- **Enter** 将消息加入 steering（引导）队列，在当前助手轮次执行完其工具调用后投递。
- **Alt+Enter** 将消息加入后续消息队列，在 agent 完成全部工作后投递。
- **Escape** 中止执行，并把已排队的消息还原到编辑器。
- **Alt+Up** 将已排队的消息取回编辑器。

在 Windows Terminal 上，Alt+Enter 默认是全屏切换。如果希望 pi 接收到该快捷键，请按[终端设置](terminal-setup.md)中的说明重新映射。

投递方式可在[设置](settings.md)中通过 `steeringMode` 和 `followUpMode` 配置。

## 会话

Session 会自动保存到 `~/.pi/agent/sessions/`，按工作目录组织。

```bash
pi -c                  # 继续最近的 session
pi -r                  # 浏览并选择 session
pi --no-session        # 临时模式；不保存
pi --name "my task"    # 启动时设置 session 显示名称
pi --session <path|id> # 使用指定的 session 文件或 session ID
pi --fork <path|id>    # 把某个 session fork 成新 session 文件
```

常用的 session 命令：

- `/session` 显示当前 session 文件和 ID。
- `/tree` 在文件内的 session 树中导航，并可为被放弃的分支生成摘要。
- `/fork` 从更早的某条用户消息创建新 session。
- `/clone` 把当前活动分支复制为新 session 文件。
- `/compact` 对较早的消息做摘要以释放上下文。

详见[会话](sessions.md)与[上下文压缩](compaction.md)。

## 上下文文件

Pi 在启动时从以下位置加载 `AGENTS.md` 或 `CLAUDE.md`：

- `~/.pi/agent/AGENTS.md`（全局指令）
- 从当前工作目录向上逐级遍历的各父目录
- 当前目录

上下文文件可用于记录项目约定、常用命令、安全规则和偏好。使用 `--no-context-files` 或 `-nc` 禁用加载。

### 系统提示词文件

用以下文件替换默认系统提示词：

- 项目级：`.pi/SYSTEM.md`
- 全局级：`~/.pi/agent/SYSTEM.md`

若只想在默认提示词后追加而不替换，可在上述任一位置放置 `APPEND_SYSTEM.md`。

### 项目信任

交互模式启动时，如果项目文件夹包含项目级设置、资源或项目 `.agents/skills`，且该文件夹及其父文件夹在 `~/.pi/agent/trust.json` 中没有已保存的决定，pi 会先询问是否信任。信任一个项目后，pi 才能加载 `.pi/settings.json` 和 `.pi` 资源、安装缺失的项目包、执行项目 extension。

在做出信任决定之前，pi 只加载上下文文件、用户/全局 extension 以及 CLI `-e` 指定的 extension，以便它们能处理 `project_trust` 事件。项目级 extension、项目包管理的 extension 和项目设置只有在项目被信任后才加载。当切换到来自其他工作目录（且其信任状态尚未在当前进程中确定）的 session 时，同样适用这一区分。

非交互模式（`-p`、`--mode json` 和 `--mode rpc`）不显示信任询问。若没有适用的已保存信任决定，它们使用全局设置中的 `defaultProjectTrust`：`ask`（默认）和 `never` 会忽略这些项目资源，而 `always` 会信任它们。传入 `--approve`/`-a` 或 `--no-approve`/`-na` 可为单次运行覆盖项目信任。

若没有适用的 extension 或已保存的决定，`defaultProjectTrust` 控制回退行为。可在 `~/.pi/agent/settings.json` 中把它设为 `"ask"`、`"always"` 或 `"never"`，或通过 `/settings` 修改。

`pi config` 和包管理命令使用相同的项目信任流程，唯一例外是 `pi update` 从不询问。传入 `--approve` 为单条命令信任项目级设置，或传入 `--no-approve` 忽略它们。

在交互模式中使用 `/trust` 保存项目信任决定供未来 session 使用，包括对直接父文件夹的信任。它只写入 `~/.pi/agent/trust.json`；当前 session 不会重新加载，所以需要重启 pi 才能生效。


## 导出与分享会话

使用 `/export [file]` 将 session 写为 HTML。

使用 `/share` 上传为私有 GitHub gist，并获得可分享的 HTML 链接。

如果你用 pi 做开源工作，并希望把 session 发布出来用于模型、prompt、tool 和评测研究，参见 [`badlogic/pi-share-hf`](https://github.com/badlogic/pi-share-hf)。它会把 session 发布到 Hugging Face 数据集。

## CLI 参考

```bash
pi [options] [@files...] [messages...]
```

### 包管理命令

```bash
pi install <source> [-l]     # 安装 pi 包，-l 表示项目级安装
pi remove <source> [-l]      # 移除 pi 包
pi uninstall <source> [-l]   # remove 的别名
pi update [source|self|pi]   # 只更新 pi，或更新某个包来源
pi update --all              # 更新 pi 和所有包；核对固定的 git 引用
pi update --extensions       # 只更新包；核对固定的 git 引用
pi update --models           # 只刷新模型目录
pi update --self             # 只更新 pi
pi update --extension <src>  # 更新单个包
pi list                      # 列出已安装的包
pi config                    # 启用/禁用包资源
```

这些命令管理 pi 包，`pi update` 还可以更新 pi CLI 本身。卸载 pi 本体参见[快速上手](quickstart.md#卸载)。`pi config` 和项目包命令接受 `--approve`/`--no-approve`，为单条命令信任或忽略项目级设置。`pi update` 从不询问项目信任。

包来源与安全注意事项参见 [Pi 包](packages.md)。

### 模式

| 标志 | 说明 |
|------|-------------|
| 默认 | 交互模式 |
| `-p`、`--print` | 打印回复后退出 |
| `--mode json` | 以 JSON 行输出所有事件；参见 [JSON 模式](json.md) |
| `--mode rpc` | 通过 stdin/stdout 的 RPC 模式；参见 [RPC 模式](rpc.md) |
| `--export <in> [out]` | 将 session 导出为 HTML |

在 print 模式下，pi 还会读取管道 stdin 并合并进初始 prompt：

```bash
cat README.md | pi -p "Summarize this text"
```

### 模型选项

| 选项 | 说明 |
|--------|-------------|
| `--provider <name>` | provider 名称，如 `anthropic`、`openai`、`google` |
| `--model <pattern>` | 模型 pattern 或 ID；支持 `provider/id` 及可选的 `:<thinking>` 后缀 |
| `--api-key <key>` | API key，覆盖环境变量 |
| `--thinking <level>` | `off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max` |
| `--models <patterns>` | 逗号分隔的 pattern 列表，用于 Ctrl+P 模型轮换 |
| `--list-models [search]` | 列出可用模型 |

### 会话选项

| 选项 | 说明 |
|--------|-------------|
| `-c`、`--continue` | 继续最近的 session |
| `-r`、`--resume` | 浏览并选择 session |
| `--session <path\|id>` | 使用指定的 session 文件或部分 UUID |
| `--fork <path\|id>` | 把 session 文件或部分 UUID fork 成新 session |
| `--session-dir <dir>` | 自定义 session 存储目录 |
| `--no-session` | 临时模式；不保存 |
| `--name <name>`、`-n <name>` | 启动时设置 session 显示名称 |

### Tool 选项

| 选项 | 说明 |
|--------|-------------|
| `--tools <list>`、`-t <list>` | 仅允许指定的内置、extension 和自定义 tool |
| `--exclude-tools <list>`、`-xt <list>` | 禁用指定的内置、extension 和自定义 tool |
| `--no-builtin-tools`、`-nbt` | 禁用内置 tool，但保留 extension/自定义 tool |
| `--no-tools`、`-nt` | 禁用所有 tool |

内置 tool：`read`、`bash`、`edit`、`write`、`grep`、`find`、`ls`。

### 资源选项

| 选项 | 说明 |
|--------|-------------|
| `-e`、`--extension <source>` | 从路径、npm 或 git 加载 extension；可重复 |
| `--no-extensions` | 禁用 extension 发现 |
| `--skill <path>` | 加载 skill；可重复 |
| `--no-skills` | 禁用 skill 发现 |
| `--prompt-template <path>` | 加载提示词模板；可重复 |
| `--no-prompt-templates` | 禁用提示词模板发现 |
| `--theme <path>` | 加载主题；可重复 |
| `--no-themes` | 禁用主题发现 |
| `--no-context-files`、`-nc` | 禁用 `AGENTS.md` 和 `CLAUDE.md` 发现 |

将 `--no-*` 与显式标志组合使用，可以忽略设置、只加载你需要的内容。示例：

```bash
pi --no-extensions -e ./my-extension.ts
```

### 其他选项

| 选项 | 说明 |
|--------|-------------|
| `--system-prompt <text>` | 替换默认提示词；上下文文件和 skill 仍会被附加 |
| `--append-system-prompt <text>` | 追加到系统提示词 |
| `--verbose` | 强制显示详细启动信息 |
| `-a`、`--approve` | 本次运行信任项目级文件 |
| `-na`、`--no-approve` | 本次运行忽略项目级文件 |
| `-h`、`--help` | 显示帮助 |
| `-v`、`--version` | 显示版本 |

### 文件参数

文件加 `@` 前缀即可包含进消息：

```bash
pi @prompt.md "Answer this"
pi -p @screenshot.png "What's in this image?"
pi @code.ts @test.ts "Review these files"
```

### 示例

```bash
# 带初始 prompt 的交互模式
pi "List all .ts files in src/"

# 非交互
pi -p "Summarize this codebase"

# 非交互 + 管道 stdin
cat README.md | pi -p "Summarize this text"

# 命名的一次性 session
pi --name "release audit" -p "Audit this repository"

# 换一个模型
pi --provider openai --model gpt-4o "Help me refactor"

# 带 provider 前缀的模型
pi --model openai/gpt-4o "Help me refactor"

# 带思考级别简写的模型
pi --model sonnet:high "Solve this complex problem"

# 限制模型轮换范围
pi --models "claude-*,gpt-4o"

# 只读模式
pi --tools read,grep,find,ls -p "Review the code"

# 禁用某个 extension 或内置 tool，其余保持可用
pi --exclude-tools ask_question
```

### 环境变量

| 变量 | 说明 |
|----------|-------------|
| `PI_CODING_AGENT_DIR` | 覆盖配置目录；默认 `~/.pi/agent` |
| `PI_CODING_AGENT_SESSION_DIR` | 覆盖 session 存储目录；会被 `--session-dir` 覆盖 |
| `PI_PACKAGE_DIR` | 覆盖包目录，适用于 Nix/Guix store 路径 |
| `PI_OFFLINE` | 禁用启动时的网络操作，包括更新检查、包更新检查以及安装/更新遥测 |
| `PI_SKIP_VERSION_CHECK` | 跳过启动时的 Pi 版本更新检查。这会阻止向 `pi.dev` 发起最新版本请求 |
| `PI_TELEMETRY` | 覆盖安装/更新遥测和 provider 归因请求头：`1`/`true`/`yes` 或 `0`/`false`/`no`。这不会禁用更新检查 |
| `PI_CACHE_RETENTION` | 设为 `long` 可在支持的 provider 上启用更长的 prompt 缓存 |
| `VISUAL`、`EDITOR` | `externalEditor` 未设置时 Ctrl+G 的外部编辑器回退；Windows 上默认记事本，其他平台默认 `nano` |

## 设计理念

Pi 保持核心精简，把与具体工作流相关的行为交给 extension、skill、提示词模板和 pi 包。

它有意不内置 MCP、子 agent、权限弹窗、计划模式、待办事项和后台 bash。你可以把这些工作流构建或安装为 extension 或 pi 包，或者借助容器、tmux 等外部工具。

完整的设计理由请阅读[博客文章](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/)。
