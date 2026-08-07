# Pi Coding Agent：配置与资源带读笔记

这份笔记从 `settings.md` 开始，记录 Pi 的配置、资源加载和相关文档带读内容。

目前读过：

- `settings.md`

## 1. settings.md：Pi 如何组织配置

Pi 的设置分为全局和项目两层：

| 文件 | 作用域 |
|---|---|
| `~/.pi/agent/settings.json` | 当前用户的所有项目 |
| `.pi/settings.json` | 当前项目 |

项目配置覆盖全局配置，嵌套对象按字段合并。

例如：

```json
// 全局
{
  "theme": "dark",
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384
  }
}
```

```json
// 项目
{
  "compaction": {
    "reserveTokens": 8192
  }
}
```

最终结果为：

```json
{
  "theme": "dark",
  "compaction": {
    "enabled": true,
    "reserveTokens": 8192
  }
}
```

项目层只覆盖明确提供的字段，不会因为只写了 `reserveTokens` 就丢失全局的 `compaction.enabled`。

### `/settings` 与直接编辑文件

`/settings` 用于交互式修改常用选项，但完整配置仍以 JSON 文件为准。文档中列出的部分高级设置可能更适合直接编辑 `settings.json`。

配置文件适合版本化和复制；`/settings` 适合临时、可发现的交互修改。

### 为什么项目设置需要信任

`.pi/settings.json` 不只是界面颜色配置。它可能启用：

- 项目 Extension
- Skills 和 Prompt Templates
- npm 或 Git Packages
- 自定义 Shell 行为
- 项目资源路径

其中 Extension 是可执行代码，Package 还可能触发依赖安装。因此 Pi 在加载项目级配置和资源前先判断项目是否可信。

交互模式下，如果项目或父目录没有保存过信任决定，Pi 会询问。信任后才会加载项目设置、安装缺失项目包并执行项目 Extension。

信任决定保存在：

```text
~/.pi/agent/trust.json
```

`/trust` 写入未来 Session 使用的决定，但当前 Session 不会热重载，必须重启 Pi 才生效。

Project Trust 是“是否加载项目行为”的门禁，不是限制 Bash、文件系统和网络访问的安全沙箱。

### 非交互模式的信任行为

以下模式不能停下来显示信任询问：

```text
pi -p
pi --mode json
pi --mode rpc
```

没有已保存决定时，它们读取全局 `defaultProjectTrust`：

| 值 | 行为 |
|---|---|
| `ask` | 非交互模式无法询问，因此忽略项目资源 |
| `never` | 忽略项目资源 |
| `always` | 自动信任项目资源 |

单次运行可以覆盖：

```text
--approve / -a       本次信任
--no-approve / -na  本次忽略
```

`defaultProjectTrust` 只能放在全局设置中。如果把它放在尚未受信任的项目配置中，让项目自行声明“信任我”，信任机制就失去意义。

### 模型与思考设置

```json
{
  "defaultProvider": "anthropic",
  "defaultModel": "claude-sonnet-4-20250514",
  "defaultThinkingLevel": "medium"
}
```

这三项决定新 Session 默认选择的 Provider、模型和思考等级。Session 中途发生的模型和思考等级切换仍会写入 SessionEntry，并随当前分支恢复。

`thinkingBudgets` 可以把抽象思考等级映射为具体 Token 预算：

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

`hideThinkingBlock` 只控制输出显示，不应理解为模型没有执行思考。

### UI 与编辑体验

常见设置包括：

- `theme`：内置或自定义主题。
- `quietStartup`：隐藏启动头部。
- `doubleEscapeAction`：双击 Escape 打开 tree、fork 或不执行动作。
- `treeFilterMode`：`/tree` 默认显示哪些条目。
- `editorPaddingX`、`outputPad`：输入和输出的水平留白。
- `autocompleteMaxVisible`：补全列表高度。
- `showHardwareCursor`：显示真实终端光标，帮助 IME 定位。

`externalEditor` 决定 Ctrl+G 使用哪个外部编辑器：

```json
{
  "externalEditor": "code --wait"
}
```

`--wait` 很重要。没有它，VS Code 命令启动后会立即返回，Pi 无法知道用户何时编辑完成。

### 遥测、更新检查和 Offline 是三件事

`enableInstallTelemetry` 控制安装或升级后向 `pi.dev` 发送一次匿名版本 ping。

关闭它不会关闭版本更新检查。版本检查仍可能请求：

```text
https://pi.dev/api/latest-version
```

只关闭版本检查：

```text
PI_SKIP_VERSION_CHECK=1
```

禁用启动阶段相关网络操作：

```text
pi --offline
PI_OFFLINE=1
```

Offline 还会影响包更新检查等启动网络行为。因此：

```text
关闭遥测 ≠ 关闭更新检查 ≠ 完整 Offline
```

### 网络代理

全局设置可以指定：

```json
{
  "httpProxy": "http://127.0.0.1:7890"
}
```

Pi 会把它应用为 `HTTP_PROXY` 和 `HTTPS_PROXY`。该设置只能位于全局配置，避免不受信任项目悄悄改变代理路径。

### Compaction 与 Branch Summary

```json
{
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  },
  "branchSummary": {
    "reserveTokens": 16384,
    "skipPrompt": false
  }
}
```

- `compaction.enabled`：是否自动压缩；关闭后仍可手动 `/compact`。
- `compaction.reserveTokens`：给正常模型回复预留空间。
- `compaction.keepRecentTokens`：压缩时保留的近期原始消息。
- `branchSummary.reserveTokens`：分支摘要生成时的预算预留。
- `branchSummary.skipPrompt`：跳过 `/tree` 时是否生成摘要的询问；文档说明默认不生成摘要。

Compaction 和 Branch Summary 是不同机制，因此使用不同配置对象。

### 两层重试机制

Pi 区分 Agent 级重试和 Provider/SDK 级重试。

Agent 级：

```json
{
  "retry": {
    "enabled": true,
    "maxRetries": 3,
    "baseDelayMs": 2000
  }
}
```

默认指数退避为：

```text
2 秒 → 4 秒 → 8 秒
```

这一层由 Pi 看见失败并产生 `auto_retry_*` 生命周期事件。

Provider 级：

```json
{
  "retry": {
    "provider": {
      "timeoutMs": 3600000,
      "maxRetries": 0,
      "maxRetryDelayMs": 60000
    }
  }
}
```

Provider/SDK 可能在错误返回 Pi 之前自行重试。默认 `maxRetries` 为 0，是为了避免 SDK 遇到配额限制后长期阻塞，而 Pi 和用户看不到明确失败。

`maxRetryDelayMs` 默认 60 秒。如果服务端要求等待 5 小时，Pi 会立即失败并报告，而不是静默挂起。设为 0 才表示取消等待上限。

一般应优先使用 Pi 可观察的 Agent 级重试，确有需要时再开启 Provider 级重试。

### Steering 与 Follow-up 投递

```json
{
  "steeringMode": "one-at-a-time",
  "followUpMode": "one-at-a-time"
}
```

两者都支持：

- `one-at-a-time`：每次只投递一条，默认行为。
- `all`：把队列中的消息一次全部投递。

这不会改变 Enter 是 Steering、Alt+Enter 是 Follow-up，只改变各自队列积累多条消息后如何交给 Agent。

### Provider 传输与超时

`transport` 可以为支持多种方式的 Provider 选择：

```text
auto
sse
websocket
websocket-cached
```

`auto` 让 Provider 选择合适传输。其余选项适合排查兼容性、代理或连接复用问题。

相关超时：

- `httpIdleTimeoutMs`：HTTP 响应长期没有任何数据时的空闲超时，默认 5 分钟。
- `websocketConnectTimeoutMs`：WebSocket 连接和握手超时，默认 15 秒。

它们是空闲或连接超时，不等同于整个 Agent 任务最多允许运行多久。设置为 0 可以禁用对应超时。

### 图片设置

```json
{
  "terminal": {
    "showImages": true,
    "imageWidthCells": 60
  },
  "images": {
    "autoResize": true,
    "blockImages": false
  }
}
```

`terminal.showImages` 只控制本地终端是否显示图片。

`images.blockImages` 控制是否阻止图片发送给 LLM。这两项不能混淆：终端不显示图片，不代表模型收不到图片。

`images.autoResize` 默认把图片限制到最大 2000×2000，以减少传输体积和多模态 Token 消耗。

### Shell 与 npm 命令

- `shellPath`：选择自定义 Shell。
- `shellCommandPrefix`：在每条 Bash 命令前添加固定前缀。
- `npmCommand`：Pi 安装和管理 npm/Git 包时实际使用的 argv。

例如通过 mise 固定 Node 20：

```json
{
  "npmCommand": ["mise", "exec", "node@20", "--", "npm"]
}
```

这里使用字符串数组而不是一整条 Shell 字符串，是为了明确每个进程参数，避免不同 Shell 的拆词和转义差异。

### Session 目录优先级

可以配置：

```json
{
  "sessionDir": ".pi/sessions"
}
```

多个来源同时指定时，优先级是：

```text
--session-dir
    ↓ 高于
PI_CODING_AGENT_SESSION_DIR
    ↓ 高于
settings.json 的 sessionDir
```

命令行适合单次覆盖，环境变量适合运行环境统一配置，JSON 设置则作为稳定默认值。

### 模型轮换

`enabledModels` 决定 Ctrl+P 快速轮换时出现哪些模型：

```json
{
  "enabledModels": ["claude-*", "gpt-4o", "gemini-2*"]
}
```

它是筛选轮换列表，不是 Provider 凭据配置，也不会安装或注册不存在的模型。

### 资源加载

Pi 可以从配置中加载：

```text
packages
extensions
skills
prompts
themes
```

全局设置中的相对路径以 `~/.pi/agent` 为基准；项目设置中的相对路径以项目 `.pi` 目录为基准。两者都支持绝对路径和 `~`。

资源数组支持：

- Glob pattern：匹配多个资源。
- `!pattern`：排除匹配项。
- `+path`：强制包含精确路径。
- `-path`：强制排除精确路径。

Package 字符串形式加载包中全部资源：

```json
{
  "packages": ["pi-skills", "@org/my-extension"]
}
```

对象形式可以只选择包内部分资源：

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

`enableSkillCommands` 决定是否把发现的 Skill 注册成 `/skill:name` 命令，不决定 Skill 文件是否被发现和加载。

### 理解 settings.md 的方式

不需要记住所有键名。更重要的是按层次理解：

```text
配置来源：全局默认 + 项目覆盖
安全门禁：Project Trust 决定是否加载项目行为
模型行为：模型、思考、压缩、重试、投递、传输
界面行为：主题、编辑器、树视图、图片显示
运行环境：代理、Shell、npm、Session 目录
扩展来源：Packages、Extensions、Skills、Prompts、Themes
```

遇到具体需求时，再回到文档查询准确键名和默认值即可。
