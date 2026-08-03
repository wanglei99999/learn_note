> **译文** | 原文：[`packages/coding-agent/docs/development.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/development.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 开发

更多规范请参见 [AGENTS.md](https://github.com/earendil-works/pi-mono/blob/main/AGENTS.md)。

## 环境搭建

```bash
git clone https://github.com/earendil-works/pi-mono
cd pi-mono
npm install
npm run build
```

从源码运行：

```bash
/path/to/pi-mono/pi-test.sh
```

该脚本可以在任意目录下运行。Pi 会保留调用者的当前工作目录。

## Fork / 换品牌

通过 `package.json` 配置：

```json
{
  "piConfig": {
    "name": "pi",
    "configDir": ".pi"
  }
}
```

为你的 fork 修改 `name`、`configDir` 以及 `bin` 字段。这会影响 CLI 横幅、配置路径和环境变量名。

## 路径解析

三种执行模式：npm 安装、独立二进制、从源码经 tsx 运行。

访问包内资源时**必须使用 `src/config.ts`**：

```typescript
import { getPackageDir, getThemeDir } from "./config.js";
```

绝不要直接用 `__dirname` 访问包内资源。

## 调试命令

`/debug`（隐藏命令）会写入 `~/.pi/agent/pi-debug.log`：
- 带 ANSI 码的已渲染 TUI 行
- 最近发送给 LLM 的消息

## 测试

```bash
./test.sh                         # 运行非 LLM 测试（无需 API key）
npm test                          # 运行全部测试
npm test -- test/specific.test.ts # 运行指定测试
```

## 项目结构

```
packages/
  ai/           # LLM provider 抽象层
  agent/        # Agent 循环与消息类型
  tui/          # 终端 UI 组件
  coding-agent/ # CLI 与交互模式
```
