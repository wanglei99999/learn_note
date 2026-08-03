> **译文** | 原文：[`packages/coding-agent/docs/skills.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

> pi 可以创建 skill。让它为你的使用场景构建一个即可。

# Skill

Skill 是自包含的能力包，agent 按需加载。一个 skill 为特定任务提供专门的工作流程、设置说明、辅助脚本和参考文档。

Pi 实现了 [Agent Skills 标准](https://agentskills.io/specification)，对大多数违规情况给出警告但保持宽松。Pi 允许 skill 名称与其父目录不同，尽管标准不允许这样做；对于在多个 agent harness 之间共享的 skill 目录来说，那条规则并不理想。

## 目录

- [位置](#位置)
- [Skill 的工作原理](#skill-的工作原理)
- [Skill 命令](#skill-命令)
- [Skill 结构](#skill-结构)
- [Frontmatter](#frontmatter)
- [校验](#校验)
- [示例](#示例)
- [Skill 仓库](#skill-仓库)

## 位置

> **安全提示：** Skill 可以指示模型执行任何操作，并可能包含供模型调用的可执行代码。使用前请审查 skill 内容。

Pi 从以下位置加载 skill：

- 全局：
  - `~/.pi/agent/skills/`
  - `~/.agents/skills/`
- 项目（仅在项目获得信任后）：
  - `.pi/skills/`
  - `cwd` 及其祖先目录中的 `.agents/skills/`（向上直到 git 仓库根目录；不在仓库中时直到文件系统根目录）
- 包：`skills/` 目录或 `package.json` 中的 `pi.skills` 条目
- 设置：`skills` 数组，可包含文件或目录
- CLI：`--skill <path>`（可重复使用；即使加了 `--no-skills` 也会叠加生效）

发现规则：
- 在 `~/.pi/agent/skills/` 和 `.pi/skills/` 中，根目录下的 `.md` 文件会被作为独立 skill 发现
- 在所有 skill 位置中，包含 `SKILL.md` 的目录会被递归发现
- 在 `~/.agents/skills/` 和项目 `.agents/skills/` 中，根目录下的 `.md` 文件会被忽略

使用 `--no-skills` 可禁用发现（显式指定的 `--skill` 路径仍会加载）。

### 使用其它 harness 的 skill

要使用 Claude Code 或 OpenAI Codex 的 skill，将它们的目录添加到设置中：

```json
{
  "skills": [
    "~/.claude/skills",
    "~/.codex/skills"
  ]
}
```

对于项目级的 Claude Code skill，添加到 `.pi/settings.json`：

```json
{
  "skills": ["../.claude/skills"]
}
```

## Skill 的工作原理

1. 启动时，pi 扫描各个 skill 位置并提取名称和描述
2. 系统提示词按照[规范](https://agentskills.io/integrate-skills)以 XML 格式列出可用的 skill
3. 当任务匹配时，agent 使用 `read` 加载完整的 SKILL.md（模型并不总是这样做；可以通过 prompt 引导或用 `/skill:name` 强制加载）
4. Agent 遵循其中的指令，使用相对路径引用脚本和资源

这就是渐进式披露（progressive disclosure）：上下文中始终只有描述，完整指令按需加载。

## Skill 命令

Skill 会注册为 `/skill:name` 命令：

```bash
/skill:brave-search           # 加载并执行该 skill
/skill:pdf-tools extract      # 带参数加载 skill
```

命令后面的参数会以 `User: <args>` 的形式追加到 skill 内容之后。

可以在交互模式中通过 `/settings`，或在 `settings.json` 中开关 skill 命令：

```json
{
  "enableSkillCommands": true
}
```

## Skill 结构

Skill 是一个包含 `SKILL.md` 文件的目录，其余内容完全自由。

```
my-skill/
├── SKILL.md              # 必需：frontmatter + 指令
├── scripts/              # 辅助脚本
│   └── process.sh
├── references/           # 按需加载的详细文档
│   └── api-reference.md
└── assets/
    └── template.json
```

### SKILL.md 格式

````markdown
---
name: my-skill
description: What this skill does and when to use it. Be specific.
---

# My Skill

## Setup

Run once before first use:
```bash
cd /path/to/skill && npm install
```

## Usage

```bash
./scripts/process.sh <input>
```
````

使用相对于 skill 目录的相对路径：

```markdown
See [the reference guide](references/REFERENCE.md) for details.
```

## Frontmatter

依照 [Agent Skills 规范](https://agentskills.io/specification#frontmatter-required)：

| 字段 | 必需 | 说明 |
|-------|----------|-------------|
| `name` | 是 | 最长 64 字符。小写 a-z、0-9、连字符。与标准不同，Pi 不要求它与父目录名一致，因为标准的这条要求对共享 skill 目录并不理想。 |
| `description` | 是 | 最长 1024 字符。说明该 skill 做什么、何时使用。 |
| `license` | 否 | 许可证名称或对随附文件的引用。 |
| `compatibility` | 否 | 最长 500 字符。环境要求。 |
| `metadata` | 否 | 任意键值映射。 |
| `allowed-tools` | 否 | 以空格分隔的预批准 tool 列表（实验性）。 |
| `disable-model-invocation` | 否 | 为 `true` 时，skill 不出现在系统提示词中。用户必须使用 `/skill:name`。 |

### 名称规则

- 1-64 个字符
- 仅限小写字母、数字、连字符
- 不能以连字符开头或结尾
- 不能有连续的连字符
Pi 不要求名称与父目录一致。Agent Skills 标准有此要求，但对于被多个工具使用的共享 skill 目录来说，该要求并不理想。

有效：`pdf-processing`、`data-analysis`、`code-review`
无效：`PDF-Processing`、`-pdf`、`pdf--processing`

### 描述的最佳实践

描述决定了 agent 何时加载该 skill。要写得具体。

好的写法：
```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents.
```

差的写法：
```yaml
description: Helps with PDFs.
```

## 校验

Pi 按照 Agent Skills 标准校验 skill。大多数问题只产生警告，skill 仍会加载：

- 名称超过 64 个字符或包含无效字符
- 名称以连字符开头/结尾，或包含连续连字符
- 描述超过 1024 个字符

未知的 frontmatter 字段会被忽略。

**例外：** 缺少 description 的 skill 不会被加载。

名称冲突（不同位置出现同名 skill）会产生警告，并保留最先发现的那个 skill。

## 示例

```
brave-search/
├── SKILL.md
├── search.js
└── content.js
```

**SKILL.md：**
````markdown
---
name: brave-search
description: Web search and content extraction via Brave Search API. Use for searching documentation, facts, or any web content.
---

# Brave Search

## Setup

```bash
cd /path/to/brave-search && npm install
```

## Search

```bash
./search.js "query"              # Basic search
./search.js "query" --content    # Include page content
```

## Extract Page Content

```bash
./content.js https://example.com
```
````

## Skill 仓库

- [Anthropic Skills](https://github.com/anthropics/skills) - 文档处理（docx、pdf、pptx、xlsx）、Web 开发
- [Pi Skills](https://github.com/badlogic/pi-skills) - Web 搜索、浏览器自动化、Google API、转录
