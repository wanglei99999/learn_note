# 翻译说明（TRANSLATION NOTES）

本文件夹是 [earendil-works/pi](https://github.com/earendil-works/pi) 官方英文文档的简体中文翻译，自包含、可整体迁移。

- **当前同步版本**：v0.84.2（commit `5cd93f688`）
- **翻译日期**：2026-07-31（首批）／2026-08-02（补齐）／2026-08-21（同步 v0.84.2）／2026-08-23（补齐当前 52 篇文档）
- **原文位置**：`packages/*/README.md`、`packages/agent/docs/`、`packages/coding-agent/docs/`

译文头部的版本行以各篇实际同步点为准。上游已删除、当前版本没有对应原文的历史译文仍保留旧版本标记，不会伪装成已校对到 v0.84.2。

## 目录结构

```
docs-zh/
├── README.md                  # 总导览索引
├── TRANSLATION-NOTES.md       # 本文件
├── agent/                     # pi-agent-core：README + 8 篇设计文档
├── coding-agent/              # pi CLI：README、使用文档、示例与测试说明
├── ai/README.md               # pi-ai README
├── client/README.md           # pi-client README
├── protocol/README.md         # pi-protocol README
├── server/README.md           # pi-server README
├── evals/README.md            # pi-evals README
├── telemetry/README.md        # pi-telemetry README
├── session-backends/          # session backend 文档
├── tui/README.md              # pi-tui README
│   └── native/                # Windows 与 Darwin 原生构建说明
└── orchestrator/README.md     # pi-orchestrator README
```

当前英文文档覆盖率为 **52/52**。另外保留 6 篇上游已删除的历史译文，它们继续使用各自旧版本标记。

注意：原仓库中文档位于各包的 `docs/` 子目录，本文件夹将其平铺到包名目录下（如 `packages/coding-agent/docs/usage.md` → `coding-agent/usage.md`）。

## 每篇译文的开头元信息（必须）

每篇译文正文标题之前，加一行引用块（路径与文件名按实际替换）：

```markdown
> **译文** | 原文：[`packages/coding-agent/docs/usage.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/usage.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21
```

## 翻译风格

1. **简体中文**，技术准确性优先；不逐词硬译，按中文表达习惯重组句子，但不得增删信息、不得虚构原文没有的内容。
2. **代码块、命令、配置键名、文件路径、环境变量、标志参数**一律原样保留；**代码块内的英文注释翻译成中文**（字符串字面量、标识符不动）。
3. 表格、列表、标题层级、粗斜体等 Markdown 结构与原文保持一致。
4. 标题翻译成中文（这会改变锚点，见下方链接规则 5）。

## 术语表

**保留英文不译**（首次出现时可加括号中文注释）：

provider、agent、harness、session、skill、extension、hook、prompt、token、tool、TUI、RPC、SDK、API key、OAuth、frontmatter、worktree、steering、shell、CLI、streaming、LLM

**固定译法**（全部译文保持一致）：

| 英文 | 译法 |
| --- | --- |
| context | 上下文 |
| compaction | 上下文压缩 |
| tool call | 工具调用 |
| system prompt | 系统提示词 |
| prompt template | 提示词模板 |
| keybinding | 快捷键 / 按键绑定 |
| theme | 主题 |
| settings | 设置 |
| branch / branching (session) | 分支 / 会话分支 |
| checkpoint / save point | 保存点 |
| resume | 恢复 |
| follow-up | 后续消息 |
| event | 事件 |
| lifecycle | 生命周期 |
| observability | 可观测性 |
| durable | 持久化 |
| pi package | pi 包 |
| sandbox | 沙箱 |
| project trust | 项目信任 |
| interactive mode | 交互模式 |
| print mode | print 模式 |
| overlay | 覆盖层 |
| component | 组件 |
| renderer / rendering | 渲染器 / 渲染 |
| autocomplete | 自动补全 |
| slash command | 斜杠命令 |

## 链接改写规则

1. **同目录文档互链**（`./foo.md`、`foo.md`）：保持不变（译文在同一平铺目录）。
2. **指向包 README**（`../README.md`）：改为 `./README.md`。
3. **跨包文档链接**（如 coding-agent 文档链到 `../../agent/docs/foo.md`）：改为译文内部相对路径（如 `../agent/foo.md`）。
4. **指向仓库源码 / 示例 / 其它非译文文件的相对链接**（如 `../src/...`、`../examples/...`）：改为 GitHub 绝对链接，格式 `https://github.com/earendil-works/pi/blob/main/packages/<包名>/<路径>`。
5. **文内锚点链接**（`[文字](#some-heading)`）：标题已译成中文，锚点同步改为中文标题形式——保留中文字符、空格换成 `-`（如 `#会话-分支`按实际标题生成）。
6. **外部链接**（http/https）：保持不变。
7. **图片**：相对路径改为 `https://raw.githubusercontent.com/earendil-works/pi/main/<原相对路径解析后的仓库路径>`。

## 长文件写入方式（给翻译代理）

超过约 600 行的源文件，禁止一次 Write 写完：先 Write 写入第一部分，随后用 Edit 以「文件当前结尾片段」为 old_string 逐段追加，直到全文完成，避免单次输出超限导致截断。完成后用 Read 抽查开头、中间、结尾各一处确认完整。
