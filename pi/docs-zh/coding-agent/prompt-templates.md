> **译文** | 原文：[`packages/coding-agent/docs/prompt-templates.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/prompt-templates.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

> pi 可以自己创建提示词模板。让它为你的工作流写一个吧。

# 提示词模板

提示词模板是可展开为完整 prompt 的 Markdown 片段。在编辑器中输入 `/name` 即可调用模板，其中 `name` 是去掉 `.md` 后缀的文件名。

## 位置

Pi 从以下位置加载提示词模板：

- 全局：`~/.pi/agent/prompts/*.md`
- 项目：`.pi/prompts/*.md`（仅在项目被信任之后）
- 包：`prompts/` 目录或 `package.json` 中的 `pi.prompts` 条目
- 设置：`prompts` 数组，可包含文件或目录
- CLI：`--prompt-template <path>`（可重复）

使用 `--no-prompt-templates` 可以禁用模板发现。

## 格式

```markdown
---
description: Review staged git changes
---
Review the staged changes (`git diff --cached`). Focus on:
- Bugs and logic errors
- Security issues
- Error handling gaps
```

- 文件名即命令名。`review.md` 变为 `/review`。
- `description` 可选。缺失时使用第一行非空内容。
- `argument-hint` 可选。设置后，该提示会显示在自动补全下拉框中描述文字之前。

### 参数提示

在 frontmatter 中使用 `argument-hint` 可以在自动补全中展示期望的参数。必填参数用 `<尖括号>`，可选参数用 `[方括号]`：

```markdown
---
description: Review PRs from URLs with structured issue and code analysis
argument-hint: "<PR-URL>"
---
```

它在自动补全下拉框中渲染为：

```
→ pr   <PR-URL>       — Review PRs from URLs with structured issue and code analysis
  is   <issue>        — Analyze GitHub issues (bugs or feature requests)
  wr   [instructions] — Finish the current task end-to-end
  cl   — Audit changelog entries before release
```

## 用法

在编辑器中输入 `/` 加模板名。自动补全会显示可用模板及其描述。

```
/review                           # 展开 review.md
/component Button                 # 带参数展开
/component Button "click handler" # 多个参数
```

## 参数

模板支持位置参数、默认值以及简单的切片：

- `$1`、`$2`、…… 位置参数
- `$@` 或 `$ARGUMENTS` 表示所有参数拼接
- `${1:-default}` 在参数 1 存在且非空时使用它，否则使用 `default`
- `${@:-default}` 或 `${ARGUMENTS:-default}` 在存在非空参数时使用全部参数，否则使用 `default`
- `${@:N}` 表示从第 N 个位置起的所有参数（从 1 开始计数）
- `${@:N:L}` 表示从第 N 个位置起的 `L` 个参数

示例：

```markdown
---
description: Create a component
---
Create a React component named $1 with features: $@
```

默认值适合用于可选参数：

```markdown
Summarize the current state in ${1:-7} bullet points.
```

用法：`/component Button "onClick handler" "disabled support"`

## 加载规则

- `prompts/` 中的模板发现是非递归的。
- 如果希望使用子目录中的模板，请通过 `prompts` 设置或包清单显式添加。
