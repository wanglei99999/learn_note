# 第十章：多跳推理——复杂问题的检索
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：02-advanced-retrieval.md，第十章（第336-499行）。本章讲解单跳 vs 多跳问题的区别、Iterative Retrieval（迭代检索）、ReAct 框架，以及减少延迟的优化方向（查询分解预处理、基于规则的问题路由）。

---

> **📌 本章核心**
>
> - 【必须掌握】**识别多跳查询**：包含条款引用（"第3.2条"）、跨章节计算（"根据...计算"）、条件推理（"如果...那么"）的查询大概率需要多跳；其他用 Multi-Query 即可
> - 【必须掌握】**DAG 依赖三类型**：纯链式（全串行）、独立分支（全并行）、混合依赖（局部并行）——关键路径决定最短执行时间，错误地串行化可并行节点是最常见的性能浪费
> - 【理解即可】**DAG 并行执行原理**：asyncio.gather 并行执行所有"依赖已满足"的就绪节点，等待前驱完成后立即启动后继——比朴素串行迭代快 2~4 倍
> - 【查阅即可】**延迟对比**：朴素串行迭代 12~20s vs DAG 并行 3~6s（混合依赖案例）；规则路由（正则检测条款引用）零延迟判断是否触发多跳

---

**🔬 研究员**

单次检索能处理简单问题，但现实中的复杂问题需要**多步推理**：

**单跳问题**（一次检索就够）：
> "合同的违约金怎么计算？"

**多跳问题**（需要多次检索，每次结果指导下次检索）：
> "如果甲方违反了第3.2条关于交货期的规定，按照第7章的违约金计算方式，应该赔偿多少？"

这个问题需要：
1. 先检索"第3.2条交货期规定"，理解违约行为
2. 再检索"第7章违约金计算方式"
3. 最后综合两个结果计算

### Iterative Retrieval（迭代检索）

```
第1轮：
  查询：   "第3.2条交货期规定"
  结果：   "甲方应在签约后30日内交货..."

第2轮（基于第1轮结果生成新查询）：
  查询：   "延迟交货的违约金计算"
  结果：   "延迟交货按合同金额0.1%/天计算..."

第3轮（如有需要）：
  查询：   "违约金上限规定"
  结果：   "违约金不超过合同总金额的20%..."

综合3轮结果 → 最终回答
```

### ReAct 框架（推理 + 行动交错）

ReAct（Reasoning + Acting）是解决多跳问题的主流框架，LLM 交替执行"思考"和"检索"：

```
Thought: 需要先了解第3.2条的具体规定
Action: search("第3.2条交货期")
Observation: 甲方应在签约后30日内交货，逾期按日计违约金

Thought: 已知违约行为，需要找到违约金计算公式
Action: search("违约金计算方式 第7章")
Observation: 逾期交货违约金 = 合同金额 × 0.1% × 逾期天数

Thought: 需要确认违约金上限
Action: search("违约金上限")
Observation: 违约金累计不超过合同金额的20%

Thought: 现在可以综合计算了
Answer: 根据合同规定，...
```

---

**🔧 工程师**

### 【理解即可】简化版迭代检索实现

```python
async def iterative_rag(
    query: str,
    llm: LLMProvider,
    retriever,
    max_iterations: int = 3,
) -> str:
    accumulated_context = []
    current_query = query

    for i in range(max_iterations):
        # 检索当前查询
        chunks = await retriever.search(current_query, top_k=3)
        accumulated_context.extend(chunks)

        # 让 LLM 判断是否需要继续检索
        decision_prompt = f"""
已收集的信息：
{format_chunks(accumulated_context)}

原始问题：{query}

判断：
1. 当前信息是否足够回答原始问题？
2. 如果不足，下一步需要检索什么？

输出 JSON：
{{"sufficient": true/false, "next_query": "..."}}
"""
        decision = await llm.generate_json(decision_prompt)

        if decision["sufficient"]:
            break

        current_query = decision["next_query"]

    return await generate(query, format_chunks(accumulated_context))
```

**注意事项：**
- `max_iterations` 要设上限，防止无限循环
- 每轮检索结果要去重，防止 context 爆炸
- 通常 2~3 轮就够

### 延迟对比

| 方式 | LLM 调用次数 | 典型延迟 |
|------|------------|---------|
| 单次 RAG | 1次 | 1~3s |
| 2轮迭代 RAG | 3次（判断×2 + 生成×1） | 3~8s |
| 3轮迭代 RAG | 5次 | 6~15s |

**工程权衡：**
1. 用简单分类器预判问题复杂度，简单问题走单次 RAG
2. 流式输出：即使多轮检索，也尽早开始 token 输出

---

**❓ 提问者**

迭代检索中每轮都多一次 LLM 调用判断是否继续，延迟叠加很严重。有没有办法减少这个开销？

---

**🔬 研究员**

有几种优化方向：

**1. 查询分解预处理（Query Decomposition）**

在检索之前，先用 LLM 把复杂问题拆成子问题列表，然后并行检索所有子问题：

```
原始：  "甲方违反第3.2条，按第7章计算赔偿多少？"
  ↓ 一次 LLM 调用
子问题：["第3.2条的内容是什么", "第7章违约金如何计算"]
  ↓ 并行检索
同时检索两个子问题，合并结果 → 一次生成
```

总 LLM 调用：分解（1次）+ 生成（1次）= 2次，比迭代的 3~5 次少。

#### 【必须掌握】串行 vs 并行：DAG 依赖分析

"什么时候必须串行，什么时候可以并行"不是凭直觉判断的——可以用**有向无环图（DAG）**对子问题的依赖关系进行形式化分析：

```
DAG 定义：
  节点 = 子问题
  有向边 (qᵢ → qⱼ) = "qⱼ 的查询需要用到 qᵢ 的答案"
```

**案例一：纯链式依赖（必须全串行）**

```
问题："A 公司 CEO 的母校在哪个城市？"

依赖图：
  q1: "A 公司的 CEO 是谁？"
    ↓
  q2: "（q1的答案）毕业于哪所大学？"    ← 必须等 q1 完成
    ↓
  q3: "（q2的答案）在哪个城市？"        ← 必须等 q2 完成

最短执行时间 = 3 次检索串行
```

**案例二：独立分支（可以全并行）**

```
问题："A 公司的 CEO 和 CTO 分别毕业于哪里？"

依赖图：
  q1: "A 公司的 CEO 是谁？"    q2: "A 公司的 CTO 是谁？"
    ↓                             ↓
  q3: "（q1）毕业于哪里？"    q4: "（q2）毕业于哪里？"

q1 和 q2 独立 → 并行执行
q3 依赖 q1，q4 依赖 q2 → q3,q4 可以在各自前驱完成后立即开始

关键路径 = max(q1→q3, q2→q4) = 2 步（而非 4 步串行）
```

**案例三：混合依赖（局部并行）**

```
问题："甲方违反第3.2条，按第7章计算赔偿多少？"

依赖图：
  q1: "第3.2条交货期规定"      q2: "第7章违约金计算方式"      q3: "合同金额"
      ↘                            ↘                            ↘
         q4: "综合q1、q2、q3，计算违约赔偿金额"

q1、q2、q3 相互独立 → 并行检索
q4 依赖所有前驱 → 等待 q1,q2,q3 全部完成后执行

最短执行时间 = 1步（并行检索）+ 1步（q4生成）= 2步 LLM 调用
（传统迭代需要：q1→q2→q3→q4 = 4步）
```

**DAG 执行的代码实现：**

```python
import asyncio

async def dag_multi_hop(query: str, llm, retriever) -> str:
    # 1. 一次 LLM 调用，输出带依赖关系的子问题 DAG
    decompose_prompt = f"""
将以下问题分解为子问题，并声明每个子问题的依赖关系。

问题：{query}

输出 JSON 格式：
{{
  "sub_questions": [
    {{"id": "q1", "query": "...", "depends_on": []}},
    {{"id": "q2", "query": "...", "depends_on": []}},
    {{"id": "q3", "query": "...", "depends_on": ["q1", "q2"]}}
  ]
}}

注意：如果 qB 的查询内容需要用到 qA 的答案，则 qB.depends_on = ["qA"]。
"""
    dag_spec = await llm.generate_json(decompose_prompt)
    sub_questions = dag_spec["sub_questions"]

    # 2. 按 DAG 拓扑顺序执行（并行化独立节点）
    results: dict[str, str] = {}
    completed: set[str] = set()

    while len(completed) < len(sub_questions):
        # 找出所有依赖已满足、且尚未执行的节点
        ready = [
            sq for sq in sub_questions
            if sq["id"] not in completed
            and all(dep in completed for dep in sq["depends_on"])
        ]

        if not ready:
            break  # 理论上不应到达（DAG 无环保证）

        # 并行执行所有就绪节点
        async def execute_subquery(sq):
            # 如果有依赖，把依赖的答案注入查询
            context = " ".join(
                f"[{dep} 的答案：{results[dep]}]"
                for dep in sq["depends_on"]
            )
            full_query = f"{context} {sq['query']}".strip()
            chunks = await retriever.search(full_query, top_k=3)
            return sq["id"], format_chunks(chunks)

        batch_results = await asyncio.gather(
            *[execute_subquery(sq) for sq in ready]
        )

        for qid, result in batch_results:
            results[qid] = result
            completed.add(qid)

    # 3. 综合所有子问题结果，生成最终答案
    all_context = "\n\n".join(
        f"子问题 {qid} 的检索结果：\n{result}"
        for qid, result in results.items()
    )
    return await llm.generate(f"基于以下信息回答问题：\n{all_context}\n\n问题：{query}")
```

**性能对比（以案例三为例）：**

| 方式 | LLM 调用次数 | 总延迟（估算） |
|------|------------|-------------|
| 朴素串行迭代（4轮） | 5次（判断×3 + 生成×1 + 初始×1） | 12~20s |
| 查询分解（无DAG，全并行） | 2次（分解 + 生成） | 3~6s |
| **DAG 执行（识别依赖）** | **2次（分解 + 生成）** | **3~6s** |
| 若有真实串行依赖（案例一） | 4次（分解 + 检索×3 + 生成） | 8~15s |

关键洞察：DAG 分析的价值在于**区分"必须串行"和"可以并行"**，避免把可并行的子问题错误地串行化——这是最常见的性能损失来源。

**2. 基于规则的问题类型路由**

不用 LLM 判断是否需要多跳，而是用规则：

```python
def needs_multi_hop(query: str) -> bool:
    # 包含章节引用、条款编号，大概率需要多跳
    multi_hop_patterns = [
        r"第\d+(\.\d+)*条",  # 第3.2条
        r"第[一二三四五六七八九十]+章",  # 第七章
        r"如果.*那么",  # 条件推理
        r"根据.*计算",  # 计算型
    ]
    return any(re.search(p, query) for p in multi_hop_patterns)
```

---

← [第九章：RAG 的失败模式](ch09-failure-modes.md) | → [第十一章：GraphRAG](ch11-graphrag.md)
