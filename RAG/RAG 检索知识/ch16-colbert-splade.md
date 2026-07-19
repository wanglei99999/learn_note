# 第十六章：超越 BM25 和 Dense——ColBERT 与 SPLADE
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：03-production-and-advanced.md，第十六章（第238-421行）。本章讲解稀疏 vs 密集检索的本质局限、ColBERT 延迟交互模型（多向量 MaxSim）与三种架构对比、SPLADE 学习稀疏表示，以及各方法的落地成本与选型建议。

---

**🔬 研究员**

前两篇讲了 BM25（稀疏检索）和 Dense Vector（密集向量检索），但这两种方式都有根本局限。学界发展出了两种新范式：

### 回顾：稀疏 vs 密集的本质

```
稀疏向量（BM25）：
  文本 → 词袋表示（大多数维度为 0）
  "合同违约" → [0, 0, ..., 1, 0, ..., 1, 0, ...]
               词汇表维度（数万维），只有出现的词非零
  优点：精确匹配，可解释  缺点：词汇鸿沟

密集向量（Dense）：
  文本 → 低维稠密向量
  "合同违约" → [0.23, -0.41, 0.87, ...]
               768 维，全部非零
  优点：语义理解  缺点：精确词匹配差，黑盒
```

### ColBERT：延迟交互模型

ColBERT（Contextualized Late Interaction over BERT）是**介于 Bi-Encoder 和 Cross-Encoder 之间**的架构。

**核心思想：每个 token 保留一个向量**

```
Bi-Encoder（单向量）：
  "合同违约赔偿" → [0.23, -0.41, ...]  （1个向量，信息损失大）

ColBERT（多向量）：
  "合同" → [0.11, 0.82, ...]
  "违约" → [0.54, -0.23, ...]
  "赔偿" → [-0.31, 0.67, ...]          （3个向量，保留词级语义）
```

**MaxSim 操作（延迟交互）**：

查询的每个 token，与文档的所有 token 向量做相似度，取最大值，再求和：

$$Score(Q, D) = \sum_{i \in Q} \max_{j \in D} \vec{q_i} \cdot \vec{d_j}$$

```
查询 token "违约"：
  与文档 token "违反" 相似度：0.87  ← 最大值
  与文档 token "合同" 相似度：0.34
  与文档 token "赔偿" 相似度：0.41
  → 贡献 0.87

所有查询 token 的最大值求和 = 最终得分
```

**三种架构对比：**

| 特性 | Bi-Encoder | ColBERT | Cross-Encoder |
|------|-----------|---------|--------------|
| 精度 | 中 | 高 | 最高 |
| 速度 | 最快 | 快 | 慢 |
| 文档可预计算 | ✅ | ✅ | ❌ |
| 词级交互 | ❌ | ✅ | ✅ |
| 存储成本 | 低 | 高 | 无需存储 |

ColBERT 可以预计算文档向量（和 Bi-Encoder 一样），但查询时有词级交互（精度比 Bi-Encoder 高），兼顾了速度和精度。

### SPLADE：学习稀疏表示

SPLADE（SParse Lexical AnD Expansion）是**学习到的稀疏向量**方法，弥合了 BM25 和 Dense 的鸿沟：

BM25 的稀疏表示是硬编码的（词出现就有值）。
SPLADE 的稀疏表示是模型学出来的：

```
输入："合同违约"
  ↓ SPLADE 模型
输出（词汇表维度的稀疏向量）：
  "违约":    2.3   ← 原词，高权重
  "违反":    1.8   ← 同义词，模型学到的扩展
  "赔偿":    1.1   ← 相关词，模型学到的扩展
  "协议":    0.9   ← 相关词
  "合同":    2.1   ← 原词
  其他词：   0     ← 稀疏，大多数为 0
```

SPLADE 做到了：
- **可解释**（稀疏，能看到哪些词有权重）
- **语义扩展**（"违约"自动扩展到"违反"、"赔偿"）
- **精确匹配**（词级别的精确性）

---

**🔬 研究员**

### ColBERT 训练：为什么难负例和知识蒸馏不可或缺

ColBERT 的初代训练和 Bi-Encoder 类似——使用 in-batch negatives（批内其他文档作为负例）。但 ColBERTv2（Santhanam et al. 2022）引入了两个关键改进，使精度大幅提升。

#### 在线难负例挖掘（Online Hard Negative Mining）

**为什么普通负例不够好？**

设训练损失为 InfoNCE 形式：

$$\mathcal{L} = -\log \frac{\exp(Score(Q, D^+))}{\exp(Score(Q, D^+)) + \sum_{i} \exp(Score(Q, D_i^-))}$$

梯度分析——负例 $D_i^-$ 对参数更新的贡献正比于：

$$\frac{\partial \mathcal{L}}{\partial \theta} \propto P_{\text{model}}(D_i^- | Q) = \frac{\exp(Score(Q, D_i^-))}{\text{normalization}}$$

**结论：** 模型认为相关性低（score 很小）的负例，$P_\text{model}(D_i^-|Q) \approx 0$，梯度接近 0，对训练几乎没有贡献。只有模型认为"几乎和正例一样好"的负例，才会产生大梯度、推动模型学习区分细微差异。

**硬负例挖掘流程：**

```
1. 用当前模型对所有训练查询做一次推理
2. 对每个查询 q，找到模型排名 2-50 的文档（排第1通常已是正例）
3. 从这些"模型以为相关"的文档中，采样真正的负例（标注为不相关）
4. 把这些"难"负例加入下一轮训练的批次
5. 每 N 步重新采样一次（"在线"的含义：随训练进行动态更新难负例）
```

难负例让模型专注于学习"真正相关 vs 表面相似但不相关"的边界，这是精排模型质量的核心。

#### KL 散度知识蒸馏（ColBERTv2）

ColBERTv2 还从 Cross-Encoder 教师模型中蒸馏知识：

**步骤：**
1. 训练一个高质量的 Cross-Encoder 教师（精度高但推理慢）
2. 对每个查询 $q$ 的候选文档集 $\{D_1, D_2, ..., D_n\}$，教师输出软标签概率分布：

$$P_{\text{teacher}}(D_i | q) = \frac{\exp(s_{\text{teacher}}(q, D_i))}{\sum_j \exp(s_{\text{teacher}}(q, D_j))}$$

3. 训练 ColBERT 最小化其分布和教师分布的 KL 散度：

$$\mathcal{L}_{\text{distill}} = \text{KL}(P_{\text{teacher}} \| P_{\text{student}}) = \sum_i P_{\text{teacher}}(D_i|q) \log \frac{P_{\text{teacher}}(D_i|q)}{P_{\text{student}}(D_i|q)}$$

4. 最终损失 = 判别损失（正例 vs 负例的分类）+ 蒸馏损失：

$$\mathcal{L} = \mathcal{L}_{\text{ranking}} + \lambda \cdot \mathcal{L}_{\text{distill}}$$

**为什么蒸馏有效：** Cross-Encoder 能看到查询和文档的联合上下文，排名质量远高于 Bi-Encoder 类方法。蒸馏把这种精细的相关性判断（不只是 0/1 标签，而是"文档A比文档B稍微更相关"的软判断）传递给 ColBERT，让轻量模型学到重量级模型的判断能力。

---

### PLAID：解决 ColBERT 的存储问题

ColBERT 的存储量是 Bi-Encoder 的 30-50 倍（每个 token 一个向量）。**PLAID**（Practical Late Interaction-based Approximate Document retrieval，Santhanam et al. 2022b）通过两个技术将其压缩到可接受范围：

#### 技术一：质心量化（Centroid Quantization）

对所有文档 token 向量做 K-Means 聚类，得到 $K$ 个质心向量（$K$ 通常为 65536）。每个 token 的向量不再完整存储，只存：
- **质心 ID**：属于哪个质心（16-bit integer），$K=65536$ 时需要 2 字节
- **残差向量**（residual）：该 token 与其质心的差值，进一步量化为 4-bit

```
原始存储：每 token 128维 × 4字节 = 512字节
PLAID 存储：2字节（质心ID）+ 128维×0.5字节（4-bit残差）= 66字节
压缩比：约 7.8×
```

#### 技术二：质心交互（Centroid Interaction）

推理时，不需要对所有 token 做完整的 MaxSim，而是先用质心做近似：

**近似 MaxSim 计算：**

查询 token $q_i$ 和文档 token $d_j$ 的精确相似度：$q_i \cdot d_j$

用质心 $c(j)$ 代替 $d_j$ 的近似版：$q_i \cdot c(j)$（只需和 $K$ 个质心做内积）

**两阶段过滤：**

```
阶段一（快速，粗糙）：
  用质心 ID 计算近似 MaxSim
  筛选出 top-k₁ 候选文档（k₁ 约为最终返回数的 20-30 倍）

阶段二（精确，但只对少量候选）：
  对 top-k₁ 候选，解压残差，计算精确 MaxSim
  返回最终 top-k 结果
```

由于阶段一只和 $K=65536$ 个质心做内积（而非 $|D|$ 个 token），速度提升了 2-10×。PLAID 在 ColBERTv2 基础上实现了：
- 存储量：降至 Bi-Encoder 的 **3-5 倍**（而非原来的 30-50 倍）
- 速度：提升 2-4×
- 精度损失：< 1%（BEIR 基准上）

---

### SPLADE 的 FLOPS 正则化：稀疏度控制的数学

SPLADE 的核心挑战：**不加约束时，模型会学到"大量词都给一点权重"的半稠密表示**，失去了稀疏检索的速度优势。

**SPLADE 的激活函数（先回顾）：**

$$\text{SPLADE}(t, d) = \log(1 + \text{ReLU}(\text{MLM}(d)_t))$$

对文档 $d$ 中每个词汇表词 $t$，输出其权重。ReLU 确保非负，log 压制大值防止某些词权重爆炸。

**问题：** 仅有 ReLU 和 log 不足以保证稀疏——很多词会得到接近 0 但非零的小权重，仍然构成稠密表示。

**解决方案：FLOPS 正则化**

FLOPS（Floating Point OPerations per Second，这里借用术语表示每次检索的计算量）正则项：

$$\mathcal{R}_{\text{FLOPS}} = \lambda_q \sum_{t=1}^{|V|} \mathbb{E}_q[q_t^2] + \lambda_d \sum_{t=1}^{|V|} \mathbb{E}_d[d_t^2]$$

其中：
- $q_t, d_t$：查询/文档在词汇表第 $t$ 个词上的激活值
- $\mathbb{E}[\cdot]$：对训练批次中所有样本取期望
- $\lambda_q, \lambda_d$：控制稀疏程度的超参数（通常 $10^{-4}$ 到 $10^{-3}$）

**完整训练目标：**

$$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{ranking}} + \lambda_q \cdot \mathcal{R}_{\text{FLOPS}}(q) + \lambda_d \cdot \mathcal{R}_{\text{FLOPS}}(d)$$

**为什么叫"FLOPS"：** 稀疏向量的内积操作次数 ∝ 非零元素个数。$\sum_t E[d_t^2]$ 大致正比于内积计算的 FLOPS 期望，所以最小化这个正则项 = 最小化检索的计算量。

**$\lambda$ 的效果（实测）：**

| $\lambda$ | 平均非零词数/文档 | BEIR NDCG@10 | 检索延迟 |
|-----------|-----------------|-------------|---------|
| 0 | ~3000（几乎稠密） | 最高 | 慢 |
| 1e-4 | ~200 | 接近最优 | 适中 |
| **3e-4** | **~100（推荐）** | **好** | **快** |
| 1e-3 | ~30 | 略有损失 | 极快 |

**实践建议：** 用 $\lambda = 3 \times 10^{-4}$ 的 SPLADE 预训练模型（`naver/splade-cocondenser-ensembledistil`），不需要自己训练——直接用这个 checkpoint 已经是最优稀疏/精度平衡的结果。

---

**🔧 工程师**

### ColBERT 实际部署

`ragatouille` 库封装得相当简洁：

```python
from ragatouille import RAGPretrainedModel

RAG = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")

# 建索引（入库时调用）
RAG.index(
    collection=["文档内容1", "文档内容2", ...],
    index_name="arc_knowledge",
    max_document_length=512,
)

# 检索（查询时调用）
results = RAG.search(
    query="合同违约如何处理",
    k=10,
)
# results: [{"content": "...", "score": 0.87, "rank": 1}, ...]
```

**ColBERT 的存储成本：**

```
Bi-Encoder：100万文档 × 768维 × 4字节  = 3GB
ColBERT：   100万文档 × 平均200token
                      × 128维 × 4字节  = 102GB
```

存储成本是 ColBERT 最大的落地障碍，中小规模（< 100万 chunk）可以接受。

### SPLADE 使用

```python
from transformers import AutoModelForMaskedLM, AutoTokenizer
import torch

model_id = "naver/splade-cocondenser-ensembledistil"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForMaskedLM.from_pretrained(model_id)

def encode_splade(text: str) -> dict[str, float]:
    inputs = tokenizer(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        output = model(**inputs).logits
    # ReLU + log + max pooling → 稀疏向量
    vector = torch.log(1 + torch.relu(output)).max(dim=1).values.squeeze()
    indices = vector.nonzero().squeeze()
    return {
        tokenizer.decode([idx]): vector[idx].item()
        for idx in indices.tolist()
    }
# 示例输出：{"违约": 2.3, "违反": 1.8, "赔偿": 1.1, ...}
```

SPLADE 的输出可以直接用于 ES 8.x 的 `sparse_vector` 类型字段。

---

**❓ 提问者**

有了 ColBERT 和 SPLADE，还需要 BM25 + Dense 的混合检索吗？是否可以直接替代？

---

**🔬 研究员**

没有"最好的"单一检索方法，要看场景：

| 方法 | 精确词匹配 | 语义理解 | 存储 | 速度 | 落地成本 |
|------|---------|---------|------|------|---------|
| BM25 | ✅✅ | ❌ | 低 | 最快 | 极低 |
| Dense（BGE） | ❌ | ✅✅ | 中 | 快 | 低 |
| ColBERT | ✅ | ✅✅ | 高 | 中 | 中 |
| SPLADE | ✅✅ | ✅ | 低 | 快 | 中 |
| BM25 + Dense（当前） | ✅✅ | ✅✅ | 中 | 快 | 低 |

**实践建议：**

- **BM25 + Dense 混合**：成熟、低成本、效果已经很好，适合大多数生产场景
- **SPLADE 替换 BM25**：用同样的稀疏检索基础设施，效果优于 BM25，落地成本低，**最有性价比的升级**
- **ColBERT**：精度最高，但存储成本高，适合精度要求极高、数据规模适中的场景
- **三路混合（BM25 + Dense + ColBERT）**：学术效果最好，生产维护成本高

---

← [第十五章：Prompt Engineering](ch15-prompt-engineering.md) | → [第十七章：RAGAS 评估框架](ch17-ragas.md)
