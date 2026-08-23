> **译文** | 原文：[`packages/tui/README.md`](https://github.com/earendil-works/pi/blob/main/packages/tui/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-02 · 更新于 2026-08-21

# @earendil-works/pi-tui

极简终端 UI 框架，带差分渲染（differential rendering）和同步输出（synchronized output），用于构建无闪烁的交互式 CLI 应用。

## 特性

- **可互换的渲染器**：共享的 `TUI` 接口，配有主屏幕与备用屏幕两种实现
- **差分渲染**：只更新变化的行或视口行
- **由应用接管滚动**：备用屏幕视口支持鼠标、触控板和键盘导航
- **同步输出**：使用 CSI 2026 实现原子化屏幕更新（无闪烁）
- **Bracketed Paste Mode**：正确处理大段粘贴，超过 10 行的粘贴会显示标记
- **基于组件**：简单的 Component 接口，只需实现 render() 方法
- **主题支持**：组件接受 theme 接口，可自定义样式
- **内置组件**：Text、TruncatedText、Input、Editor、Markdown、Loader、SelectList、SettingsList、Spacer、Image、Box、Container、VStack、HStack、ScrollView
- **内联图片**：在支持 Kitty 或 iTerm2 图形协议的终端中渲染图片
- **自动补全支持**：文件路径和斜杠命令

## 快速开始

```typescript
import { type TUI, Text, Editor, ProcessTerminal, TuiMainScreen, matchesKey } from "@earendil-works/pi-tui";

// 创建终端
const terminal = new ProcessTerminal();

// 通过共享的 TUI 接口创建默认的主屏幕渲染器
const tui: TUI = new TuiMainScreen(terminal);

// 添加组件
tui.addChild(new Text("Welcome to my app!"));

import { defaultEditorTheme as editorTheme } from './test/test-themes.ts';
const editor = new Editor(tui, editorTheme);
editor.onSubmit = (text) => {
  console.log("Submitted:", text);
  tui.addChild(new Text(`You said: ${text}`));
};
tui.addChild(editor);

// 让编辑器获得焦点以接收键盘输入
tui.setFocus(editor);

// 在 raw mode 下 Ctrl+C 不会发送 SIGINT —— 在这里拦截以允许退出
tui.addInputListener((data) => {
  if (matchesKey(data, 'ctrl+c')) {
    tui.stop();
    process.exit(0);
  }
});

// 启动
tui.start();
```

## 核心 API

### TUI 接口与渲染器

`TUI` 是组件管理、焦点、overlay、输入、生命周期、终端查询与渲染的共享接口。只在构建应用时才需要选择具体的渲染器：

- `TuiMainScreen` 渲染到主终端缓冲区，保留终端回滚缓冲。
- `TuiAltScreen` 在备用终端缓冲区中渲染一个固定高度的视口，滚动由应用自己接管。停止时它会恢复主缓冲区，并打印完整的最终文档。

```typescript
import { type TUI, TuiAltScreen, TuiMainScreen } from "@earendil-works/pi-tui";

const tui: TUI = new TuiMainScreen(terminal);
// 若改为在备用终端缓冲区中使用由应用接管的视口：
// const tui: TUI = new TuiAltScreen(terminal);

tui.addChild(component);
tui.removeChild(component);
tui.start();
tui.stop();
tui.requestRender(); // 请求重新渲染

// 全局调试按键处理器（Shift+Ctrl+D）
tui.onDebug = () => console.log("Debug triggered");
```

### 备用屏幕的视口布局

`TuiAltScreen` 可以渲染一套明确的、按终端高度排布的布局。`VStack` 和 `HStack` 负责分配受约束的区域，`ScrollView` 则为某个区域接管滚动。这些语义在 `TuiMainScreen` 上是有意不提供的——那里回滚由终端掌管。

```typescript
import {
  Container,
  isViewportTUI,
  ScrollView,
  Text,
  VStack,
} from "@earendil-works/pi-tui";

const transcript = new Container();
transcript.addChild(new Text("History"));

const editorAndFooter = new VStack([
  editor,
  new Text("status"),
]);

if (isViewportTUI(tui)) {
  tui.setLayoutRoot(new VStack([
    {
      component: new ScrollView(transcript, {
        follow: "end",
        primary: true,
        overscroll: "chain",
      }),
      basis: 0,
      grow: 1,
      minSize: 1,
    },
    {
      component: editorAndFooter,
      basis: "auto",
      shrink: 1,
      minSize: 1,
    },
  ]));
}
```

Stack 条目支持 `basis`、`grow`、`shrink`、`minSize`、`maxSize` 以及响应式的 `visible` 回调。鼠标滚轮输入作用于指针下方的滚动视图，未消耗的增量默认会向外层滚动视图链式传递。主滚动视图会接收备用屏幕的键盘导航动作，以及位于不可滚动区域上方的滚轮输入。它还能在 OSC 133 语义提示符标记之间跳转，与常见终端的提示符导航快捷键一致。按 `Ctrl+Shift+F` 搜索其已渲染的内容，用 `Enter`/`Ctrl+G` 和 `Shift+Enter`/`Ctrl+Shift+G` 在匹配项之间移动，按 `Escape` 关闭搜索。`TuiAltScreenOptions.searchMatchStyle` 和 `searchCurrentMatchStyle` 可自定义匹配高亮。

每请求一帧，布局几何都会重新构建。有状态的组件会被保留，它们已有的渲染行缓存仍然有效。直接对这些布局组件调用 `render(width)` 会产生一份不受高度限制的文档；alt 模式恢复主屏幕时用的也是它。

### Overlays

Overlay 在现有内容之上渲染组件而不替换它。适用于对话框、菜单和模态 UI。

```typescript
// 用默认选项显示 overlay（居中，最大 80 列）
const handle = tui.showOverlay(component);

// 用自定义定位和尺寸显示 overlay
// 值可以是数字（绝对值）或百分比字符串（如 "50%"）
const handle = tui.showOverlay(component, {
  // 尺寸
  width: 60,              // 固定宽度（列数）
  width: "80%",           // 相对终端的百分比宽度
  minWidth: 40,           // 最小宽度下限
  maxHeight: 20,          // 最大高度（行数）
  maxHeight: "50%",       // 相对终端的百分比最大高度

  // 基于 anchor 的定位（默认：'center'）
  anchor: 'bottom-right', // 相对锚点定位
  offsetX: 2,             // 相对锚点的水平偏移
  offsetY: -1,            // 相对锚点的垂直偏移

  // 基于百分比的定位（anchor 的替代方式）
  row: "25%",             // 垂直位置（0%=顶部，100%=底部）
  col: "50%",             // 水平位置（0%=左侧，100%=右侧）

  // 绝对定位（覆盖 anchor/百分比）
  row: 5,                 // 精确行位置
  col: 10,                // 精确列位置

  // 距终端边缘的 margin
  margin: 2,              // 四边
  margin: { top: 1, right: 2, bottom: 1, left: 2 },

  // 响应式可见性
  visible: (termWidth, termHeight) => termWidth >= 100  // 窄终端上隐藏

  // 焦点行为
  nonCapturing: true       // 显示时不自动获取焦点
});

// OverlayHandle 方法
handle.hide();              // 永久移除 overlay
handle.setHidden(true);     // 临时隐藏（还可以再显示）
handle.setHidden(false);    // 隐藏后再次显示
handle.isHidden();          // 检查是否处于临时隐藏
handle.focus();             // 获得焦点并置于视觉最前
handle.unfocus();           // 释放焦点到常规回退目标
handle.unfocus({ target: baseComponent }); // 将此 overlay 的焦点释放给指定组件
handle.unfocus({ target: null });   // 释放此 overlay 的焦点且不指定接收者
handle.isFocused();         // 检查 overlay 是否拥有焦点

handle.unfocus();
// Overlay 失去焦点；TUI 回退到另一个可见的 capturing overlay 或之前的焦点目标。

handle.unfocus({ target: null });
// Overlay 失去焦点；在再次设置焦点之前没有组件接收输入。

// 拥有焦点的可见 overlay 会在临时替换 UI 释放焦点后重新获得键盘输入。
// 如果你希望在 overlay 保持可见时由某个特定组件接收输入，
// 调用 handle.unfocus({ target: component })。

// 隐藏最顶层的 overlay
tui.hideOverlay();

// 检查是否有任何可见的 overlay 处于活动状态
tui.hasOverlay();
```

**Anchor 值**：`'center'`、`'top-left'`、`'top-right'`、`'bottom-left'`、`'bottom-right'`、`'top-center'`、`'bottom-center'`、`'left-center'`、`'right-center'`

**解析顺序**：
1. `minWidth` 在宽度计算后作为下限应用
2. 位置：绝对 `row`/`col` > 百分比 `row`/`col` > `anchor`
3. `margin` 会钳制最终位置使其保持在终端边界内
4. `visible` 回调控制 overlay 是否渲染（每帧调用）

### Component 接口

所有组件都实现：

```typescript
interface Component {
  render(width: number): string[];
  handleInput?(data: string): void;
  invalidate?(): void;
}
```

| 方法 | 描述 |
|--------|-------------|
| `render(width)` | 返回字符串数组，每行一个。每行**不得超过 `width`**，否则 TUI 会报错。使用 `truncateToWidth()` 或手动换行来保证这一点。 |
| `handleInput?(data)` | 当组件拥有焦点并接收键盘输入时被调用。`data` 字符串包含原始终端输入（可能含 ANSI 转义序列）。 |
| `invalidate?()` | 被调用以清除任何缓存的渲染状态。组件应在下一次 `render()` 调用时从头重新渲染。 |

TUI 会在每条渲染行的末尾追加完整的 SGR reset 和 OSC 8 reset。样式不会跨行延续。如果你输出带样式的多行文本，请逐行重新应用样式，或使用 `wrapTextWithAnsi()`，使每个换行后的行都保留样式。

### Focusable 接口（IME 支持）

需要显示文本光标并支持 IME（输入法编辑器）的组件应实现 `Focusable` 接口：

```typescript
import { CURSOR_MARKER, type Component, type Focusable } from "@earendil-works/pi-tui";

class MyInput implements Component, Focusable {
  focused: boolean = false;  // 焦点变化时由 TUI 设置

  render(width: number): string[] {
    const marker = this.focused ? CURSOR_MARKER : "";
    // 在假光标之前输出 marker
    return [`> ${beforeCursor}${marker}\x1b[7m${atCursor}\x1b[27m${afterCursor}`];
  }
}
```

当一个 `Focusable` 组件获得焦点时，TUI 会：
1. 在组件上设置 `focused = true`
2. 在渲染输出中扫描 `CURSOR_MARKER`（一个零宽的 APC 转义序列）
3. 将硬件终端光标定位到该位置
4. 仅在启用 `showHardwareCursor` 时显示硬件光标

光标默认保持隐藏。这样既保留了假光标的渲染，又能为那些用隐藏光标跟踪 IME 候选窗口的终端定位硬件光标。有些终端需要可见的硬件光标才能定位 IME；可通过渲染器构造函数的 `showHardwareCursor` 参数、`setShowHardwareCursor(true)` 或 `PI_HARDWARE_CURSOR=1` 启用。内置的 `Editor` 和 `Input` 组件已实现该接口。

**包含内嵌输入的容器组件：** 当容器组件（对话框、选择器等）包含 `Input` 或 `Editor` 子组件时，容器必须实现 `Focusable` 并把焦点状态传播给子组件：

```typescript
import { Container, type Focusable, Input } from "@earendil-works/pi-tui";

class SearchDialog extends Container implements Focusable {
  private searchInput: Input;

  // 将焦点传播给子输入组件，以便 IME 光标定位
  private _focused = false;
  get focused(): boolean { return this._focused; }
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

没有这种传播，使用 IME（中文、日文、韩文等）输入时候选窗口会显示在错误的位置。

## 内置组件

### Container

对子组件进行分组。

```typescript
const container = new Container();
container.addChild(component);
container.removeChild(component);
```

### Box

对所有子组件应用 padding 和背景色的容器。

```typescript
const box = new Box(
  1,                              // paddingX（默认：1）
  1,                              // paddingY（默认：1）
  (text) => chalk.bgGray(text)   // 可选的背景函数
);
box.addChild(new Text("Content"));
box.setBgFn((text) => chalk.bgBlue(text));  // 动态更改背景
```

### Text

显示带自动换行和 padding 的多行文本。

```typescript
const text = new Text(
  "Hello World",                  // 文本内容
  1,                              // paddingX（默认：1）
  1,                              // paddingY（默认：1）
  (text) => chalk.bgGray(text)   // 可选的背景函数
);
text.setText("Updated text");
text.setCustomBgFn((text) => chalk.bgBlue(text));
```

### TruncatedText

截断以适应视口宽度的单行文本。适用于状态栏和 header。

```typescript
const truncated = new TruncatedText(
  "This is a very long line that will be truncated...",
  0,  // paddingX（默认：0）
  0   // paddingY（默认：0）
);
```

### Input

带水平滚动的单行文本输入框。

```typescript
const input = new Input();
input.onSubmit = (value) => console.log(value);
input.setValue("initial");
input.getValue();
```

**按键绑定：**
- `Enter` —— 提交
- `Ctrl+A` / `Ctrl+E` —— 行首/行尾
- `Ctrl+W` 或 `Alt+Backspace` —— 向后删除单词
- `Ctrl+U` —— 删除到行首
- `Ctrl+K` —— 删除到行尾
- `Ctrl+Left` / `Ctrl+Right` —— 按单词导航
- `Alt+Left` / `Alt+Right` —— 按单词导航
- 方向键、Backspace、Delete 均按预期工作

### Editor

多行文本编辑器，带自动补全、文件补全、粘贴处理，以及内容超过终端高度时的垂直滚动。

```typescript
interface EditorTheme {
  borderColor: (str: string) => string;
  selectList: SelectListTheme;
}

interface EditorOptions {
  paddingX?: number;  // 水平 padding（默认：0）
}

const editor = new Editor(tui, theme, options?);  // tui 为必需，用于感知高度的滚动
editor.onSubmit = (text) => console.log(text);
editor.onChange = (text) => console.log("Changed:", text);
editor.disableSubmit = true; // 临时禁用提交
editor.setAutocompleteProvider(provider);
editor.borderColor = (s) => chalk.blue(s); // 动态更改边框
editor.setPaddingX(1); // 动态更新水平 padding
editor.getPaddingX();  // 获取当前 padding
```

**特性：**
- 带自动换行的多行编辑
- 斜杠命令自动补全（输入 `/`）
- 文件路径自动补全（按 `Tab`）
- 大段粘贴处理（>10 行会创建 `[paste #1 +50 lines]` 标记）
- 编辑器上下方的水平分隔线
- 假光标渲染（隐藏真实光标）

**按键绑定：**
- `Enter` —— 提交
- `Shift+Enter`、`Ctrl+Enter` 或 `Alt+Enter` —— 换行（取决于终端，Alt+Enter 最可靠）
- `Tab` —— 自动补全
- `Ctrl+K` —— 删除到行尾
- `Ctrl+U` —— 删除到行首
- `Ctrl+W` 或 `Alt+Backspace` —— 向后删除单词
- `Alt+D` 或 `Alt+Delete` —— 向前删除单词
- `Ctrl+A` / `Ctrl+E` —— 行首/行尾
- `Ctrl+]` —— 向前跳到某字符（等待下一次按键，然后将光标移到第一个出现位置）
- `Ctrl+Alt+]` —— 向后跳到某字符
- 方向键、Backspace、Delete 均按预期工作

### Markdown

渲染 markdown，支持语法高亮和主题。

```typescript
interface MarkdownTheme {
  heading: (text: string) => string;
  link: (text: string) => string;
  linkUrl: (text: string) => string;
  code: (text: string) => string;
  codeBlock: (text: string) => string;
  codeBlockBorder: (text: string) => string;
  quote: (text: string) => string;
  quoteBorder: (text: string) => string;
  hr: (text: string) => string;
  listBullet: (text: string) => string;
  bold: (text: string) => string;
  italic: (text: string) => string;
  strikethrough: (text: string) => string;
  underline: (text: string) => string;
  highlightCode?: (code: string, lang?: string) => string[];
}

interface DefaultTextStyle {
  color?: (text: string) => string;
  bgColor?: (text: string) => string;
  bold?: boolean;
  italic?: boolean;
  strikethrough?: boolean;
  underline?: boolean;
}

const md = new Markdown(
  "# Hello\n\nSome **bold** text",
  1,              // paddingX
  1,              // paddingY
  theme,          // MarkdownTheme
  defaultStyle    // 可选的 DefaultTextStyle
);
md.setText("Updated markdown");
```

**特性：**
- 标题、粗体、斜体、代码块、列表、链接、引用块
- HTML 标签以纯文本渲染
- 通过 `highlightCode` 提供可选的语法高亮
- 支持 padding
- 渲染缓存以提升性能

### Loader

动画加载指示器。

```typescript
const loader = new Loader(
  tui,                              // 用于渲染更新的 TUI 实例
  (s) => chalk.cyan(s),            // spinner 颜色函数
  (s) => chalk.gray(s),            // 消息颜色函数
  "Loading..."                      // 消息（默认："Loading..."）
);
loader.start();
loader.setMessage("Still loading...");
loader.stop();
```

### CancellableLoader

在 Loader 基础上扩展了 Escape 键处理和用于取消异步操作的 AbortSignal。

```typescript
const loader = new CancellableLoader(
  tui,                              // 用于渲染更新的 TUI 实例
  (s) => chalk.cyan(s),            // spinner 颜色函数
  (s) => chalk.gray(s),            // 消息颜色函数
  "Working..."                      // 消息
);
loader.onAbort = () => done(null); // 用户按 Escape 时调用
doAsyncWork(loader.signal).then(done);
```

**属性：**
- `signal: AbortSignal` —— 用户按 Escape 时被 abort
- `aborted: boolean` —— loader 是否已被中止
- `onAbort?: () => void` —— 用户按 Escape 时的回调

### SelectList

支持键盘导航的交互式选择列表。

```typescript
interface SelectItem {
  value: string;
  label: string;
  description?: string;
}

interface SelectListTheme {
  selectedPrefix: (text: string) => string;
  selectedText: (text: string) => string;
  description: (text: string) => string;
  scrollInfo: (text: string) => string;
  noMatch: (text: string) => string;
}

const list = new SelectList(
  [
    { value: "opt1", label: "Option 1", description: "First option" },
    { value: "opt2", label: "Option 2", description: "Second option" },
  ],
  5,      // maxVisible
  theme   // SelectListTheme
);

list.onSelect = (item) => console.log("Selected:", item);
list.onCancel = () => console.log("Cancelled");
list.onSelectionChange = (item) => console.log("Highlighted:", item);
list.setFilter("opt"); // 过滤条目
```

**操作：**
- 方向键：导航
- Enter：选择
- Escape：取消

### SettingsList

带值循环切换和子菜单的设置面板。

```typescript
interface SettingItem {
  id: string;
  label: string;
  description?: string;
  currentValue: string;
  values?: string[];  // 提供时，Enter/Space 会在这些值之间循环
  submenu?: (currentValue: string, done: (selectedValue?: string) => void) => Component;
}

interface SettingsListTheme {
  label: (text: string, selected: boolean) => string;
  value: (text: string, selected: boolean) => string;
  description: (text: string) => string;
  cursor: string;
  hint: (text: string) => string;
}

const settings = new SettingsList(
  [
    { id: "theme", label: "Theme", currentValue: "dark", values: ["dark", "light"] },
    { id: "model", label: "Model", currentValue: "gpt-4", submenu: (val, done) => modelSelector },
  ],
  10,      // maxVisible
  theme,   // SettingsListTheme
  (id, newValue) => console.log(`${id} changed to ${newValue}`),
  () => console.log("Cancelled")
);
settings.updateValue("theme", "light");
```

**操作：**
- 方向键：导航
- Enter/Space：激活（循环切换值或打开子菜单）
- Escape：取消

### Spacer

用于垂直间距的空行。

```typescript
const spacer = new Spacer(2); // 2 个空行（默认：1）
```

### Image

在支持 Kitty 图形协议（Kitty、Ghostty、WezTerm）或 iTerm2 内联图片的终端中内联渲染图片。不支持的终端上回退为文本占位符。

```typescript
interface ImageTheme {
  fallbackColor: (str: string) => string;
}

interface ImageOptions {
  maxWidthCells?: number;
  maxHeightCells?: number;
  filename?: string;
}

const image = new Image(
  base64Data,       // base64 编码的图片数据
  "image/png",      // MIME 类型
  theme,            // ImageTheme
  options           // 可选的 ImageOptions
);
tui.addChild(image);
```

支持的格式：PNG、JPEG、GIF、WebP。尺寸会自动从图片头部解析。

#### 备用屏幕下的图片兼容性

在实现了 Kitty 图形协议的终端（包括 Kitty 和 Ghostty）中，`TuiAltScreen` 支持内联图片以及视口内的局部裁剪。iTerm2 的内联图片协议没有提供在滚动过程中删除既有放置或裁剪其源图的操作。为避免过期图片残留在已重绘的内容之上，`TuiAltScreen` 在 iTerm2 中会把图片组件渲染成文本占位符。`TuiMainScreen` 则仍然正常渲染 iTerm2 内联图片。

## 自动补全

### CombinedAutocompleteProvider

同时支持斜杠命令和文件路径。

```typescript
import { CombinedAutocompleteProvider } from "@earendil-works/pi-tui";

const provider = new CombinedAutocompleteProvider(
  [
    { name: "help", description: "Show help" },
    { name: "clear", description: "Clear screen" },
    { name: "delete", description: "Delete last message" },
  ],
  process.cwd() // 文件补全的基础路径
);

editor.setAutocompleteProvider(provider);
```

**特性：**
- 输入 `/` 查看斜杠命令
- 按 `Tab` 进行文件路径补全
- 支持 `~/`、`./`、`../` 和 `@` 前缀
- `@` 前缀时过滤为可附加的文件

## 按键检测

使用 `matchesKey()` 配合 `Key` 辅助对象检测键盘输入（支持 Kitty 键盘协议）：

```typescript
import { matchesKey, Key } from "@earendil-works/pi-tui";

if (matchesKey(data, Key.ctrl("c"))) {
  process.exit(0);
}

if (matchesKey(data, Key.enter)) {
  submit();
} else if (matchesKey(data, Key.escape)) {
  cancel();
} else if (matchesKey(data, Key.up)) {
  moveUp();
}
```

**按键标识符**（使用 `Key.*` 获得自动补全，或用字符串字面量）：
- 基本按键：`Key.enter`、`Key.escape`、`Key.tab`、`Key.space`、`Key.backspace`、`Key.delete`、`Key.home`、`Key.end`
- 方向键：`Key.up`、`Key.down`、`Key.left`、`Key.right`
- 带修饰键：`Key.ctrl("c")`、`Key.shift("tab")`、`Key.alt("left")`、`Key.ctrlShift("p")`
- 字符串格式也可以：`"enter"`、`"ctrl+c"`、`"shift+tab"`、`"ctrl+shift+p"`

## 渲染模式

`TuiMainScreen` 使用三种渲染策略：

1. **首次渲染**：输出所有行，不清除 scrollback
2. **宽度变化或视口上方发生变化**：清屏并完整重渲染
3. **常规更新**：将光标移动到第一个变化的行，清除到末尾，渲染变化的行

`TuiAltScreen` 掌管一个终端高度的视口。在没有显式布局根的情况下，它保持原有的单文档滚动行为。使用 `setLayoutRoot()` 后，`VStack`、`HStack` 和嵌套的 `ScrollView` 组件可以预留固定区域，并让受约束的区域各自独立滚动。它会就地更新发生变化的视口行，在位于底部时跟随流式输出，并在内容增长时保持手动选定的滚动位置。鼠标滚轮和可配置的键盘导航在滚动时不会改动终端回滚缓冲，其中也包括在 OSC 133 语义提示符标记之间跳转。点击 OSC 8 超链接会用配置好的 URL 处理程序打开它。按住主鼠标键拖动可选中文本并通过 OSC 52 复制到剪贴板；把拖动停在某个滚动视图的顶部或底部边缘会自动滚动，并把选区延伸到屏幕外的内容。Kitty 图片支持垂直方向的视口裁剪；iTerm2 内联图片则回退为文本，因为 iTerm2 协议无法在视口重绘期间删除或裁剪已放置的图像。

两种渲染器都会把更新包裹在**同步输出**（`\x1b[?2026h` ... `\x1b[?2026l`）中，实现原子化、无闪烁的渲染。

## Terminal 接口

TUI 可与任何实现了 `Terminal` 接口的对象配合工作：

```typescript
interface Terminal {
  start(onInput: (data: string) => void, onResize: () => void): void;
  stop(): void;
  write(data: string): void;
  get columns(): number;
  get rows(): number;
  moveBy(lines: number): void;
  hideCursor(): void;
  showCursor(): void;
  clearLine(): void;
  clearFromCursor(): void;
  clearScreen(): void;
}
```

**内置实现：**
- `ProcessTerminal` —— 使用 `process.stdin/stdout`
- `VirtualTerminal` —— 用于测试（使用 `@xterm/headless`）

## 工具函数

```typescript
import { visibleWidth, truncateToWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";

// 获取字符串的可见宽度（忽略 ANSI 码）
const width = visibleWidth("\x1b[31mHello\x1b[0m"); // 5

// 将字符串截断到指定宽度（保留 ANSI 码，添加省略号）
const truncated = truncateToWidth("Hello World", 8); // "Hello..."

// 不带省略号的截断
const truncatedNoEllipsis = truncateToWidth("Hello World", 8, ""); // "Hello Wo"

// 将文本按宽度换行（跨换行保留 ANSI 码）
const lines = wrapTextWithAnsi("This is a long line that needs wrapping", 20);
// ["This is a long line", "that needs wrapping"]
```

## 创建自定义组件

创建自定义组件时，**`render()` 返回的每一行都不得超过 `width` 参数**。如果有任何一行比终端宽，TUI 会报错。

### 处理输入

使用 `matchesKey()` 配合 `Key` 辅助对象处理键盘输入：

```typescript
import { matchesKey, Key, truncateToWidth } from "@earendil-works/pi-tui";
import type { Component } from "@earendil-works/pi-tui";

class MyInteractiveComponent implements Component {
  private selectedIndex = 0;
  private items = ["Option 1", "Option 2", "Option 3"];

  public onSelect?: (index: number) => void;
  public onCancel?: () => void;

  handleInput(data: string): void {
    if (matchesKey(data, Key.up)) {
      this.selectedIndex = Math.max(0, this.selectedIndex - 1);
    } else if (matchesKey(data, Key.down)) {
      this.selectedIndex = Math.min(this.items.length - 1, this.selectedIndex + 1);
    } else if (matchesKey(data, Key.enter)) {
      this.onSelect?.(this.selectedIndex);
    } else if (matchesKey(data, Key.escape) || matchesKey(data, Key.ctrl("c"))) {
      this.onCancel?.();
    }
  }

  render(width: number): string[] {
    return this.items.map((item, i) => {
      const prefix = i === this.selectedIndex ? "> " : "  ";
      return truncateToWidth(prefix + item, width);
    });
  }
}
```

### 处理行宽

使用提供的工具函数保证每行都在宽度之内：

```typescript
import { visibleWidth, truncateToWidth } from "@earendil-works/pi-tui";
import type { Component } from "@earendil-works/pi-tui";

class MyComponent implements Component {
  private text: string;

  constructor(text: string) {
    this.text = text;
  }

  render(width: number): string[] {
    // 方式 1：截断过长的行
    return [truncateToWidth(this.text, width)];

    // 方式 2：检查并填充到精确宽度
    const line = this.text;
    const visible = visibleWidth(line);
    if (visible > width) {
      return [truncateToWidth(line, width)];
    }
    // 填充到精确宽度（可选，用于背景色）
    return [line + " ".repeat(width - visible)];
  }
}
```

### ANSI 码注意事项

`visibleWidth()` 和 `truncateToWidth()` 都能正确处理 ANSI 转义码：

- `visibleWidth()` 计算宽度时忽略 ANSI 码
- `truncateToWidth()` 保留 ANSI 码，并在截断时正确闭合它们

```typescript
import chalk from "chalk";

const styled = chalk.red("Hello") + " " + chalk.blue("World");
const width = visibleWidth(styled); // 11（不计 ANSI 码）
const truncated = truncateToWidth(styled, 8); // 红色 "Hello" + " W..."，并正确 reset
```

### 缓存

出于性能考虑，组件应缓存其渲染输出，仅在必要时重新渲染：

```typescript
class CachedComponent implements Component {
  private text: string;
  private cachedWidth?: number;
  private cachedLines?: string[];

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) {
      return this.cachedLines;
    }

    const lines = [truncateToWidth(this.text, width)];

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

## 示例

完整的聊天界面示例见 `test/chat-simple.ts`，包含：
- 带自定义背景色的 Markdown 消息
- 响应期间的加载 spinner
- 带自动补全和斜杠命令的编辑器
- 消息之间的 Spacer

运行：
```bash
npx tsx test/chat-simple.ts
```

## 开发

```bash
# 安装依赖（在 monorepo 根目录）
npm install

# 运行类型检查
npm run check

# 运行演示
npx tsx test/chat-simple.ts
```

### 调试日志

设置 `PI_TUI_WRITE_LOG` 以捕获写入 stdout 的原始 ANSI 流。

```bash
PI_TUI_WRITE_LOG=/tmp/tui-ansi.log npx tsx test/chat-simple.ts
```
