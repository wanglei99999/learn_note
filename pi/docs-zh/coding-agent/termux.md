> **译文** | 原文：[`packages/coding-agent/docs/termux.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/termux.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# Termux（Android）配置

Pi 可以通过 [Termux](https://termux.dev/)（Android 上的终端模拟器与 Linux 环境）在 Android 上运行。

## 前置条件

1. 从 GitHub 或 F-Droid 安装 [Termux](https://github.com/termux/termux-app#installation)（不要用 Google Play，那个版本已废弃）
2. 从 GitHub 或 F-Droid 安装 [Termux:API](https://github.com/termux/termux-api#installation)，用于剪贴板等设备集成

## 安装

```bash
# 更新软件包
pkg update && pkg upgrade

# 安装依赖
pkg install nodejs termux-api git

# 安装 pi
npm install -g --ignore-scripts @earendil-works/pi-coding-agent

# 创建配置目录
mkdir -p ~/.pi/agent

# 运行 pi
pi
```

## 剪贴板支持

在 Termux 中运行时，剪贴板操作使用 `termux-clipboard-set` 和 `termux-clipboard-get`。必须安装 Termux:API 应用它们才能工作。

Termux 上不支持图片剪贴板（`ctrl+v` 图片粘贴功能无法使用）。

## Termux 的 AGENTS.md 示例

创建 `~/.pi/agent/AGENTS.md`，帮助 agent 理解 Termux 环境：

````markdown
# Agent Environment: Termux on Android

## Location
- **OS**: Android (Termux terminal emulator)
- **Home**: `/data/data/com.termux/files/home`
- **Prefix**: `/data/data/com.termux/files/usr`
- **Shared storage**: `/storage/emulated/0` (Downloads, Documents, etc.)

## Opening URLs
```bash
termux-open-url "https://example.com"
```

## Opening Files
```bash
termux-open file.pdf          # 用默认应用打开
termux-open --chooser image.jpg      # 选择应用
```

## Clipboard
```bash
termux-clipboard-set "text"   # 复制
termux-clipboard-get          # 粘贴
```

## Notifications
```bash
termux-notification -t "Title" -c "Content"
```

## Device Info
```bash
termux-battery-status         # 电池信息
termux-wifi-connectioninfo    # WiFi 信息
termux-telephony-deviceinfo   # 设备信息
```

## Sharing
```bash
termux-share -a send file.txt # 分享文件
```

## Other Useful Commands
```bash
termux-toast "message"        # 快速 toast 弹窗
termux-vibrate                # 设备振动
termux-tts-speak "hello"      # 文字转语音
termux-camera-photo out.jpg   # 拍照
```

## Notes
- Termux:API app must be installed for `termux-*` commands
- Use `pkg install termux-api` for the command-line tools
- Storage permission needed for `/storage/emulated/0` access
````

## 限制

- **没有图片剪贴板**：Termux 剪贴板 API 只支持文本
- **没有原生二进制**：部分可选的原生依赖（例如剪贴板模块）在 Android ARM64 上不可用，安装时会被跳过
- **存储访问**：要访问 `/storage/emulated/0`（Downloads 等）中的文件，需运行一次 `termux-setup-storage` 授予权限

## 故障排查

### 剪贴板不工作

确认两个应用都已安装：
1. Termux（来自 GitHub 或 F-Droid）
2. Termux:API（来自 GitHub 或 F-Droid）

然后安装 CLI 工具：
```bash
pkg install termux-api
```

### 共享存储 Permission denied

运行一次以授予存储权限：
```bash
termux-setup-storage
```

### Node.js 安装问题

如果 npm 失败，尝试清理缓存：
```bash
npm cache clean --force
```
