> **译文** | 原文：[`packages/coding-agent/docs/environment-variables.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/environment-variables.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# 环境变量

Pi 以三种方式使用环境变量：

- `PI_OFFLINE` 等变量用于配置 Pi 进程。
- Pi 设置进程标记，让子进程能够识别启动它们的 agent 是 Pi。
- LLM 可调用的 bash 工具所运行的命令会收到描述当前 session 的 `PI_*` 变量。

Provider API key 变量单独记录在 [Providers](03.providers.md#环境变量或认证文件) 中。

## 进程标记

CLI 和 RPC 入口点会设置两个进程标记：

- `AI_AGENT=pi` 是通用标记，让工具能够识别启动该进程的 agent 是 Pi。
- `PI_CODING_AGENT=true` 是 Pi 专用标记，让子进程能够检测到自己运行在 Pi 内部。

子进程会继承这两个标记。它们不针对特定 session；通过 SDK 嵌入 Pi 时也不会自动设置。

## Bash 工具的 Session 环境

bash 工具运行的命令会收到当前 Pi session 状态：

| 变量 | 描述 |
|----------|-------------|
| `PI_SESSION_ID` | 当前 session ID |
| `PI_SESSION_FILE` | 当前 session JSONL 文件的绝对路径；临时 session 不设置 |
| `PI_PROVIDER` | 当前选择的模型 provider |
| `PI_MODEL` | 当前选择的模型 ID |
| `PI_REASONING_LEVEL` | 当前有效推理级别：`off`、`minimal`、`low`、`medium`、`high`、`xhigh` 或 `max` |

每条命令启动时才解析这些值。因此，切换模型或更改推理级别会影响下一条 bash 命令，无需重启 Pi。`PI_PROVIDER` 和 `PI_MODEL` 标识所选择的 Pi 模型，而不是 router 内部可能选择的其他上游模型。

被问到正在运行哪个模型或 provider 时，应检查这些变量，不要根据 system prompt 推断：

```bash
printf '%s/%s\n' "$PI_PROVIDER" "$PI_MODEL"
printf 'reasoning=%s session=%s\n' "$PI_REASONING_LEVEL" "$PI_SESSION_ID"
```

对于持久化 session，可以直接检查 session 文件：

```bash
if [ -n "$PI_SESSION_FILE" ]; then
  tail -n 1 "$PI_SESSION_FILE"
fi
```

这些变量会注入 LLM 可调用的 bash 工具，不会注入用户输入的 `!` 或 `!!` 命令。

### 自定义 Bash 工具

使用 `createBashTool()` 创建的 bash 工具在 Pi 中注册后，默认会暴露 session 环境。注入发生在 `spawnHook` 之前，因此 hook 可以从 `ctx.env` 获取这些变量：

```typescript
const bashTool = createBashTool(cwd, {
  spawnHook: (ctx) => ({
    ...ctx,
    env: { ...ctx.env, CI: "1" },
  }),
});
```

可以独立于 spawn hook 禁用 session 元信息：

```typescript
const bashTool = createBashTool(cwd, {
  exposeSessionEnvironment: false,
  spawnHook: (ctx) => ctx,
});
```

禁用后，Pi 会移除继承的这些变量，避免嵌套 Pi 进程暴露过时的父 session 元信息。

## Pi 进程配置

以下变量由 Pi 自身读取：

| 变量 | 描述 |
|----------|-------------|
| `PI_CODING_AGENT_DIR` | 覆盖配置目录；默认为 `~/.pi/agent` |
| `PI_CODING_AGENT_SESSION_DIR` | 覆盖 session 存储目录；会被 `--session-dir` 覆盖 |
| `PI_PACKAGE_DIR` | 覆盖包目录，适用于 Nix/Guix store 路径 |
| `PI_OFFLINE` | 禁用启动时的网络操作，包括更新检查、包更新和安装/更新 telemetry |
| `PI_SKIP_VERSION_CHECK` | 禁用对 `pi.dev` 最新版本的请求 |
| `PI_TELEMETRY` | 覆盖安装/更新 telemetry 和 provider attribution header：`1`/`true`/`yes` 或 `0`/`false`/`no` |
| `PI_CACHE_RETENTION` | 设为 `long`，在支持的 provider 上启用延长的 prompt caching |
| `PI_SHARE_VIEWER_URL` | 覆盖 `/share` 使用的 base URL |
| `PI_HARDWARE_CURSOR` | 设为 `1` 以显示硬件光标；参见[终端设置](terminal-setup.md) |
| `PI_TUI_ESC_TIMEOUT` | 单独收到 ESC 后等待多久才将其视为 Escape，单位为毫秒；SSH 下默认 `100`，其他环境默认 `10`。如果 Alt 组合键被误读为 Escape，请增大该值 |
| `VISUAL`, `EDITOR` | 未设置 `externalEditor` 时使用的外部编辑器 fallback |
| `HTTP_PROXY`, `HTTPS_PROXY` | 代理出站 HTTP 请求 |

`ANTHROPIC_API_KEY`、`OPENAI_API_KEY` 等 provider 凭据及 cloud provider 配置列在 [Providers](03.providers.md#环境变量或认证文件) 中。
