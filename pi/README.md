# Pi 学习笔记

个人学习 pi coding agent 的笔记，与 pi 源码仓库分开维护。

目录里有四类东西，**只有第一类是主线**。

---

## 一、主线：有目的的源码精读（01–07）

对话式逐行走读产出，动笔前真读源码，论断落到 `文件:行号`（文中注明 commit）。
**这是会反复回来翻的那部分。**

```text
01 ─→ 02 ─→ 03        会话树 → 出去 → 回来          数据路径闭环
04 ─→ 05              扩展装配 → Context 汇合        组装闭环
06                    压缩：唯一改写历史的机制
07                    从 pi 剥出来的坐标系            ← 终点
```

| 篇 | 主题 | 一句话 |
|---|---|---|
| [01](01-session-tree-and-context.md) | 会话树与上下文 | JSONL 只追加、树状分支、`leafId` 是 HEAD；分支 = 移指针 |
| [02](02-context-to-llm.md) | Context 出去 | 树 → 路径 → 消息 → 报文；**事实层 vs 投影层**；`convertToLlm` 是全链路唯一不可逆的一步 |
| [03](03-llm-response-to-session.md) | Context 回来 | 一轮的时间线 T0–T6；SSE → 状态机 → `AssistantMessage` → 落盘 |
| [04](04-extension-loading-path.md) | 扩展装配线 | 磁盘 `.ts` → 盒子 → `bindCore` 激活 → 运行期派发；盒子隔离 / runtime 共享 |
| [05](05-tools-and-systemprompt-to-context.md) | tools 与 systemPrompt 汇合 | `Context` 三字段三种更新策略；**前缀缓存与延迟加载**那条横切线 |
| [06](06-compaction.md) | 压缩 | 何时压、谁来压、摘要怎么生成、压完怎么生效；四套摘要提示词 |
| [07](07-harness-design-space.md) | **harness 设计空间** | 不提 pi 的文件名——四方向模型 + 十五问 + 可带走的检查清单 |

**从哪进**：

- 想弄懂 pi 本身 → 从 01 顺着读，01→02→03 是一条完整的数据路径
- 想弄懂 agent harness 的通用设计 → **直接读 07**，需要实现细节时再回查 01–06

每篇末尾都有**工程模式清单**（能带走的部分）和**复习自测**（筛真懂假懂）。

---

## 二、`generated/` — 早期通篇生成的源码笔记

一次性生成的全量走读，按**模块**组织，没有编号（它本来就没有阅读顺序）。

**覆盖面广但偏空泛，未精读，留作查阅。** 其中这几篇仍有独立价值，主线里会点名引用：

| 文件 | 为什么还留着 |
|---|---|
| [`modes-and-tui.md`](generated/modes-and-tui.md) | TUI 差分渲染、三种前端模式的接缝——主线完全没覆盖 |
| [`extensions.md`](generated/extensions.md) | 扩展系统的参考手册（事件目录、快捷键仲裁、两个官方案例），与 04 篇互补 |
| [`robustness-and-cost.md`](generated/robustness-and-cost.md) | Usage 五桶、价格结构、`cache_control` 滚动前缀，与 05 篇第 4 章互为入口 |

其余：`全景地图.md`、`agent.md`、`ai.md`、`coding-agent-core.md`、`testing.md`，以及更早的随记 `mynote.md`（内容已被 01 篇覆盖）。

---

## 三、`docs-reading/` — 官方文档带读笔记

读 pi **官方文档**（而非源码）时的记录，四份：配置与资源、扩展与个性化、文档总览、会话与上下文。

和主线的区别：主线读的是代码，这些读的是文档。

---

## 四、`translations/` — 中文译文

不是笔记，是 pi 文档的中文翻译。

- [`docs-zh/`](translations/docs-zh/README.md) — pi 中文文档总览
- [`packages/`](translations/packages/DOCS.zh.md) — packages 中文文档导览
- [`README.zh.md`](translations/README.zh.md) — 项目中文 README

---

## 写作约定（主线）

- 动笔前真读源码；每个论断落到 `文件:行号`，文中注明所基于的 commit
- **按数据路径分章，不按代码位置**——每章都要能回答"我现在在路径的哪一段"；实现细节挂在路径段下，参照性内容标明"路旁参照"
- 讲一个东西要有逻辑主线，**不能列清单**——每个点都要说清它为什么存在、和主线什么关系
- 敢下判断（标注「判断：」），砍套话
- 打印友好：开头目录、交叉引用写「见第 X 章」、单一自包含 Markdown
- 篇末列**工程模式清单**与**复习自测**
- 发现旧篇有错就当场更正并标注日期（例：03 篇 6.5 关于自动压缩位置的更正）
