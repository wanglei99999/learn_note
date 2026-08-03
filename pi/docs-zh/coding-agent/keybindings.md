> **译文** | 原文：[`packages/coding-agent/docs/keybindings.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/keybindings.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 快捷键

所有键盘快捷键都可以通过 `~/.pi/agent/keybindings.json` 自定义。每个动作可以绑定一个或多个按键。

配置文件使用与 pi 内部相同的带命名空间的快捷键 id，extension 作者在 `keyHint()` 和注入的 `keybindings` 管理器中使用的也是这些 id。

使用旧式无命名空间 id（如 `cursorUp`、`expandTools`）的配置会在启动时自动迁移到带命名空间的 id。

编辑 `keybindings.json` 后，在 pi 中运行 `/reload` 即可应用更改，无需重启会话。

## 按键格式

格式为 `modifier+key`，其中修饰键为 `ctrl`、`shift`、`alt`（可组合），按键包括：

- **字母：** `a-z`
- **数字：** `0-9`
- **特殊键：** `escape`、`esc`、`enter`、`return`、`tab`、`space`、`backspace`、`delete`、`insert`、`clear`、`home`、`end`、`pageUp`、`pageDown`、`up`、`down`、`left`、`right`
- **功能键：** `f1`-`f12`
- **符号：** `` ` ``、`-`、`=`、`[`、`]`、`\`、`;`、`'`、`,`、`.`、`/`、`!`、`@`、`#`、`$`、`%`、`^`、`&`、`*`、`(`、`)`、`_`、`+`、`|`、`~`、`{`、`}`、`:`、`<`、`>`、`?`

修饰键组合示例：`ctrl+shift+x`、`alt+ctrl+x`、`ctrl+shift+alt+x`、`ctrl+1` 等。

## 全部动作

### TUI 编辑器光标移动

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `tui.editor.cursorUp` | `up` | 光标上移 |
| `tui.editor.cursorDown` | `down` | 光标下移 |
| `tui.editor.cursorLeft` | `left`、`ctrl+b` | 光标左移 |
| `tui.editor.cursorRight` | `right`、`ctrl+f` | 光标右移 |
| `tui.editor.cursorWordLeft` | `alt+left`、`ctrl+left`、`alt+b` | 光标左移一个词 |
| `tui.editor.cursorWordRight` | `alt+right`、`ctrl+right`、`alt+f` | 光标右移一个词 |
| `tui.editor.cursorLineStart` | `home`、`ctrl+a` | 移到行首 |
| `tui.editor.cursorLineEnd` | `end`、`ctrl+e` | 移到行尾 |
| `tui.editor.jumpForward` | `ctrl+]` | 向前跳转到指定字符 |
| `tui.editor.jumpBackward` | `ctrl+alt+]` | 向后跳转到指定字符 |
| `tui.editor.pageUp` | `pageUp` | 向上翻页 |
| `tui.editor.pageDown` | `pageDown` | 向下翻页 |

### TUI 编辑器删除

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `tui.editor.deleteCharBackward` | `backspace` | 向后删除一个字符 |
| `tui.editor.deleteCharForward` | `delete`、`ctrl+d` | 向前删除一个字符 |
| `tui.editor.deleteWordBackward` | `ctrl+w`、`alt+backspace` | 向后删除一个词 |
| `tui.editor.deleteWordForward` | `alt+d`、`alt+delete` | 向前删除一个词 |
| `tui.editor.deleteToLineStart` | `ctrl+u` | 删除到行首 |
| `tui.editor.deleteToLineEnd` | `ctrl+k` | 删除到行尾 |

### TUI 输入

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `tui.input.newLine` | `shift+enter`、`ctrl+j` | 插入新行 |
| `tui.input.submit` | `enter` | 提交输入 |
| `tui.input.tab` | `tab` | Tab / 自动补全 |

### TUI Kill Ring

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `tui.editor.yank` | `ctrl+y` | 粘贴最近删除的文本 |
| `tui.editor.yankPop` | `alt+y` | yank 之后循环切换已删除的文本 |
| `tui.editor.undo` | `ctrl+-` | 撤销上一次编辑 |

### TUI 剪贴板与选择

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `tui.input.copy` | `ctrl+c` | 复制选中内容 |
| `tui.select.up` | `up` | 选择项上移 |
| `tui.select.down` | `down` | 选择项下移 |
| `tui.select.pageUp` | `pageUp` | 列表向上翻页 |
| `tui.select.pageDown` | `pageDown` | 列表向下翻页 |
| `tui.select.confirm` | `enter` | 确认选择 |
| `tui.select.cancel` | `escape`、`ctrl+c` | 取消选择 |

### 应用

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `app.interrupt` | `escape` | 取消 / 中止 |
| `app.clear` | `ctrl+c` | 清空编辑器 |
| `app.exit` | `ctrl+d` | 退出（编辑器为空时） |
| `app.suspend` | `ctrl+z`（Windows 上无默认值） | 挂起到后台 |
| `app.editor.external` | `ctrl+g` | 在外部编辑器中打开（`externalEditor`、`$VISUAL`、`$EDITOR`，Windows 上为 Notepad，其它平台为 `nano`） |
| `app.clipboard.pasteImage` | `ctrl+v`（Windows 上为 `alt+v`） | 从剪贴板粘贴图片 |

### 会话

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `app.session.new` | *（无）* | 开始新会话（`/new`） |
| `app.session.tree` | *（无）* | 打开会话树导航（`/tree`） |
| `app.session.fork` | *（无）* | fork 当前会话（`/fork`） |
| `app.session.resume` | *（无）* | 打开会话恢复选择器（`/resume`） |
| `app.session.togglePath` | `ctrl+p` | 切换路径显示 |
| `app.session.toggleSort` | `ctrl+s` | 切换排序方式 |
| `app.session.toggleNamedFilter` | `ctrl+n` | 切换「仅显示已命名会话」筛选 |
| `app.session.rename` | `ctrl+r` | 重命名会话 |
| `app.session.delete` | `ctrl+d` | 删除会话 |
| `app.session.deleteNoninvasive` | `ctrl+backspace` | 在搜索框为空时删除会话 |

### 模型与思考

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `app.model.select` | `ctrl+l` | 打开模型选择器 |
| `app.model.cycleForward` | `ctrl+p` | 切换到下一个模型 |
| `app.model.cycleBackward` | `shift+ctrl+p` | 切换到上一个模型 |
| `app.thinking.cycle` | `shift+tab` | 循环切换思考级别 |
| `app.thinking.toggle` | `ctrl+t` | 折叠或展开思考块 |

### 显示与消息队列

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `app.tools.expand` | `ctrl+o` | 折叠或展开工具输出 |
| `app.message.copy` | `ctrl+x` | 复制最后一条 assistant 消息，或 `/tree` 中选中的消息 |
| `app.message.followUp` | `alt+enter` | 将后续消息加入队列 |
| `app.message.dequeue` | `alt+up` | 将队列中的消息还原到编辑器 |

### 树视图导航

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `app.tree.foldOrUp` | `ctrl+left`、`alt+left` | 折叠当前分支段，或跳到上一个分支段的起点 |
| `app.tree.unfoldOrDown` | `ctrl+right`、`alt+right` | 展开当前分支段，或跳到下一个分支段的起点或分支末尾 |
| `app.tree.editLabel` | `shift+l` | 编辑选中树节点上的标签 |
| `app.tree.toggleLabelTimestamp` | `shift+t` | 切换树中标签时间戳的显示 |
| `app.tree.filter.default` | `ctrl+d` | 将树筛选设为默认视图 |
| `app.tree.filter.noTools` | `ctrl+t` | 切换隐藏工具结果的树筛选 |
| `app.tree.filter.userOnly` | `ctrl+u` | 切换仅显示用户消息的树筛选 |
| `app.tree.filter.labeledOnly` | `ctrl+l` | 切换仅显示带标签条目的树筛选 |
| `app.tree.filter.all` | `ctrl+a` | 切换显示全部条目的树筛选 |
| `app.tree.filter.cycleForward` | `ctrl+o` | 正向循环切换树筛选 |
| `app.tree.filter.cycleBackward` | `shift+ctrl+o` | 反向循环切换树筛选 |

### 作用域模型选择器

在作用域模型选择器（通过 `/scoped-models` 打开）内部使用。

| 快捷键 id | 默认值 | 说明 |
|--------|---------|-------------|
| `app.models.save` | `ctrl+s` | 将当前模型选择保存到设置 |
| `app.models.enableAll` | `ctrl+a` | 启用全部模型（或匹配当前搜索的全部模型） |
| `app.models.clearAll` | `ctrl+x` | 清除全部模型（或匹配当前搜索的全部模型） |
| `app.models.toggleProvider` | `ctrl+p` | 切换当前 provider 的全部模型 |
| `app.models.reorderUp` | `alt+up` | 在循环顺序中将选中模型上移 |
| `app.models.reorderDown` | `alt+down` | 在循环顺序中将选中模型下移 |

## 自定义配置

创建 `~/.pi/agent/keybindings.json`：

```json
{
  "tui.editor.cursorUp": ["up", "ctrl+p"],
  "tui.editor.cursorDown": ["down", "ctrl+n"],
  "tui.editor.deleteWordBackward": ["ctrl+w", "alt+backspace"]
}
```

每个动作可以绑定单个按键或按键数组。用户配置会覆盖默认值。

在原生 Windows 上，`app.suspend` 没有默认绑定，因为 Windows 终端不支持 Unix 作业控制。如果你手动绑定它，pi 会显示一条状态消息而不是挂起。在 WSL 中，正常的 Linux `ctrl+z`/`fg` 行为仍然适用。

### Emacs 示例

```json
{
  "tui.editor.cursorUp": ["up", "ctrl+p"],
  "tui.editor.cursorDown": ["down", "ctrl+n"],
  "tui.editor.cursorLeft": ["left", "ctrl+b"],
  "tui.editor.cursorRight": ["right", "ctrl+f"],
  "tui.editor.cursorWordLeft": ["alt+left", "alt+b"],
  "tui.editor.cursorWordRight": ["alt+right", "alt+f"],
  "tui.editor.deleteCharForward": ["delete", "ctrl+d"],
  "tui.editor.deleteCharBackward": ["backspace", "ctrl+h"],
  "tui.input.newLine": ["shift+enter", "ctrl+j"]
}
```

### Vim 示例

```json
{
  "tui.editor.cursorUp": ["up", "alt+k"],
  "tui.editor.cursorDown": ["down", "alt+j"],
  "tui.editor.cursorLeft": ["left", "alt+h"],
  "tui.editor.cursorRight": ["right", "alt+l"],
  "tui.editor.cursorWordLeft": ["alt+left", "alt+b"],
  "tui.editor.cursorWordRight": ["alt+right", "alt+w"]
}
```
