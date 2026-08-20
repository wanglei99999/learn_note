> **译文** | 原文：[`packages/coding-agent/docs/tui.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/tui.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

> pi 可以创建 TUI 组件。让它为你的使用场景构建一个即可。

# TUI 组件

extension 和自定义 tool 可以渲染自定义 TUI 组件，构建交互式用户界面。本页介绍组件系统与可用的基础构建块。

**源码：** [`@earendil-works/pi-tui`](https://github.com/earendil-works/pi-mono/tree/main/packages/tui)

## 组件接口

所有组件都实现：

```typescript
interface Component {
  render(width: number): string[];
  handleInput?(data: string): void;
  wantsKeyRelease?: boolean;
  invalidate(): void;
}
```

| 方法 | 说明 |
|--------|-------------|
| `render(width)` | 返回字符串数组（每行一个元素）。每行**不得超过 `width`**。 |
| `handleInput?(data)` | 当组件获得焦点时接收键盘输入。 |
| `wantsKeyRelease?` | 为 true 时，组件会接收按键释放事件（Kitty 协议）。默认：false。 |
| `invalidate()` | 清除缓存的渲染状态。主题变更时会被调用。 |

TUI 会在每行渲染结果的末尾追加完整的 SGR 重置和 OSC 8 重置。样式不会跨行延续。如果你输出带样式的多行文本，需要对每一行重新应用样式，或使用 `wrapTextWithAnsi()`，以确保每个折行都保留样式。

## Focusable 接口（IME 支持）

需要显示文本光标并支持 IME（输入法编辑器）的组件，应实现 `Focusable` 接口：

```typescript
import { CURSOR_MARKER, type Component, type Focusable } from "@earendil-works/pi-tui";

class MyInput implements Component, Focusable {
  focused: boolean = false;  // 焦点变化时由 TUI 设置

  render(width: number): string[] {
    const marker = this.focused ? CURSOR_MARKER : "";
    // 在假光标之前紧挨着输出 marker
    return [`> ${beforeCursor}${marker}\x1b[7m${atCursor}\x1b[27m${afterCursor}`];
  }
}
```

当 `Focusable` 组件获得焦点时，TUI 会：
1. 将该组件的 `focused` 设为 `true`
2. 在渲染输出中扫描 `CURSOR_MARKER`（一个零宽的 APC 转义序列）
3. 将硬件终端光标定位到该位置
4. 仅当启用 `showHardwareCursor` 时才显示硬件光标

光标默认保持隐藏。这样既保留了假光标的渲染，又能为那些在光标隐藏时也会跟踪 IME 候选窗口的终端定位硬件光标。有些终端要求硬件光标可见才能正确定位 IME；可通过 `showHardwareCursor`、`setShowHardwareCursor(true)` 或 `PI_HARDWARE_CURSOR=1` 启用。内置组件 `Editor` 和 `Input` 已经实现了该接口。

### 内嵌输入框的容器组件

当容器组件（对话框、选择器等）包含 `Input` 或 `Editor` 子组件时，容器必须实现 `Focusable` 并将焦点状态传递给子组件。否则，硬件光标无法为 IME 输入正确定位。

```typescript
import { Container, type Focusable, Input } from "@earendil-works/pi-tui";

class SearchDialog extends Container implements Focusable {
  private searchInput: Input;

  // Focusable 实现——把焦点传递给子输入框，用于 IME 光标定位
  private _focused = false;
  get focused(): boolean {
    return this._focused;
  }
  set focused(value: boolean) {
    this._focused = value;
    this.searchInput.focused = value;
  }

  constructor() {
    super();
    this.searchInput = new Input();
    this.addChild(this.searchInput);
  }
}
```

如果不做这个传递，使用 IME（中文、日文、韩文等）输入时，候选窗口会显示在屏幕上错误的位置。

## 使用组件

**在 extension 中**通过 `ctx.ui.custom()`：

```typescript
pi.on("session_start", async (_event, ctx) => {
  const result = await ctx.ui.custom<string | null>((tui, theme, keybindings, done) =>
    new MyComponent({
      theme,
      keybindings,
      onChange: () => tui.requestRender(),
      onSelect: (value) => done(value),
      onCancel: () => done(null),
    })
  );
});
```

**在自定义 tool 中**通过 `ctx.ui.custom()`：

```typescript
async execute(toolCallId, params, signal, onUpdate, ctx) {
  const result = await ctx.ui.custom<string | null>((tui, theme, keybindings, done) =>
    new MyComponent({
      theme,
      keybindings,
      onChange: () => tui.requestRender(),
      onSelect: (value) => done(value),
      onCancel: () => done(null),
    })
  );
  // 使用 result...
}
```

## 覆盖层

覆盖层（overlay）在现有内容之上渲染组件，而不清屏。向 `ctx.ui.custom()` 传入 `{ overlay: true }`：

```typescript
const result = await ctx.ui.custom<string | null>(
  (tui, theme, keybindings, done) => new MyDialog({ onClose: done }),
  { overlay: true }
);
```

定位和尺寸通过 `overlayOptions` 设置：

```typescript
const result = await ctx.ui.custom<string | null>(
  (tui, theme, keybindings, done) => new SidePanel({ onClose: done }),
  {
    overlay: true,
    overlayOptions: {
      // 尺寸：数字或百分比字符串
      width: "50%",          // 终端宽度的 50%
      minWidth: 40,          // 最小 40 列
      maxHeight: "80%",      // 最高为终端高度的 80%

      // 位置：基于锚点（默认："center"）
      anchor: "right-center", // 9 个位置：center、top-left、top-center 等
      offsetX: -2,            // 相对锚点的偏移
      offsetY: 0,

      // 也可以用百分比 / 绝对定位
      row: "25%",            // 距顶部 25%
      col: 10,               // 第 10 列

      // 边距
      margin: 2,             // 四边统一，或 { top, right, bottom, left }

      // 响应式：在窄终端上隐藏
      visible: (termWidth, termHeight) => termWidth >= 80,
    },
    // 获取句柄，用于以编程方式控制焦点和可见性
    onHandle: (handle) => {
      // handle.focus() - 聚焦此覆盖层并将其置于视觉最前
      // handle.unfocus() - 释放输入，回退到常规目标
      // handle.unfocus({ target }) - 释放输入给特定组件或 null
      // handle.setHidden(true/false) - 切换可见性
      // handle.hide() - 永久移除
    },
  }
);
```

### 覆盖层焦点

获得焦点的可见覆盖层会在临时的非覆盖层 UI 期间保持输入所有权。如果一个覆盖层打开了另一个未带 `{ overlay: true }` 的 `ctx.ui.custom()` 组件，该替换 UI 在活动期间接收输入；它关闭后，获得焦点的覆盖层可以重新拿回输入。

当可见覆盖层应停止占有输入、让 TUI 回退到另一个可见的输入捕获覆盖层或先前的焦点目标时，使用 `handle.unfocus()`。当覆盖层保持可见、但某个特定组件应接收输入时，使用 `handle.unfocus({ target })`。传入 `{ target: null }` 则有意让任何组件都不获得焦点，直到再次设置焦点为止。

### 覆盖层生命周期

覆盖层组件在关闭时会被销毁。不要复用引用——每次都创建新实例：

```typescript
// 错误——过期引用
let menu: MenuComponent;
await ctx.ui.custom((_, __, ___, done) => {
  menu = new MenuComponent(done);
  return menu;
}, { overlay: true });
setActiveComponent(menu);  // 已被销毁

// 正确——重新调用即可重新显示
const showMenu = () => ctx.ui.custom((_, __, ___, done) =>
  new MenuComponent(done), { overlay: true });

await showMenu();  // 第一次显示
await showMenu();  // “返回”= 再调用一次
```

覆盖锚点、边距、堆叠、响应式可见性和动画的完整示例见 [overlay-qa-tests.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/overlay-qa-tests.ts)。

## 内置组件

从 `@earendil-works/pi-tui` 导入：

```typescript
import { Text, Box, Container, Spacer, Markdown } from "@earendil-works/pi-tui";
```

### Text

支持自动换行的多行文本。

```typescript
const text = new Text(
  "Hello World",    // 内容
  1,                // paddingX（默认：1）
  1,                // paddingY（默认：1）
  (s) => bgGray(s)  // 可选的背景函数
);
text.setText("Updated");
```

### Box

带内边距和背景色的容器。

```typescript
const box = new Box(
  1,                // paddingX
  1,                // paddingY
  (s) => bgGray(s)  // 背景函数
);
box.addChild(new Text("Content", 0, 0));
box.setBgFn((s) => bgBlue(s));
```

### Container

将子组件垂直排列成组。

```typescript
const container = new Container();
container.addChild(component1);
container.addChild(component2);
container.removeChild(component1);
```

### Spacer

空白的垂直间距。

```typescript
const spacer = new Spacer(2);  // 2 个空行
```

### Markdown

渲染带语法高亮的 markdown。

```typescript
const md = new Markdown(
  "# Title\n\nSome **bold** text",
  1,        // paddingX
  1,        // paddingY
  theme     // MarkdownTheme（见下文）
);
md.setText("Updated markdown");
```

### Image

在支持的终端（Kitty、iTerm2、Ghostty、WezTerm、Warp）中渲染图片。

```typescript
const image = new Image(
  base64Data,   // base64 编码的图片
  "image/png",  // MIME 类型
  theme,        // ImageTheme
  { maxWidthCells: 80, maxHeightCells: 24 }
);
```

## 键盘输入

使用 `matchesKey()` 检测按键：

```typescript
import { matchesKey, Key } from "@earendil-works/pi-tui";

handleInput(data: string) {
  if (matchesKey(data, Key.up)) {
    this.selectedIndex--;
  } else if (matchesKey(data, Key.enter)) {
    this.onSelect?.(this.selectedIndex);
  } else if (matchesKey(data, Key.escape)) {
    this.onCancel?.();
  } else if (matchesKey(data, Key.ctrl("c"))) {
    // Ctrl+C
  }
}
```

**按键标识符**（用 `Key.*` 获得自动补全，或使用字符串字面量）：
- 基本按键：`Key.enter`、`Key.escape`、`Key.tab`、`Key.space`、`Key.backspace`、`Key.delete`、`Key.home`、`Key.end`
- 方向键：`Key.up`、`Key.down`、`Key.left`、`Key.right`
- 带修饰键：`Key.ctrl("c")`、`Key.shift("tab")`、`Key.alt("left")`、`Key.ctrlShift("p")`
- 字符串格式也可以：`"enter"`、`"ctrl+c"`、`"shift+tab"`、`"ctrl+shift+p"`

## 行宽

**关键：** `render()` 返回的每一行都不得超过 `width` 参数。

```typescript
import { visibleWidth, truncateToWidth } from "@earendil-works/pi-tui";

render(width: number): string[] {
  // 截断过长的行
  return [truncateToWidth(this.text, width)];
}
```

工具函数：
- `visibleWidth(str)` - 获取显示宽度（忽略 ANSI 代码）
- `truncateToWidth(str, width, ellipsis?)` - 截断，可选省略号
- `wrapTextWithAnsi(str, width)` - 保留 ANSI 代码的自动换行

## 创建自定义组件

示例：交互式选择器

```typescript
import {
  matchesKey, Key,
  truncateToWidth, visibleWidth
} from "@earendil-works/pi-tui";

class MySelector {
  private items: string[];
  private selected = 0;
  private cachedWidth?: number;
  private cachedLines?: string[];

  public onSelect?: (item: string) => void;
  public onCancel?: () => void;

  constructor(items: string[]) {
    this.items = items;
  }

  handleInput(data: string): void {
    if (matchesKey(data, Key.up) && this.selected > 0) {
      this.selected--;
      this.invalidate();
    } else if (matchesKey(data, Key.down) && this.selected < this.items.length - 1) {
      this.selected++;
      this.invalidate();
    } else if (matchesKey(data, Key.enter)) {
      this.onSelect?.(this.items[this.selected]);
    } else if (matchesKey(data, Key.escape)) {
      this.onCancel?.();
    }
  }

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) {
      return this.cachedLines;
    }

    this.cachedLines = this.items.map((item, i) => {
      const prefix = i === this.selected ? "> " : "  ";
      return truncateToWidth(prefix + item, width);
    });
    this.cachedWidth = width;
    return this.cachedLines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }
}
```

在 extension 中的用法：

```typescript
pi.registerCommand("pick", {
  description: "Pick an item",
  handler: async (_args, ctx) => {
    const items = ["Option A", "Option B", "Option C"];
    const selected = await ctx.ui.custom<string | null>((tui, _theme, _keybindings, done) => {
      const selector = new MySelector(items);
      selector.onSelect = done;
      selector.onCancel = () => done(null);

      return {
        render: (width) => selector.render(width),
        handleInput: (data) => {
          selector.handleInput(data);
          tui.requestRender();
        },
        invalidate: () => selector.invalidate(),
      };
    });

    if (selected !== null) {
      ctx.ui.notify(`Selected: ${selected}`, "info");
    }
  }
});
```

## 主题

组件接受主题对象来定义样式。

**在 `renderCall`/`renderResult` 中**，使用 `theme` 参数：

```typescript
renderResult(result, options, theme, context) {
  // 用 theme.fg() 设置前景色
  return new Text(theme.fg("success", "Done!"), 0, 0);

  // 用 theme.bg() 设置背景色
  const styled = theme.bg("toolPendingBg", theme.fg("accent", "text"));
}
```

**前景色**（`theme.fg(color, text)`）：

| 类别 | 颜色 |
|----------|--------|
| 通用 | `text`、`accent`、`muted`、`dim` |
| 状态 | `success`、`error`、`warning` |
| 边框 | `border`、`borderAccent`、`borderMuted` |
| 消息 | `userMessageText`、`customMessageText`、`customMessageLabel` |
| 工具 | `toolTitle`、`toolOutput` |
| Diff | `toolDiffAdded`、`toolDiffRemoved`、`toolDiffContext` |
| Markdown | `mdHeading`、`mdLink`、`mdLinkUrl`、`mdCode`、`mdCodeBlock`、`mdCodeBlockBorder`、`mdQuote`、`mdQuoteBorder`、`mdHr`、`mdListBullet` |
| 语法 | `syntaxComment`、`syntaxKeyword`、`syntaxFunction`、`syntaxVariable`、`syntaxString`、`syntaxNumber`、`syntaxType`、`syntaxOperator`、`syntaxPunctuation` |
| 思考 | `thinkingOff`、`thinkingMinimal`、`thinkingLow`、`thinkingMedium`、`thinkingHigh`、`thinkingXhigh`、`thinkingMax` |
| 模式 | `bashMode` |

**背景色**（`theme.bg(color, text)`）：

`selectedBg`、`userMessageBg`、`customMessageBg`、`toolPendingBg`、`toolSuccessBg`、`toolErrorBg`

**Markdown 使用** `getMarkdownTheme()`：

```typescript
import { getMarkdownTheme } from "@earendil-works/pi-coding-agent";
import { Markdown } from "@earendil-works/pi-tui";

renderResult(result, options, theme, context) {
  const mdTheme = getMarkdownTheme();
  return new Markdown(result.details.markdown, 0, 0, mdTheme);
}
```

**自定义组件**可以定义自己的主题接口：

```typescript
interface MyTheme {
  selected: (s: string) => string;
  normal: (s: string) => string;
}
```

## 调试日志

设置 `PI_TUI_WRITE_LOG` 可捕获写入 stdout 的原始 ANSI 流。

```bash
PI_TUI_WRITE_LOG=/tmp/tui-ansi.log npx tsx packages/tui/test/chat-simple.ts
```

## 性能

尽可能缓存渲染输出：

```typescript
class CachedComponent {
  private cachedWidth?: number;
  private cachedLines?: string[];

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) {
      return this.cachedLines;
    }
    // ... 计算 lines ...
    this.cachedWidth = width;
    this.cachedLines = lines;
    return lines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }
}
```

状态变化时调用 `invalidate()`，然后使用注入的 `tui.requestRender()` 触发重新渲染。

## 缓存失效与主题变更

主题变更时，TUI 会对所有组件调用 `invalidate()` 以清除其缓存。组件必须正确实现 `invalidate()`，才能确保主题变更生效。

### 问题所在

如果组件把主题颜色预先烘焙进字符串（通过 `theme.fg()`、`theme.bg()` 等）并缓存起来，缓存的字符串就包含旧主题的 ANSI 转义码。如果组件把带主题样式的内容单独存储，仅清除渲染缓存是不够的。

**错误做法**（主题颜色不会更新）：

```typescript
class BadComponent extends Container {
  private content: Text;

  constructor(message: string, theme: Theme) {
    super();
    // 预先烘焙的主题颜色被存进 Text 组件
    this.content = new Text(theme.fg("accent", message), 1, 0);
    this.addChild(this.content);
  }
  // 没有重写 invalidate——父类的 invalidate 只清除
  // 子组件的渲染缓存，不会清除预先烘焙的内容
}
```

### 解决方案

用主题颜色构建内容的组件，必须在 `invalidate()` 被调用时重建这些内容：

```typescript
class GoodComponent extends Container {
  private message: string;
  private content: Text;

  constructor(message: string) {
    super();
    this.message = message;
    this.content = new Text("", 1, 0);
    this.addChild(this.content);
    this.updateDisplay();
  }

  private updateDisplay(): void {
    // 用当前主题重建内容
    this.content.setText(theme.fg("accent", this.message));
  }

  override invalidate(): void {
    super.invalidate();  // 清除子组件缓存
    this.updateDisplay(); // 用新主题重建
  }
}
```

### 模式：在 invalidate 时重建

对于内容复杂的组件：

```typescript
class ComplexComponent extends Container {
  private data: SomeData;

  constructor(data: SomeData) {
    super();
    this.data = data;
    this.rebuild();
  }

  private rebuild(): void {
    this.clear();  // 移除所有子组件

    // 用当前主题构建 UI
    this.addChild(new Text(theme.fg("accent", theme.bold("Title")), 1, 0));
    this.addChild(new Spacer(1));

    for (const item of this.data.items) {
      const color = item.active ? "success" : "muted";
      this.addChild(new Text(theme.fg(color, item.label), 1, 0));
    }
  }

  override invalidate(): void {
    super.invalidate();
    this.rebuild();
  }
}
```

### 何时需要这样做

以下情况需要此模式：

1. **预先烘焙主题颜色**——用 `theme.fg()` 或 `theme.bg()` 创建带样式的字符串并存入子组件
2. **语法高亮**——使用会应用基于主题的语法颜色的 `highlightCode()`
3. **复杂布局**——构建内嵌主题颜色的子组件树

以下情况不需要此模式：

1. **使用主题回调**——传入形如 `(text) => theme.fg("accent", text)` 的函数，在渲染时才调用
2. **简单容器**——仅对其他组件分组，不添加带主题样式的内容
3. **无状态渲染**——每次 `render()` 都重新计算带主题的输出（不缓存）

## 常见模式

这些模式覆盖了 extension 中最常见的 UI 需求。**直接复制这些模式，不要从零开始搭建。**

### 模式 1：选择对话框（SelectList）

让用户从选项列表中挑选。使用 `@earendil-works/pi-tui` 的 `SelectList`，并用 `DynamicBorder` 加边框。

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { DynamicBorder } from "@earendil-works/pi-coding-agent";
import { Container, type SelectItem, SelectList, Text } from "@earendil-works/pi-tui";

pi.registerCommand("pick", {
  handler: async (_args, ctx) => {
    const items: SelectItem[] = [
      { value: "opt1", label: "Option 1", description: "First option" },
      { value: "opt2", label: "Option 2", description: "Second option" },
      { value: "opt3", label: "Option 3" },  // description 可选
    ];

    const result = await ctx.ui.custom<string | null>((tui, theme, _kb, done) => {
      const container = new Container();

      // 顶部边框
      container.addChild(new DynamicBorder((s: string) => theme.fg("accent", s)));

      // 标题
      container.addChild(new Text(theme.fg("accent", theme.bold("Pick an Option")), 1, 0));

      // 带主题的 SelectList
      const selectList = new SelectList(items, Math.min(items.length, 10), {
        selectedPrefix: (t) => theme.fg("accent", t),
        selectedText: (t) => theme.fg("accent", t),
        description: (t) => theme.fg("muted", t),
        scrollInfo: (t) => theme.fg("dim", t),
        noMatch: (t) => theme.fg("warning", t),
      });
      selectList.onSelect = (item) => done(item.value);
      selectList.onCancel = () => done(null);
      container.addChild(selectList);

      // 帮助文本
      container.addChild(new Text(theme.fg("dim", "↑↓ navigate • enter select • esc cancel"), 1, 0));

      // 底部边框
      container.addChild(new DynamicBorder((s: string) => theme.fg("accent", s)));

      return {
        render: (w) => container.render(w),
        invalidate: () => container.invalidate(),
        handleInput: (data) => { selectList.handleInput(data); tui.requestRender(); },
      };
    });

    if (result) {
      ctx.ui.notify(`Selected: ${result}`, "info");
    }
  },
});
```

**示例：** [preset.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/preset.ts)、[tools.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/tools.ts)

### 模式 2：可取消的异步操作（BorderedLoader）

用于耗时且可取消的操作。`BorderedLoader` 显示一个加载动画，并处理按 escape 取消。

```typescript
import { BorderedLoader } from "@earendil-works/pi-coding-agent";

pi.registerCommand("fetch", {
  handler: async (_args, ctx) => {
    const result = await ctx.ui.custom<string | null>((tui, theme, _kb, done) => {
      const loader = new BorderedLoader(tui, theme, "Fetching data...");
      loader.onAbort = () => done(null);

      // 执行异步任务
      fetchData(loader.signal)
        .then((data) => done(data))
        .catch(() => done(null));

      return loader;
    });

    if (result === null) {
      ctx.ui.notify("Cancelled", "info");
    } else {
      ctx.ui.setEditorText(result);
    }
  },
});
```

**示例：** [qna.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/qna.ts)、[handoff.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/handoff.ts)

### 模式 3：设置/开关（SettingsList）

用于切换多个设置项。使用 `@earendil-works/pi-tui` 的 `SettingsList` 搭配 `getSettingsListTheme()`。

```typescript
import { getSettingsListTheme } from "@earendil-works/pi-coding-agent";
import { Container, type SettingItem, SettingsList, Text } from "@earendil-works/pi-tui";

pi.registerCommand("settings", {
  handler: async (_args, ctx) => {
    const items: SettingItem[] = [
      { id: "verbose", label: "Verbose mode", currentValue: "off", values: ["on", "off"] },
      { id: "color", label: "Color output", currentValue: "on", values: ["on", "off"] },
    ];

    await ctx.ui.custom((_tui, theme, _kb, done) => {
      const container = new Container();
      container.addChild(new Text(theme.fg("accent", theme.bold("Settings")), 1, 1));

      const settingsList = new SettingsList(
        items,
        Math.min(items.length + 2, 15),
        getSettingsListTheme(),
        (id, newValue) => {
          // 处理值变更
          ctx.ui.notify(`${id} = ${newValue}`, "info");
        },
        () => done(undefined),  // 关闭时
        { enableSearch: true }, // 可选：按 label 启用模糊搜索
      );
      container.addChild(settingsList);

      return {
        render: (w) => container.render(w),
        invalidate: () => container.invalidate(),
        handleInput: (data) => settingsList.handleInput?.(data),
      };
    });
  },
});
```

**示例：** [tools.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/tools.ts)

### 模式 4：持久状态指示器

在页脚显示跨渲染保留的状态。适合模式指示器。

```typescript
// 设置状态（显示在页脚）
ctx.ui.setStatus("my-ext", ctx.ui.theme.fg("accent", "● active"));

// 清除状态
ctx.ui.setStatus("my-ext", undefined);
```

**示例：** [status-line.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/status-line.ts)、[plan-mode/index.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/plan-mode/index.ts)、[preset.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/preset.ts)

### 模式 4b：自定义工作指示器

自定义 pi 在流式输出响应时显示的内联工作指示器。

```typescript
// 静态指示器
ctx.ui.setWorkingIndicator({ frames: [ctx.ui.theme.fg("accent", "●")] });

// 自定义动画指示器
ctx.ui.setWorkingIndicator({
  frames: [
    ctx.ui.theme.fg("dim", "·"),
    ctx.ui.theme.fg("muted", "•"),
    ctx.ui.theme.fg("accent", "●"),
    ctx.ui.theme.fg("muted", "•"),
  ],
  intervalMs: 120,
});

// 完全隐藏指示器
ctx.ui.setWorkingIndicator({ frames: [] });

// 恢复 pi 默认的加载动画
ctx.ui.setWorkingIndicator();
```

这只影响正常 streaming 时的工作指示器。上下文压缩和重试的加载器保持其内置样式。自定义帧会原样渲染，因此 extension 需要自行添加所需的颜色。

**示例：** [working-indicator.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/working-indicator.ts)

### 模式 5：编辑器上方/下方的小部件

在输入编辑器的上方或下方显示持久内容。适合待办列表、进度展示。

```typescript
// 简单的字符串数组（默认在编辑器上方）
ctx.ui.setWidget("my-widget", ["Line 1", "Line 2"]);

// 渲染在编辑器下方
ctx.ui.setWidget("my-widget", ["Line 1", "Line 2"], { placement: "belowEditor" });

// 或者带主题
ctx.ui.setWidget("my-widget", (_tui, theme) => {
  const lines = items.map((item, i) =>
    item.done
      ? theme.fg("success", "✓ ") + theme.fg("muted", item.text)
      : theme.fg("dim", "○ ") + item.text
  );
  return {
    render: () => lines,
    invalidate: () => {},
  };
});

// 清除
ctx.ui.setWidget("my-widget", undefined);
```

**示例：** [plan-mode/index.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/plan-mode/index.ts)

### 模式 6：自定义页脚

替换页脚。`footerData` 暴露了 extension 无法通过其他途径获取的数据。

```typescript
ctx.ui.setFooter((tui, theme, footerData) => ({
  invalidate() {},
  render(width: number): string[] {
    // footerData.getGitBranch(): string | null
    // footerData.getExtensionStatuses(): ReadonlyMap<string, string>
    return [`${ctx.model?.id} (${footerData.getGitBranch() || "no git"})`];
  },
  dispose: footerData.onBranchChange(() => tui.requestRender()), // 响应式
}));

ctx.ui.setFooter(undefined); // 恢复默认
```

token 统计信息可通过 `ctx.sessionManager.getBranch()` 和 `ctx.model` 获取。

**示例：** [custom-footer.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/custom-footer.ts)

### 模式 7：自定义编辑器（vim 模式等）

用自定义实现替换主输入编辑器。适用于模态编辑（vim）、不同的快捷键方案（emacs）或特殊的输入处理。

```typescript
import { CustomEditor, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { matchesKey, truncateToWidth } from "@earendil-works/pi-tui";

type Mode = "normal" | "insert";

class VimEditor extends CustomEditor {
  private mode: Mode = "insert";

  handleInput(data: string): void {
    // Escape：切换到 normal 模式，或透传给应用处理
    if (matchesKey(data, "escape")) {
      if (this.mode === "insert") {
        this.mode = "normal";
        return;
      }
      // normal 模式下，escape 会中止 agent（由 CustomEditor 处理）
      super.handleInput(data);
      return;
    }

    // insert 模式：全部交给 CustomEditor
    if (this.mode === "insert") {
      super.handleInput(data);
      return;
    }

    // normal 模式：vim 风格导航
    switch (data) {
      case "i": this.mode = "insert"; return;
      case "h": super.handleInput("\x1b[D"); return; // 左
      case "j": super.handleInput("\x1b[B"); return; // 下
      case "k": super.handleInput("\x1b[A"); return; // 上
      case "l": super.handleInput("\x1b[C"); return; // 右
    }
    // 未处理的按键传给 super（ctrl+c 等），但过滤掉可打印字符
    if (data.length === 1 && data.charCodeAt(0) >= 32) return;
    super.handleInput(data);
  }

  render(width: number): string[] {
    const lines = super.render(width);
    // 在底部边框上添加模式指示（用 truncateToWidth 做 ANSI 安全截断）
    if (lines.length > 0) {
      const label = this.mode === "normal" ? " NORMAL " : " INSERT ";
      const lastLine = lines[lines.length - 1]!;
      // 传入 "" 作为省略号，避免截断时添加 "..."
      lines[lines.length - 1] = truncateToWidth(lastLine, width - label.length, "") + label;
    }
    return lines;
  }
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", (_event, ctx) => {
    // 工厂函数从应用接收 TUI、主题和快捷键
    ctx.ui.setEditorComponent((tui, theme, keybindings) =>
      new VimEditor(tui, theme, keybindings)
    );
  });
}
```

**要点：**

- **继承 `CustomEditor`**（而不是基类 `Editor`），以获得应用级快捷键（escape 中止、ctrl+d 退出、模型切换等）
- 对不处理的按键**调用 `super.handleInput(data)`**
- **工厂模式**：`setEditorComponent` 接收一个工厂函数，该函数会拿到 `tui`、`theme` 和 `keybindings`
- **传入 `undefined`** 可恢复默认编辑器：`ctx.ui.setEditorComponent(undefined)`

**示例：** [modal-editor.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/modal-editor.ts)

## 关键规则

1. **始终使用回调中的 theme**——不要直接导入主题。使用 `ctx.ui.custom((tui, theme, keybindings, done) => ...)` 回调中的 `theme`。

2. **始终为 DynamicBorder 的颜色参数标注类型**——写成 `(s: string) => theme.fg("accent", s)`，而不是 `(s) => theme.fg("accent", s)`。

3. **状态变化后调用 tui.requestRender()**——在 `handleInput` 中更新状态后调用 `tui.requestRender()`。

4. **返回三方法对象**——自定义组件需要 `{ render, invalidate, handleInput }`。

5. **使用现有组件**——`SelectList`、`SettingsList`、`BorderedLoader` 覆盖 90% 的场景。不要重新造轮子。

## 示例

- **选择 UI**：[examples/extensions/preset.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/preset.ts) - SelectList 搭配 DynamicBorder 边框
- **可取消的异步操作**：[examples/extensions/qna.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/qna.ts) - 用 BorderedLoader 包装 LLM 调用
- **设置开关**：[examples/extensions/tools.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/tools.ts) - 用 SettingsList 启用/禁用 tool
- **状态指示器**：[examples/extensions/plan-mode/index.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/plan-mode/index.ts) - setStatus 与 setWidget
- **工作指示器**：[examples/extensions/working-indicator.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/working-indicator.ts) - setWorkingIndicator
- **自定义页脚**：[examples/extensions/custom-footer.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/custom-footer.ts) - setFooter 加统计信息
- **自定义编辑器**：[examples/extensions/modal-editor.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/modal-editor.ts) - 类 vim 模态编辑
- **贪吃蛇游戏**：[examples/extensions/snake.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/snake.ts) - 带键盘输入和游戏循环的完整游戏
- **自定义 tool 渲染**：[examples/extensions/todo.ts](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/todo.ts) - renderCall 与 renderResult
