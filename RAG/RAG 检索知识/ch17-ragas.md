# 第十七章：RAG 评估框架——RAGAS
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：03-production-and-advanced.md，第十七章（第423-596行）。本章讲解 RAGAS 框架的四个核心指标（Context Precision / Recall / Faithfulness / Answer Relevancy）、快速上手代码、无 ground_truth 的 LLM-as-Judge 评估、CI 持续集成评估，以及 Self-Preference Bias 问题与缓解措施。

---

**🔬 研究员**

手写评估脚本（P@K / MRR）只能评估**检索质量**，但 RAG 系统的最终质量是"用户问题有没有被正确回答"——需要端到端评估，涵盖检索 + 生成两个阶段。

**RAGAS** 是目前最主流的 RAG 端到端评估框架。

### RAGAS 的四个核心指标

```
RAG 系统的四个评估维度：

                  检索质量
          ┌───────────────────────┐
          │  Context Precision    │ 检索到的 chunk 有多少是相关的？
          │  Context Recall       │ 相关 chunk 被检索到了多少？
          └───────────────────────┘
                  生成质量
          ┌───────────────────────┐
          │  Faithfulness         │ 答案有多少内容有 context 支撑？
          │  Answer Relevancy     │ 答案和问题的相关程度？
          └───────────────────────┘
```

**1. Context Precision（上下文精确率）**

检索到的 chunk 中，有多少是真正有用的？考虑了**排名**，相关 chunk 排在越前面得分越高：

$$ContextPrecision@K = \frac{\sum_{k=1}^{K} Precision@k \cdot v_k}{\text{相关文档总数}}$$

**2. Context Recall（上下文召回率）**

答案中的每个陈述，都能在检索到的 chunk 中找到支撑吗？

$$ContextRecall = \frac{\text{有 context 支撑的陈述数}}{\text{答案中的总陈述数}}$$

需要 ground truth answer，评估的是"正确答案所需的信息是否被检索到了"。

**3. Faithfulness（忠实度）**

生成的答案中，有多少陈述能在 context 中找到依据？专门衡量**幻觉程度**：

$$Faithfulness = \frac{\text{有 context 支撑的陈述数}}{\text{答案中的总陈述数}}$$

**4. Answer Relevancy（答案相关性）**

实现方式巧妙——不直接比较答案和问题，而是：
1. 让 LLM 基于答案生成 N 个可能的问题
2. 计算生成的问题与原始问题的向量相似度均值

$$AnswerRelevancy = \frac{1}{N} \sum_{i=1}^{N} \text{sim}(q_i^{\text{generated}}, q_{\text{original}})$$

原理：如果答案真的回答了问题，从答案反推出来的问题应该和原始问题很像。

#### Answer Relevancy 的理论基础：不对称语义空间问题

"反向生成问题再比较"不是一个工程 trick，背后有深刻的语义几何动机。

**直接比较为什么不可靠？**

直接计算 $\text{sim}(\text{answer}, \text{question})$ 面临**语义不对称**问题：

- 问题（question）：短、疑问句式、明确提出缺失信息（"违约金上限**是多少**？"）
- 答案（answer）：长、陈述句式、填充信息（"根据第7.3条，违约金**不超过**合同金额的**20%**"）

这两类文本在 Embedding 空间里聚集在不同区域。对比以下情形：

```
原始问题："合同的违约金上限是多少？"

好答案："根据合同第7.3条，违约金不超过合同总金额的20%。"
空洞答案："合同条款中有许多重要规定。"（根本没回答）

直接相似度：
  sim(问题, 好答案)  ≈ 0.65  （共享"合同"、"违约金"等词）
  sim(问题, 空洞答案) ≈ 0.60  （共享"合同"、"条款"等词）
差距：仅 0.05，几乎无法区分
```

**反向生成如何解决这个问题：**

反向生成是一个**语义空间对齐变换** $T$：

$$T: \text{answer} \to \text{question-form paraphrase}$$

好答案 → $T$("根据第7.3条，违约金不超过20%") = **"合同违约金的最高比例是多少？"**
空洞答案 → $T$("合同条款中有许多规定") = **"合同都有哪些条款？"**

现在两者都被变换到"问题分布"，在同一语义区域内比较：

```
反向生成后的相似度：
  sim("合同违约金的最高比例是多少？", "合同的违约金上限是多少？") ≈ 0.91  ✓
  sim("合同都有哪些条款？", "合同的违约金上限是多少？") ≈ 0.42             ✗
差距：0.49，清晰区分好答案和空洞答案
```

**信息论解释：**

一个完美的答案 $A$ 对问题 $Q$ 应该包含重建 $Q$ 所需的全部信息，且不引入无关信息。反向生成度量的是"从 $A$ 能恢复多少 $Q$ 的信息"，这在信息论上类似于**条件互信息** $I(Q; A)$：

$$AnswerRelevancy \approx \mathbb{E}[\text{sim}(T(A), Q)]$$

是对 $I(Q; A)$ 的近似——$A$ 保留了越多关于 $Q$ 的信息，反向生成的问题 $T(A)$ 就越接近原始问题 $Q$。

---

**🔧 工程师**

### RAGAS 快速上手

```python
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
)
from datasets import Dataset

eval_data = {
    "question": [
        "合同的违约金上限是多少？",
        "乙方的交货期是多少天？",
    ],
    "answer": [
        "根据合同第7.3条，违约金不超过合同总金额的20%。",
        "根据第3.2条，乙方应在签约后30日内完成交货。",
    ],
    "contexts": [
        ["第7.3条：违约金累计不超过合同金额的20%...", "第7.1条：..."],
        ["第3.2条：甲方应在签订合同后30日内..."],
    ],
    "ground_truth": [
        "违约金上限为合同总金额的20%。",
        "乙方需在签约后30日内完成交货。",
    ],
}

dataset = Dataset.from_dict(eval_data)
result = evaluate(dataset, metrics=[
    context_precision, context_recall,
    faithfulness, answer_relevancy,
])

print(result)
# {'context_precision': 0.83, 'context_recall': 0.91,
#  'faithfulness': 0.94, 'answer_relevancy': 0.88}
```

### 无 ground_truth 的评估（LLM-as-Judge）

```python
# 不需要 ground_truth，使用不依赖它的指标子集
result = evaluate(
    dataset,
    metrics=[
        faithfulness,       # 不需要 ground_truth
        answer_relevancy,   # 不需要 ground_truth
    ],
)
```

### 持续集成评估

```python
# ci_eval.py —— 在 CI/CD 中自动运行，质量下降时阻断部署
THRESHOLDS = {
    "faithfulness": 0.85,       # 幻觉率不超过 15%
    "answer_relevancy": 0.80,   # 答案相关性不低于 80%
    "context_precision": 0.75,  # 检索精度不低于 75%
}

result = evaluate(dataset, metrics=[...])

failed = []
for metric, threshold in THRESHOLDS.items():
    if result[metric] < threshold:
        failed.append(f"{metric}: {result[metric]:.2f} < {threshold}")

if failed:
    print("❌ RAG 质量低于阈值：")
    for f in failed:
        print(f"  - {f}")
    sys.exit(1)

print("✅ RAG 质量检查通过")
```

---

**❓ 提问者**

RAGAS 用 LLM 评估 LLM 的输出，会不会存在自我偏袒（LLM 对自己的输出打高分）？

---

**🔬 研究员**

**自我偏袒（Self-Preference Bias）** 确实存在：GPT-4 评估 GPT-4 生成的内容时，给分系统性地偏高。

**RAGAS 的缓解措施：**

1. **操作化指标**：把模糊的"质量"转化为可操作的具体问题
   - 不问"这个答案好吗"（主观）
   - 而问"答案中这个陈述能在 context 中找到依据吗"（客观）

2. **分解评估**：把答案拆成多个独立陈述逐一验证，降低整体偏差

3. **使用强评估模型**：建议用比生成模型更强的模型做评估（用 GPT-4 评估 GPT-3.5 的输出）

**实际可靠性（RAGAS 论文）：**

与人工评估的 Pearson 相关系数（Es et al. 2023，RAGAS 原论文）：

| 指标 | r（Pearson） | 解释 |
|------|------------|------|
| Faithfulness | 0.82 | 强相关，自动化可信度高 |
| Context Precision | 0.78 | 强相关 |
| **Answer Relevancy** | **0.71** | **中等相关，差距来源值得分析** |

**为什么 Answer Relevancy 相关性最低（r=0.71）：**

1. **人工判断能识别"听起来相关但不回答问题"的答案**。比如"这是一个复杂的法律问题，涉及多个方面"——人类标注者知道这没回答，但反向生成的问题可能确实和原始问题相似（都在法律领域）。

2. **反向生成本身也有噪声**：LLM 在生成 $T(A)$ 时可能生成笼统的问题，而不是精确对应原始问题的问题。

3. **Faithfulness 相关性高（0.82）的原因**：Faithfulness 的评判更接近"是非题"——陈述在 context 中是否有明确依据，人机标注的分歧较小。

**Pearson r 的实用意义：**

r=0.71 意味着 RAGAS 的 Answer Relevancy 得分解释了人工评分方差的 $r^2 = 50\%$。这说明：
- 如果 RAGAS 分数从 0.7 → 0.9，人工评分大概率也会提升（正相关）
- 但**不能直接用绝对值判断质量**——RAGAS 0.85 不代表人类会给 0.85 分
- 更适合用于**相对比较**：A 系统 vs B 系统的 RAGAS 分数差，通常反映了真实质量差

**实践建议：** RAGAS 作为批量自动化评估是合理的（便宜、快、可持续集成）。但每隔一段时间（如每月）需要抽样 50-100 条让人工标注，与 RAGAS 分数做相关性验证，确保没有发生系统性偏差（如模型更新后 RAGAS 失准）。

---

← [第十六章：ColBERT 与 SPLADE](ch16-colbert-splade.md) | → [第十八章：Agentic RAG](ch18-agentic-rag.md)
