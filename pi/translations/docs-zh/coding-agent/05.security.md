> **译文** | 原文：[`packages/coding-agent/docs/security.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/security.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 安全

Pi 是一个本地编码 agent。它以启动它的用户账户的权限运行，并将该用户可写的文件视为处于同一个本地信任边界之内。

## 项目信任

项目信任（project trust）控制 pi 是否加载项目本地的设置、资源、包和 extension。它不是沙箱，也不会在你开始在某个目录中工作之后限制模型能让工具做什么。

当 pi 从当前工作目录出发发现以下任意一项时，即认为该项目包含需要信任的资源：

- `.pi/settings.json`
- `.pi/extensions`、`.pi/skills`、`.pi/prompts` 或 `.pi/themes`
- `.pi/SYSTEM.md` 或 `.pi/APPEND_SYSTEM.md`
- 当前目录或某个祖先目录中的项目级 `.agents/skills`

一个空的 `.pi` 目录本身不算需要信任的项目资源。

当交互式 session 在包含需信任资源的项目中启动，且当前目录或某个父目录没有已保存的决定时，pi 会遵循全局设置中的 `defaultProjectTrust`。其默认值为 `"ask"`，即在 UI 可用时询问是否信任该项目。已保存的决定按规范化目录存储在 `~/.pi/agent/trust.json` 中；当前路径或父路径上最近的已保存决定优先于全局默认值生效。

信任一个项目后，pi 才会加载需要信任的项目资源，包括：

- `.pi/settings.json`
- `.pi` 资源，例如 extension、skill、提示词模板、主题以及系统提示词文件
- 通过项目设置配置的缺失项目包
- 项目本地 extension 以及由项目包管理的 extension

拒绝信任会跳过这些受保护的资源。除非上下文加载被禁用，`AGENTS.md` 和 `CLAUDE.md` 上下文文件无论项目信任与否都会被加载。在信任状态确定之前，pi 只加载上下文文件、用户级/全局 extension 以及 CLI `-e` 指定的 extension。用户级/全局及 CLI extension 可以处理 `project_trust` 事件；第一个返回是/否决定的 extension 拥有该决定权。

非交互模式（`-p`、`--mode json` 和 `--mode rpc`）不会显示信任提示。在没有适用的已保存信任决定时，`defaultProjectTrust: "ask"` 和 `"never"` 会忽略这些资源，而 `"always"` 会信任它们。使用 `--approve`/`-a` 或 `--no-approve`/`-na` 可以为单次运行覆盖项目信任。

## 没有内置沙箱

Pi 不包含内置沙箱。内置工具可以以 pi 进程的权限读文件、写文件、编辑文件以及运行 shell 命令。Extension 是以相同权限运行的 TypeScript 模块。包安装、shell 命令、语言服务器、测试命令以及其它开发者工具都表现为普通的本地进程。

这是有意为之。Pi 的设计目标就是操作本地源码树、调用项目工具链，并与用户既有的开发环境集成。一个不完整的进程内沙箱很容易被误解为安全边界，而实际上它仍然依赖宿主的 shell、文件系统、包管理器、凭据以及 extension 代码。真正的隔离必须来自操作系统或虚拟化/容器边界。

项目信任只是一道输入加载的防线。它防止一个仓库在你批准之前悄悄改变 pi 的设置或 extension。它并不能让不受信任的代码、不受信任的 prompt 或不受信任的模型输出变得安全。来自仓库文件、注释、文档、上下文文件或构建产物的提示词注入（prompt injection）属于本地 agent 的固有风险，pi 无法可靠地防止。

## 运行不受信任或无人监督的工作

对于不受信任的仓库、你不打算密切监督的生成代码、或无人值守的自动化任务，请在受隔离的环境中运行 pi。使用容器、VM、micro-VM、远程沙箱或策略控制型沙箱，并只提供任务所需的文件与凭据。

常见模式记录在[容器化](containerization.md)中：

- 将整个 `pi` 进程放在容器/沙箱内运行
- 在宿主机上运行 pi，同时把内置工具的执行路由到 Gondolin micro-VM 中
- 只挂载 agent 应该访问的工作区路径
- 除非容器需要访问宿主机的 session、设置与凭据，否则不要挂载宿主机的 `~/.pi/agent`
- 只传入所需的最少 API key，或使用短期凭据
- 任务不需要网络时限制网络访问
- 在把结果复制回受信任系统之前审查 diff 与输出

如果你以读写方式 bind-mount 宿主机工作区，容器或 VM 内的写入仍会修改宿主机文件。当你需要更强的防意外写入保护时，请使用只读挂载，或以复制的方式在沙箱内外传递文件。

## 报告安全问题

要报告安全问题，请遵循仓库的[安全策略](https://github.com/earendil-works/pi-mono/blob/main/SECURITY.md)。请勿为安全敏感的报告开公开 issue。

符合预期的本地 agent 行为、内置沙箱的缺失、来自不受信任内容的提示词注入、以及用户自行安装的 extension 或 skill 的行为，通常都在安全边界之外——除非报告能证明真实的权限边界绕过，或者展示了 pi 授予了本地用户原本不具备的访问权限。
