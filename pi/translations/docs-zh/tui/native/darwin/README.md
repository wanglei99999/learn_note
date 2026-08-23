> **译文** | 原文：[`packages/tui/native/darwin/README.md`](https://github.com/earendil-works/pi/blob/main/packages/tui/native/darwin/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-23

# Darwin 原生预构建

在仓库根目录构建两种 macOS 架构：

```sh
npm --prefix packages/tui run build:native:darwin
```

构建以 macOS 11.0 作为 arm64 deployment target，以 macOS 10.15 作为 x86_64 deployment target。在 macOS 上，`build.sh` 通过 `xcrun` 查找 Apple clang 和当前 macOS SDK。Intel 或 Apple Silicon 主机均可构建两种产物。

非 macOS 主机需要完整的 Darwin cross-toolchain，包括 macOS SDK 和 Mach-O linker。例如，可通过 `CC` 和 `SDKROOT` 选择 osxcross installation：

```sh
CC=/path/to/osxcross/clang SDKROOT=/path/to/MacOSX.sdk \
  npm --prefix packages/tui run build:native:darwin
```

SDK 的获取和使用必须遵守 Apple 许可。普通 Linux 或 Windows clang 不够，因为 addon 会包含并链接 CoreGraphics。

这里不使用 Zig，因为它不提供 Apple SDK 或 CoreGraphics framework stub。因此，它不能让此构建摆脱 SDK 依赖；其 clang driver 目前也无法直接替代 Apple clang 处理这套 Mach-O bundle 构建方式。
