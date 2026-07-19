# 第七章：评估——如何知道检索变好了
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：01-retrieval-fundamentals.md，第七章及总结（第1715-1913行）。本章讲解 Precision / Recall / MRR / NDCG 等核心指标、NDCG 完整数值示例、评估集构建方法，以及完整检索链路与优化路线图（总结章节）。

---

> **📌 本章核心**
>
> - 【必须掌握】**指标选择原则**：Recall@K 衡量"找到了没有"，Precision@K 衡量"找到的有没有用"，NDCG@K 同时考虑命中和排名位置——RAG 场景首选 NDCG
> - 【必须掌握】**优化优先级表**：Rerank①→上下文压缩②→QueryRewrite③→构建评估集④（之后才数据驱动）；⑤⑥需重新入库，没有评估数据不要做
> - 【理解即可】**Bootstrap 显著性检验**：10000 次重采样估计 p-value；p<0.05 才说明 A/B 差值是真实提升而非随机噪声；评估集需 200+ 样本，重要决策需 400+
> - 【查阅即可】**评估集构建**：LLM 自动生成（快，有偏）+ 30% 真实用户问题（降低偏差）；最终以线上 A/B 用户满意度为准

---

**🔬 研究员**

没有评估，优化就是盲目的。

### 【必须掌握】核心指标

**Precision@K**：Top-K 结果中相关文档的比例。

$$P@K = \frac{Top\text{-}K\ 中相关文档数量}{K}$$

**Recall@K**：Top-K 结果覆盖了多少相关文档。

$$Recall@K = \frac{Top\text{-}K\ 中相关文档数量}{总相关文档数}$$

**MRR（Mean Reciprocal Rank）**：第一个相关文档出现的位置，越靠前越好。

$$MRR = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{rank_i}$$

**NDCG@K**：考虑相关性分级和排名位置的综合指标，业界最主流。

$$NDCG@K = \frac{DCG@K}{IDCG@K}, \quad DCG@K = \sum_{i=1}^{K} \frac{rel_i}{\log_2(i+1)}$$

排名越靠前的相关文档，贡献越大。

**NDCG 完整数值示例：**

假设查询"违约金计算方法"，有 4 篇候选文档，人工标注相关性（3=高度相关，1=一般，0=不相关）：

```
文档A：违约金条款详解          相关性 = 3（高度相关）
文档B：合同纠纷处理流程        相关性 = 1（一般）
文档C：合同模板下载            相关性 = 0（不相关）
文档D：损失赔偿计算方法        相关性 = 3（高度相关）
```

**场景1：检索系统返回顺序 [A, C, B, D]（把不相关的 C 排在了第2）**

$$DCG@4 = \frac{3}{\log_2(2)} + \frac{0}{\log_2(3)} + \frac{1}{\log_2(4)} + \frac{3}{\log_2(5)}$$
$$= 3 + 0 + 0.5 + 1.292 = 4.792$$

**理想顺序 [A, D, B, C]（相关性从高到低排）对应 IDCG：**

$$IDCG@4 = \frac{3}{\log_2(2)} + \frac{3}{\log_2(3)} + \frac{1}{\log_2(4)} + \frac{0}{\log_2(5)}$$
$$= 3 + 1.893 + 0.5 + 0 = 5.393$$

$$NDCG@4 = \frac{DCG}{IDCG} = \frac{4.792}{5.393} = 0.889$$

**场景2：加入 Rerank 后返回顺序 [A, D, B, C]（接近理想顺序）**

$$DCG@4 = 5.393，\quad NDCG@4 = \frac{5.393}{5.393} = 1.0$$

NDCG 从 0.889 提升到 1.0，说明 Rerank 把最相关的两篇都推到了前面。

**关键理解：** NDCG 同时惩罚"相关文档排名靠后"和"不相关文档排名靠前"两种错误。Precision@K 只看有没有命中，NDCG 还关心命中的位置——这正是 RAG 场景最需要的：第一个 chunk 最相关，LLM 才能优先利用它。

### 构建评估集

```python
eval_dataset = [
    {
        "query": "劳动合同可以提前解除吗",
        "relevant_chunk_ids": ["chunk_123", "chunk_456"],
        "relevance_scores": [3, 2],  # 3=高度相关，2=相关，1=一般
    },
    ...
]
```

**评估集构建方式（成本从低到高）：**

| 方式 | 质量 | 成本 |
|------|------|------|
| LLM 自动生成（读 chunk 生成问题） | 中 | 低 |
| 用户日志挖掘（有点击行为的查询） | 高 | 中 |
| 人工标注 | 最高 | 高 |

---

**🔧 工程师**

### 快速评估脚本

```python
async def evaluate_retrieval(
    eval_dataset: list[dict],
    retriever,
    k: int = 5,
) -> dict:
    metrics = {"precision": [], "recall": [], "mrr": []}

    for item in eval_dataset:
        query = item["query"]
        relevant_ids = set(item["relevant_chunk_ids"])

        results = await retriever.search(query, top_k=k)
        retrieved_ids = [r["chunk_id"] for r in results]

        hits = sum(1 for cid in retrieved_ids if cid in relevant_ids)
        metrics["precision"].append(hits / k)
        metrics["recall"].append(hits / len(relevant_ids))

        mrr = 0
        for rank, cid in enumerate(retrieved_ids):
            if cid in relevant_ids:
                mrr = 1 / (rank + 1)
                break
        metrics["mrr"].append(mrr)

    return {k: sum(v) / len(v) for k, v in metrics.items()}
```

### A/B 评估示例

```
基线：BM25 + 向量，RRF，无 Rerank
  → P@5=0.62, Recall@5=0.58, MRR=0.71

实验组1：加入 QueryRewrite
  → P@5=0.68 (+9.7%), Recall@5=0.71 (+22.4%), MRR=0.75

实验组2：加入 Rerank
  → P@5=0.79 (+27.4%), Recall@5=0.61 (+5.2%), MRR=0.83

两者叠加：
  → P@5=0.82 (+32.3%), Recall@5=0.74 (+27.6%), MRR=0.87
```

Rerank 大幅提升 Precision，QueryRewrite 大幅提升 Recall，两者互补。

---

**🔬 研究员**

### 【理解即可】统计显著性检验：你的 A/B 结果是真实提升还是随机噪声？

上面的 A/B 数据看起来很好——Rerank 让 P@5 从 0.62 提升到 0.79，差了 0.17。但在评估集只有几百个样本时，这个差值可能只是抽样的随机波动，而非真实的系统改进。

**问题的本质：** 如果我们把评估集打乱重新抽样，这个 0.17 的差值还会稳定存在吗？

**Bootstrap 重采样检验（Efron & Tibshirani 1993）：**

Bootstrap 是一种非参数统计方法——不假设数据服从正态分布，直接通过重复采样来估计统计量的分布。

算法步骤：

```
输入：
  - 基线系统 A 在 N 个评估样本上的得分：[a₁, a₂, ..., aₙ]
  - 实验系统 B 在同 N 个样本上的得分：[b₁, b₂, ..., bₙ]
  - 重采样次数 R（通常 10000 次）

步骤：
1. 计算原始差值：Δ = mean(b) - mean(a)

2. For r in range(R):
   a. 有放回地从 N 个样本中随机抽取 N 个（允许重复）
   b. 用抽到的样本计算 Δ_r = mean(b_sample) - mean(a_sample)

3. p-value = #{Δ_r ≤ 0} / R
   （有多少次重采样中，B 并不比 A 更好？）

4. 若 p-value < 0.05，则认为提升在 95% 置信水平上显著
```

**代码实现：**

```python
import numpy as np

def bootstrap_significance_test(
    scores_a: list[float],    # 基线系统在每个评估样本上的得分
    scores_b: list[float],    # 实验系统在每个评估样本上的得分
    n_bootstrap: int = 10000,
    random_seed: int = 42,
) -> dict:
    """
    Bootstrap 重采样检验：B 是否显著优于 A？
    返回 p-value 和置信区间。
    """
    rng = np.random.default_rng(random_seed)
    a = np.array(scores_a)
    b = np.array(scores_b)
    n = len(a)

    observed_delta = b.mean() - a.mean()  # 观察到的原始差值

    # Bootstrap 重采样
    bootstrap_deltas = []
    for _ in range(n_bootstrap):
        indices = rng.integers(0, n, size=n)  # 有放回采样
        delta = b[indices].mean() - a[indices].mean()
        bootstrap_deltas.append(delta)

    bootstrap_deltas = np.array(bootstrap_deltas)

    # p-value：B 不优于 A 的概率
    p_value = (bootstrap_deltas <= 0).mean()

    # 95% 置信区间（差值 Δ 的分布）
    ci_lower = np.percentile(bootstrap_deltas, 2.5)
    ci_upper = np.percentile(bootstrap_deltas, 97.5)

    return {
        "observed_delta": observed_delta,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "ci_95": (ci_lower, ci_upper),
        "n_samples": n,
        "n_bootstrap": n_bootstrap,
    }


# 使用示例
results = bootstrap_significance_test(
    scores_a=baseline_p_at_5_scores,    # 每个评估样本的 P@5（0或1）
    scores_b=reranker_p_at_5_scores,
)

print(f"观察差值: {results['observed_delta']:+.4f}")
print(f"p-value: {results['p_value']:.4f}")
print(f"95% 置信区间: [{results['ci_95'][0]:+.4f}, {results['ci_95'][1]:+.4f}]")
print(f"显著性（p<0.05）: {'✅ 是' if results['significant'] else '❌ 否'}")
```

**A/B 结果的解读：**

```
示例输出：
  观察差值: +0.170         （P@5 从 0.62 → 0.79）
  p-value: 0.0008         （只有 0.08% 的重采样中 B ≤ A）
  95% 置信区间: [+0.11, +0.22]  （差值范围）
  显著性: ✅ 是（p < 0.05）

解读：
  - 置信区间完全在 0 以上，说明提升是真实的，不依赖特定样本
  - p=0.0008 远低于 0.05 → 放心部署实验系统
```

**反例——什么情况下结果不显著：**

```
若评估集只有 50 个样本，且差值只有 +0.03：
  p-value: 0.28   （28% 的概率这只是随机波动）
  95% CI: [-0.02, +0.08]  （置信区间跨越 0）
  显著性: ❌ 否

结论：评估集太小，无法得出可靠结论，需要更多样本或更大的改进才能置信
```

**需要多少评估样本：**

要在 p<0.05 的水平检测到 Δ=0.05 的真实提升（P@5 从 0.75 → 0.80），大约需要：
- N ≈ 400 个评估样本（一般场景）
- 提升越小，需要的样本越多；提升越大，样本越少

实践建议：评估集至少准备 **200 个高质量查询-文档对**，重要决策（如替换 Embedding 模型）前要达到 **400+ 样本**。

---

**❓ 提问者**

用 LLM 自动生成评估集，再用它评估检索效果——这是否存在循环论证？LLM 生成的问题可能天然偏向 LLM 擅长检索的内容。

---

**🔬 研究员**

你说的完全正确。LLM 生成评估集的偏差来源：

1. 倾向于生成"标准化"问题，而真实用户问题往往口语化、模糊、有错别字
2. 对语言规范的 chunk 生成质量好，对表格、代码等生成质量差
3. 用同一 LLM 生成问题再评估，可能高估模型效果

**缓解方案：**

1. **混合评估集**：70% LLM 生成 + 30% 真实用户问题
2. **多样化生成**：让 LLM 生成不同类型的问题（事实型、推理型、比较型）
3. **交叉验证**：用 A 模型生成评估集，用独立方式评估检索
4. **最终以真实用户反馈为准**：线上 A/B 测试的用户满意度是最终标准

---

## 总结：完整检索链路与优化路线图

### 完整链路

```
用户问题
  │
  ├─ [意图识别]      过滤无关查询（可选）
  │
  ├─ [Query Rewrite] LLM 生成 3 个语义变体（并行）
  │
  ├─ [并行召回]
  │    ├── BM25（ES）         → top-30  擅长：专有名词、精确匹配
  │    └── ANN 向量（Milvus） → top-30  擅长：语义理解、同义词
  │
  ├─ [RRF Fusion]    合并去重 → top-50（基于排名，不依赖分数量纲）
  │
  ├─ [Rerank]        Cross-Encoder 精排 → top-5~10
  │
  └─ [LLM 生成]      拼入 Context → 流式输出
```

### 【必须掌握】优化路线图（按性价比排序）

| 优先级 | 优化点                       | Precision 提升 | Recall 提升 | 改动成本 | 何时值得做                                  |
| --- | ------------------------- | ------------ | --------- | ---- | -------------------------------------- |
| ①   | Rerank                    | +20~30%      | —         | 低    | 系统上线后第一件事，几乎总是值得的                      |
| ②   | 上下文压缩                     | —            | —         | 低    | LLM context 超过 2000 tokens，或回答出现"答非所问" |
| ③   | QueryRewrite（Multi-Query） | —            | +15~20%   | 低    | 用户反馈"搜不到"，但文档里确实有答案                    |
| ④   | 构建评估集                     | —            | —         | 中    | 做任何进一步优化之前，先有度量基准                      |
| ⑤   | 分块策略优化（父子 Chunk）          | 综合提升         | 综合提升      | 高    | Rerank 后仍有大量"找到了文档但 LLM 答错"的情况         |
| ⑥   | 替换 Embedding 模型（bge-m3）   | 基础提升         | 基础提升      | 高    | 向量召回率（Recall@20）低于 0.7，专业领域效果差         |
| ⑦   | HyDE                      | —            | +10~15%   | 中    | 开放域知识库，用户问题口语化、短句居多                    |
| ⑧   | 加权 RRF / 融合策略调优           | 场景特化         | 场景特化      | 低    | 已有评估集，且明确知道某一路检索更可信                    |
| ⑨   | Multi-hop Query           | 复杂问题提升       | —         | 高    | 用户问题需要跨多个文档串联推理                        |
| ⑩   | Reranker Fine-tune        | +5~15%       | —         | 极高   | 有 500+ 标注的查询-文档相关性数据，且通用模型效果已到瓶颈       |

**决策原则：**
- 没有评估集之前，优先做①②③（改动小、效果明显、可回滚）
- 评估集建好后，用数据驱动后续所有决策
- ⑤⑥需要重新入库，是不可逆操作，做之前必须有评估数据支撑

---

← [第六章：分块策略](ch06-chunking.md) | → [第八章：Lost in the Middle](ch08-lost-in-middle.md)
