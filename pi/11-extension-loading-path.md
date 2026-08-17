# 11 — 从磁盘文件到可调用的工具：扩展装配线

> 学习系列第 11 篇。08/09/10 三篇跟完了 `messages` 那条支流（树 → 路径 → 消息 → 报文 → 回来 → 落盘）。但 `Context` 是三个字段：
>
> ```typescript
> export interface Context {
> 	systemPrompt?: string;   // ← 没跟过
> 	messages: Message[];     // ← 09（出去）+ 10（回来）跟完了
> 	tools?: Tool[];          // ← 没跟过
> }
> ```
>
> 剩下两条的源头是同一套东西：**extension / skill / prompt / theme 的加载**。本篇跟 extension 这一条，路径是：**磁盘上的一个 `.ts` 文件 → 模型能调用的工具**。
>
> 与 05 篇的关系：05 篇是**参考手册**（事件目录、上下文对象、快捷键仲裁、两个官方案例），按模块组织；本篇是**路径视角**，只跟一条数据流，实现细节挂在路径段下。两篇互补，不重复的部分请看 05。
>
> 所有 `文件:行号` 基于 commit `859bd29bd`。核心文件两个：`packages/coding-agent/src/core/extensions/loader.ts`（发现 + 加载）、`runner.ts`（激活 + 派发）；汇合点在 `core/agent-session.ts`。

## 目录

- 第 1 章 全景：两条时间线，一条路径
- 第 2 章 发现段：三个来源怎么摊成一个路径数组
- 第 3 章 加载段：一个文件怎么变成一个盒子
- 第 4 章 盒子：加载段的产物长什么样
- 第 5 章 `runtime`：全场唯一的那一份
- 第 6 章 激活段：`bindCore` 把桩换成真货
- 第 7 章 运行期：生命周期点上现查现用
- 第 8 章 工程模式清单
- 第 9 章 复习自测

---

## 第 1 章 全景：两条时间线，一条路径

### 1.1 先分清两条时间线

这是本篇最容易混的前提。pi 里有两条节奏完全不同的线：

```text
【启动时，跑一次】                       【每一轮请求，重复跑】

ResourceLoader.reload()                  systemPrompt 现拼
  ├─ 发现 + 加载 extension                 tools 现结算
  ├─ 扫描 skill                                  ↓
  ├─ 加载 prompt template                Context { systemPrompt, messages, tools }
  ├─ 加载 theme                                  ↑
  └─ 读 AGENTS.md / CLAUDE.md              09/10 篇讲的就是这条
       ↑
   本篇在这条线上
```

**备料 vs 现炒。** 09/10 学的全是"现炒"——每轮都要重走一遍。本篇学的是"备料"：进程起来时干一次，之后摆在那儿等着被取用。

搞混的后果很具体：**你会以为改了扩展文件下一轮就生效。不会的，得 reload。**

### 1.2 一条路径，六段

```text
磁盘文件 ──发现──► 路径数组 ──加载──► 盒子 ──收拢──► Runner ──bindCore──► 激活 ──► 每轮进 Context
   ①            ②              ③           ④            ⑤          ⑥         ⑦
```

| 段 | 干什么 | 主函数 |
|---|---|---|
| ① 启动 | 六类资源分头加载 | `ResourceLoader.reload()` |
| ② 发现 | 三个来源 → 扁平路径数组 | `discoverAndLoadExtensions` `loader.ts:694` |
| ③ 加载 | 每个路径 → 一个盒子 | `loadExtension` `loader.ts:483` |
| ④ 收拢 | 盒子们 + 共享 runtime 一起交出 | `loadExtensionsInternal` `loader.ts:534` |
| ⑤ 激活 | 桩 ← 真实现 | `bindCore` `runner.ts:320` |
| ⑥ 结算 | 内置工具 + 各盒子 tools | `_refreshToolRegistry` `agent-session.ts:2874` |
| ⑦ 运行期 | 生命周期点上派发 | `emit` / `emitXxx` `runner.ts:820` 起 |

后面每章放大其中一段。

### 1.3 管家：`ResourceLoader`

`core/resource-loader.ts:39` 定义了一个接口，七个 getter 管六类资源：

```typescript
interface ResourceLoader {
	getExtensions(): LoadExtensionsResult;
	getSkills(): Skill[];
	getPrompts(): PromptTemplate[];
	getThemes(): Theme[];
	getContextFiles(): ContextFile[];
	// ...
	extendResources(...): ...;
	reload(): Promise<...>;
}
```

命令行上那排开关（`--no-extensions` / `--no-skills` / …，`main.ts:742` 附近）是**逐类独立**的：关掉扩展，skill 和 prompt 照常加载。这说明六类资源虽由一个管家统管，彼此并不依赖。

本篇只跟 extension 这一类。

---

## 第 2 章 发现段：三个来源怎么摊成一个路径数组

入口 `discoverAndLoadExtensions`（`loader.ts:694`）。名字里两个动词，前面全在"发现"，最后一行才"加载"。

### 2.1 三个来源，有序

```typescript
// :717  ① 项目本地
const localExtDir = path.join(resolvedCwd, CONFIG_DIR_NAME, "extensions");
addPaths(discoverExtensionsInDir(localExtDir));

// :722  ② 用户全局
const globalExtDir = path.join(resolvedAgentDir, "extensions");
addPaths(discoverExtensionsInDir(globalExtDir));

// :727  ③ 显式配置（--extensions / 设置文件）
for (const p of configuredPaths) { ... }
```

即 `<项目>/.pi/extensions/`、`~/.pi/extensions/`、显式指定。

### 2.2 去重：判重用绝对路径，入列用原始路径

```typescript
// :705-713
const addPaths = (paths: string[]) => {
	for (const p of paths) {
		const resolved = path.resolve(p);
		if (!seen.has(resolved)) {
			seen.add(resolved);
			allPaths.push(p);          // ← 存的是原始 p，不是 resolved
		}
	}
};
```

两个点：

- **判重用绝对路径**，保证 `./foo.ts` 和 `foo.ts` 不被当成两个。
- **入列用原始路径**，让"用户当初怎么称呼它"活到后面——错误信息里显示得像人话。

**先来先得。** 项目本地先扫，所以同名文件如果又被全局目录或显式参数指到，以最先加入的为准。这就是"项目覆盖全局"的实现——不是后者压前者，是**后者根本进不了队**。

### 2.3 一个目录里怎么分诊

`discoverExtensionsInDir`（`:654`）逐项判断，**只扫一层**：

```typescript
for (const entry of entries) {
	// 第一类：直接就是 .ts / .js 文件
	if ((entry.isFile() || entry.isSymbolicLink()) && isExtensionFile(entry.name)) {
		discovered.push(entryPath);
		continue;
	}
	// 第二/三类：一级子目录
	if (entry.isDirectory() || entry.isSymbolicLink()) {
		const entries = resolveExtensionEntries(entryPath);
		if (entries) discovered.push(...entries);
	}
}
```

**为什么不递归？** 注释说得直白：`No recursion beyond one level. Complex packages must use package.json manifest.` 递归会让"我这个目录到底会不会被当成扩展"变得不可预测；一层扫描 + 清单声明，行为是确定的。

### 2.4 `.ts.off` 为什么能当开关

```typescript
// :592-594
function isExtensionFile(name: string): boolean {
	return name.endsWith(".ts") || name.endsWith(".js");
}
```

只看后缀。`extension-test01.ts.off` 结尾是 `.off`，第一类不通过；它又不是目录，第二类也不进。**对整个系统就是不存在的。**

这不是设计出来的禁用机制，是判断条件的自然结果——但正因为足够自然，可以放心当开关用。

### 2.5 子目录的三级降级

`resolveExtensionEntries`（`:608`）决定一个子目录算不算扩展：

```text
① package.json 里有 pi.extensions 声明？
      → 逐个 path.resolve，只收 fs.existsSync 为真的
      → 收到至少一个 → 返回它们                    ← 声明式，支持多入口
      ↓ 没有清单 / 清单里的路径全都不存在
② 有 index.ts？              → 返回 [index.ts]      ← 约定式
      ↓
③ 有 index.js？              → 返回 [index.js]
      ↓
④ 返回 null                  → 整个目录跳过         ← 不报错，静默忽略
```

注意 ① 里的 `if (entries.length > 0)`：清单声明了三个入口但文件全没了，会**继续往下试 index**，而不是就此失败。**三级之间是降级，不是短路。**

### 2.6 这一段的产出

一个扁平路径数组，没有层级、没有分组、没有来源标记：

```javascript
[".pi/extensions/a.ts", ".pi/extensions/b/index.ts", "/abs/path/c.ts", ...]
```

**来源信息在这一步就丢了。** 后面 `createExtension` 会重新造一份 `sourceInfo`，那是给诊断用的，和发现来源不是一回事。

---

## 第 3 章 加载段：一个文件怎么变成一个盒子

### 3.1 循环之外先造 runtime

进入 `loadExtensionsInternal`（`:534`），循环**开始之前**：

```typescript
const resolvedRuntime = runtime ?? createExtensionRuntime();   // :546
```

**全场只造一个。** 这是整条线唯一"共享一份"的东西，第 5 章专门讲。先记住它在循环外。

### 3.2 每个路径六步

`loadExtension`（`:483`），去掉计时和错误处理是这样：

```typescript
const resolvedPath = resolvePath(extensionPath, cwd, { normalizeUnicodeSpaces: true });  // ①
const factory = await loadExtensionModule(resolvedPath, cacheToken);                     // ②
if (!factory) return { extension: null, error: `Extension does not export a valid factory function: ${extensionPath}` };

const extension = createExtension(extensionPath, resolvedPath);                          // ③
const api = createExtensionAPI(extension, runtime, cwd, eventBus);                       // ④
await factory(api);                                                                       // ⑤
return { extension, error: null };                                                        // ⑥
```

大白话：

```text
① 把路径变成绝对路径
② jiti import 进来，拿到 export default 的那个函数
③ 准备一个空盒子：{ tools: 空Map, handlers: 空Map, ... }
④ 造一个 pi 对象，它记住了"要往③那个盒子里放"
⑤ 调用你的函数：factory(pi)
     └─ 你写的 pi.registerTool(...) 就在这一刻把工具塞进盒子
⑥ 函数返回，盒子装好了
```

### 3.3 关键认知：工厂函数只跑一次

```typescript
export default function (pi: ExtensionAPI) { ... }
```

**只在启动时被调用一次**，就是第 ⑤ 步。不是每轮请求跑一遍，也不是每次工具调用跑一遍。

它的唯一职责是**声明**：把工具、事件处理器、命令登记到盒子里，然后返回。真正干活的代码（工具的 `execute`、事件 handler）是作为**闭包**被登记进去的，将来由别人在别的时刻调用。

**这个区分是后面一切的地基**（第 5、6、7 章全建立在它之上）。

### 3.4 第 ③ 步：`extensionPath` 与 `resolvedPath` 为什么是两个

```typescript
// :462-481
function createExtension(extensionPath: string, resolvedPath: string): Extension {
	const source =
		extensionPath.startsWith("<") && extensionPath.endsWith(">")
			? extensionPath.slice(1, -1).split(":")[0] || "temporary"
			: "local";
	const baseDir = extensionPath.startsWith("<") ? undefined : path.dirname(resolvedPath);
	return {
		path: extensionPath,
		resolvedPath,
		sourceInfo: createSyntheticSourceInfo(extensionPath, { source, baseDir }),
		handlers: new Map(), tools: new Map(), messageRenderers: new Map(),
		entryRenderers: new Map(), commands: new Map(), flags: new Map(), shortcuts: new Map(),
	};
}
```

| | `extensionPath` | `resolvedPath` |
|---|---|---|
| 是什么 | 原始路径，人写下的那串 | 规范化后的绝对路径 |
| 可能长什么样 | `.pi/extensions/a.ts`、`<temporary:abc>` | `D:/.../a.ts` |
| 干什么用 | 显示、错误信息、来源判定 | 真去磁盘找文件（`loadExtensionModule` 用它） |

三处用途正好印证分工：`source` 判"是不是 `<...>` 形式"，看的是**原始**路径的形状；`baseDir` 用 `path.dirname(resolvedPath)`，必须**绝对**路径算才靠谱；两个都原样存进盒子，供后续 reload、报错、资源归属各取所需。

**支路：内联扩展。** `loadExtensionFromFactory`（`:515`）是同一条装配线的第二个进料口——不给路径，直接给工厂函数：

```typescript
const extension = createExtension(extensionPath, extensionPath);   // 两个都传 "<inline>"
const api = createExtensionAPI(extension, runtime, resolvedCwd, eventBus);
await factory(api);
```

**唯一区别是 factory 从哪来**：文件扩展要 `import` 才拿到，内联扩展直接当参数传。之后 ③④⑤ 完全同流。用于测试和程序内嵌。它没有磁盘位置，所以用 `<...>` 合成标识占住路径的位置——那对"看起来多余的两个路径"，正是为了让它也能套进同一套代码。

### 3.5 第 ④ 步：`pi` 怎么和盒子绑上

```typescript
// :247-270
function createExtensionAPI(extension: Extension, runtime: ExtensionRuntime, cwd: string, eventBus: EventBus): ExtensionAPI {
	const api = {
		registerTool(tool: ToolDefinition): void {
			runtime.assertActive();
			extension.tools.set(tool.name, {       // ← extension 是闭包变量，不是参数
				definition: tool,
				sourceInfo: extension.sourceInfo,
			});
			runtime.refreshTools();
		},
		// ...
	};
	return api;
}
```

`registerTool` 里的 `extension` 是**闭包捕获**的——就是第 ③ 步刚造出来的那一个盒子。

所以三个扩展会走三遍 ③④⑤：

```text
扩展 A → 盒子A → piA（写向盒子A）→ factoryA(piA)
扩展 B → 盒子B → piB（写向盒子B）→ factoryB(piB)
扩展 C → 盒子C → piC（写向盒子C）→ factoryC(piC)
```

**三个盒子，三个 `pi`，互不相干。** A 注册的工具不可能跑到 B 的盒子里——不是因为有什么检查，而是因为 `piA` 的闭包里压根没有盒子 B 的引用。**用闭包做隔离，比用 id 做归属检查更省事也更可靠。**

### 3.6 `pi` 和 `extension` 是两个东西

最容易糊在一起的地方：

```text
extension  ── 纯数据。7 个 Map，没有任何方法。
pi (api)   ── 纯方法。registerTool / on / registerCommand…，自己不存数据。
```

**`pi` 是一个"专门往某个盒子里放东西"的遥控器，`extension` 是那个盒子。** factory 手里只拿到遥控器，够不到盒子本身，只能通过按钮往里放。这也是为什么每个扩展要配一个自己的 `pi`——遥控器和盒子一对一绑死。

### 3.7 `pi` 上的方法分两类

```typescript
const api = {
	// 【注册类】写向 extension 的 Map
	registerTool(tool)   { extension.tools.set(...); },
	on(event, handler)   { extension.handlers.get(...)...push(...); },
	registerCommand(...) { extension.commands.set(...); },

	// 【动作类】不碰 Map，转发给共享 runtime
	sendMessage(msg)     { runtime.assertActive(); runtime.sendMessage(msg); },   // :329
	appendEntry(...)     { runtime.assertActive(); runtime.appendEntry(...); },   // :339
	exec(cmd, args, o)   { runtime.assertActive(); return execCommand(...); },    // :359
};
```

- **注册类**：写进自己的盒子。声明"我有这些能力"。加载期就绪。
- **动作类**：转发给 `runtime`。真去"发消息、写会话、执行命令"。**加载期还不能用**（第 5 章）。

注：`exec` 是个小例外——它不转发 `runtime.exec`，直接调 `execCommand`，只借 runtime 做 `assertActive` 和 cwd 兜底。

### 3.8 错误隔离

```typescript
// :557-560
if (error) { errors.push({ path: extPath, error }); continue; }
if (extension) { extensions.push(extension); }
```

**单个扩展抛错只记进 `errors` 数组，不影响其它扩展继续加载。** 这条在第 7 章还会以另一种形式出现（handler 级别的隔离）。

---

## 第 4 章 盒子：加载段的产物长什么样

### 4.1 类型定义

```typescript
// types.ts:1752
export interface Extension {
	path: string;                                  // 原始路径
	resolvedPath: string;                          // 绝对路径
	hidden?: boolean;
	sourceInfo: SourceInfo;

	handlers:         Map<string, HandlerFn[]>;        // 事件名 → 处理器【数组】
	tools:            Map<string, RegisteredTool>;     // 工具名 → 工具
	commands:         Map<string, RegisteredCommand>;  // 命令名 → 命令
	messageRenderers: Map<string, MessageRenderer>;    // customType → 渲染器
	entryRenderers?:  Map<string, EntryRenderer>;
	flags:            Map<string, ExtensionFlag>;
	shortcuts:        Map<KeyId, ExtensionShortcut>;
	markdownTransformer?: MarkdownTransformer;         // 唯一非 Map 的可注册项
}
```

三个元数据 + 七个 Map。

**注意 `handlers` 的值是数组**，别的都是单值。因为同一事件可以挂多个处理器（`pi.on("x", a); pi.on("x", b)` 两个都留着），而同名工具/命令是覆盖关系。

### 4.2 一个填满的盒子

设扩展这么写：

```typescript
export default function (pi: ExtensionAPI) {
	pi.registerTool(defineTool({
		name: "git_recent", label: "Git Recent",
		description: "列出最近若干条 git 提交",
		parameters: gitRecentSchema,
		async execute(id, params, signal, onUpdate, ctx) { /* ... */ },
		renderCall(args, theme) { /* ... */ },
		renderResult(result, state, theme) { /* ... */ },
	}));
	pi.registerCommand("git-log", { description: "打印最近提交", handler: async (args, ctx) => { /* ... */ } });
	pi.on("session_start", async (event, ctx) => { /* ... */ });
	pi.on("turn_end",      async (event, ctx) => { /* ... */ });
	pi.on("turn_end",      async (event, ctx) => { /* 第二个 */ });
}
```

`await factory(api)` 返回的那一刻，盒子是：

```javascript
{
  path:         ".pi/extensions/git-recent.ts",
  resolvedPath: "D:/Coding/GitCoding/pi/.pi/extensions/git-recent.ts",
  sourceInfo:   { source: "local", baseDir: "D:/.../.pi/extensions", ... },

  tools: Map(1) {
    "git_recent" => {
      definition: {                          // ← 你传给 defineTool 的对象，原样躺着
        name: "git_recent", label: "Git Recent",
        description: "列出最近若干条 git 提交",
        parameters: { type: "object", properties: { count: {...} } },
        execute:      [Function],            // ← 函数本体，此刻不执行
        renderCall:   [Function],
        renderResult: [Function],
      },
      sourceInfo: { source: "local", ... }   // ← 加载器补的
    }
  },
  commands: Map(1) {
    "git-log" => { name: "git-log", description: "打印最近提交", handler: [Function], sourceInfo: {...} }
  },
  handlers: Map(2) {
    "session_start" => [ [Function] ],
    "turn_end"      => [ [Function], [Function] ]   // ← 两个，按注册顺序
  },
  messageRenderers: Map(0) {},   entryRenderers: Map(0) {},
  flags:            Map(0) {},   shortcuts:      Map(0) {},
}
```

### 4.3 三个值得盯的点

**① 全是"躺着的函数"。** `execute`、`handler`、那两个 `turn_end`——加载结束时一个都没跑过。**盒子是声明清单，不是执行结果。**

**② `sourceInfo` 是加载器塞的，不是你写的。**

```typescript
extension.tools.set(tool.name, {
	definition: tool,                 // ← 你给的，原样包住
	sourceInfo: extension.sourceInfo, // ← 加载器补的
});
```

典型的**包装模式**：你的对象整个塞进 `definition`，外面套一层记"这东西哪来的"。将来界面要显示"该工具来自哪个扩展"、出错要指出是谁的锅，靠的就是这层。跟 09 篇的"外来对象整体存，自家字段拆开存"是同一判据——`definition` 的 schema 归你，`sourceInfo` 归 pi。

**③ 没注册的是空 Map，不是 `undefined`。** `createExtension` 一律预填 `new Map()`，所以上层汇总时可以无脑遍历，不用到处判空。

### 4.4 盒子不聚合

```javascript
extensionA = { path: "a.ts", tools: Map{"git_recent"}, handlers: Map{"turn_end"}, ... }
extensionB = { path: "b.ts", tools: Map{},             handlers: Map{"session_start"}, ... }
extensionC = { path: "c.ts", tools: Map{"foo","bar"},  commands: Map{"hello"}, ... }
```

`LoadExtensionsResult.extensions` 就是这三个盒子组成的数组。**盒子不聚合、不排序、不去重**——它只忠实记录"这一个扩展声明了什么"。聚合是上层的活（第 7 章）。

---

## 第 5 章 `runtime`：全场唯一的那一份

### 5.1 份数：和盒子正好相反

```typescript
// loadExtensionsInternal :546  —— 循环之外，只造一个
const resolvedRuntime = runtime ?? createExtensionRuntime();

for (const extPath of paths) {
	await loadExtension(extPath, resolvedCwd, resolvedEventBus, resolvedRuntime, cacheToken);
	//                                                          ↑ 每个扩展收到同一个
}
```

对照 `extension` 是在 `loadExtension` **内部**每次新造的：

```text
          piA ──┬──► extensionA（自己的盒子）
                └──► runtime ─┐
          piB ──┬──► extensionB（自己的盒子）
                └──► runtime ─┼──►  同一个 runtime
          piC ──┬──► extensionC（自己的盒子）
                └──► runtime ─┘

盒子：一扩展一个，隔离          runtime：全场一个，共享
```

### 5.2 为什么正好相反

因为两者性质相反：

- **盒子装"声明"**——A 注册了什么，是 A 私有的事，绝不能漏进 B。**必须隔离**。
- **runtime 装"动作能力"**——发消息、执行命令、往会话树追加。这些操作的对象是**同一个会话、同一个进程**。A 发消息和 B 发消息，发的是同一个对话，没有"A 的会话"之说。**必须共享**。

一句话：**盒子回答"谁声明了什么"（各人各账），runtime 回答"怎么真正干活"（干的是同一件事）。**

### 5.3 一造出来全是"调了就抛错"的桩

```typescript
// loader.ts:184-239
export function createExtensionRuntime(): ExtensionRuntime {
	const notInitialized = () => {
		throw new Error("Extension runtime not initialized. Action methods cannot be called during extension loading.");
	};
	const runtime: ExtensionRuntime = {
		sendMessage:     notInitialized,
		sendUserMessage: notInitialized,
		appendEntry:     notInitialized,
		setSessionName:  notInitialized,
		getActiveTools:  notInitialized,
		setActiveTools:  notInitialized,
		// ...一大排
		refreshTools: () => {},                  // ← 例外，见 5.5
		setModel: () => Promise.reject(new Error("Extension runtime not initialized")),
		flagValues: new Map(),
		pendingProviderRegistrations: [],        // ← 另一种解法，见 5.6
		pendingNativeProviderRegistrations: [],
		assertActive,
		invalidate: (message) => { state.staleMessage ??= message ?? "...stale..."; },
		registerProvider: (name, config, extensionPath = "<unknown>") => {
			runtime.pendingProviderRegistrations.push({ name, config, extensionPath });
		},
		// ...
	};
	return runtime;
}
```

### 5.4 为什么是桩：先有鸡还是先有蛋

```text
启动顺序：
  1. 加载扩展   ← factory 在这里跑，需要一个 runtime 传给 pi
  2. 建 AgentSession（会话、模型、工具集这些"真能力"这时才成型）
  3. 把 2 的能力灌进 runtime（bindCore）
```

扩展在**第 1 步**就要 `factory(pi)`，可 `sendMessage` 真正依赖的会话（第 2 步）**还不存在**。runtime 必须在第 1 步先造出来交给 pi，但它此刻是个空壳。

两个选择：

- 让它是 `undefined` / 空函数 → 扩展调了静默无事发生，人一头雾水。
- 让它是 `notInitialized`（**调了就抛明确的错**）→ 作者立刻看到 `"Action methods cannot be called during extension loading."`，知道自己用错了阶段。

pi 选后者。**桩不是占位，是护栏。**

于是"为什么 factory 里 `pi.sendMessage` 会报错"就闭环了：

```typescript
export default function (pi) {
	pi.registerTool(tool);       // ✅ 注册类 → 写自己的盒子，随时能干
	pi.sendMessage("hi");        // ❌ 动作类 → 转发到 runtime.sendMessage，此刻是桩 → 抛错
}
```

### 5.5 `refreshTools` 为什么是空函数不是桩

```typescript
// registerTool() is valid during extension load; refresh is only needed post-bind.
refreshTools: () => {},
```

加载期注册工具是**合法的**（注册类嘛），而 `registerTool` 内部会调 `runtime.refreshTools()`。但那会儿还没有"已结算的工具表"需要刷新，所以给个空函数直接吞掉，**而不是抛错**。

**判据：这个调用在当前阶段是不是合法行为。** 合法但无事可做 → 空函数；不合法 → 抛错。

### 5.6 同一难题的另一种解法：排队

```typescript
registerProvider: (name, config, extensionPath = "<unknown>") => {
	runtime.pendingProviderRegistrations.push({ name, config, extensionPath });
},
```

**同样是"东西还没就绪"，这里用排队而不是抛错。** 取决于语义：

| 方法 | 语义 | 加载期能不能兑现 | 解法 |
|---|---|---|---|
| `sendMessage` | "现在就给我发一条" | 加载期没有"现在" | **拒绝**（抛错） |
| `registerProvider` | "我想登记一个 provider" | 是可推迟的意愿 | **记账**（排队，后补） |

**一个是即时动作，一个是可延迟兑现的意愿。** 分清这两者，就知道该抛错还是该排队。

### 5.7 `assertActive`：另一个维度的失效

```typescript
const state: { staleMessage?: string } = {};
const assertActive = () => { if (state.staleMessage) throw new Error(state.staleMessage); };
```

注意 `pi` 上**注册类和动作类方法都会先调 `runtime.assertActive()`**。这防的是另一件事：会话被替换（`newSession` / `fork` / `switchSession` / `reload`）之后，扩展还攥着旧的 `pi` 不放。`invalidate()` 一旦被调，整个 runtime 就"作废"，任何后续调用都抛出带修复建议的错。

**两道防线各管一头：`notInitialized` 管"太早"，`assertActive` 管"太晚"。**

---

## 第 6 章 激活段：`bindCore` 把桩换成真货

### 6.1 收拢：交出三样东西

```typescript
// :567-571
return { extensions, errors, runtime: resolvedRuntime };
```

`runtime` 也被一并交出去——它得往上传，因为**上面那层才有能力把桩换掉**。

到这里"加载"结束，所有扩展的声明都已定型，但**动作还全是死的**。

### 6.2 `AgentSession` 构造时激活

```typescript
// agent-session.ts:2850 起
const extensionsResult = this._resourceLoader.getExtensions();   // 取回上一段的产物

this._extensionRunner = new ExtensionRunner(
	extensionsResult.extensions,   // 所有盒子
	extensionsResult.runtime,      // 那个共享 runtime
	this._cwd, this.sessionManager, new ModelRegistry(this._modelRuntime),
);                                                                // :2857
this._bindExtensionCore(this._extensionRunner);                   // :2867 ← 里面调 bindCore
this._applyExtensionBindings(this._extensionRunner);
```

### 6.3 `bindCore` 干的事：就地替换

```typescript
// runner.ts:320-344
bindCore(actions: ExtensionActions, contextActions: ExtensionContextActions, providerActions?: {...}) {
	this.runtime.sendMessage     = actions.sendMessage;
	this.runtime.sendUserMessage = actions.sendUserMessage;
	this.runtime.appendEntry     = actions.appendEntry;
	this.runtime.setSessionName  = actions.setSessionName;
	this.runtime.getActiveTools  = actions.getActiveTools;
	this.runtime.setActiveTools  = actions.setActiveTools;
	this.runtime.refreshTools    = actions.refreshTools;
	this.runtime.setModel        = actions.setModel;
	// ...十几行，桩逐个换成能摸到真会话的实现
```

`agent-session.ts:2635` 传进去的 `actions` 就是这些真实现——它们能摸到 `sessionManager`、当前模型、abort 信号这些真会话资源。

顺带把加载期排队的 provider 冲刷进 `ModelRegistry`，并把 `registerProvider` 从"排队版"换成"立即生效版"：

```typescript
// :379-418
this.runtime.pendingProviderRegistrations = [];        // 冲刷完清空
// ...
this.runtime.registerProvider = (name, config) => {    // 换成直接调用
	if (providerActions?.registerProvider) { providerActions.registerProvider(name, config); return; }
	this.modelRegistry.registerProvider(name, config);
};
```

### 6.4 `bindCore` 完全没碰盒子

**它只管 runtime。** 你注册的工具、handler 早在加载段就填好了。

这是本篇最需要分清的两条线：

```text
线一（盒子）：handler 函数 ──加载段存进盒子──┐
                                            ├─► 运行期回调执行时相遇 → 能干活
线二（runtime）：sendMessage ──bindCore换真──┘
```

- **线一在加载段定型**，内容是"什么时候、调什么"。
- **线二在 bindCore 定型**，内容是"调用能不能真正生效"。
- **回调把两者在运行期粘起来。**

所以"动作要写进注册内容里"的道理，**不是动作晚点才生成，而是执行时机被推迟到了 runtime 就绪之后**。

### 6.5 落到扩展作者手上的一条规则

```typescript
export default function (pi) {
	// 【位置 A】factory 体本身 —— 执行时机 = bindCore 之前
	pi.sendMessage("hi");                    // ❌ 撞桩
	pi.registerTool(myTool);                 // ✅ 注册类

	// 【位置 B】回调 —— 只是登记，此刻不执行
	pi.on("session_start", async (event, ctx) => {
		await pi.sendMessage("会话开始了");   // ✅ 触发时 bindCore 早已完成
	});
}
// 【位置 C】工具的 execute —— 模型调用工具时才跑，同样安全
```

> **不要在 `export default` 函数体里直接调动作；把动作放进回调里**——`pi.on(...)` 的处理器、工具的 `execute`、命令的 handler。那些回调都是会话跑起来才被触发的，动作那时保证可用。

**factory 体的唯一职责是声明"我有什么"；真正"干什么"永远发生在回调里。**

### 6.6 结算工具

```typescript
// agent-session.ts:2874
this._refreshToolRegistry({ activeToolNames: baseActiveToolNames, includeAllExtensionTools: options.includeAllExtensionTools });
```

内置工具 + 各盒子的 `tools` Map 汇成一份工具注册表。**这就是 `Context.tools` 的源头。**

具体怎么结算、怎么进 `Context`，以及 `systemPrompt` 那条支流——是下一段的内容，本篇未跟。

---

## 第 7 章 运行期：生命周期点上现查现用

### 7.1 没有合并索引，全是临时遍历

```typescript
// runner.ts:585
hasHandlers(eventType: string): boolean {
	for (const ext of this.extensions) {                 // ← 外层：遍历所有盒子
		const handlers = ext.handlers.get(eventType);      // ← 内层：现查这个盒子的 Map
		if (handlers && handlers.length > 0) return true;
	}
	return false;
}
```

连"有没有人监听这个事件"都是**每次现场扫一遍**，没有预建索引。其它 getter 同理：

```typescript
// :595
getMessageRenderer(customType) {
	for (const ext of this.extensions) {
		const renderer = ext.messageRenderers.get(customType);
		if (renderer) return renderer;      // ← 先找到的赢，天然"先来先得"
	}
	return undefined;
}

// :605
getMarkdownTransformers(): MarkdownTransformer[] {
	return this.extensions.flatMap((ext) => (ext.markdownTransformer ? [ext.markdownTransformer] : []));
}
```

**为什么不合并成一张大表：**

1. **遍历成本可忽略。** 扩展是个位数，每个一次 `Map.get`，相比 handler 里的 IO 是噪音。
2. **合并表要同步。** 一旦建了 `mergedHandlers`，reload / 启停扩展 / 动态注册就都得记得更新它。**多一份派生状态就多一处能失配的地方；现场遍历永远不会过期。**
3. **冲突语义要留给调用方**——见 7.3。

### 7.2 派发的骨架：两层循环

```typescript
// runner.ts:820
async emit<TEvent extends RunnerEmitEvent>(event: TEvent): Promise<RunnerEmitResult<TEvent>> {
	const ctx = this.createContext();
	let result: SessionBeforeEventResult | undefined;

	for (const ext of this.extensions) {                     // ← 第一层：按扩展加载顺序
		const handlers = ext.handlers.get(event.type);
		if (!handlers || handlers.length === 0) continue;

		for (const handler of handlers) {                     // ← 第二层：按注册顺序
			try {
				const handlerResult = await handler(event, ctx);
				if (this.isSessionBeforeEvent(event) && handlerResult) {
					result = handlerResult as SessionBeforeEventResult;
					if (result.cancel) return result as RunnerEmitResult<TEvent>;   // ← 短路
				}
			} catch (err) { /* 记进 errors，不打断 */ }
		}
	}
	// ...
}
```

**两层循环的顺序就是语义**：扩展加载顺序（项目 → 全局 → 显式）套上单扩展内的注册顺序，合起来是一条确定的询问链。注释写明：`严格按扩展加载顺序和 handler 注册顺序串行执行，后续处理器可观察前序产生的外部状态。`

### 7.3 四种聚合语义

关键在于**"根据逻辑执行"的逻辑不是一套，每个事件各有各的**。看类型定义：

```typescript
// runner.ts:129
/**
 * Events handled by the generic emit() method.
 * Events with dedicated emitXxx() methods are excluded for stronger type safety.
 * 专用分派方法承载各事件不同的短路、链式变换或聚合语义，不能退化为统一返回类型。
 */
type RunnerEmitEvent = Exclude<ExtensionEvent, ToolCallEvent | ProjectTrustEvent | ...>;
```

**事件分两类**：普通事件走通用 `emit()`；返回值有意义的事件从类型里 `Exclude` 出去，**逼你走专用通道** `emitXxx()`。

| 语义 | 例子 | 行为 |
|---|---|---|
| 广播 | 大多数事件 | 全叫一遍，返回值丢弃 |
| 短路投票 | `project_trust` | 首个明确表态者胜出，弃权者继续往下问 |
| 链式变换 | `before_agent_start` 的 `systemPrompt` | 上一个的输出当下一个的输入 |
| 聚合收集 | `before_agent_start` 的 `messages` | 每个都可能贡献，合并成数组 |

短路投票（`:208-227`）：

```typescript
for (const handler of handlers) {
	const handlerResult = await handler(event, ctx) as ProjectTrustEventResult;
	if (handlerResult.trusted === "undecided") continue;      // 弃权 → 问下一个
	return { result: handlerResult, errors };                 // 表态 → 立刻返回
}
```

**链式 + 收集同时发生在一个循环里**（`:1129-1153`），这是最精彩的一例：

```typescript
let currentSystemPrompt = systemPrompt;
const messages = [];

for (const ext of this.extensions) {
	for (const handler of ext.handlers.get("before_agent_start") ?? []) {
		const event = { type: "before_agent_start", prompt, images, systemPrompt: currentSystemPrompt, ... };
		const result = await handler(event, ctx);
		if (result?.message)               messages.push(result.message);   // ← 收集
		if (result?.systemPrompt !== undefined) {
			currentSystemPrompt = result.systemPrompt;                        // ← 链式
			systemPromptModified = true;
		}
	}
}
```

**同一个 handler 的返回值，两个字段走两种语义**：`message` 是收集（人人有份），`systemPrompt` 是链式（一棒接一棒）。而且传给下一个 handler 的 `event.systemPrompt` 是**累计值**，连 `ctx.getSystemPrompt()` 都被特意重写成返回当前累计值：

```typescript
// :1121-1125
ctx.getSystemPrompt = () => {
	// before_agent_start 链中 getSystemPrompt 返回当前累计值，而非事件开始前的静态提示词。
	this.assertActive();
	return currentSystemPrompt;
};
```

**这就是"一张合并表"方案做不到的事**——同一份数据四种读法，预先合并只能挑一种。

### 7.4 有些 handler 不只是被通知，而是能改变结果

广播型 handler 只是旁观者。链式/投票型是**决策参与者**：

```text
project_trust        → 返回值决定这个项目要不要被信任
before_agent_start   → 返回值改写 systemPrompt、往上下文塞消息
tool_call            → 可以拦截、改参数、阻止工具执行
```

这才是扩展系统真正的威力：不是"发生了什么告诉我一声"，而是"**在这个决策点上，你有发言权**"。

顺带，`before_agent_start` 能改 `systemPrompt` 说明：**`Context.systemPrompt` 不只是拼装出来的静态文本，扩展在每轮开始前还能插手改它。** 这是下一段的伏笔。

### 7.5 唯一的例外：工具被结算

工具确实有一份**汇总产物**——`_refreshToolRegistry`。为什么它特殊？

因为工具清单要**整体发给模型**（进 `Context.tools`），必须是确定的、去过重的、当轮固定的列表；而且它带状态（哪些 active、哪些禁用）。所以它需要"结算"，不能每次现查。

这正是 `runtime.refreshTools()` 存在的理由——扩展在运行期动态注册工具时，得**主动通知**注册表重算：

```typescript
registerTool(tool) {
	extension.tools.set(tool.name, {...});
	runtime.refreshTools();          // ← 盒子变了，通知上层重新结算
}
```

回头看 5.5 那个空函数就通了：加载期没有已结算的表，所以吞掉；bindCore 后换成真的重算函数。

**判据：需要"整体一致的快照"才结算，否则现查。** 结算的代价是必须有显式失效机制。

### 7.6 运行期的一句话总结

> **到了某个生命周期点 → 遍历所有盒子，现查该事件的全部 handler（按扩展顺序 + 注册顺序）→ 按该事件专属的聚合规则依次执行（广播 / 短路 / 链式 / 收集）→ 单个 handler 抛错只记进 errors，不打断其余。**

---

## 第 8 章 工程模式清单

1. **备料与现炒分离。** 启动时跑一次的加载，和每轮跑一遍的组装，是两条时间线。混淆的后果是"改了文件为什么不生效"。
2. **判重用规范化值，入列用原始值。** 绝对路径保证判重正确，原始路径保证错误信息可读。
3. **先来先得代替覆盖。** 项目扩展优先于全局，不是靠"后者覆盖前者"，是靠**后者根本进不了队**。少一次覆盖就少一次顺序依赖。
4. **只扫一层 + 清单声明。** 拒绝递归换来"我这个目录会不会被加载"的可预测性。
5. **降级链不短路。** 清单里的入口全失效时继续试 `index.ts`，而不是就此失败。
6. **后缀判定天然提供开关。** `.ts.off` 不是设计出来的禁用机制，是 `endsWith(".ts")` 的自然结果——够自然才敢当开关用。
7. **同一条装配线开多个进料口。** 文件扩展和内联扩展只在"factory 从哪来"分叉，之后完全同流；用 `<...>` 合成标识让无磁盘位置的一方也能套进同一套代码。
8. **闭包做隔离，胜过 id 做归属检查。** `piA` 的闭包里没有盒子 B 的引用，所以串不了——不需要任何运行时校验。
9. **数据与方法分离。** `extension` 是纯数据（7 个 Map），`pi` 是纯方法（自己不存数据）。遥控器和盒子一对一绑死。
10. **声明与执行分离。** factory 只跑一次、只做声明；真正干活的代码作为闭包被登记，由别人在别的时刻调用。
11. **按份数区分隔离与共享。** 私有声明一实例一份（盒子），共享能力全场一份（runtime）。份数就是设计意图。
12. **桩是护栏，不是占位。** 时序上不可能就绪的方法，做成"调了就抛明确错误"，比 `undefined` 或空函数更早暴露误用。
13. **合法但无事可做 → 空函数；不合法 → 抛错。** `refreshTools` 与 `sendMessage` 在加载期的不同待遇。
14. **即时动作拒绝，延迟意愿排队。** 同一个"还没就绪"，`sendMessage` 抛错、`registerProvider` 记账，取决于语义能否推迟兑现。
15. **两道防线各管一头。** `notInitialized` 管"太早"（未绑定），`assertActive` 管"太晚"（已失效）。
16. **就地替换完成阶段切换。** `bindCore` 不换对象、只换方法，因此所有早已持有 runtime 引用的 `pi` 自动获得新能力。
17. **包装保留归属。** 外来对象整个塞进 `definition`，外面套 `sourceInfo` 记来源——schema 归谁，谁的字段就整体存。
18. **预填空集合，免去下游判空。** 七个 Map 一律 `new Map()`，上层可以无脑遍历。
19. **错误隔离到最小单元。** 单个扩展加载失败只记进 `errors`；单个 handler 抛错不打断其余 handler。
20. **现查现用胜过合并索引。** 派生状态会过期、要同步；现场遍历永不失配，且允许每个调用方自定冲突语义。
21. **返回值有意义的事件走专用通道。** 用类型 `Exclude` 把它们从通用 `emit` 里剔出去，逼调用方选对聚合语义。
22. **只有需要"整体一致快照"的才结算。** 工具清单要发给模型所以必须结算，代价是引入 `refreshTools()` 显式失效。

---

## 第 9 章 复习自测

1. "备料"和"现炒"两条时间线分别包含什么？改了扩展文件为什么下一轮不生效？
2. 扩展的三个发现来源是什么？顺序如何？"项目覆盖全局"是靠覆盖实现的吗？
3. `addPaths` 为什么判重用 `path.resolve(p)` 却入列 `p`？
4. `discoverExtensionsInDir` 为什么拒绝递归？复杂目录该怎么办？
5. `.ts.off` 为什么能禁用扩展？这是专门设计的机制吗？
6. `resolveExtensionEntries` 的三级降级是哪三级？清单里的路径全都不存在时会发生什么？
7. `loadExtension` 的六步分别是什么？
8. `createExtension` 为什么要收 `extensionPath` 和 `resolvedPath` 两个路径？它们各自用在哪三处？
9. 内联扩展和文件扩展的唯一区别是什么？为什么它的两个路径参数传同一个值？
10. `extension` 和 `pi` 分别是什么？为什么每个扩展要配一个自己的 `pi`？
11. `pi` 上的方法分哪两类？各自写向哪里？`exec` 属于哪类，有什么特别？
12. 工厂函数被调用几次？在什么时候？它的职责是什么？
13. `runtime` 有几份？为什么和盒子的份数相反？
14. `notInitialized` 桩解决的时序难题是什么？为什么不用 `undefined` 或空函数？
15. `refreshTools` 在加载期为什么是空函数而不是桩？判据是什么？
16. `registerProvider` 为什么排队而不抛错？和 `sendMessage` 的区别在哪？
17. `notInitialized` 和 `assertActive` 各防什么？
18. `bindCore` 绑定的是什么？它碰盒子吗？
19. 为什么"动作要写进注册内容里"就能用？两条线在哪里合流？
20. 盒子里的 `handlers` 为什么值是数组，而 `tools` 不是？
21. `RegisteredTool` 为什么要把你的对象包一层再存？
22. 事件派发为什么不建合并索引？三条理由分别是什么？
23. 四种聚合语义分别是什么？各举一例。
24. `before_agent_start` 的 `message` 和 `systemPrompt` 两个字段语义有何不同？为什么 `ctx.getSystemPrompt` 要被重写？
25. `RunnerEmitEvent` 为什么要用 `Exclude` 剔掉一批事件？
26. 为什么只有工具被"结算"，其它都现查？结算的代价是什么？
27. 从磁盘文件到模型能调用这个工具，完整经过哪几段？每段的产物是什么？

---

> **下一段**：`systemPrompt` 和 `tools` 怎么真正进 `Context`——`_refreshToolRegistry` 的结算规则、系统提示词的拼装顺序，以及 skill / prompt / theme 是不是同一套加载规则。跟完那段，`Context` 三个字段的源头就全通了，本系列 08–09–10–11 也就闭环回到了 09 篇的起点。
