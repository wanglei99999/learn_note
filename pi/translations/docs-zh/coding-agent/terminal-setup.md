> **译文** | 原文：[`packages/coding-agent/docs/terminal-setup.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/terminal-setup.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 终端设置

Pi 使用 [Kitty 键盘协议](https://sw.kovidgoyal.net/kitty/keyboard-protocol/)来可靠地检测修饰键。大多数现代终端都支持该协议，但有些需要额外配置。

## Kitty、iTerm2

开箱即用。

## Apple Terminal（macOS 自带终端）

Pi 会在可用时启用增强按键上报。如果 Terminal.app 在按下 `Shift+Enter` 时仍然只发送普通的 Return，pi 会使用本地 macOS 修饰键回退机制，把该 Return 视为 `Shift+Enter`。

该回退机制只在 pi 与 Terminal.app 运行在同一台 Mac 上时生效。通过远程 SSH 无法检测本地键盘。

## Ghostty

在你的 Ghostty 配置文件中添加（macOS 上为 `~/Library/Application Support/com.mitchellh.ghostty/config`，Linux 上为 `~/.config/ghostty/config`）：

```
keybind = alt+backspace=text:\x1b\x7f
```

较旧版本的 Claude Code 可能添加过这条 Ghostty 映射：

```
keybind = shift+enter=text:\n
```

这条映射会发送一个原始换行字节。在 pi 内部，它与 `Ctrl+J` 无法区分，因此 tmux 和 pi 都不再能收到真正的 `shift+enter` 按键事件。

如果你添加这条映射的唯一原因是 Claude Code 2.x 或更新版本，那么可以删除它；除非你还想在 tmux 中使用 Claude Code——那种场景下仍然需要这条 Ghostty 映射。

Pi 默认将 `Ctrl+J` 绑定为换行别名，因此通过这条重映射，`Shift+Enter` 在 tmux 中也能继续工作，无需额外的 pi 配置。

## WezTerm

对于 `Shift+Enter`，WezTerm 通常通过 xterm modifyOtherKeys 开箱即用。若要显式启用 Kitty 键盘协议，创建 `~/.wezterm.lua`：

```lua
local wezterm = require 'wezterm'
local config = wezterm.config_builder()
config.enable_kitty_keyboard = true
return config
```

在 macOS 上，WezTerm 默认将 `Option+Enter` 绑定为全屏。若要将 `Option+Enter` 用于 pi 的后续消息（follow-up）排队，添加以下按键覆盖：

```lua
local wezterm = require 'wezterm'
local config = wezterm.config_builder()
config.keys = {
  {
    key = 'Enter',
    mods = 'ALT',
    action = wezterm.action.SendString('\x1b[13;3u'),
  },
}
return config
```

如果你已经有 `config.keys` 表，把该条目加进去即可。

在 WSL 上，WezTerm 可能需要可见的硬件光标来定位输入法（IME）候选窗口。如果中日韩输入法候选框不跟随文本光标，可以在运行 pi 前设置 `PI_HARDWARE_CURSOR=1`，或在设置中把 `showHardwareCursor` 设为 `true`。

## Alacritty

对于 `Shift+Enter`，Alacritty 通常开箱即用。在 macOS 上，`Option+Enter` 可能被当作普通 `Enter` 传入。若要将 `Option+Enter` 用于 pi 的后续消息排队，在 `~/.config/alacritty/alacritty.toml` 中添加：

```toml
[[keyboard.bindings]]
key = "Enter"
mods = "Alt"
chars = "\u001b[13;3u"
```

修改配置后重启 Alacritty。

## VS Code（集成终端）

VS Code 1.109.5 及更新版本默认在集成终端中启用 Kitty 键盘协议，因此 `Shift+Enter` 应该开箱即用。

低于 1.109.5 的 VS Code 版本需要为 `Shift+Enter` 显式添加终端快捷键。

`keybindings.json` 的位置：
- macOS：`~/Library/Application Support/Code/User/keybindings.json`
- Linux：`~/.config/Code/User/keybindings.json`
- Windows：`%APPDATA%\\Code\\User\\keybindings.json`

在 `keybindings.json` 中添加：

```json
{
  "key": "shift+enter",
  "command": "workbench.action.terminal.sendSequence",
  "args": { "text": "\u001b[13;2u" },
  "when": "terminalFocus"
}
```

## Windows Terminal

在 `settings.json` 中（按 Ctrl+Shift+, 或「设置 → 打开 JSON 文件」）添加以下内容，以转发 pi 使用的带修饰键的 Enter：

```json
{
  "actions": [
    {
      "command": { "action": "sendInput", "input": "\u001b[13;2u" },
      "keys": "shift+enter"
    },
    {
      "command": { "action": "sendInput", "input": "\u001b[13;3u" },
      "keys": "alt+enter"
    }
  ]
}
```

- `Shift+Enter` 插入新行。
- Windows Terminal 默认将 `Alt+Enter` 绑定为全屏，这会导致 pi 无法收到用于后续消息排队的 `Alt+Enter`。
- 将 `Alt+Enter` 重映射为 `sendInput` 后，真实的按键组合会被转发给 pi。

如果你已经有 `actions` 数组，把这些对象加进去即可。如果旧的全屏行为仍然存在，请完全关闭并重新打开 Windows Terminal。

## xfce4-terminal、terminator

这些终端对转义序列的支持有限。带修饰键的 Enter（如 `Ctrl+Enter`、`Shift+Enter`）无法与普通 `Enter` 区分开，导致诸如 `submit: ["ctrl+enter"]` 之类的自定义快捷键无法工作。

为获得最佳体验，请使用支持 Kitty 键盘协议的终端：
- [Kitty](https://sw.kovidgoyal.net/kitty/)
- [Ghostty](https://ghostty.org/)
- [WezTerm](https://wezfurlong.org/wezterm/)
- [iTerm2](https://iterm2.com/)
- [Alacritty](https://github.com/alacritty/alacritty)（需要编译时启用 Kitty 协议支持）

## IntelliJ IDEA（集成终端）

内置终端对转义序列的支持有限。在 IntelliJ 的终端中，Shift+Enter 无法与 Enter 区分。

如果你希望显示硬件光标，可以在运行 pi 前设置 `PI_HARDWARE_CURSOR=1`（出于兼容性考虑默认禁用）。

为获得最佳体验，建议使用专门的终端模拟器。
