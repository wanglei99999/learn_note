# TypeScript 学习笔记

> 目标：**看懂 agent 源码**。不追求语言层面的完备，只记读源码时会撞上的东西。

## 目录

| # | 章节 | 说明 |
|---|---|---|
| 一 | [为什么 Agent 大多用 TypeScript](#一为什么-agent-大多用-typescript) | 动机 |
| 二 | [Node 是什么](#二node-是什么) | 前置 |
| 三 | [导读：学什么、不学什么](#三导读学什么不学什么) | **先读这章** |
| 四 | [异步模型：Promise / async / await](#四异步模型promise--async--await) | **核心** |
| 五 | [深入：异步的底层](#五深入异步的底层选读) | 选读 |
| 六 | [流式三件套](#六流式三件套readablestream--asynciterable--async-generator) | 核心 |
| 七 | [类型系统：泛型 / 约束 / 条件类型 / infer](#七类型系统泛型--约束--条件类型--infer) | 核心 |
| 八 | [类型收窄与可辨识联合](#八类型收窄与可辨识联合) | 核心 |
| 九 | [Zod（工具定义）](#九zod工具定义) | 依赖七、八 |
| 十 | [AbortSignal 与取消传播](#十abortsignal-与取消传播) | 核心 |
| — | [附录：术语对照表](#附录术语对照表) | 中英对照 |
| — | [下一步](#下一步) | **读完看这里** |

### 三条要点速查

1. **函数调用 = 发射，await = 收货** —— `Promise.all` 本身不并发任何东西，I/O 在调用函数那一刻就发出去了
2. **每个 await 都是一道缝** —— 函数内保证语句**顺序**，但不保证**时间连续**；跨 await 状态可能已经变了
3. **异步只对"等外部"有效** —— 等网络/磁盘/子进程能救；自己算 CPU 无能为力

---

# 一、为什么 Agent 大多用 TypeScript

> 起点疑问：TS 不是前端语言吗？

**核心结论：TS 不是前端语言，它就是带类型的 JavaScript。**
JavaScript 通过 Node / Deno / Bun 做了十几年服务端。Agent 这个场景恰好把 JS 运行时的几个特性全踩中了。

## 1. Agent 是 I/O 密集，不是 CPU 密集

Agent 干的事 95% 是在等：等 LLM 返回 token、等工具调用、等网络、等文件读写。真正的计算量几乎为零。

Node 的单线程事件循环就是为这种负载设计的：

- 并发发起 20 个工具调用 = `await Promise.all([...])`
- 不需要线程池、不用绕 GIL
- 生态里几乎没有同步 I/O 库，天然一致（不像 Python asyncio 里混进一个同步库就堵住整个 loop）

## 2. 流式和取消是平台原生支持的

Agent 输出必须流式，且用户随时可能 Ctrl+C 打断。Web 标准里这些都是现成的：

```ts
const controller = new AbortController()
for await (const chunk of stream) { /* SSE / ReadableStream */ }
controller.abort()   // 取消沿整条调用链传播
```

`AbortSignal` 能一路穿透到 subagent、子工具调用，取消语义干净。别的语言里这块往往要自己搭。

## 3. 类型系统正好匹配 LLM 的 I/O 形状

LLM 的输入输出全是 JSON。TS 的结构化类型 + 类型推导，描述任意 JSON 形状的能力很强。最典型的是工具定义：

```ts
const readFile = tool({
  description: '读取文件',
  parameters: z.object({ path: z.string(), limit: z.number().optional() }),
  execute: async ({ path, limit }) => { /* 参数类型自动推出来 */ }
})
```

一份 Zod schema 同时产出三样东西，且永不漂移：给模型看的 JSON Schema、运行时校验、`execute` 里的静态类型。

另一个被低估的是**可辨识联合（discriminated union）**，建模流式事件和 agent 状态机极顺手：

```ts
type Event =
  | { type: 'text_delta';  text: string }
  | { type: 'tool_use';    id: string; input: unknown }
  | { type: 'tool_result'; id: string; output: string }
// switch 到每个 case，编译器保证没漏分支
```

> 公平地说：Python 的 Pydantic + `Literal` 联合能做到差不多的事，这不是 TS 独有优势，只是 TS 更自然。

## 4. 分发和部署

很多 agent 是**产品**而不是脚本，这块 TS 优势明显：

- `npx some-agent` 直接跑，用户不用管 Python 版本、venv、系统依赖
- 打包成单文件，跨平台一致（Claude Code 本身就是 TS + npm 分发）
- 能跑在 Cloudflare Workers / Vercel Edge，冷启动毫秒级——按请求计费的 agent 很在意
- 要做 VS Code 插件或 Electron 桌面端，只有 JS 一条路

## 5. 前后端同一套类型

Agent 基本都带聊天 UI。后端定义的消息类型、事件类型可被前端直接 import，改一个字段编译器立刻告诉你哪些地方要跟着改。

## 6. 生态正反馈

MCP 的参考实现是 TS 的（协议规范本身就是用 TS 类型写的），加上 Vercel AI SDK、Mastra、LangChain.js、Anthropic / OpenAI 官方 SDK。选 TS 就能直接接上 MCP 生态。

## 什么时候仍然该用 Python

分界线大致是：**这个 agent 碰不碰数据和模型。**

| 场景 | 更适合 |
|---|---|
| 产品化 agent、CLI、Web 服务、IDE 插件、MCP server | TypeScript |
| 涉及 embedding / 向量检索 / 本地模型 / 微调 | Python |
| 数据处理、评测（eval）、实验脚本 | Python |
| 需要 numpy / pandas / torch 生态 | Python |

实际项目混用很常见：TS 写 agent 主循环和对外服务，Python 跑离线 eval 和数据管线。

---

# 二、Node 是什么

**Node（Node.js）是让 JavaScript 能脱离浏览器、在本机或服务器上运行的程序。**

## 来龙去脉

JavaScript 最初只活在浏览器里，只能操作网页——它压根没有"读文件""开端口"这类能力，因为浏览器出于安全根本不给。

2009 年有人把 Chrome 里跑 JS 的引擎（**V8**）单独抠出来，外面套一层操作系统能力：读写文件、发网络请求、启动子进程、读环境变量……这个组合就是 Node。从此 JavaScript 变成了和 Python 同级别的通用语言。

一个好用的类比：

```
Node.js  之于  JavaScript   ==   CPython  之于  Python
```

都是「语言的运行时/解释器」。装了 Python 才能跑 `.py`，装了 Node 才能跑 `.js`。

## 具体长什么样

```bash
node app.js        # 跑脚本，和 python app.py 一样
node               # 交互式 REPL，和直接敲 python 一样
npm install zod    # npm 是 JS 的包管理器，相当于 pip
```

`app.js` 里可以写浏览器绝对干不了的事：

```js
import { readFile } from 'node:fs/promises'

const text = await readFile('./notes.md', 'utf-8')          // 读本地文件
const res  = await fetch('https://api.anthropic.com/...')   // 发请求
```

## TypeScript 和 Node 的关系

TS 不能直接跑，要先编译（其实主要是**擦掉类型**）成 JS，再交给 Node 执行：

```
你写的 .ts  ──编译/擦类型──▶  .js  ──▶  Node 执行
```

> Node 新版本已能直接吃 `.ts` 文件（内部自动擦类型），实践中这一步经常是透明的。

**重要推论：TS 只是类型层，编译完类型就没了，运行时行为和 JS 完全一样。**
单线程、事件循环这些特性属于 **Node 运行时**，不属于 TS。
（"TS 是前端语言""TS 是异步的"都是误解——TS 只是类型。）

## 同类运行时

| 运行时 | 特点 |
|---|---|
| **Node** | 生态最成熟，遇到问题最好搜。学习阶段用这个 |
| **Bun** | 主打快，启动和装依赖明显更快，原生支持 TS |
| **Deno** | 默认安全（要显式授权才能读文件/联网），原生支持 TS |

三者跑的都是 JS/TS，大部分代码可互换。

---

# 三、导读：学什么、不学什么

> 背景：网上常见的说法是「Node 事件循环、流、异步抽象、吃透 Zod/TypeBox」。
> 方向对，但**权重偏了**，而且漏掉了 agent 真正难的部分。

| 常见说法 | 实际评价 |
|---|---|
| Node 事件循环 | 半对——要的是**异步心智模型**，不是 libuv 内部原理 |
| 流 | 对，但**学错对象**了 |
| 异步抽象 | 对，而且是**最被低估**的一项 |
| 吃透 Zod / TypeBox | 别"吃透"，**20% 就够**，过深反而有害 |


> ⚠️ **这份笔记实际走的路和本章建议不完全一致。**
> 本章主张「以战代练」——先写循环，撞上问题再学。但后面六到十章是成体系讲的，
> 一行循环也没写。代价是：**所有例子都是构造的，没有一行代码跑过。**
> 所以读完之后务必去做「下一步」里那件事。


---

# 四、异步模型：Promise / async / await

> 这是读 agent 源码时最高频的东西，几乎每一行都和它有关。

**一句话定位：`async/await` 表达的是「异步执行 + 函数内语句串行」的语法。**

| 词 | 指什么 |
|---|---|
| **异步** | 对进程而言——等待时线程让出去，别人能跑 |
| **函数内串行** | 对这个函数而言——语句一条条按顺序走 |
| **语法** | 语言层的表达方式，**本身不产生异步能力**（见第五章） |

## 1. 先分清三种情况

**① 同步计算** —— 占用线程**在干活**，不叫阻塞，没浪费

```js
function sum(n) { let s = 0; for (let i = 0; i < n; i++) s += i; return s }
```

**② 同步 I/O（真正的阻塞）** —— 占着线程，却**没在用 CPU**，纯粹干等

```js
const text = readFileSync('a.md')   // 3 秒的网络请求 = 3 秒的纯浪费
```

**③ 异步 I/O** —— 要解决的就是 ② 这种浪费

## 2. Promise：一张"未来兑现的凭证"

异步函数不直接给结果，而是**立刻**返回一个 Promise（取餐号码牌）：

```
pending（等待中） ──▶ fulfilled（成功，带一个值）
                  └─▶ rejected（失败，带一个错误）
```

```js
const p = fetch('https://...')
console.log(p)   // Promise { <pending> } ← 不是数据，是号码牌
```

## 3. await 的本质：不是"停在那儿等"，是"函数直接返回了"

这是最容易误解的一点。

> **执行到 `await` 时，这个 async 函数就 return 了。**
> 控制权回到调用方继续往下跑，函数剩下的半截被**存起来**，等 I/O 完成后再回来接着跑。

### 验证实验

```js
async function f() {
  console.log('B')
  const data = await readFile('a.md')   // ← 就在这一行，f 返回了
  console.log('D')                      // ← 这半截被存起来，稍后才跑
}

console.log('A')
f()
console.log('C')
```

输出是 `A B C D`，不是 `A B D C`。`C` 先于 `D`，证明 f 在 await 那一行确实交出了控制权。

### 函数被切成了段

```
async function f() {
  ┌──────────┐
  │   段 1   │  console.log('B')
  └──────────┘
     await ──▶ 发起 I/O，返回，把"段 2"登记为待恢复
  ┌──────────┐
  │   段 2   │  console.log('D')   ← I/O 完成后由事件循环调起
  └──────────┘
}
```

`await` 就是切口。函数不是一口气跑完的，是分段跑的；段与段之间线程去干别的了。

**那谁在等？没有人在等。** I/O 由操作系统负责，完成后发通知；Node 主线程只维护一张「哪个 I/O 完成了 → 该恢复哪段代码」的表。

> **一句话总结**：await 把**唯一的 JS 执行线程**交还给事件循环，让它去跑别的代码；I/O 好了再回来接着跑剩下的部分。

## 4. async：声明函数内可以 await

```js
async function summarize(path) {
  const text  = await readFile(path, 'utf-8')
  const reply = await callLLM(text)
  return reply
}
```

**规则：async 函数一定返回 Promise。** 上面 `return reply` 返回字符串，但调用方拿到的是 `Promise<string>`，所以调用时也要 await。

### 新手最常踩的坑：忘了 await

```js
const text = readFile('a.md', 'utf-8')
console.log(text.length)   // undefined —— text 是 Promise，不是字符串
```

更坑的是**错误会静默消失**：

```js
try {
  doSomethingAsync()   // ← 忘了 await
} catch (e) {
  // 永远不会进来，即使内部报错了
}
```

> TS 能挡住第一种（类型对不上会报错）。这是写 agent 该用 TS 的实际理由之一。

## 5. 串行 vs 并发（最重要）

三个文件各 100ms：

```js
const a = await readFile('a.md')   // 等 100ms
const b = await readFile('b.md')   // 再等 100ms
const c = await readFile('c.md')   // 再等 100ms
// 总共 300ms —— 串行
```

问题在于：**你在发起第二个请求之前就先停下来等了。**

```js
const pa = readFile('a.md')   // 发出去，不等
const pb = readFile('b.md')   // 发出去，不等
const pc = readFile('c.md')   // 发出去，不等
const a = await pa            // 现在三个都在飞
const b = await pb
const c = await pc
// 总共 100ms —— 并发
```

```
串行：  [--a--][--b--][--c--]        300ms
并发：  [--a--]
        [--b--]                      100ms
        [--c--]
```

### 关键口诀

> **函数调用 = 发射，await = 收货。**

`Promise.all` **本身不"并发"任何东西——它只负责等**。真正发起 I/O 的动作是**调用函数的那一刻**。

```js
Promise.all([f('a'), f('b'), f('c')])
//           ↑ 这三个调用在同一瞬间执行，请求同时飞出去
//  Promise.all 拿到的已经是三张"在飞"的号码牌，它只是一起等
```

## 6. Promise 的组合方法

### Promise.all —— 并发的标准写法

```js
const [a, b, c] = await Promise.all([
  readFile('a.md'), readFile('b.md'), readFile('c.md'),
])
```

- 结果按**原数组顺序**排列，不是完成顺序
- **快速失败**：任一个 reject，整体立刻 reject，只拿到第一个错误
- 注意：其他 promise **不会被取消**，仍会在后台跑完，只是结果没人要

配合 `map` 处理动态数量（agent 里的典型场景：模型一次返回 3 个 `tool_use`）：

```js
const results = await Promise.all(toolCalls.map(call => executeTool(call)))
```

### Promise.allSettled —— agent 里更常用

某个工具失败不该拖垮其他工具，而且失败信息本身要作为 `tool_result` 回给模型：

```js
const results = await Promise.allSettled(toolCalls.map(c => executeTool(c)))

for (const r of results) {
  if (r.status === 'fulfilled') use(r.value)
  else                          report(r.reason)
}
```

**永远不会 reject**，每项是 `{status:'fulfilled', value}` 或 `{status:'rejected', reason}`。

### 汇总

| 语法 | 作用 |
|---|---|
| `async` | 标记函数内可用 await；该函数必返回 Promise |
| `await` | 等一个 Promise 出结果；暂停本函数，**不阻塞进程** |
| `Promise.all` | 并发跑多个，全成功才成功，一个失败全盘失败 |
| `Promise.allSettled` | 并发跑多个，全部等完，逐个报告成败 |
| `Promise.race` | 谁先**完成**（成功或失败）就返回谁，常用来做超时 |
| `Promise.any` | 第一个**成功**的 |

**判断标准**：有依赖（B 需要 A 的结果）就串行 await；互不依赖就 `Promise.all`。
Agent 的性能优化，很大一部分就是把不必要的串行改成并发。

## 7. "函数内是同步的"——这句要拧准

保证的是**语句顺序**：A 一定在 B 之前执行。
**不保证时间连续**：A 和 B 之间可能隔了 3 秒，期间跑了一大堆别人的代码。

```js
const a = state.count       // 假设是 5
await callLLM()             // ← 过了 3 秒，别的代码跑过了
const b = state.count       // 可能已经不是 5 了
```

顺序对，但世界变了。这是「同步」和「顺序保证」的实质差别。

> **每一个 await 都是一道缝，外界会从这道缝里挤进来。**

### 实际会咬人的两种情况

```js
// ① 防重入失效
async function handleMessage(msg) {
  if (this.running) return
  this.running = true
  await callLLM(msg)          // ← 3 秒。期间 handleMessage 可能又被调了一次
  this.running = false
}

// ② 读到旧数据
async function save() {
  const snapshot = state.messages   // 拿了个快照
  await writeFile(path, snapshot)   // 写的时候 state.messages 早就变了
}
```

### 但这比多线程简单太多

| | 多线程 | async/await |
|---|---|---|
| 调度方式 | **抢占式**——任何一行都可能被打断 | **协作式**——只在 await 处让出 |
| 需警惕的位置 | 到处都是 | 只有 await 那几行 |
| 需要加锁吗 | 需要 | 基本不需要 |

因为 JS 是单线程的，两段代码永远不会真正同时跑，不存在"半条语句执行到一半被打断"，`state.count++` 这类操作绝对安全。

**只需盯着写了 `await` 的那几行——那是唯一的交错点。**

## 8. 两个重要推论

**① await 不会让慢的事变快。**
一个 3 秒的 LLM 调用，await 之后还是 3 秒。省下的是"这 3 秒里别的代码可以跑"。对单个请求无加速，对整体吞吐是数量级提升。

**② await 治不了 CPU 密集。**

```js
async function heavy() {
  for (let i = 0; i < 1e10; i++) {}   // 加了 async 也没用，整个进程卡死
}
```

没有 I/O 就没有切口可以让出去。这种情况要用 worker 线程或子进程。

> **分界线：等外部（网络/磁盘/子进程）→ 异步能救；自己算 → 异步无能为力。**

## 9. 日常真正用得上的三条

**1. 该并发的别串行**

```js
for (const c of calls) results.push(await run(c))   // ✗ 串行
const results = await Promise.all(calls.map(run))   // ✓ 并发
```

**2. 每个 await 都是一道缝，跨过它状态可能变了**

**3. 别在 async 函数里写重 CPU 的同步代码**

这三条内化了，异步这块就过关了。

---

# 五、深入：异步的底层（选读）

> **选读。** 写 agent 只要第四章第 9 节那三条规则就够了；这一章讲「为什么」。
> 想搞清楚机制再来，不影响前面的使用。

## 1. Promise 内部：`f` 函数长什么样

```js
function f(name) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(name), 100)
  })
}
```

`f('a')` 被调用时：

```
① new Promise(executor) 被调用
② executor 也就是 (resolve)=>{...} 【同步】立刻执行
③ 里面调 setTimeout：登记一个 100ms 后的回调，然后【立刻返回】
④ new Promise 返回一个 pending 的 Promise
⑤ f 把它 return 出去
   ↑ ①~⑤ 纳秒级，f 执行完毕退出

   ...... 100ms 过去，f 早就不在调用栈上了 ......

⑥ 事件循环发现定时器到期，调那个回调
⑦ resolve(name) 被调用 → Promise: pending → fulfilled
⑧ 所有 await 它的代码被唤醒
```

**关键在 ③**：`setTimeout` / `fetch` / `fs.readFile` 都只是"登记"，登记完就返回。

### `resolve` 是什么

**一个函数，引擎递给你的。调用它 = 宣布这个 Promise 成功，并交出结果。**

```js
const p = new Promise((resolve, reject) => {
  if (ok) resolve('结果')       // ① → await p 得到 '结果'
  else    reject(new Error())   // ② → await p 抛出那个 Error
})
```

它就是个普通函数，可以存起来随时调：

```js
let 开关
const p = new Promise(r => { 开关 = r })
p.then(v => console.log('拿到', v))
setTimeout(() => 开关('hello'), 3000)     // 3 秒后手动兑现
```

三个细节：

- 名字是形参名，随便取（`resolve`/`reject` 只是约定）
- **只生效一次**，状态一旦变了不可逆
- **忘了调 = 永远 pending**，await 它的代码永远醒不过来，而且**不报错**，很难查

### `resolve` 不是 `f` 调的

```js
function f(name) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(name), 100)
    //          └─ 这个闭包捕获了 resolve，100ms 后由事件循环调起
  })
  // ← f 在这里就返回了，此刻 resolve 还没被调用过
}
```

> **Promise 在 `f` 返回后仍然活着，独立地等着被兑现。**
> 这就是为什么 `pb` 不需要 `await` 来驱动——它的完成逻辑早已登记好，跟谁在等它无关。

### async 写法是同一回事

```js
async function f(url) {
  const res = await fetch(url)     // ← 执行到这里，f 就 return 一个 pending Promise 了
  return res.json()
}
```

`return` ≈ `resolve()`，`throw` ≈ `reject()`——引擎帮你调那两个开关。
**手写 `new Promise` 的"立刻返回"和 `async function` 的"立刻返回"，是同一件事。**

## 2. 什么才是异步的关键：Promise 是果，不是因

```
④ async / await        语法糖 —— 怎么写得好看
③ Promise              通知机制 —— 完成时怎么告诉你
② 事件循环             调度 —— 决定谁该恢复
① 非阻塞 I/O           ★ 真正的地基 —— 等待时不占线程
   （epoll / 线程池）
```

**只有 ① 是"异步"的实质，③④ 只是表达方式。**

### 反例：包成 Promise 不产生异步

```js
function bad(path) {
  const data = fs.readFileSync(path)   // ← 同步 API，真的卡住 100ms
  return Promise.resolve(data)         // ← 包了 Promise
}

const pa = bad('a'), pb = bad('b'), pc = bad('c')
await Promise.all([pa, pb, pc])        // 仍然 300ms，Promise.all 救不了
```

`fs.readFileSync` 和 `fs.readFile` 的区别在第 ① 层，**Promise 无论如何包装都改变不了**。

### `await` 一个非 Promise 值，仍然会暂停

```js
async function f() { console.log('A'); await 42; console.log('C') }
f(); console.log('B')
// 输出 A B C —— 不是 A C B
```

`await` 遇到普通值会包成 `Promise.resolve(42)` 再等，**照样让出一次微任务**。
所以它造成了异步的执行顺序，但没有任何 I/O 等待——纯属白让。

> **`await` 永远会暂停，哪怕等的是个常数。**

### 判定标准

> **这个函数被调用后，是立刻返回，还是要等 I/O 才返回？**

```js
fetch(url)              // 立刻返回 → 真异步
fs.readFile(p, cb)      // 立刻返回 → 真异步
fs.readFileSync(p)      // 等 I/O 才返回 → 同步，包成 Promise 也没用
```

## 3. 「暂停」不是「阻塞」

```
阻塞 (blocking)：占着线程，什么也不干        ← readFileSync
暂停 (suspend) ：交出线程，别人可以用它      ← await
```

**对你这条逻辑链来说结果一样**（都得等），但代价天差地别：

```js
// 单个 Node 进程，一个 JS 线程
await Promise.all(Array.from({ length: 1000 }, () => fetch(url)))
// 1000 个并发请求同时在飞
```

真阻塞的话这需要 1000 个线程，实际只用了 1 个。**这是 `await` 不是阻塞的硬证据。**

### 两个视角，都对

| 视角 | 看到的 |
|---|---|
| 从**函数内部** | 像同步——一行行往下走，`await` 处停住等结果 |
| 从**整个进程** | 完全异步——线程跑别的去了，这个函数只是被挂起 |

> **`async/await` 给的是「同步的写法」，不是「同步的语义」。**

### 历史脉络：写法在变，执行模型没变

```js
// ① 回调：一点也不像同步
readFile(a, (e, d1) => { readFile(b, (e, d2) => { readFile(c, ...) }) })

// ② Promise 链：好一些，但还是变形的
readFile(a).then(d1 => readFile(b)).then(d2 => ...)

// ③ async/await：和同步代码几乎一模一样
const d1 = await readFile(a)
const d2 = await readFile(b)
```

三种写法**底层执行完全相同**。`async/await` 是这条路的终点——
把异步写得和同步一样，但它没有、也不可能把异步变成同步。

---

以下是**和 epoll 的对照**——有 OS 课的底子的话，学 Node 异步基本没有新概念要建立，
只是把「手写状态机」换成了语法糖。

> 有 OS 课的 epoll 底子的话，学 Node 异步基本没有新概念要建立，只是把「手写状态机」换成了语法糖。

**这不是类比——Node 的事件循环底层就是 epoll。**
libuv（Node 的 I/O 层）在 Linux 上用 epoll，macOS 上用 kqueue，Windows 上用 IOCP。

## 4. 概念映射

| epoll 世界 | Node 世界 |
|---|---|
| fd | libuv 内部的 handle / req（**JS 层不可见**） |
| `epoll_ctl(ADD)` 注册 | 调 `fetch()` 时 libuv 帮你注册 |
| `epoll_wait()` | 事件循环的 **poll 阶段** |
| 就绪事件 → 查表找到 `struct conn *` | 就绪 → 找到对应 Promise → resolve |
| 你手写的状态机 | **async 函数被自动切好的段** |

**校正：Promise 不是 fd。** fd 在 libuv 层，JS 根本看不到。Promise 是用户态的高层对象，很多 Promise 压根不对应任何 fd（`Promise.resolve(1)`、`setTimeout`、纯计算的 async 函数）。

> Promise 更像是「`epoll_wait` 返回后，要跳去执行的那个**续体**的凭证」，而不是被监听的 fd。

## 5. 是阻塞等待，不是忙轮询

**Node 空闲时 CPU 是 0%。**

事件循环走到 poll 阶段会真的阻塞在 `epoll_wait(timeout)` 里。timeout 根据最近一个定时器算出来——100ms 后有 `setTimeout` 就传 100，没定时器就传 -1 死等。和手写 epoll server 的做法一模一样。

## 6. libuv 不是一个裸 epoll 循环

一轮有好几个阶段，epoll 只是其中一个：

```
┌─▶ timers          执行到期的 setTimeout / setInterval
│   pending         上一轮没跑完的 I/O 回调
│   idle / prepare  内部用
│   poll  ◀───────  这里才是 epoll_wait，等 I/O
│   check           setImmediate
└── close           socket close 之类的回调
```

## 7. 多出来的一层：微任务队列

这是 C 里没有的东西。Promise 的 resolve **不是直接调回调**，而是往微任务队列里塞一项。每跑完一个宏任务回调，引擎会**立刻把微任务队列抽干**，才进入下一阶段。

```
epoll_wait 返回
  → 执行 I/O 回调（libuv 层）
  → resolve 对应的 Promise
  → 微任务队列被抽干 → 所有 await 着它的函数在这里被恢复
  → 进入下一阶段
```

## 8. 文件 I/O 走的不是 epoll

**普通文件的 fd 在 epoll 里永远是"就绪"的**，epoll 对磁盘 I/O 没意义。所以 libuv 分了两条路：

| 类型 | 机制 |
|---|---|
| 网络 socket | epoll / kqueue / IOCP，**不占线程** |
| 文件 I/O、DNS 解析（getaddrinfo）、部分 crypto | **线程池**跑同步系统调用，默认 4 线程（`UV_THREADPOOL_SIZE` 可调） |

> **所以"Node 是单线程"严格说只对 JS 执行成立**，底下是有线程池的，只是碰不到。

**实际影响**：大量并发文件读写会打满那 4 个线程互相排队——网络请求开几千个没事，文件操作开几千个反而会堵。（新版 libuv 在 Linux 上开始用 io_uring 处理部分文件操作，这个限制在缓解。）

## 9. 真正的增量：续体是白送的

**这是最值得带走的一点。**

裸写 epoll 时，`epoll_wait` 只告诉你「fd 5 好了」，**接下来干什么得你自己记住**——要么维护显式状态机：

```c
struct conn { int fd; enum { READ_HDR, READ_BODY, WRITE } state; char *buf; ... };
// epoll_wait 返回后: switch (conn->state) { ... }
```

要么写回调套回调（JS 早年的 callback hell 就是这个）。

而 `async/await` 是**引擎帮你把函数自动切成了状态机**：

```js
async function handle(req) {
  const a = await readHeader(req)
  const b = await readBody(req, a.len)
  await write(req, process(b))
}
```

它被转成的东西，语义上等价于手写的 `struct conn` + `switch(state)`：局部变量 `a`、`b` 就是那些要跨 I/O 保存的字段，`state` 就是"停在第几个 await"。

> **epoll 解决"什么时候该继续"；async/await 解决"继续的时候从哪儿接着跑、上下文在哪"。**
> 原来手工维护的那部分，现在语言给了。

**够用程度提示**：libuv 的更多细节是写运行时的人才需要的，写 agent 用不上。理解到这里就可以停，剩下的全是习惯问题（见四-9）。

---

# 六、流式三件套：ReadableStream / AsyncIterable / async generator

> 读 LLM SDK 源码必撞的一条线。三者不是竞争关系，是**分层**关系。

## 0. 先别混：JS 里有三套"流"

| | 是什么 | 该不该学 |
|---|---|---|
| Node `stream` 模块 | Node 自己的老 API | 基本不用，历史包袱 |
| Web Streams（`ReadableStream`） | W3C 标准，浏览器/Node 都有 | 认识即可 |
| async iterator（`for await`） | 语言级语法，不是库 | **重点学** |

## 1. ReadableStream = 通用字节流容器

**是 Web 标准，不是 Node 内置的**，和 SSE 也没有任何关系——它只管"一块块把字节递给你"，
不认识里面装的是什么。同一个流里可以是 JPEG、zip、视频、或 SSE 文本。

```
┌───────────────────────────────────┐
│ { type: "content_block_delta" }   │ ← 业务数据（JSON）
├───────────────────────────────────┤
│ data: {...}\n\n                   │ ← SSE 文本协议 ← 要你自己解析
├───────────────────────────────────┤
│ ReadableStream<Uint8Array>        │ ← 只搬字节，不认识上面两层
├───────────────────────────────────┤
│ HTTP chunked / TCP                │
└───────────────────────────────────┘
```

**`res.body` 的三个坑**

1. 类型是 `ReadableStream<Uint8Array> | null` —— `HEAD`/`204`/`304` 没有 body，要判空
2. **只对 fetch 成立** —— Node 老的 `http.request` 给的是 `IncomingMessage`（Node stream）
3. **只能读一次** —— `res.json()` 之后再读 body 会报 disturbed；要两遍得 `res.clone()` 或 `body.tee()`

> 浏览器自带的 SSE API `EventSource` 用不了：只支持 GET、不能自定义 header，
> 而 LLM 调用要 POST + `Authorization`。所以 SDK 都是 fetch + 手动解析。

**关键：分块边界是网络切的，和内容无关。** 一个 chunk 里可能有 5 个完整事件、也可能半个都没有，
甚至切在一个 UTF-8 汉字的三个字节中间。所以处理流永远是这个形状：

```
攒进 buffer → 找分隔符 → 切出完整单元 → 残余留着等下一块
```

`TextDecoder` 的 `{ stream: true }` 处理"字符被切断"，你自己的 `\n\n` 切分处理"协议单元被切断"。

## 2. AsyncIterable = 一个协议，不是一个类

数组能 `for...of`，是因为身上有 `[Symbol.iterator]` 方法。**不是继承某个类，是长了某个形状。**
异步版只改两点：方法名叫 `Symbol.asyncIterator`，`next()` 返回 Promise。

```ts
interface AsyncIterable<T> { [Symbol.asyncIterator](): AsyncIterator<T> }
interface AsyncIterator<T> { next(): Promise<IteratorResult<T>> }

type IteratorResult<T> =
  | { done: false; value: T }
  | { done: true;  value: undefined }

interface AsyncGenerator<T> extends AsyncIterator<T>, AsyncIterable<T> {}
```

> 看到 `AsyncIterable<MessageStreamEvent>` 就知道：能 `for await`，每次给一个 `MessageStreamEvent`。

**Iterable vs Iterator**（最常混的一对）：
Iterable =「我**能提供**一个遍历器」；Iterator =「我**就是**那个遍历器」（有 `next()`）。
数组是 Iterable 但不是 Iterator。AsyncGenerator 两个都是（`[Symbol.asyncIterator]()` 就是 `return this`）。

**实践：参数类型写 `AsyncIterable<T>`**（宽松，ReadableStream / AsyncGenerator / 手写对象都能收）。

## 3. generator 与 async：两种暂停点

**`yield` 和 `await` 是同一个机制**——保存现场、交出控制权、稍后恢复。
差别只在两栏：

| | 为什么暂停 | 谁来唤醒 |
|---|---|---|
| `yield` | **我产出了一个值**，交给你 | **消费方**——调 `next()` 才继续 |
| `await` | **我在等外部** | **事件循环**——I/O 完成时自动恢复 |

`async function*` 能表达流，就是因为它**同时有这两种暂停点**：等到数据（await 恢复）→ 交付一个（yield 暂停）→ 再去等下一批。

### `yield` 不是 `return`

```
return x  →  交付 x，然后【销毁】栈帧，局部变量全没了
yield  x  →  交付 x，然后【冻结】栈帧，局部变量原封不动等着
```

所以准确说是「**多次交付，一次退出**」。这也是 `parseSSE` 里的 `buf` 能自动保存的原因——
**栈帧是冻结的，不是重建的**。

### 各自补了什么

| | 能表达什么 |
|---|---|
| 只有 `async` | 一次返回一个完整结果——`await` 一坨，3 秒后整段蹦出来 |
| 只有 `function*` | 多次交付，但每次都得**当场给得出**——同步序列、遍历树、无限自然数 |
| **两个都有** | **异步地、逐个地、数量未知地**产出 = 流 |

- **generator 管**：值的数量（一个→多个）、控制权能否中途交还
- **async 管**：暂停期间不占线程、`done` 能不能延迟

> 措辞注意：**async 自己不做调度**，它只标记让出点并保存现场，调度器是事件循环。
> 相当于协作式多任务里的 `yield_cpu()` 调用点——没写 `await` 的地方谁也抢不走执行权。

### `async` 作用在哪

**`async function*` 执行不返回 Promise，返回 AsyncGenerator，函数体一行不跑。**

> `async *` 的 async **不作用于函数的返回值，而是作用于迭代器的 `.next()`**。

| | 协议 | `next()` 返回 | 消费 |
|---|---|---|---|
| `function*` | `Symbol.iterator` | `{ value, done }` | `for...of` |
| `async function*` | `Symbol.asyncIterator` | `Promise<{ value, done }>` | `for await` |

## 4. 数据链路：三层壳

```
最内层   x                              业务数据（一个 token、一个事件）
中间层   { done, value: x }             迭代协议的「信封」
最外层   Promise<{ done, value: x }>    异步的「壳」
```

| 层 | 回答的问题 |
|---|---|
| `x` | 数据是什么 |
| `{ done, value }` | 还有没有下一个？这个是什么？ |
| `Promise` | 上面这个信封**什么时候**能拿到？ |

```
生产侧                                消费侧
────────────────────────────         ──────────────────────
  yield x ─┐
           │ ① x 若是 Promise，先 await 展开
           ↓
   { done:false, value:x }           ② 装进信封
           ↓
 Promise<{ done:false, value:x }>    ③ 包上异步壳
           ↓
   it.next() 返回 ──────────────▶  await → 剥壳
                                    查 done → false
                                    取 value → x
```

### 命门：壳和信封的嵌套顺序

```
✅ Promise< { done, value: x } >     壳在外，信封在内
❌ { done, value: Promise<x> }       信封在外，壳在内
```

第二种正是「同步 generator + yield 一个 Promise」的形状，致命伤是 **`done` 留在了壳外面，必须当场给出**。
而流式场景里「还有没有下一块」本身就得等网络才知道，所以信封必须整个装进壳里。

> **这就是必须有 `Symbol.asyncIterator` 独立协议、不能拿同步 generator 凑合的根本原因。**

而且规范强制 `value` 不能是 Promise（yield 时自动 await 展开），不会出现双层壳。

### 终止那一次，壳还在

```js
await it.next()   // Promise<{ done:true, value:undefined }>  ← 仍然要 await
```

**「结束了」这个消息本身也是异步送达的。** 最后一次 `next()` 不产出数据，
纯粹是在异步确认终止——N 个值需要 N+1 次 `next()`。

### `done:true` 时 value 未必是 undefined

```js
async function* g() { yield 1; return 'DONE' }
// await it.next() → { done:true, value:'DONE' }     ← 有 return 就不是 undefined
// 再调一次      → { done:true, value:undefined }    ← return 值只给一次

for await (const x of g()) {}   // 只拿到 1，'DONE' 被静默丢弃
```

`for await` 只消费 `done:false`，看到 `done:true` 就退出，`value` 看都不看。
`return` 的值只有手动 `.next()` 或被 `yield*` 委托时才拿得到。

> **实践推论：别用 `return` 传结果。** agent 主循环最后的「总结 / token 用量 / 停止原因」
> 用 return 会被上层吞掉，必须 `yield { type:'done', usage }` 显式产出。

### `next()` 的真实时序（容易搞反）

```js
const p = it.next()   // ← 立刻返回 pending Promise，函数体还在后台跑
const r = await p     // ← 跑到 yield 时才 resolve
```

**不是"跑完再包 Promise 返回"**——那样就阻塞了。只有函数体里恰好没有 await 时，看着才像同步跑到 yield。

## 5. 全景四格表

`*` 管"多个"，`async` 管"异步"，两个修饰符正交：

| | 类型 | 生产语法 | 消费语法 |
|---|---|---|---|
| 一个值 · 同步 | `T` | `function f()` | `const x = f()` |
| 一个值 · 异步 | `Promise<T>` | `async function f()` | `const x = await f()` |
| 多个值 · 同步 | `Iterable<T>` | `function* f()` | `for (const x of f())` |
| 多个值 · 异步 | `AsyncIterable<T>` | `async function* f()` | `for await (const x of f())` |

分层关系：

```
Promise + async/await        地基（AsyncIterator 的 next() 返回 Promise）
        ↓
AsyncIterable / AsyncIterator    协议
        ↓
async function*  |  ReadableStream    实现（语法糖 / 标准库现成的）
        ↓
for await ... of             消费
```

## 6. 实战：把三层串起来

**字节流 → 事件流**

```js
async function* parseSSE(res) {
  const decoder = new TextDecoder()
  let buf = ''

  for await (const chunk of res.body) {          // 消费 ReadableStream（字节）
    buf += decoder.decode(chunk, { stream: true })

    let i
    while ((i = buf.indexOf('\n\n')) !== -1) {   // 攒 buffer → 切分
      const raw = buf.slice(0, i)
      buf = buf.slice(i + 2)
      if (raw.startsWith('data: ')) yield JSON.parse(raw.slice(6))
    }
  }
}
```

`buf` 这个残余状态被 generator 自动保存了——**有状态的流式处理，写起来像一段直线代码**。
不用 generator 就得建 `class SSEParser`、把 buf 存成实例字段、暴露 `feed(chunk)`、调用方自己驱动循环。

**agent 主循环也是这个形状**

```ts
async function* runAgent(input: string): AsyncGenerator<AgentEvent> {
  const messages = [{ role: 'user', content: input }]
  while (true) {
    const res = await callLLM(messages)
    for await (const delta of res)  yield { type: 'text', text: delta }
    if (!res.toolCalls.length)      return
    for (const call of res.toolCalls) {
      yield { type: 'tool_start', call }
      yield { type: 'tool_end', out: await execute(call) }
    }
    messages.push(/* ... */)
  }
}

for await (const ev of runAgent('帮我改个 bug')) {
  switch (ev.type) { /* 可辨识联合，编译器保证不漏分支 */ }
}
```

**把"agent 逻辑"和"怎么展示"彻底解耦**——同一个 `runAgent` 可以接终端、接 Web UI、接测试断言。
Claude Code、AI SDK 这类项目核心都是这个形状。

**完整的一条线**

```
res.body          字节流（ReadableStream）
  ↓ async generator 包一层解析
parseSSE(res)     事件流（AsyncIterable）
  ↓ async generator 再包一层业务
runAgent(input)   agent 事件流（AsyncIterable）
  ↓ for await
UI 渲染
```

每一层都是 `async function*`，每一层都惰性、可取消、自带状态。

## 7. 实用要点

**① 用 `try/finally` 做清理** —— 消费方 `break`（比如用户 Ctrl+C），引擎会调 generator 的 `return()`，`finally` 照常跑。**agent 的资源清理和取消就靠这个。**

```js
async function* readSSE(res) {
  const reader = res.body.getReader()
  try { while (true) { /* ... yield ... */ } }
  finally { reader.releaseLock() }
}
```

**② 组合是惰性的管道** —— 不会先把上游读完再处理

```js
async function* map(src, fn) { for await (const x of src) yield fn(x) }
```

**③ 一次性，不能重放，也没有 `.map`/`.filter`** —— 它不是数组。
要复用先 `await Array.fromAsync(stream())`（Node 22+）；要变换就再套一层 async generator。

---

# 七、类型系统：泛型 / 约束 / 条件类型 / infer

> 目标不是会写，是**读得懂 SDK 的 `.d.ts`**，出错时知道编译器在推什么。

## 1. 泛型 = 类型的函数

没有泛型只能用 `any`，而 `any` **切断了输入和输出的关系**：

```ts
function first(arr: any[]): any { return arr[0] }
const x = first([1, 2, 3])   // x: any
x.toUpperCase()              // 不报错，运行时炸
```

```ts
function first<T>(arr: T[]): T { return arr[0] }
const x = first([1, 2, 3])   // x: number ← 自动推导，不用写 first<number>
x.toUpperCase()              // ✗ 编译期就报错
```

```
值的函数：   function f(x: number): number    传值，返回值
类型的函数： type    F<T> = T[]               传类型，返回类型
```

> **泛型的价值不是"能装任何类型"（`any` 也能），而是能表达输入与输出的关系。**

你已经用过一堆了：`Promise<string>`、`Map<string, number>`、`AsyncIterable<Event>`。
注意 **`Promise` 本身不是类型，`Promise<string>` 才是**——前者是类型的函数。

## 2. `extends` 约束

### 语法拆解

```ts
function len<T extends { length: number }>(x: T): number { return x.length }
//           └─────────────┬─────────────┘└──┬──┘└──┬──┘
//                   类型参数列表          值参数  返回类型
```

**两套参数列表，写法是对仗的**：

| | 名字 | 分隔符 | 限定 |
|---|---|---|---|
| 值参数 | `x` | `:` | `T` |
| 类型参数 | `T` | `extends` | `{ length: number }` |

`x` 的类型是 `T`；`T` 的"可接受范围"是 `{ length: number }`。

### `{ A: B }` 是形状说明书

```
{ length: number }
    ↑        ↑
  属性名   该属性的类型
```

和值世界对照——同样的花括号，**位置决定属于哪个世界**：

```ts
const v = { length: 3 }        // 值：  键 length 装着 3
type  T = { length: number }   // 类型：键 length 装着「number 类型的东西」
```

**判定规则：可以多，不能少**

```ts
'hello'  ✓   [1,2,3]  ✓   { length:5, name:'a' }  ✓   { size:5 }  ✗   42  ✗
```

`string` 能满足是因为 **TS 是结构化类型系统——只看形状，不看名字和继承**。
没有 `implements` 声明，形状对上就算数。

### `extends` 后面可以是任何类型

`{A:B}` 只是最常见的一种：

```ts
<T extends string>            <T extends unknown[]>
<T extends ZodType>           <T extends string | number>
<T extends Record<string, unknown>>
```

`extends` 只是在说「**至少得是右边这个**」。

### 关键：约束保留具体类型，直接标注会拓宽

```ts
// ✗ 类型被拓宽成约束本身
function pick(x: { length: number }) { return x }
const a = pick('hello')     // a: { length: number } —— 不再是 string！
a.toUpperCase()             // ✗

// ✓ 具体类型被保留
function pick<T extends { length: number }>(x: T): T { return x }
const b = pick('hello')     // b: string ✓
```

> **`x: C` 是「你就是 C」，会拓宽；`T extends C` 是「你至少是 C」，具体是什么原样留着。**

agent 里的典型形状：

```ts
function tool<T extends ZodType>(def: {
  parameters: T                                    // 记住是哪个具体 schema
  execute: (args: z.infer<T>) => Promise<string>   // 才能从它挖出参数类型
}) { }
```

写成 `parameters: ZodType` 就被拓宽了，只知道"是个 schema"，`execute` 的参数只能是 `any`。

## 3. `typeof`：值 → 类型

TS 有两个平行世界，`typeof` 是它们之间的**单向桥**：

```
值世界  ──typeof──▶  类型世界
类型世界 ──✗ 无反向通道──▶  值世界     （类型编译完就擦掉了）
```

```ts
const schema = z.object({ path: z.string() })   // 值

type A = schema           // ✗ schema 是值不是类型
type B = typeof schema    // ✓ ZodObject<{ path: ZodString }>
```

⚠️ **和 JS 运行时的 `typeof x === 'string'` 完全无关**，长得一样而已。
**位置决定含义**：写在类型位置就是类型运算符。

高频组合 `keyof typeof`：

```ts
const COLORS = { red: '#f00', blue: '#00f' } as const
type ColorName = keyof typeof COLORS    // 'red' | 'blue'
//               └─┬─┘ └──┬──┘
//                 │      └─ 先把值变成类型
//                 └─ 再取所有键名
```

（不加 `as const` 值类型会被拓宽成 `string`。）

## 4. 条件类型 = 类型世界的三元运算符

```ts
const x = cond ? 'yes' : 'no'                  // 值世界
type IsString<T> = T extends string ? true : false   // 类型世界

type A = IsString<'hello'>   // true
type B = IsString<42>        // false
```

### `extends` 的两种语气

同一个关系（左边是不是右边的子类型），出现在两个位置只是**语气不同**：

| 位置 | 语气 | 意思 |
|---|---|---|
| `<T extends C>` | 祈使句 | 「T 必须至少是 C」——**要求**，卡住入口 |
| `A extends C ? X : Y` | 疑问句 | 「A 是不是至少是 C？」——**提问**，按答案分支 |

## 5. `infer` = 在模式里挖洞捕获

### 对比着看最清楚

```ts
// 只能判断，里面装的取不出来
type IsPromise<T> = T extends Promise<any> ? true : false
//                                    ↑ 匹配完就丢了

// 同一个位置，把它接住
type Unwrap<T> = T extends Promise<infer U> ? U : never
//                                  ↑ 挖个洞叫 U

type A = Unwrap<Promise<string>>   // string
type B = Unwrap<number>            // number（没匹配上，走 else）
```

**就是正则的捕获组**：

```
/^Promise<.+>$/       只知道匹配上了
/^Promise<(.+)>$/     加括号 → 能拿到中间那段
          ↑
        infer U
```

### 三条规则

1. 只能写在 `extends` **右边**（模式那一侧），不能独立存在
2. 匹配成功后，`U` 只在 **`?` 后面那支**里可用
3. 没匹配上走 `:` 那支

### U 就是那个类型，不是"有一个类型"

```
① T = Promise<string>
② 拿它和模式 Promise<infer U> 对
③ 对上了 → U 被绑定成 string      ← U 就是 string
④ 返回 ? 那一支 → string
```

证据：`U` 后面能直接跟 `[]`，说明它本身就是类型：

```ts
type ToArray<T> = T extends Promise<infer U> ? U[] : never
type A = ToArray<Promise<string>>    // string[]
```

作用域是局部的，不同条件类型里的 `U` 互不相干。一个模式里可以挖多个洞：

```ts
type Fn<T> = T extends (a: infer A) => infer R ? [A, R] : never
type X = Fn<(x: number) => string>   // [number, string]
```

### 三种"给类型起名字"的机制，别混

| 写法 | 是什么 | 谁决定它指向哪个类型 |
|---|---|---|
| `type X = Y` | **类型别名** | **你**，定义时写死 |
| `<T>` | **类型参数** | **调用方**传进来 |
| `infer U` | **捕获** | **编译器**匹配出来 |

```ts
type A = infer U     // ✗ 语法错误——infer 离不开条件类型
```

这条就证明了它和别名根本不是一类东西。

### 常见挖法（TS 都内置了）

```ts
T extends (infer U)[]              ? U : never   // 数组元素      ≈ 无内置
T extends (...a: any[]) => infer R ? R : never   // 函数返回值    ≈ ReturnType<F>
T extends Promise<infer U>         ? U : never   // 剥 Promise    ≈ Awaited<T>
T extends AsyncIterable<infer U>   ? U : never   // 流的元素类型（agent 常用）
```

| 内置 | 作用 |
|---|---|
| `ReturnType<F>` / `Parameters<F>` | 函数返回类型 / 参数元组 |
| `Awaited<T>` | 剥 Promise（能递归剥多层） |
| `Extract<T,U>` / `Exclude<T,U>` | 从联合里挑出 / 剔除 |

打开 `lib.es5.d.ts` 会看到它们就是上面这几行——**不是魔法，标准库用同一套语法写的**。

## 6. 映射类型 = 类型层的 map

遍历一个类型的所有键，生成新类型：

```ts
type Optional<T> = { [K in keyof T]?: T[K] }
//                    └─ 遍历每个键   └─ 取原值类型

type A = Optional<{ path: string; limit: number }>   // { path?: string; limit?: number }
```

`Partial` / `Required` / `Readonly` / `Pick` 全是这么实现的。

## 7. 分布式条件类型（读源码会撞上）

T 是**联合类型**时，条件类型会逐个成员分发再合并：

```ts
type Extract<T, U> = T extends U ? T : never

Extract<'a'|'b'|'c', 'a'|'b'>
//   'a' extends 'a'|'b' ? 'a' : never  →  'a'
//   'b' → 'b'    'c' → never（被吸收）
// 结果：'a' | 'b'
```

agent 里的典型用法——**从事件联合里精确挑出一种**：

```ts
type AgentEvent =
  | { type: 'text';       text: string }
  | { type: 'tool_start'; call: ToolCall }

function handleText(e: Extract<AgentEvent, { type: 'text' }>) {
  e.text     // ✓ 编译器知道这一支一定有 text
}
```

## 8. 诚实的话：这些主要是「读」，不是「写」

写 agent 几乎不需要自己定义条件类型。价值在于：

- 看懂 SDK 的 `.d.ts`，不再觉得是天书
- 类型报错时知道编译器在推什么，而不是随手 `as any`
- 会用 `Extract` / `Awaited` / `ReturnType` 这几个内置的

真要自己写条件类型的场合，通常说明你在造框架，不是在用框架。

---

# 八、类型收窄与可辨识联合

> agent 的核心数据结构（事件流、内容块、工具结果）全是联合类型，这章是读写它们的基本功。

## 1. 问题：联合类型不能直接用

```ts
function f(x: string | number) {
  x.toUpperCase()   // ✗ number 上没有这个方法
}
```

编译器必须先确定 x 是哪一支才允许你用对应能力。**把宽类型缩小到具体一支，叫收窄（narrowing）。**

```ts
if (typeof x === 'string') x.toUpperCase()   // ✓ 这支里 x: string
else                       x.toFixed(2)      // ✓ 这支里 x: number
```

**编译器在跟踪控制流**——它知道进了 if 意味着什么，进了 else 又意味着什么。

## 2. 收窄的六种手段

```ts
typeof x === 'string'        // 原始类型
x instanceof Error           // 类
'data' in obj                // 属性存在
x.type === 'text'            // 字面量比较 ← 可辨识联合靠它
if (x) { }                   // 真值检查，排除 null / undefined / ''
Array.isArray(x)             // 数组
```

### ⚠️ `in` 的坑：它查的是「键」，不是「值」

```js
const r = { data: 'hello' }
'data'  in r      // true  ← r 上有 data 这个属性
'hello' in r      // false ← 'hello' 是值，不是键
```

对数组尤其反直觉——**数组的"键"是索引**：

```js
const arr = ['a', 'b', 'c']
'a'      in arr   // false ← 'a' 是元素，不是键
0        in arr   // true  ← 0 是索引
'length' in arr   // true  ← length 也是属性
```

如果你来自 Python，那边 `'a' in ['a','b']` 是 True，**语义完全不同**。

同一个坑的延续：

```js
for (const x of arr) { }   // 'a' 'b' 'c'  ← of 遍历【值】
for (const x in arr) { }   // '0' '1' '2'  ← in 遍历【键】
```

> **数组只用 `for...of`。** `for...in` 遍历数组几乎总是 bug。

各种"包含"该用什么：

| 想判断 | 写法 |
|---|---|
| 对象有没有某个键 | `'k' in obj` |
| 对象有没有**自有**键（不查原型链） | `Object.hasOwn(obj, 'k')` |
| **数组**有没有某个值 | `arr.includes(v)` |
| 字符串包含子串 | `s.includes(sub)` |
| Map / Set | `map.has(k)` / `set.has(v)` |

注意 `in` 会查原型链：`'toString' in {}` 是 `true`。用于联合收窄时安全（声明的字段都是自有属性）。

## 3. 可辨识联合（Discriminated Union）

**一组对象类型，每个都有同名字段，该字段是字面量类型且值互不相同。** 那个字段叫**判别式**。

```ts
type AgentEvent =
  | { type: 'text';       text: string }
  | { type: 'tool_start'; call: ToolCall }
  | { type: 'tool_end';   id: string; output: string }
  | { type: 'error';      error: Error }
//    ↑ 判别式：字段名相同，值是四个不同的字面量
```

关键在于 `'text'` 是**字面量类型**（只能是这一个值），不是 `string`。
所以 `e.type === 'text'` 足以让编译器锁定是哪一支：

```ts
switch (e.type) {
  case 'text':       e.text;   break   // ✓ 编译器知道这支有 text
  case 'tool_start': e.call;   break   // ✓ 也知道这支没有 text
}
```

**agent 的核心结构全是这个形状**：

```ts
// 消息内容块
{ type:'text', text } | { type:'tool_use', id, input } | { type:'tool_result', ... }
// 流式事件
{ type:'message_start' } | { type:'content_block_delta' } | { type:'message_stop' }
```

## 4. 穷尽检查——最实用的一个技巧

**协议加了新事件类型时，编译器告诉你哪里漏了。**

```ts
function handle(e: AgentEvent) {
  switch (e.type) {
    case 'text':       return renderText(e.text)
    case 'tool_start': return showSpinner(e.call)
    case 'tool_end':   return showResult(e.output)
    case 'error':      return showError(e.error)
    default: {
      const _exhaustive: never = e     // ← 全处理完了，e 收窄成 never
      throw new Error(`未处理的事件: ${JSON.stringify(e)}`)
    }
  }
}
```

**原理**：每 `case` 一支就从联合里排除一支，全排除完 `e` 是 `never`（不可能有值）。

往联合里加一种：

```ts
type AgentEvent = /* ... */ | { type: 'thinking'; text: string }
```

`e` 在 default 里不再是 `never`，赋值立刻报错：

```
Type '{ type: "thinking"; ... }' is not assignable to type 'never'
```

**一次 `tsc`，所有该改的地方全列出来。** SDK 升级加了新事件类型时，你不会漏掉任何一处。

> 用 `return` 而不是 `break`，能保证 default 只在真漏了时才可达。

## 5. 类型谓词 `x is T`（type predicate）

内置手段不够时自己写。这种函数叫**类型守卫（type guard）**，
`x is T` 这个返回类型的写法叫**类型谓词（type predicate）**：

```ts
function isToolUse(b: ContentBlock): b is ToolUseBlock {
  return b.type === 'tool_use'
}
//                                   └──────┬──────┘
//                                     类型谓词，写在返回类型位置
```

### 它不是一个类型，是返回类型的特殊形式

函数**运行时返回的仍然是 `true` / `false`**。`b is ToolUseBlock` 只是额外告诉编译器一句话：

> **「当我返回 `true` 时，参数 `b` 就是 `ToolUseBlock`」**

```ts
function isStr1(v: unknown): boolean      { return typeof v === 'string' }
function isStr2(v: unknown): v is string  { return typeof v === 'string' }

if (isStr1(x)) x.toUpperCase()   // ✗ x 还是 unknown
if (isStr2(x)) x.toUpperCase()   // ✓ x 收窄成 string
```

**两者运行时行为完全一样**，唯一区别是**收窄信息能不能跨函数边界传递**。

### 语法约束：`is` 左边必须是参数名

```ts
function f(a: unknown, b: unknown): a is string   // ✓ a 是参数
function f(a: unknown):             x is string   // ✗ x 不是这个函数的参数
```

只能写形参名（或 `this`）。

### 两个分支都收窄

```ts
declare const e: TextEvent | ToolEvent
if (isText(e)) e    // TextEvent
else           e    // ToolEvent ← else 分支排除掉了 TextEvent
```

### ⚠️ 编译器不验证你的实现

```ts
function isString(x: unknown): x is string {
  return typeof x === 'number'    // 写错了，编译器照信不误
}
```

类型谓词是**你对编译器的承诺**，写错了就是自己骗自己。这是它唯一的风险。

### 兄弟形式：断言函数 `asserts x is T`

不返回 boolean，语义是「**没抛异常就说明是 T**」：

```ts
function assertString(v: unknown): asserts v is string {
  if (typeof v !== 'string') throw new Error('不是字符串')
}

assertString(x)
x.toUpperCase()      // ✓ 这行之后 x 一直是 string，不需要 if
```

| | 用法 | 收窄范围 |
|---|---|---|
| `v is T` | `if (check(v)) { }` | 只在 if / else 分支内 |
| `asserts v is T` | `assert(v)` 后直接用 | 从这行往后一直有效 |

### 为什么 `filter` 认它

原理就写在 `filter` 的类型签名里：

```ts
// lib.es5.d.ts
filter<S extends T>(predicate: (value: T) => value is S): S[]
//                                           └────┬────┘   └┬┘
//                                        要求是类型谓词    返回窄化后的数组
```

```ts
res.content.filter(isToolUse)                    // ToolUseBlock[] ✓
res.content.filter(b => b.type === 'tool_use')   // ContentBlock[] ✗ 没收窄
```

第二种的箭头函数返回类型被推成 `boolean`，不是类型谓词，`filter` 走了另一个重载。
想让内联写法也生效，得显式标注：

```ts
res.content.filter((b): b is ToolUseBlock => b.type === 'tool_use')   // ✓
```

## 6. `unknown` / `any` / `never`

| | 含义 | 能干什么 |
|---|---|---|
| `any` | 放弃类型检查 | 什么都能干——**关掉了安全网** |
| `unknown` | 我不知道它是什么 | 什么都不能干，**必须先收窄** |
| `never` | 不可能存在的值 | 穷尽检查、永不返回的函数 |

**`unknown` 是 `any` 的安全版。** 模型输出、`JSON.parse` 结果、`catch` 的错误都该标 `unknown`：

```ts
try { /* ... */ }
catch (e) {                          // e: unknown（TS 4.4+ 默认）
  if (e instanceof Error) e.message  // ✓ 先收窄
  else String(e)
}
```

## 7. Zod 其实就是自动化的类型守卫

手写守卫处理 `unknown` 很啰嗦：

```ts
const data: unknown = JSON.parse(raw)
if (typeof data === 'object' && data !== null && 'path' in data && typeof data.path === 'string') {
  // 才敢用 data.path
}
```

所以实践中用 Zod：

```ts
const r = schema.safeParse(data)
if (r.success) r.data.path      // ✓ 完整类型，一行搞定
```

**`safeParse` 的返回类型本身就是可辨识联合**（判别式是 `success`），
收窄到 `true` 那支就拿到了完整类型。

> 第九章和这一章是同一件事的两个视角：**怎么安全地把 `unknown` 变成有类型的东西。**


---

# 九、Zod（工具定义）

> 第三章记的是**该学多少**（20% 就够），这章是那 20% 的内容。

## 1. 为什么 agent 必须有它

模型返回的工具参数是一坨**不可信的 JSON**：

```ts
toolUse.input   // unknown —— 可能少字段、类型错、幻觉出不存在的参数
```

同时模型也需要知道该填什么。**这两件事一份 schema 全包了。**

## 2. 一份 schema，三处用

```ts
const schema = z.object({
  path:     z.string().describe('要读取的文件绝对路径'),
  limit:    z.number().int().positive().optional().describe('最多读多少行'),
  encoding: z.enum(['utf-8', 'ascii']).default('utf-8'),
})
```

```ts
// ① 给模型看的 JSON Schema —— 模型照着它生成参数
z.toJSONSchema(schema)
// { type:'object', properties:{ path:{type:'string', description:'...'} }, required:['path'] }

// ② 运行时校验 —— 挡住模型的错误输出
const r = schema.safeParse(toolUse.input)

// ③ 静态类型
type Args = z.infer<typeof schema>
// { path: string; limit?: number; encoding: 'utf-8' | 'ascii' }
```

三者从同一处生成，**永远不会漂移**。这就是它在 agent 里的全部价值。

## 3. 校验失败要回给模型，不是抛出去

```ts
const r = schema.safeParse(toolUse.input)
if (!r.success) {
  return {                                      // ← 不 throw
    type: 'tool_result', tool_use_id: toolUse.id,
    is_error: true,
    content: `参数不合法: ${r.error.message}`,   // ← 让模型看到，自己改正重试
  }
}
await readFile(r.data.path)                     // r.data 类型完整
```

`.parse()` 抛异常，那是给「本该正确」的场景用的。
**模型输出出错属于正常流程**，所以 agent 里几乎总是 `safeParse`。

## 4. API 速查（会这些就够）

```ts
z.string()  z.number()  z.boolean()  z.enum(['a','b'])
z.array(...)  z.object({...})  z.union([...])  z.discriminatedUnion('type', [...])

.optional()  .nullable()  .default(v)  .describe('给模型看的说明')
.int()  .positive()  .min(1)  .max(100)  .regex(/.../)

schema.safeParse(x)        // { success, data } | { success, error }
z.infer<typeof schema>     // 拿类型
z.toJSONSchema(schema)     // 拿 JSON Schema（v4 内置）
```

## 5. 最重要的一条：哪些约束模型看得见

| 模型**看得见**（进 JSON Schema） | 模型**看不见**（转换时丢失） |
|---|---|
| `.min()` `.max()` `.int()` `.positive()` | `.refine()` |
| `.regex()` `.enum()` `.length()` | `.superRefine()` |
| `.optional()` `.default()` | `.transform()` |
| **`.describe()`** ← 最重要 | `.custom()` |

左边写进 JSON Schema，模型生成时就遵守 → **预防**错误。
右边只在运行时校验 → 只能**事后**报错，模型撞上了才知道。

```ts
z.string().refine(s => s.startsWith('/'), '必须是绝对路径')   // ✗ 模型不知道，只会不断试错
z.string().regex(/^\//).describe('必须是绝对路径，如 /home/a.txt')  // ✓ 一开始就知道
```

## 6. `.describe()` 是在写 prompt

它的内容会进 JSON Schema 的 `description`，**直接进模型的上下文**。

所以它不是注释，是 prompt 的一部分——写清含义、单位、格式、边界，比任何校验逻辑都管用。
字段名同理，`p` 和 `absolutePath` 对模型是两回事。

> **工具 schema 的质量取决于模型好不好懂，不取决于你用哪个库。**
> 结构扁平、字段名自解释、`describe` 写足，比精巧的校验重要得多。

## 7. `z.infer` 到底怎么工作的

先说实话：**`z.infer` 不是条件类型，也没用 `infer` 关键字**，真实定义就一行：

```ts
export type infer<T extends ZodType<any,any,any>> = T['_output']
//                                                  ↑ 索引访问
```

类型信息**不是事后推断的，是构造 schema 时一路带着的**。极简版：

```ts
interface Schema<T> {
  _output: T                    // ← 幽灵字段，只存在于类型层，运行时没有
  parse(x: unknown): T
}

declare function string(): Schema<string>

// object：遍历每个字段取出它的 _output 重新组装（映射类型）
declare function object<S extends Record<string, Schema<any>>>(
  shape: S
): Schema<{ [K in keyof S]: S[K]['_output'] }>

type Infer<T extends Schema<any>> = T['_output']
```

整条链：

```
z.string()               → Schema<string>            ① 原子类型自带标记
z.object({ path: ... })  → Schema<{path: string}>    ② 映射类型逐字段组装
typeof schema            → 那个 Schema<...> 类型      ③ 值 → 类型
z.infer<...>             → { path: string }          ④ 索引访问取出来
```

**没有一处是魔法**，全是第七章那几样：泛型、`extends` 约束、`typeof`、索引访问 + 映射类型。

## 8. TypeBox：知道就行，不用学

**它构造出来的东西本身就是一个 JSON Schema 对象**：

```ts
const S = Type.Object({ path: Type.String() })
console.log(S)   // { type:'object', properties:{path:{type:'string'}}, required:['path'] }
type T = Static<typeof S>
```

| | Zod | TypeBox |
|---|---|---|
| schema 本体 | Zod 自己的结构 | **就是 JSON Schema** |
| 拿 JSON Schema | 要转换 | 零转换 |
| 校验 | 内置 `.safeParse` | 接 Ajv 或自带 `TypeCompiler` |
| 校验性能 | 每次遍历 schema 树 | 预编译成直线 JS，快一个数量级 |
| 表达力 | 富（transform/refine） | 只有 JSON Schema 能表达的 |
| 生态文档 | 好很多 | 小众 |

**有意思的点**：TypeBox 那个"表达力受限"在 agent 场景里**其实是优点**——
它的表达力上限正好等于模型的理解上限，从设计上堵死了"写了模型却看不见的约束"这条岔路。

**但仍然建议 Zod**，决定性理由是生态：MCP 的 TS SDK、Vercel AI SDK、tRPC 第一公民都是 Zod，
`tool({ parameters: zodSchema })` 直接可用；TypeBox 通常得走"传原始 JSON Schema"的备用通道。
你读源码撞上的也几乎全是 Zod。

> 真要切也很快——API 一一对应，半小时的事。

---

# 十、AbortSignal 与取消传播

> 第三章说过这是「最被低估的一项」。agent 里唯一还没碰的运行时能力。

## 1. 什么需要取消

```
用户按 Ctrl+C      → 正在飞的 LLM 请求、正在跑的 bash、所有 subagent 都得停
请求超时            → 30 秒还没回来就放弃
用户发了新消息      → 上一轮的请求作废
一个子任务失败      → 其他并行任务没必要继续
```

共同点：**取消信号要从最上层，一路传到最下面每一个正在等待的地方。**

## 2. Controller / Signal：权限分离

```ts
const ac = new AbortController()

ac.signal        // 接收端 —— 发给下游，下游只能被动响应
ac.abort()       // 遥控器 —— 只有持有 controller 的人能触发
```

**为什么拆成两个**：你把 `signal` 传给一百个下游，它们都能感知取消，
但**谁都无法取消别人**。取消权只在持有 controller 的那一方手里。

## 3. 基本用法

```ts
const res = await fetch(url, { signal: ac.signal })
```

`abort()` 后这个 `await` 会**抛异常**——取消不是返回 null，是走异常路径。
所以必须区分「被取消」和「真出错」：

```ts
try {
  await fetch(url, { signal })
} catch (e) {
  if (signal.aborted) {
    // 正常取消，不是错误 —— 别打 error 日志、别上报
  } else {
    throw e     // 真的网络错误
  }
}
```

> ⚠️ 常见的 `e.name === 'AbortError'` 只在 `abort()` **不带参数**时成立。
> 一旦写 `abort(new Error('用户中断'))`，抛出来的就是你传的东西。
> **判断 `signal.aborted` 更可靠。**

## 4. signal 的 API

```ts
signal.aborted             // boolean，当前是否已取消
signal.reason              // abort(reason) 传进来的东西
signal.throwIfAborted()    // 已取消就抛，否则什么都不做
signal.addEventListener('abort', fn, { once: true })
```

## 5. 核心：传播（最容易出 bug 的地方）

```ts
async function* runAgent(input: string, signal: AbortSignal) {
  while (true) {
    signal.throwIfAborted()                            // ① 循环顶部检查

    const res = await callLLM(messages, { signal })    // ② 往下传

    for (const call of res.toolCalls) {
      const out = await executeTool(call, { signal })  // ③ 继续往下传
      yield { type: 'tool_end', out }
    }
  }
}
```

> **没传 signal 的那一层，就是取消断掉的地方。**

最常见的症状：用户按了 Ctrl+C，界面停了，但某个 `bash` 工具还在后台跑——
因为 `executeTool` 那层忘了接 signal。

## 6. 自己的异步操作怎么响应

**① 检查点（循环里）**

```ts
for (const item of items) {
  if (signal.aborted) break
  await process(item)
}
```

**② 监听 + 竞速（阻塞操作）**

```ts
function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const onAbort = () => { clearTimeout(t); reject(signal!.reason) }

    const t = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)   // ← 正常结束也要摘
      resolve()
    }, ms)

    signal?.addEventListener('abort', onAbort, { once: true })
  })
}
```

**两条路径各摘各的**：abort 走 `once`，正常结束走显式 `removeEventListener`。
（`once: true` 只在 listener **触发过**之后才自动摘除。）

> 能用内置的就别手写：
> `import { setTimeout as sleep } from 'node:timers/promises'`，然后 `await sleep(1000, undefined, { signal })`。

**③ 子进程**

```ts
const child = spawn('bash', ['-c', cmd], { signal })   // Node 原生支持，abort 时自动 SIGTERM
```

## 7. 组合 signal

```ts
AbortSignal.timeout(30_000)      // 30 秒后自动取消
AbortSignal.any([s1, s2])        // 任一触发就取消（Node 20+）
```

agent 里非常实用的组合——**用户中断和超时，哪个先到算哪个**：

```ts
const signal = AbortSignal.any([
  userSignal,                    // Ctrl+C
  AbortSignal.timeout(30_000),   // 超时兜底
])
```

## 8. 和 async generator 配合（回扣第六章）

```ts
async function* readStream(res: Response, signal: AbortSignal) {
  const reader = res.body!.getReader()
  try {
    while (true) {
      signal.throwIfAborted()
      const { done, value } = await reader.read()
      if (done) break
      yield value
    }
  } finally {
    reader.releaseLock()      // ← abort 抛异常、消费方 break，都会走到这里
  }
}
```

**这两个机制是配套的**：

- 消费方 `break` → 引擎调 generator 的 `return()` → `finally` 执行
- `signal` 抛异常 → 异常穿过 generator → `finally` 同样执行

所以资源清理写在 `finally` 里，两条路径都覆盖到。

## 9. 四个常见错误

| 错误 | 后果 |
|---|---|
| 忘了往下传 signal | 上层停了，下层还在跑 |
| 把 AbortError 当真错误 | 日志刷屏、错误上报全是噪音 |
| listener 不加 `{ once: true }` 也不摘 | 长生命周期的 signal 上挂几千个 listener，内存泄漏 |
| **复用同一个 AbortController** | **`abort()` 过的 signal 永远是 aborted，无法重置** |

最后一条最坑——**AbortController 是一次性的**：

```ts
const ac = new AbortController()
ac.abort()
ac.signal.aborted    // true，永远是 true，没法重置
// ✓ 每一轮新建一个
```

## 10. agent 里的完整形状

```ts
const ac = new AbortController()
process.on('SIGINT', () => ac.abort(new Error('用户中断')))

try {
  for await (const ev of runAgent(input, ac.signal)) render(ev)
} catch (e) {
  if (ac.signal.aborted) console.log('\n已停止')
  else throw e
}
```

一个 controller 在最顶层，`signal` 往下贯穿到每一个 `fetch`、每一个子进程、每一个 `sleep`。
**这条链哪里断了，哪里就停不下来。**

## 附：listener 与 `{ once: true }`

**listener = 一个函数，登记给某个事件，事件发生时被自动调用。**

```js
signal.addEventListener('abort', () => cleanup(), { once: true })
//     └──────┬───────┘  └──┬──┘  └──────┬──────┘   └────┬────┘
//         登记动作      监听哪个事件   listener 本体   触发一次后自动摘除
```

核心是**控制反转**：不是你去轮询「发生了吗」，而是登记好等它来叫你。

和 Promise 的区别：

| | Promise / await | listener |
|---|---|---|
| 触发次数 | **只有一次** | 可以**很多次** |
| 谁驱动 | 你主动 await | 事件源主动调你 |
| 一对多 | 一个 Promise 一个结果 | **同一事件可挂多个 listener，全都会被调** |

**AbortSignal 用 listener 而不是 Promise，就是为了这个一对多广播**——
同一个 signal 传给了 LLM 请求、子进程、三个 subagent，各自登记各自的清理逻辑。

> `AbortSignal` 是个 **EventTarget**，和浏览器里的 DOM 元素共用同一套事件 API。
> 顺带：`addEventListener` 自己也接受 `{ signal }`，可以用一个 signal **批量卸载**一堆监听器。

---

# 附录：术语对照表

> 记住专业术语有两个好处：查资料时知道搜什么，读英文文档时不卡壳。
> 中文技术术语大多是直译，单看很怪，对上英文原文就通了。

## 异步与运行时

| 中文 | 英文 | 一句话 |
|---|---|---|
| 事件循环 | event loop | 反复检查"哪个 I/O 完成了、该恢复哪段代码"的循环 |
| **阻塞** | blocking | **占着线程什么也不干**（`readFileSync`） |
| **暂停 / 挂起** | suspend | **交出线程，别人可以用**（`await`） |
| 微任务队列 | microtask queue | Promise 回调排队的地方，每个宏任务后被抽干 |
| 协作式 / 抢占式 | cooperative / preemptive | 只在 `await` 处让出 / 任何一行都可能被打断 |
| 续体 | continuation | 函数暂停后"剩下要跑的那部分" |
| 重入 | reentrancy | 上一次还没跑完，同一个函数又被调了 |
| 背压 | backpressure | 消费方跟不上时让生产方慢下来 |
| 类型擦除 | type erasure | TS 编译后类型信息全部消失 |

## 流与迭代

| 中文 | 英文 | 一句话 |
|---|---|---|
| 可迭代对象 | Iterable | 有 `[Symbol.iterator]`，**能提供**遍历器 |
| 迭代器 | Iterator | 有 `next()`，**它就是**遍历器 |
| 生成器 | Generator | `function*` 产出的对象，上面两者都是 |
| 迭代结果 | IteratorResult | `{ value, done }` 那个信封 |
| 监听器 | listener | 登记给某个事件、发生时被自动调用的函数 |
| 事件目标 | EventTarget | 能被 `addEventListener` 的东西（DOM 元素、AbortSignal） |

## 类型系统

| 中文 | 英文 | 一句话 |
|---|---|---|
| 泛型 | generic | 类型的参数 |
| 类型参数 | type parameter | `<T>` 里的 `T` |
| 泛型约束 | generic constraint | `T extends C`，「至少得是 C」 |
| **结构化类型** | structural typing | **只看形状，不看名字和继承** |
| 类型别名 | type alias | `type X = Y` |
| 字面量类型 | literal type | `'text'` 这种只能取一个值的类型 |
| 联合类型 | union type | `A \| B` |
| **可辨识联合** | discriminated union | 带同名字面量字段的联合 |
| 判别式 | discriminant | 用来区分是哪一支的那个字段（通常叫 `type`） |
| **类型收窄** | narrowing | 把宽类型缩小到具体一支 |
| 控制流分析 | control flow analysis | 编译器跟踪 if/else 来做收窄 |
| 类型守卫 | type guard | 能触发收窄的函数 |
| **类型谓词** | type predicate | `x is T` 这种返回类型的写法 |
| 断言函数 | assertion function | `asserts x is T`，没抛异常就说明是 T |
| **穷尽检查** | exhaustiveness checking | 用 `never` 保证 switch 没漏分支 |
| 条件类型 | conditional type | `A extends B ? X : Y` |
| 映射类型 | mapped type | `{ [K in keyof T]: ... }`，类型层的 map |
| 索引访问类型 | indexed access type | `T['field']` |
| 分布式条件类型 | distributive conditional type | 联合类型逐成员分发再合并 |
| 工具类型 | utility type | `ReturnType` / `Awaited` / `Extract` 这些内置的 |
| 幽灵字段 | phantom field | 只存在于类型层、运行时没有的字段（Zod 的 `_output`） |

## 通用编程术语（常见直译词）

| 中文 | 英文 | 实际意思 |
|---|---|---|
| 一等公民 | first-class | 享有完整待遇，能赋值/传参/返回，无特殊限制 |
| 语法糖 | syntactic sugar | 更好写的等价写法，不增加新能力 |
| 副作用 | side effect | 函数除返回值之外对外界的改动 |
| 样板代码 | boilerplate | 每次都得重复写的固定套路 |
| 控制反转 | inversion of control | 不是你调它，是它调你（listener 就是这个） |
| 心智模型 | mental model | 你脑中对某个东西如何运作的理解 |
| 幂等 | idempotent | 执行多次和执行一次效果相同 |
| 银弹 | silver bullet | 一招解决所有问题的万灵药（通常用于否定） |

---

# 下一步

语言层面到这里基本够了。剩下的（`as const`、`?.` / `??`、ESM/CJS、`satisfies`）
都是撞上了查五分钟就懂的，不值得预习。

## 真正的门槛不在语言

这份笔记全是「TS/Node 基础设施」，零「agent 架构」。而 agent 难的地方基本都在后者，
且**和语言无关**——换成 Python 一样难：

1. **Agent 主循环** —— messages 数组怎么维护、`tool_use` / `tool_result` 怎么配对、
   循环什么时候终止。核心中的核心，代码可能就 100 行，但每行都有讲究。
2. **上下文管理** —— 长对话必然爆 context。什么时候压缩、压缩掉什么、怎么保留关键信息。
   **实际项目里的头号瓶颈。**
3. **工具设计** —— 粒度多大、返回多少内容、
   **出错时不要 throw，要把错误信息作为 `tool_result` 返给模型**让它自己纠正。
4. **权限与副作用控制** —— 什么操作要人确认，怎么做沙箱。
5. **Eval** —— 改了个 prompt，怎么知道变好还是变差。没有 eval 就是在盲调。
6. **成本与延迟** —— prompt caching、模型路由、什么时候值得开 subagent。

> 一个把事件循环研究得很透、但从没想过上下文压缩的人，写出来的 agent 一定不好用。

## 该做的两件事

### ① 先做一次真实自测

打开 `node_modules/@anthropic-ai/sdk/` 里任意一个 `.d.ts`，
或者 `@modelcontextprotocol/sdk` 的 `client/index.ts`，读十分钟，标出看不懂的地方。

- 看不懂的少 → 这份笔记生效了，直接去做 ②
- 看不懂的多 → 缺口在别处（模块系统？class？SDK 自己的抽象？），
  比继续泛泛补 TS 精准得多

### ② 写一个最小 agent 循环

不依赖任何框架，大约 200 行：

```
一个 while 循环
两三个工具（读文件、跑命令、写文件）
messages 数组自己拼
先不要流式，先跑通
```

跑通后逐个加，每加一样正好回到本文的一章：

| 加什么 | 回看哪章 |
|---|---|
| 流式输出 | 六（async generator / AsyncIterable） |
| Ctrl+C 中断 | 十（AbortSignal 传播） |
| 参数校验 | 九（Zod）+ 八（收窄） |
| 事件分发 | 八（可辨识联合 + 穷尽检查） |
| 上下文压缩 | —（和 TS 无关，见上面第 2 条） |

**每个知识点都挂在一个真实遇到过的问题上，比按清单预习牢得多。**
