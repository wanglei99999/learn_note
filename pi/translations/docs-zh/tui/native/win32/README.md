> **译文** | 原文：[`packages/tui/native/win32/README.md`](https://github.com/earendil-works/pi/blob/main/packages/tui/native/win32/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-23

# Windows 原生预构建

在仓库根目录构建两种 Windows 架构：

```sh
npm --prefix packages/tui run build:native:win32
```

在 Windows 上，构建使用 Visual Studio 的 Microsoft C++ Build Tools。`build.mjs` 会定位 `VsDevCmd.bat`，分别为 `amd64` 和 `arm64` 初始化开发环境，再使用 `cl.exe`/`link.exe` 构建 addon。

请安装“使用 C++ 的桌面开发”工作负载，或至少安装 MSVC toolset 和 Windows SDK 组件。不需要 Node header；addon 会从宿主进程解析 N-API symbol。

在非 Windows 系统上交叉构建，或使用自定义 Windows toolchain 时，请设置 `PI_TUI_WIN32_TOOLCHAIN=mingw` 并提供兼容 MinGW 的 compiler：

```sh
PI_TUI_WIN32_TOOLCHAIN=mingw \
CC_X64=/path/to/x86_64-w64-mingw32-gcc \
CC_ARM64=/path/to/aarch64-w64-mingw32-gcc \
npm --prefix packages/tui run build:native:win32
```

该 addon 有意避免使用 C runtime，仅链接 `kernel32`。
