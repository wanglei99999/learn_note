> **译文** | 原文：[`packages/coding-agent/docs/sessions.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sessions.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 会话（Sessions）

Pi 将对话保存为会话（session），让你可以继续之前的工作、从更早的轮次创建分支、以及回顾曾经走过的路径。

## 会话存储

会话自动保存到 `~/.pi/agent/sessions/`，按工作目录组织。每个会话是一个具有树形结构的 JSONL 文件。

```bash
pi -c                  # 继续最近一次会话
pi -r                  # 浏览并选择历史会话
pi --no-session        # 临时模式；不保存
pi --name "my task"    # 启动时设置会话显示名称
pi --session <path|id> # 使用指定的会话文件或部分会话 ID
pi --fork <path|id>    # 将某个会话文件或部分会话 ID fork 为新会话
```

在交互模式中使用 `/session` 可以查看当前会话文件、会话 ID、消息数量、token 数和费用。

关于 JSONL 文件格式和 SessionManager API，参见[会话格式](session-format.md)。

## 会话命令

| 命令 | 说明 |
|---------|-------------|
| `/resume` | 浏览并选择之前的会话 |
| `/new` | 开始新会话 |
| `/name <name>` | 设置当前会话的显示名称 |
| `/session` | 显示会话信息 |
| `/tree` | 浏览当前会话树 |
| `/fork` | 从之前的某条用户消息创建新会话 |
| `/clone` | 将当前活动分支复制为新会话 |
| `/compact [prompt]` | 对较早的上下文做摘要；参见[上下文压缩](compaction.md) |
| `/export [file]` | 将会话导出为 HTML |
| `/share` | 上传为私有 GitHub gist，生成可分享的 HTML 链接 |

## 恢复与删除会话

`/resume` 会打开当前项目的交互式会话选择器。`pi -r` 在启动时打开同一个选择器。

在选择器中你可以：

- 输入文字进行搜索
- 用 Ctrl+P 切换路径显示
- 用 Ctrl+S 切换排序方式
- 用 Ctrl+N 筛选出已命名的会话
- 用 Ctrl+R 重命名
- 用 Ctrl+D 删除，然后确认

在可用时，pi 会使用 `trash` CLI 进行删除，而不是永久移除文件。

## 为会话命名

使用 `/name <name>` 设置一个便于阅读的会话名称：

```text
/name Refactor auth module
```

也可以在启动时用 `--name` 或 `-n` 设置名称：

```bash
pi --name "Refactor auth module"
pi --name "CI audit" -p "Review this build failure"
```

命名过的会话在 `/resume` 和 `pi -r` 中更容易找到。

## 用 `/tree` 创建分支

会话以树形结构存储。每个条目都有 `id` 和 `parentId`，当前位置是活动叶节点。`/tree` 让你跳转到之前的任意节点并从那里继续，而无需创建新文件。

<p align="center"><img src="https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/images/tree-view.png" alt="Tree View" width="600"></p>

示例结构：

```text
├─ user: "Hello, can you help..."
│  └─ assistant: "Of course! I can..."
│     ├─ user: "Let's try approach A..."
│     │  └─ assistant: "For approach A..."
│     │     └─ user: "That worked..."  ← active
│     └─ user: "Actually, approach B..."
│        └─ assistant: "For approach B..."
```

### 树视图操作

| 按键 | 操作 |
|-----|--------|
| ↑/↓ | 在可见条目间移动 |
| ←/→ | 上翻/下翻一页 |
| Ctrl+←/Ctrl+→ 或 Alt+←/Alt+→ | 折叠/展开，或在分支段之间跳转 |
| Shift+L | 为选中条目设置或清除标签 |
| Shift+T | 切换标签时间戳显示 |
| Enter | 选择条目 |
| Escape/Ctrl+C | 取消 |
| Ctrl+O | 循环切换筛选模式 |

筛选模式包括：default、no-tools、user-only、labeled-only、all。可通过[设置](settings.md)中的 `treeFilterMode` 配置默认值。

### 选中后的行为

选中用户消息或自定义消息时：

1. 将叶节点移动到所选消息的父节点。
2. 将所选消息的文本放入编辑器。
3. 让你编辑后重新提交，从而创建一个新分支。

选中 assistant 消息、工具、上下文压缩或其它非用户条目时：

1. 将叶节点移动到该条目。
2. 编辑器保持为空。
3. 让你从该节点继续。

选中根用户消息会将叶节点重置为空对话，并把最初的 prompt 放入编辑器。

## `/tree`、`/fork` 与 `/clone`

| 特性 | `/tree` | `/fork` | `/clone` |
|---------|---------|---------|----------|
| 输出 | 同一会话文件 | 新会话文件 | 新会话文件 |
| 视图 | 完整树 | 用户消息选择器 | 当前活动分支 |
| 典型用途 | 就地探索不同方案 | 从较早的 prompt 开启新会话 | 在继续之前复制当前工作 |
| 摘要 | 可选的分支摘要 | 无 | 无 |

想把不同方案放在一起时用 `/tree`；想要独立的会话文件时用 `/fork` 或 `/clone`。

## 分支摘要

当 `/tree` 从一个分支切换到另一个分支时，pi 可以对被放弃的分支做摘要，并把摘要附加到新位置。这样无需重放整个分支，就能保留你离开的那条路径上的重要上下文。

出现提示时，可以选择：

1. 不生成摘要
2. 使用默认 prompt 生成摘要
3. 使用自定义关注点指令生成摘要

关于分支摘要的内部机制和 extension hook，参见[上下文压缩](compaction.md)。

## 会话格式

会话文件为 JSONL 格式，包含消息条目、模型变更、思考级别变更、标签、上下文压缩、分支摘要以及 extension 条目。

关于解析器、extension、SDK 用法和完整的 SessionManager API，参见[会话格式](session-format.md)。
