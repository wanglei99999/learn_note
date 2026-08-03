> **译文** | 原文：[`packages/coding-agent/docs/themes.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/themes.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

> pi 可以创建主题。让它给你的环境做一个吧。

# 主题

主题是为 TUI 定义颜色的 JSON 文件。

## 目录

- [加载位置](#加载位置)
- [选择主题](#选择主题)
- [创建自定义主题](#创建自定义主题)
- [主题格式](#主题格式)
- [颜色 Token](#颜色-token)
- [颜色值](#颜色值)
- [技巧](#技巧)

## 加载位置

Pi 从以下位置加载主题：

- 内置：`dark`、`light`
- 全局：`~/.pi/agent/themes/*.json`
- 项目：`.pi/themes/*.json`（仅在项目被信任之后）
- pi 包：`themes/` 目录或 `package.json` 中的 `pi.themes` 条目
- 设置：`themes` 数组，可指定文件或目录
- CLI：`--theme <path>`（可重复）

使用 `--no-themes` 禁用主题发现。

## 选择主题

通过 `/settings` 或在 `settings.json` 中选择主题：

```json
{
  "theme": "my-theme"
}
```

首次运行时，pi 会检测终端背景色，默认使用 `dark` 或 `light`。

## 创建自定义主题

1. 创建主题文件：

```bash
mkdir -p ~/.pi/agent/themes
vim ~/.pi/agent/themes/my-theme.json
```

2. 定义主题，包含所有必需颜色（见[颜色 Token](#颜色-token)）：

```json
{
  "$schema": "https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/src/modes/interactive/theme/theme-schema.json",
  "name": "my-theme",
  "vars": {
    "primary": "#00aaff",
    "secondary": 242
  },
  "colors": {
    "accent": "primary",
    "border": "primary",
    "borderAccent": "#00ffff",
    "borderMuted": "secondary",
    "success": "#00ff00",
    "error": "#ff0000",
    "warning": "#ffff00",
    "muted": "secondary",
    "dim": 240,
    "text": "",
    "thinkingText": "secondary",
    "selectedBg": "#2d2d30",
    "userMessageBg": "#2d2d30",
    "userMessageText": "",
    "customMessageBg": "#2d2d30",
    "customMessageText": "",
    "customMessageLabel": "primary",
    "toolPendingBg": "#1e1e2e",
    "toolSuccessBg": "#1e2e1e",
    "toolErrorBg": "#2e1e1e",
    "toolTitle": "primary",
    "toolOutput": "",
    "mdHeading": "#ffaa00",
    "mdLink": "primary",
    "mdLinkUrl": "secondary",
    "mdCode": "#00ffff",
    "mdCodeBlock": "",
    "mdCodeBlockBorder": "secondary",
    "mdQuote": "secondary",
    "mdQuoteBorder": "secondary",
    "mdHr": "secondary",
    "mdListBullet": "#00ffff",
    "toolDiffAdded": "#00ff00",
    "toolDiffRemoved": "#ff0000",
    "toolDiffContext": "secondary",
    "syntaxComment": "secondary",
    "syntaxKeyword": "primary",
    "syntaxFunction": "#00aaff",
    "syntaxVariable": "#ffaa00",
    "syntaxString": "#00ff00",
    "syntaxNumber": "#ff00ff",
    "syntaxType": "#00aaff",
    "syntaxOperator": "primary",
    "syntaxPunctuation": "secondary",
    "thinkingOff": "secondary",
    "thinkingMinimal": "primary",
    "thinkingLow": "#00aaff",
    "thinkingMedium": "#00ffff",
    "thinkingHigh": "#ff00ff",
    "thinkingXhigh": "#ff0000",
    "thinkingMax": "#ff0088",
    "bashMode": "#ffaa00"
  }
}
```

3. 通过 `/settings` 选择该主题。

**热重载：** 当你编辑当前激活的自定义主题文件时，pi 会自动重新加载，即时呈现视觉效果。

## 主题格式

```json
{
  "$schema": "https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/src/modes/interactive/theme/theme-schema.json",
  "name": "my-theme",
  "vars": {
    "blue": "#0066cc",
    "gray": 242
  },
  "colors": {
    "accent": "blue",
    "muted": "gray",
    "text": "",
    ...
  }
}
```

- `name` 必填，必须唯一，且不能包含 `/`。
- `vars` 可选。在这里定义可复用的颜色，然后在 `colors` 中引用。
- `colors` 必须定义全部 51 个必需 token。`thinkingMax` 可选，缺省时回退到 `thinkingXhigh`。

`$schema` 字段可启用编辑器的自动补全与校验。

## 颜色 Token

每个主题都必须定义全部 51 个必需颜色 token。为兼容既有主题，`thinkingMax` 是可选的；省略时使用 `thinkingXhigh`。

### 核心 UI（11 个颜色）

| Token | 用途 |
|-------|---------|
| `accent` | 主强调色（logo、选中项、光标） |
| `border` | 普通边框 |
| `borderAccent` | 高亮边框 |
| `borderMuted` | 弱化边框（编辑器） |
| `success` | 成功状态 |
| `error` | 错误状态 |
| `warning` | 警告状态 |
| `muted` | 次要文本 |
| `dim` | 三级文本 |
| `text` | 默认文本（通常为 `""`） |
| `thinkingText` | 思考块文本 |

### 背景与内容（11 个颜色）

| Token | 用途 |
|-------|---------|
| `selectedBg` | 选中行背景 |
| `userMessageBg` | 用户消息背景 |
| `userMessageText` | 用户消息文本 |
| `customMessageBg` | extension 消息背景 |
| `customMessageText` | extension 消息文本 |
| `customMessageLabel` | extension 消息标签 |
| `toolPendingBg` | tool 框（等待中） |
| `toolSuccessBg` | tool 框（成功） |
| `toolErrorBg` | tool 框（错误） |
| `toolTitle` | tool 标题 |
| `toolOutput` | tool 输出文本 |

### Markdown（10 个颜色）

| Token | 用途 |
|-------|---------|
| `mdHeading` | 标题 |
| `mdLink` | 链接文字 |
| `mdLinkUrl` | 链接 URL |
| `mdCode` | 行内代码 |
| `mdCodeBlock` | 代码块内容 |
| `mdCodeBlockBorder` | 代码块围栏 |
| `mdQuote` | 引用块文本 |
| `mdQuoteBorder` | 引用块边框 |
| `mdHr` | 水平分隔线 |
| `mdListBullet` | 列表项目符号 |

### Tool Diff（3 个颜色）

| Token | 用途 |
|-------|---------|
| `toolDiffAdded` | 新增行 |
| `toolDiffRemoved` | 删除行 |
| `toolDiffContext` | 上下文行 |

### 语法高亮（9 个颜色）

| Token | 用途 |
|-------|---------|
| `syntaxComment` | 注释 |
| `syntaxKeyword` | 关键字 |
| `syntaxFunction` | 函数名 |
| `syntaxVariable` | 变量 |
| `syntaxString` | 字符串 |
| `syntaxNumber` | 数字 |
| `syntaxType` | 类型 |
| `syntaxOperator` | 运算符 |
| `syntaxPunctuation` | 标点符号 |

### 思考级别边框（6 个必需，1 个可选）

指示思考级别的编辑器边框颜色（视觉层级从低调到醒目）：

| Token | 用途 |
|-------|---------|
| `thinkingOff` | 思考关闭 |
| `thinkingMinimal` | 最低思考 |
| `thinkingLow` | 低思考 |
| `thinkingMedium` | 中等思考 |
| `thinkingHigh` | 高思考 |
| `thinkingXhigh` | 超高思考 |
| `thinkingMax` | 最高思考；可选，回退到 `thinkingXhigh` |

### Bash 模式（1 个颜色）

| Token | 用途 |
|-------|---------|
| `bashMode` | bash 模式下的编辑器边框（`!` 前缀） |

### HTML 导出（可选）

`export` 部分控制 `/export` HTML 输出的颜色。省略时，颜色会从 `userMessageBg` 派生。

```json
{
  "export": {
    "pageBg": "#18181e",
    "cardBg": "#1e1e24",
    "infoBg": "#3c3728"
  }
}
```

## 颜色值

支持四种格式：

| 格式 | 示例 | 说明 |
|--------|---------|-------------|
| 十六进制 | `"#ff0000"` | 6 位十六进制 RGB |
| 256 色 | `39` | xterm 256 色调色板索引（0-255） |
| 变量 | `"primary"` | 引用 `vars` 中的条目 |
| 默认 | `""` | 终端默认颜色 |

### 256 色调色板

- `0-15`：基本 ANSI 颜色（取决于终端）
- `16-231`：6×6×6 RGB 立方体（`16 + 36×R + 6×G + B`，其中 R、G、B 取 0-5）
- `232-255`：灰度渐变

### 终端兼容性

Pi 使用 24 位 RGB 颜色。大多数现代终端都支持（iTerm2、Kitty、WezTerm、Windows Terminal、VS Code）。对于只支持 256 色的旧终端，pi 会回退到最接近的近似色。

检查 truecolor 支持：

```bash
echo $COLORTERM  # 应输出 "truecolor" 或 "24bit"
```

## 技巧

**深色终端：** 使用明亮、高饱和度、对比度更高的颜色。

**浅色终端：** 使用更深、低饱和度、对比度更低的颜色。

**配色协调：** 从一个基础调色板出发（Nord、Gruvbox、Tokyo Night），在 `vars` 中定义，并保持一致地引用。

**测试：** 用不同的消息类型、tool 状态、markdown 内容和长换行文本检查你的主题。

**VS Code：** 将 `terminal.integrated.minimumContrastRatio` 设置为 `1` 以获得准确的颜色。

## 示例

参见内置主题：
- [dark.json](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/modes/interactive/theme/dark.json)
- [light.json](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/modes/interactive/theme/light.json)
