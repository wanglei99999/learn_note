> **译文** | 原文：[`packages/coding-agent/docs/tmux.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/tmux.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-07-31

# tmux 配置

pi 可以在 tmux 中运行，但 tmux 默认会剥离某些按键的修饰键信息。不加配置的话，`Shift+Enter` 和 `Ctrl+Enter` 通常与普通 `Enter` 无法区分。

## 推荐配置

在 `~/.tmux.conf` 中添加：

```tmux
set -g extended-keys on
set -g extended-keys-format csi-u
```

然后完全重启 tmux：

```bash
tmux kill-server
tmux
```

当 Kitty 键盘协议不可用时，pi 会自动请求扩展按键上报（extended key reporting）。配置了 `extended-keys-format csi-u` 后，tmux 会以 CSI-u 格式转发带修饰键的按键，这是最可靠的配置。`extended-keys-format` 选项要求 tmux 3.5 或更高版本。

## 为什么推荐 `csi-u`

如果只配置：

```tmux
set -g extended-keys on
```

tmux 会默认使用 `extended-keys-format xterm`。当应用请求扩展按键上报时，带修饰键的按键会以 xterm `modifyOtherKeys` 格式转发，例如：

- `Ctrl+C` → `\x1b[27;5;99~`
- `Ctrl+D` → `\x1b[27;5;100~`
- `Ctrl+Enter` → `\x1b[27;5;13~`

配置 `extended-keys-format csi-u` 后，同样的按键会转发为：

- `Ctrl+C` → `\x1b[99;5u`
- `Ctrl+D` → `\x1b[100;5u`
- `Ctrl+Enter` → `\x1b[13;5u`

两种格式 pi 都支持，但 `csi-u` 是推荐的 tmux 配置。

## 这解决了什么问题

没有 tmux 扩展按键时，带修饰键的 Enter 会坍缩成传统序列：

| 按键 | 无扩展按键 | 配置 `csi-u` 后 |
|-----|-----------------|--------------|
| Enter | `\r` | `\r` |
| Shift+Enter | `\r` | `\x1b[13;2u` |
| Ctrl+Enter | `\r` | `\x1b[13;5u` |
| Alt/Option+Enter | `\x1b\r` | `\x1b[13;3u` |

这影响默认快捷键（`Enter` 提交、`Shift+Enter` 换行）以及任何使用带修饰键 Enter 的自定义快捷键。

## 要求

- tmux 3.5 或更高版本才支持 `extended-keys-format csi-u`（运行 `tmux -V` 检查）
- 支持扩展按键的终端模拟器（Ghostty、Kitty、iTerm2、WezTerm、Windows Terminal）

tmux 3.2 到 3.4 版本请省略 `extended-keys-format csi-u`；pi 依然支持 tmux 默认的 xterm `modifyOtherKeys` 格式。
