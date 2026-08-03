> **译文** | 原文：[`packages/coding-agent/docs/windows.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/windows.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-07-31

# Windows 配置

pi 在 Windows 上需要一个 bash shell。查找位置（按顺序）：

1. `~/.pi/agent/settings.json` 中的自定义路径
2. Git Bash（`C:\Program Files\Git\bin\bash.exe`）
3. PATH 上的 `bash.exe`（Cygwin、MSYS2、WSL）

对大多数用户来说，[Git for Windows](https://git-scm.com/download/win) 就足够了。

## 自定义 shell 路径

```json
{
  "shellPath": "C:\\cygwin64\\bin\\bash.exe"
}
```
