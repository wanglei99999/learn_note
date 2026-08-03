> **译文** | 原文：[`packages/coding-agent/docs/settings.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 设置

Pi 使用 JSON 设置文件，项目设置会覆盖全局设置。

| 位置 | 作用域 |
|----------|-------|
| `~/.pi/agent/settings.json` | 全局（所有项目） |
| `.pi/settings.json` | 项目（当前目录） |

可直接编辑文件，或用 `/settings` 修改常用选项。

## 项目信任

交互模式启动时，如果项目文件夹包含项目级设置、资源或项目 `.agents/skills`，且该文件夹及其父文件夹在 `~/.pi/agent/trust.json` 中没有已保存的决定，pi 会先询问是否信任。信任一个项目后，pi 才能加载 `.pi/settings.json` 和 `.pi` 资源、安装缺失的项目包、执行项目 extension。

非交互模式（`-p`、`--mode json` 和 `--mode rpc`）不显示信任询问。若没有适用的已保存信任决定，它们使用全局设置中的 `defaultProjectTrust`：`ask`（默认）和 `never` 会忽略这些项目资源，而 `always` 会信任它们。传入 `--approve`/`-a` 或 `--no-approve`/`-na` 可为单次运行覆盖项目信任。

若没有适用的 extension 或已保存的决定，`defaultProjectTrust` 控制回退行为。可在 `~/.pi/agent/settings.json` 中把它设为 `"ask"`、`"always"` 或 `"never"`，或通过 `/settings` 修改。

`pi config` 和包管理命令使用相同的项目信任流程，唯一例外是 `pi update` 从不询问。传入 `--approve` 为单条命令信任项目级设置，或传入 `--no-approve` 忽略它们。

在交互模式中使用 `/trust` 保存项目信任决定供未来 session 使用，包括对直接父文件夹的信任。它只写入 `~/.pi/agent/trust.json`；当前 session 不会重新加载，所以需要重启 pi 才能生效。

## 全部设置项

### 模型与思考

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `defaultProvider` | string | - | 默认 provider（如 `"anthropic"`、`"openai"`） |
| `defaultModel` | string | - | 默认模型 ID |
| `defaultThinkingLevel` | string | - | `"off"`、`"minimal"`、`"low"`、`"medium"`、`"high"`、`"xhigh"`、`"max"` |
| `hideThinkingBlock` | boolean | `false` | 在输出中隐藏思考块 |
| `showCacheMissNotices` | boolean | `false` | 当出现明显的 prompt 缓存未命中时，在会话记录中显示提示 |
| `thinkingBudgets` | object | - | 各思考级别的自定义 token 预算 |

#### thinkingBudgets

```json
{
  "thinkingBudgets": {
    "minimal": 1024,
    "low": 4096,
    "medium": 10240,
    "high": 32768
  }
}
```

### UI 与显示

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `theme` | string | `"dark"` | 主题名称（`"dark"`、`"light"` 或自定义） |
| `externalEditor` | string | 依次为 `$VISUAL`、`$EDITOR`，Windows 上为记事本，其他平台为 `nano` | Ctrl+G 外部编辑器命令；优先级高于环境变量 |
| `quietStartup` | boolean | `false` | 隐藏启动头部 |
| `defaultProjectTrust` | string | `"ask"` | 项目信任的回退行为：`"ask"`、`"always"` 或 `"never"`。仅限全局设置 |
| `collapseChangelog` | boolean | `false` | 更新后显示精简版更新日志 |
| `enableInstallTelemetry` | boolean | `true` | 在首次安装或通过更新日志检测到更新后，发送一次匿名的安装/更新版本 ping。不控制更新检查 |
| `enableAnalytics` | boolean | `false` | 选择性加入的分析数据共享。目前仅在实验性的首次运行设置流程（`PI_EXPERIMENTAL=1`）中询问 |
| `trackingId` | string | - | 分析跟踪标识符，在开启 `enableAnalytics` 时生成 |
| `doubleEscapeAction` | string | `"tree"` | 双击 Escape 的动作：`"tree"`、`"fork"` 或 `"none"` |
| `treeFilterMode` | string | `"default"` | `/tree` 的默认过滤器：`"default"`、`"no-tools"`、`"user-only"`、`"labeled-only"`、`"all"` |
| `editorPaddingX` | number | `0` | 输入编辑器的水平内边距（0-3） |
| `outputPad` | number | `1` | 用户消息、助手消息和思考块的水平内边距（0 或 1） |
| `autocompleteMaxVisible` | number | `5` | 自动补全下拉框最多显示的条目数（3-20） |
| `showHardwareCursor` | boolean | `false` | 显示终端光标，TUI 会为 IME 支持定位它 |

对于 VS Code，加上 `--wait` 让 pi 在编辑器退出后继续：

```json
{
  "externalEditor": "code --wait"
}
```

### 遥测与更新检查

`enableInstallTelemetry` 只控制发往 `https://pi.dev/api/report-install` 的匿名安装/更新 ping。关闭遥测并不会禁用更新检查；Pi 仍可能请求 `https://pi.dev/api/latest-version` 查询最新版本。

设置 `PI_SKIP_VERSION_CHECK=1` 可禁用 Pi 版本更新检查。使用 `--offline` 或 `PI_OFFLINE=1` 可禁用此处描述的所有启动网络操作，包括更新检查、包更新检查和安装/更新遥测。

### 网络

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `httpProxy` | string | - | HTTP 代理 URL，会应用为 `HTTP_PROXY` 和 `HTTPS_PROXY`。仅限全局设置。 |

```json
{
  "httpProxy": "http://127.0.0.1:7890"
}
```

### 警告

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `warnings.anthropicExtraUsage` | boolean | `true` | 当 Anthropic 订阅认证可能使用付费额外用量时显示警告 |

```json
{
  "warnings": {
    "anthropicExtraUsage": false
  }
}
```

### 上下文压缩

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `compaction.enabled` | boolean | `true` | 启用自动上下文压缩 |
| `compaction.reserveTokens` | number | `16384` | 为 LLM 回复预留的 token 数 |
| `compaction.keepRecentTokens` | number | `20000` | 保留（不做摘要）的近期 token 数 |

```json
{
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  }
}
```

### 分支摘要

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `branchSummary.reserveTokens` | number | `16384` | 为分支摘要预留的 token 数 |
| `branchSummary.skipPrompt` | boolean | `false` | 在 `/tree` 导航时跳过"是否总结分支？"询问（默认不生成摘要） |

### 重试

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `retry.enabled` | boolean | `true` | 对瞬时错误启用 agent 级自动重试 |
| `retry.maxRetries` | number | `3` | agent 级重试的最大次数 |
| `retry.baseDelayMs` | number | `2000` | agent 级指数退避的基础延迟（2s、4s、8s） |
| `retry.provider.timeoutMs` | number | SDK 默认值 | provider/SDK 请求超时（毫秒） |
| `retry.provider.maxRetries` | number | `0` | provider/SDK 重试次数 |
| `retry.provider.maxRetryDelayMs` | number | `60000` | 服务端要求的重试延迟上限，超过则直接失败（60 秒） |

当 provider 要求的重试延迟超过 `retry.provider.maxRetryDelayMs`（例如 Google 的"配额将在 5 小时后重置"）时，请求会立即失败并给出明确的错误信息，而不是静默等待。设为 `0` 可取消该上限。

除非确实需要 provider 级重试，否则请让 `retry.provider.maxRetries` 保持为 `0`。将其设为大于 `0` 可能导致 SDK/provider 的重试在 Pi 看到之前就处理了用量超限错误，在某些情况下会让 agent 一直阻塞到 provider 配额重置。

```json
{
  "retry": {
    "enabled": true,
    "maxRetries": 3,
    "baseDelayMs": 2000,
    "provider": {
      "timeoutMs": 3600000,
      "maxRetries": 0,
      "maxRetryDelayMs": 60000
    }
  }
}
```

### 消息投递

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `steeringMode` | string | `"one-at-a-time"` | steering 消息的发送方式：`"all"` 或 `"one-at-a-time"` |
| `followUpMode` | string | `"one-at-a-time"` | 后续消息的发送方式：`"all"` 或 `"one-at-a-time"` |
| `transport` | string | `"auto"` | 对支持多种传输方式的 provider 的首选传输：`"sse"`、`"websocket"`、`"websocket-cached"` 或 `"auto"` |
| `httpIdleTimeoutMs` | number | `300000` | HTTP 头/正文空闲超时（毫秒），也用于具有显式流空闲超时的 provider。设为 `0` 可禁用。 |
| `websocketConnectTimeoutMs` | number | `15000` | 支持 WebSocket 传输的 provider 的 WebSocket 连接/握手超时（毫秒）。设为 `0` 可禁用。 |

### 终端与图片

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `terminal.showImages` | boolean | `true` | 在终端中显示图片（如支持） |
| `terminal.imageWidthCells` | number | `60` | 终端内联图片的首选宽度（单位：终端单元格） |
| `terminal.clearOnShrink` | boolean | `false` | 内容收缩时清除空行（可能引起闪烁） |
| `images.autoResize` | boolean | `true` | 将图片缩放到最大 2000x2000 |
| `images.blockImages` | boolean | `false` | 阻止所有图片发送给 LLM |

### Shell

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `shellPath` | string | - | 自定义 shell 路径（例如 Windows 上的 Cygwin）；支持以 `~` 开头表示主目录 |
| `shellCommandPrefix` | string | - | 每条 bash 命令的前缀（例如 `"shopt -s expand_aliases"`） |
| `npmCommand` | string[] | - | npm 包查找/安装操作使用的命令 argv（例如 `["mise", "exec", "node@20", "--", "npm"]`） |

```json
{
  "npmCommand": ["mise", "exec", "node@20", "--", "npm"]
}
```

`npmCommand` 用于所有 npm 包管理器操作，包括安装、卸载以及 git 包内的依赖安装。用户级 npm 包安装在 `~/.pi/agent/npm/` 下；项目级 npm 包安装在 `.pi/npm/` 下。请按进程实际启动方式逐项填写 argv。配置了 `npmCommand` 后，git 包的依赖安装会使用普通的 `install`，以避免在包装器或其他包管理器中使用 npm 特有的标志。

### 会话

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `sessionDir` | string | - | session 文件的存储目录。接受绝对或相对路径，以及 `~`。 |

```json
{ "sessionDir": ".pi/sessions" }
```

当多个来源都指定了 session 目录时，优先级依次为 `--session-dir`、`PI_CODING_AGENT_SESSION_DIR`，最后是 settings.json 中的 `sessionDir`。

### 模型轮换

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `enabledModels` | string[] | - | Ctrl+P 模型轮换的模型 pattern（格式同 `--models` CLI 标志） |

```json
{
  "enabledModels": ["claude-*", "gpt-4o", "gemini-2*"]
}
```

### Markdown

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `markdown.codeBlockIndent` | string | `"  "` | 代码块的缩进 |

### 资源

以下设置定义 extension、skill、prompt 和主题的加载来源。

`~/.pi/agent/settings.json` 中的路径相对 `~/.pi/agent` 解析。`.pi/settings.json` 中的路径相对 `.pi` 解析。支持绝对路径和 `~`。

| 设置项 | 类型 | 默认值 | 说明 |
|---------|------|---------|-------------|
| `packages` | array | `[]` | 要从中加载资源的 npm/git 包 |
| `extensions` | string[] | `[]` | 本地 extension 文件路径或目录 |
| `skills` | string[] | `[]` | 本地 skill 文件路径或目录 |
| `prompts` | string[] | `[]` | 本地提示词模板路径或目录 |
| `themes` | string[] | `[]` | 本地主题文件路径或目录 |
| `enableSkillCommands` | boolean | `true` | 将 skill 注册为 `/skill:name` 命令 |

数组支持 glob pattern 和排除规则。用 `!pattern` 排除。用 `+path` 强制包含某个精确路径，用 `-path` 强制排除某个精确路径。

#### packages

字符串形式表示加载包内的全部资源：

```json
{
  "packages": ["pi-skills", "@org/my-extension"]
}
```

对象形式可筛选要加载的资源：

```json
{
  "packages": [
    {
      "source": "pi-skills",
      "skills": ["brave-search", "transcribe"],
      "extensions": []
    }
  ]
}
```

包管理详情参见 [packages.md](packages.md)。

## 示例

```json
{
  "defaultProvider": "anthropic",
  "defaultModel": "claude-sonnet-4-20250514",
  "defaultThinkingLevel": "medium",
  "theme": "dark",
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  },
  "retry": {
    "enabled": true,
    "maxRetries": 3
  },
  "enabledModels": ["claude-*", "gpt-4o"],
  "warnings": {
    "anthropicExtraUsage": true
  },
  "packages": ["pi-skills"]
}
```

## 项目级覆盖

项目设置（`.pi/settings.json`）覆盖全局设置。嵌套对象会做合并：

```json
// ~/.pi/agent/settings.json（全局）
{
  "theme": "dark",
  "compaction": { "enabled": true, "reserveTokens": 16384 }
}

// .pi/settings.json（项目）
{
  "compaction": { "reserveTokens": 8192 }
}

// 合并结果
{
  "theme": "dark",
  "compaction": { "enabled": true, "reserveTokens": 8192 }
}
```
