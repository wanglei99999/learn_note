# 第四章：查询改写——让问题更好检索
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：01-retrieval-fundamentals.md，第四章（第897-1136行）。本章讲解 Multi-Query 多路语义扩展、HyDE 假设文档嵌入、意图识别、以及多跳查询（Multi-hop）的原理与实现。

---

> **📌 本章核心**
>
> - 【必须掌握】**Multi-Query 是默认改写策略**：用小模型生成 3~5 个语义变体并行检索，Rerank 时用**原始问题**评分（防止查询漂移），延迟增加 200~400ms 可接受
> - 【必须掌握】**Multi-hop 适用于依赖链问题**：每步结果是下步输入，无法并行；包含条款引用/条件推理的查询才需要；大多数场景 Multi-Query 就够
> - 【理解即可】**HyDE 为何有效**：向量空间中查询区和文档区存在系统性偏移（文档间相似度比查询-文档高 15%+），HyDE 将查询搬进文档分布区，实验提升 +8.9% MRR
> - 【理解即可】**HyDE 三类失效场景**：LLM 生成错误事实、查询本身已是文档风格、简短事实查询——这三种情况分布鸿沟小，HyDE 无收益
> - 【查阅即可】**延迟成本表**：Multi-Query+Haiku +200~400ms，HyDE +500~1000ms；查询改写用小模型，最终生成用强模型

---

**🔬 研究员**

用户的自然语言问题往往不是最优的检索查询。查询改写在不改变意图的前提下，生成更容易命中相关文档的查询形式。

### 【必须掌握】Multi-Query：多路语义扩展

用 LLM 生成 N 个语义等价但表达不同的查询，并行检索后合并：

```
原始查询：   "劳动合同可以提前解除吗"
变体1：     "员工主动辞职的提前通知期规定"
变体2：     "用人单位单方面解除劳动合同的条件"
变体3：     "劳动合同解除的法定情形有哪些"
变体4：     "提前终止劳动关系需要满足什么条件"
```

**Prompt 设计：**

```python
MULTI_QUERY_PROMPT = """
你是一个信息检索专家。给定用户问题，生成 {n} 个语义等价但表达不同的检索查询。

要求：
1. 保持原始意图不变
2. 使用不同词汇和句式
3. 覆盖不同角度（定义、条件、例子、对比等）
4. 每行一个，不加编号

用户问题：{query}
"""
```

### 【必须掌握】HyDE：假设文档嵌入

查询（短、口语）和文档（长、书面）的向量分布差异大，HyDE 先让 LLM 生成假设答案文档，再用这段文字做向量检索：

```
用户问：  "如何处理合同纠纷"（短，口语）
  ↓ LLM
生成：   "合同纠纷的处理方式主要有以下几种：
          首先，当事人可以协商解决...
          其次，可申请仲裁机构调解..."（长，书面）
  ↓ Embedding
向量检索 → 风格与文档库更匹配
```

#### HyDE 为什么有效：查询-文档分布鸿沟理论

"查询和文档向量分布差异大"值得从理论上深入理解——这不只是风格问题，而是向量空间的**几何结构问题**。

**分布鸿沟的本质：**

在训练 Embedding 模型时，正例 pair 是 (查询, 相关文档)：
- 查询：短、关键词密集、口语化（"合同违约怎么办"）
- 文档：长、结构化、书面语（"第五章 违约责任……按照合同金额的10%……"）

虽然训练目标是让它们向量相近，但这两类文本的词汇分布、句式结构、长度分布都不同，导致 Embedding 空间中：

- **查询向量**聚集在某个区域（"口语查询簇"）
- **文档向量**聚集在另一个区域（"书面文档簇"）

两个区域之间存在系统性的**偏移（offset）**。

**量化证据：**

在 MS MARCO 数据集上测量：

| 向量对类型 | 平均余弦相似度 |
|-----------|--------------|
| 查询向量 ↔ 相关文档向量 | 0.65-0.75 |
| 文档向量 ↔ 同主题文档向量 | 0.80-0.90 |

**文档之间的相似度，比查询和文档之间的相似度高 15% 以上。** 这意味着：如果你用一个文档去查找相关文档（文档级查询），精度远高于用短查询去找文档。

**HyDE 的几何解释：**

设查询向量 $\vec{q}$，假设文档向量 $\vec{h}$（HyDE 生成的），正例文档向量 $\vec{d}^+$：

$$d(\vec{h}, \vec{d}^+) < d(\vec{q}, \vec{d}^+)$$

HyDE 将查询从"查询分布区"搬到了"文档分布区"，缩短了到正例文档的距离。

```
向量空间示意（简化为2D）：

  查询区域                  文档区域
  ┌─────────┐              ┌─────────────────┐
  │  q ●    │              │                 │
  │         │              │  d⁺ ●    d⁻ ○  │
  └─────────┘    ←─ 分布鸿沟 ─→     ↑        │
                              h ●（HyDE生成） │
                              └─────────────┘

d(q, d⁺) > d(h, d⁺)：h 比 q 更接近 d⁺
```

Gao et al.（2022，HyDE 原论文）在 MS MARCO 和 TREC-COVID 上验证：
- 标准密集检索：MRR@10 = 0.316（MS MARCO dev）
- HyDE：MRR@10 = 0.344（+8.9%）
- 领域专业文档（生物医学 TREC-COVID）提升更大，因为分布鸿沟更显著

**HyDE 失效的场景：**

1. **LLM 生成了事实错误的假设文档**：向量确实在"文档区"，但指向错误方向——检索到的是"风格匹配但内容不相关"的文档。对知识密集、精确性要求高的查询（如特定法规引用），风险较大。

2. **查询本身已经是文档风格**：技术文档查询（"INSERT INTO 语法"）、精确引用查询（"第37条第二款"），分布鸿沟小，HyDE 增加延迟而无明显收益。

3. **简短事实查询**（"CEO 是谁"）：生成的假设文档内容有限，向量和直接查询向量差异不大。

**实践建议：** 先用 Multi-Query 作为默认改写策略，对长篇报告、学术文献等文档风格和查询风格差距明显的知识库，再加入 HyDE 测试提升效果。

### 意图识别：过滤无关查询

```python
INTENT_PROMPT = """
判断以下用户问题是否与知识库内容相关。

知识库主题：{kb_description}
用户问题：{query}

分类：
- RELEVANT：与知识库主题相关，应该检索
- IRRELEVANT：与知识库主题无关
- CLARIFY：问题太模糊，需要追问

只输出分类标签。
"""
```

---

**🔧 工程师**

### Multi-Query 的并行实现

```python
import asyncio

async def multi_query_retrieve(
    query: str,
    llm: LLMProvider,
    retriever,
    n_variants: int = 3,
) -> list[dict]:
    # 1. 生成变体（一次 LLM 调用）
    variants_text = await llm.generate(
        MULTI_QUERY_PROMPT.format(n=n_variants, query=query)
    )
    variants = [q.strip() for q in variants_text.split("\n") if q.strip()]
    all_queries = [query] + variants[:n_variants]  # 原始查询也参与

    # 2. 并行检索（所有变体同时发出请求）
    tasks = [retriever.search(q) for q in all_queries]
    results_list = await asyncio.gather(*tasks)

    # 3. 去重合并（按 chunk_id 去重）
    seen_ids = set()
    merged = []
    for results in results_list:
        for item in results:
            if item["chunk_id"] not in seen_ids:
                seen_ids.add(item["chunk_id"])
                merged.append(item)

    return merged
```

### 延迟与成本权衡

| 方案 | 额外延迟 | 场景适用性 |
|------|---------|-----------|
| 不改写（当前） | 0ms | 实时要求极高 |
| Multi-Query（用 Haiku/快速模型） | +200~400ms | 多数实时场景可接受 |
| Multi-Query（用 GPT-4） | +800~1500ms | 明显卡顿 |
| HyDE | +500~1000ms | 对延迟敏感的场景慎用 |

**最佳实践：查询改写用小模型，最终生成用强模型**

```python
rewrite_llm = HaikuLLM()   # 快，便宜
generate_llm = GPT4LLM()   # 慢，准
```

**查询改写缓存：**

```python
async def cached_rewrite(query: str, cache: Redis, llm) -> list[str]:
    cache_key = f"qr:{hashlib.md5(query.encode()).hexdigest()}"
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)
    variants = await generate_variants(query, llm)
    await cache.setex(cache_key, 86400, json.dumps(variants))
    return variants
```

---

**❓ 提问者**

LLM 生成的查询变体如果语义偏了，不就引入了噪声？

---

**🔬 研究员**

确实存在"查询漂移"问题。缓解方式：

1. 变体数量不要太多（3~5 个），多了噪声会累积
2. Rerank 阶段用**原始问题**评分，而不是变体——Reranker 拿的是"原始问题 vs chunk"的相关性
3. 保留原始查询参与融合，不完全依赖改写结果

---

**❓ 提问者**

有些问题很复杂，单次检索根本无法回答——比如"A 公司 CEO 的母校在哪个城市"，要先知道 CEO 是谁，再知道他的学校，再知道学校在哪。这种情况 Multi-Query 够用吗？

---

**🔬 研究员**

不够用。你描述的是**多跳查询（Multi-hop Query）**，它的特点是：**答案依赖于多步推理，每一步的结果是下一步的输入**。Multi-Query 只是同义词扩展，并没有解决推理链的问题。

### 【必须掌握】多跳查询（Multi-hop Query）

**问题结构分析：**

```
原始问题："A 公司 CEO 的母校在哪个城市？"
  ↓
子问题1："A 公司的 CEO 是谁？"          → 检索 → 答案：张三
  ↓（用上一步结果补充查询）
子问题2："张三毕业于哪所大学？"          → 检索 → 答案：清华大学
  ↓
子问题3："清华大学在哪个城市？"          → 检索 → 答案：北京
  ↓
最终答案："北京"
```

每一跳依赖前一跳的结果，无法并行，必须**串行推理**。

**实现思路——ReAct（推理 + 行动）模式：**

```python
REACT_PROMPT = """
你是一个信息检索助手。对于复杂问题，先分解再逐步检索。

格式：
思考：分析当前需要什么信息
行动：search("检索查询")
观察：[检索结果]
思考：根据结果分析下一步
行动：search("下一个查询")
...
最终答案：综合所有信息给出答案

问题：{question}
"""
```

**执行流程：**

```python
async def multi_hop_retrieve(question: str, retriever, llm) -> str:
    history = []
    max_hops = 4   # 防止无限循环

    for _ in range(max_hops):
        # LLM 决定下一步：思考 + 生成检索动作
        response = await llm.generate(
            REACT_PROMPT.format(question=question) + "\n".join(history)
        )

        if "最终答案" in response:
            return response.split("最终答案：")[-1].strip()

        # 提取 search("...") 动作
        query = extract_search_query(response)
        results = await retriever.search(query)

        # 把检索结果追加到历史
        history.append(f"行动：search('{query}')")
        history.append(f"观察：{format_results(results)}")

    return "无法在限定步数内得出答案"
```

**Multi-hop 与 Multi-Query 的对比：**

| | Multi-Query | Multi-hop |
|-|------------|-----------|
| 适用场景 | 同一问题的不同表达 | 需要多步推理才能回答的问题 |
| 并行/串行 | 并行（同时发出多个查询） | 串行（每步依赖上一步） |
| LLM 调用次数 | 1 次（生成变体） | N 次（每跳一次） |
| 延迟 | 低 | 高（N 跳 × LLM 延迟） |
| 实现复杂度 | 低 | 高 |

**实践建议：** 大多数 RAG 场景不需要 Multi-hop，先用 Multi-Query 覆盖 80% 的情况。只有当用户明显在问需要串联多个事实的问题时，才值得引入 Multi-hop 的复杂度。

---

← [第三章：混合检索与 RRF](ch03-hybrid-rrf.md) | → [第五章：重排序](ch05-rerank.md)
