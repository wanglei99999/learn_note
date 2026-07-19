# 第五章：重排序——精度的最后一关
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：01-retrieval-fundamentals.md，第五章（第1138-1511行）。本章讲解为什么 RRF 之后还需要 Rerank、Bi-Encoder vs Cross-Encoder 原理、Cross-Encoder 内部原理、输出分数机制、BGE-Reranker 训练方式、本地部署与云端 API，以及上下文压缩（Context Compression）。

---

> **📌 本章核心**
>
> - 【必须掌握】**两阶段检索范式**：粗排（快，百万→Top-20）→精排（准，Top-20→Top-5）；Rerank 是系统上线后性价比最高的第一个优化点
> - 【必须掌握】**Cross-Encoder 精度更高的根本原因**：query 和 doc 拼接后共享同一 Transformer，每层 attention 双向交互；Bi-Encoder 独立编码无法感知对方，精度有结构性上限
> - 【理解即可】**难负例的梯度优势**：随机负例梯度≈0（模型已能区分），难负例（P=0.3）提供的梯度是随机负例的 **数十倍到数百倍**——同等训练数据，难负例效率远高于随机负例
> - 【查阅即可】**部署方案选择**：本地 BGE-Reranker-large（约 60~100ms/20条，需 1.3GB 显存）；无 GPU 用 DashScope gte-rerank 或 Cohere（注意数据出境合规）

---

**🔬 研究员**

### 【必须掌握】为什么 RRF 之后还需要 Rerank

RRF 解决了"如何合并两路分数"的问题，但没有解决"候选文档是否真正相关"的问题。

RRF 是按**排名**合并，不理解语义——它只知道"这个文档在两个列表里排名都靠前"，不知道"这个文档和用户问题有多相关"。结果是：两路召回的 Top-20 里可能混入一些排名凑巧靠前、但实际不相关的文档。

**一个具体例子：**

用户问："合同违约的赔偿标准是什么？"

RRF 融合后的 Top-5：

```
1. 合同法第114条（违约金条款）         ← 相关 ✅
2. 合同签订注意事项清单                ← 不太相关 ⚠️
3. 赔偿损失的计算方法                  ← 相关 ✅
4. 合同模板下载说明                    ← 无关 ❌
5. 违约金与定金的区别                  ← 相关 ✅
```

Rerank 之后的 Top-3：

```
1. 合同法第114条（违约金条款）         ← 最相关
2. 违约金与定金的区别                  ← 第二相关
3. 赔偿损失的计算方法                  ← 第三相关
```

无关文档被踢出，顺序也更准确，LLM 拿到的上下文质量更高。

### Rerank 在整体流程中的位置

```
向量检索  ──┐
            ├──→ RRF 融合（Top-20）──→ Reranker ──→ Top-5 ──→ LLM
关键词检索 ──┘

        粗排（快，大海捞针）          精排（准，人工复试）
```

**为什么不直接用 Reranker 做召回？**

太慢。Reranker 需要把"问题 + 每篇文档"拼在一起跑一遍模型，100 万文档全部跑一遍不现实。固定套路是：

```
粗排（快）→ 从百万文档召回 Top-20~100
精排（准）→ 从 Top-20 里挑 Top-5
```

两阶段各发挥优势。

---

### 【必须掌握】Bi-Encoder vs Cross-Encoder

召回阶段使用 **Bi-Encoder**：查询和文档分别独立编码，速度快但精度有上限——编码时两段文本互不可见。

Rerank 使用 **Cross-Encoder**：查询和候选文档拼接后整体输入模型，每一层 Transformer 都能捕捉两段文本的交互：

```
Bi-Encoder（召回）：
  query → [Encoder] → q_vec
  doc   → [Encoder] → d_vec
  score = cosine(q_vec, d_vec)

Cross-Encoder（Rerank）：
  [query; doc] → [Encoder] → score
  （查询和文档在每一层都互相 attention）
```

Cross-Encoder 精度更高，但**无法预计算文档向量**——每次查询都要对所有候选对重新计算，所以只能用于小规模候选集（20~100 个）。

### Cross-Encoder 内部如何让 query 和 doc "互相看到对方"

Bi-Encoder 的根本局限在于：query 和 doc 是分开送进模型的，编码完成后只靠一个点积来决定相关性。模型内部的每一层 attention，query 的 token 只能关注 query 自身的其他 token，看不到 doc 里的任何词。

Cross-Encoder 的做法是把两段文本**拼成一个序列**再送进去：

```
输入序列：[CLS] query token₁ token₂ ... [SEP] doc token₁ token₂ ... [SEP]
```

这样在每一层 Transformer 的 Self-Attention 里，query 的每个 token 都可以直接 attend 到 doc 的每个 token，反之亦然：

```
层 1 attention：
  query "违约" → 关注到 doc 里的 "赔偿"、"责任"、"金额" ...
  doc "违约金" → 关注到 query 里的 "标准"、"计算" ...

层 2 attention（基于层 1 的输出继续细化）：
  ...

层 N attention（最终）：
  [CLS] token 汇聚了所有 query-doc 交互信息
```

经过 N 层双向 attention 之后，`[CLS]` 位置的向量已经充分融合了"这个 query 在这个 doc 的语境下"的信息，用它做分类就非常准确。

**为什么 Bi-Encoder 做不到这一点？**

Bi-Encoder 为了速度，必须能对文档**离线预计算**向量——文档入库时就算好存起来，查询时只算一次 query 向量，再做向量比较。这就要求文档向量和 query 向量**独立存在**，无法在编码时感知对方。

这是一个根本性的速度-精度权衡：Bi-Encoder 用独立编码换来了可预计算的速度，Cross-Encoder 用联合编码换来了更高的精度。

### 为什么输出是一个 0~1 的分数，而不是向量

Cross-Encoder 最后接的是一个**二分类头**（Binary Classification Head）：

```
[CLS] 向量（768 维）
    ↓
Linear 层（768 → 2）
    ↓
Softmax（输出两个概率：相关 / 不相关）
    ↓
取"相关"的概率 → 0~1 的分数
```

训练时用的是二分类任务：正样本（query, relevant_doc）标签=1，负样本（query, irrelevant_doc）标签=0。模型学会输出"这对 query-doc 是相关的概率"。

推理时取这个概率值，对所有候选 doc 排序，分数越高越相关。

**注意**：这个 0~1 的分数是**概率估计**，不是像余弦相似度那样的几何度量。不同 Reranker 模型的分数分布差别很大（有的集中在 0.9~1.0，有的均匀分布），所以不能跨模型直接比较绝对分数，只用它做**同一批候选之间的排序**就好。

### 【理解即可】BGE-Reranker 的训练方式

用**成对排序（Pairwise Ranking）**训练：

```
正样本：(query, relevant_doc)   → label=1
负样本：(query, irrelevant_doc) → label=0
```

训练时特意加入**难负例（Hard Negatives）**：用 BM25 或向量检索找到"看起来相关但实际不相关"的文档作为负样本，让模型学会精细区分。

#### 【理解即可】为什么难负例优于随机负例：梯度幅度分析

直觉上，难负例比随机负例"更难区分"，所以更有训练价值。这个直觉可以从梯度分析中严格推导：

**随机负例的问题：**

随机选取的负例通常和查询完全不相关（如"问合同违约"，随机负例是"太阳系的行星"）。模型很轻松地就能区分，对应的预测概率接近 0：

$$P(\text{random\_neg} | q) \approx 0$$

根据 InfoNCE / 交叉熵损失对负例的梯度：

$$\frac{\partial \mathcal{L}}{\partial \text{sim}(q, d^-)} \propto P(d^- | q)$$

当 $P(d^- | q) \approx 0$ 时，梯度几乎为 0——**随机负例对模型权重几乎没有更新贡献**，训练完全是在浪费计算资源。

**难负例的效果：**

难负例（如"合同签订注意事项"）和查询在表面上很相似，但并不是真正的答案。模型对它的预测概率较高：

$$P(\text{hard\_neg} | q) \gg 0 \text{（比如 } P = 0.3\text{）}$$

此时梯度幅度 = $P(\text{hard\_neg} | q) = 0.3$——比随机负例高 30 倍或更多。

**结论：** 难负例给模型提供的学习信号，按梯度幅度算是随机负例的 **数十倍到数百倍**。同样数量的训练数据，用难负例的模型可以学到"在表面相似的文档中区分真正相关和伪相关"的细粒度判断能力——这正是 Reranker 的核心能力。

**难负例的挖掘方法：**

```python
def mine_hard_negatives(
    query: str,
    positive_doc: str,
    retriever,
    top_k: int = 100,
    hard_neg_range: tuple = (2, 20),  # 排名第2到第20的文档
) -> list[str]:
    """
    用当前模型检索，排名靠前但非正例的文档 = 难负例
    避免用第1名（可能是另一个正例）
    """
    results = retriever.search(query, top_k=top_k)

    hard_negatives = []
    for rank, doc in enumerate(results, 1):
        if rank < hard_neg_range[0]:
            continue  # 跳过可能是正例的最高分结果
        if rank > hard_neg_range[1]:
            break
        if doc["content"] != positive_doc:  # 确认不是正例
            hard_negatives.append(doc["content"])

    return hard_negatives
```

挖掘原则：排名第2-20的文档是"模型认为相关，但实际上不是"的理想难负例。排名太低的文档（第50+）可能又退化成"容易的负例"，梯度贡献有限。

---

**🔧 工程师**

### 【查阅即可】BGE-Reranker 本地部署

```python
from FlagEmbedding import FlagReranker

reranker = FlagReranker(
    "BAAI/bge-reranker-large",
    use_fp16=True,  # 半精度，减少显存，精度损失极小
)

def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    pairs = [(query, chunk["content"]) for chunk in chunks]
    scores = reranker.compute_score(pairs, normalize=True)

    ranked = sorted(
        zip(chunks, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    return [
        {**chunk, "rerank_score": score}
        for chunk, score in ranked[:top_k]
    ]
```

**性能参考（RTX 3090）：**

| 模型 | 对数/秒 | 首次加载 | 显存 |
|------|--------|---------|------|
| bge-reranker-base | ~800 | ~3s | 500MB |
| bge-reranker-large | ~300 | ~5s | 1.3GB |
| bge-reranker-v2-m3 | ~200 | ~8s | 2.3GB |

20 个候选 chunk，bge-reranker-large 约 **60~100ms**，在可接受范围内。

**注意：模型首次加载耗时较长，部署时提前 warm up，避免第一个请求超时。**

### Cohere Rerank API（托管方案）

```python
import cohere

co = cohere.Client("your-api-key")
response = co.rerank(
    model="rerank-multilingual-v3.0",  # 支持中文
    query=query,
    documents=[chunk["content"] for chunk in chunks],
    top_n=5,
)
reranked = [chunks[r.index] for r in response.results]
```

适用于不想本地部署的场景，注意数据出境合规问题。

### DashScope gte-rerank（阿里云托管方案）

阿里云 DashScope 提供专用 Rerank 模型 `gte-rerank`，接口风格独立于 Chat API：

```python
import dashscope
from dashscope import TextReRank

def rerank_with_dashscope(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    documents = [chunk["content"] for chunk in chunks]

    resp = TextReRank.call(
        model="gte-rerank",
        query=query,
        documents=documents,
        top_n=top_k,
        return_documents=False,   # 只返回排名和分数，不重复返回文档内容
        api_key="your-dashscope-key",
    )

    results = []
    for item in resp.output.results:
        chunk = chunks[item.index]
        results.append({**chunk, "rerank_score": item.relevance_score})

    return results
```

**与 Chat API 的区别：**

| | Chat API（`qwen-plus` 等） | Rerank API（`gte-rerank`） |
|-|--------------------------|--------------------------|
| 用途 | 对话、生成 | 给文档打相关性分数 |
| 输入 | 消息列表 | query + documents 列表 |
| 输出 | 生成文本 | 每个文档的 relevance_score |
| 价格 | 按 token 计费 | 按请求次数计费，便宜很多 |

**优先选择 `gte-rerank` 而非用 Qwen LLM 做 Rerank 的原因：**

用 LLM 做 Rerank 需要对每个候选文档单独发一次 Chat 请求（让 LLM 打分），20 个文档 = 20 次 LLM 调用，慢且贵。`gte-rerank` 一次请求处理全部文档，专为这个任务训练，效果更好，成本低一个数量级。

---

**❓ 提问者**

Cross-Encoder 输入是 [query; doc]，如果文档很长超过模型 max_length（通常 512），会发生什么？

---

**🔬 研究员**

这会导致**静默截断**——超出部分被丢弃，模型只看到文档前半部分打分，关键信息如果在末尾会被漏掉。

**解决方案：**

1. **控制 chunk 大小**：入库时保证每个 chunk ≤ 400 tokens，为查询留足空间
2. **使用支持长文本的 Reranker**：`bge-reranker-v2-m3` 支持 8192 tokens
3. **滑动窗口 Rerank**：

```python
def rerank_long_doc(query: str, doc: str, max_len: int = 400) -> float:
    if len(doc) <= max_len:
        return reranker.compute_score([(query, doc)])[0]

    # 滑动窗口，取最高分
    windows = [doc[i:i+max_len] for i in range(0, len(doc), max_len//2)]
    scores = reranker.compute_score([(query, w) for w in windows])
    return max(scores)
```

---

### 上下文压缩（Context Compression）

Rerank 解决了"哪些文档更相关"的问题，但没有解决"文档里哪些句子更相关"的问题。

Rerank Top-5，每个 chunk 500 tokens，5 个就是 2500 tokens 送给 LLM。其中大量句子是背景介绍、过渡段落，和用户问题关系不大。上下文压缩在 Rerank 之后，把每个 chunk 里不相关的部分过滤掉，只留真正有用的句子。

**完整链路加入压缩后：**

```
Rerank（Top-5 chunks）
    ↓
上下文压缩（每个 chunk 过滤无关句子）
    ↓
压缩后的精华段落（token 数大幅减少）
    ↓
LLM 生成
```

**实现方式一：LLM 抽取压缩**

用一个小 LLM 对每个 chunk 做句子级过滤：

```python
COMPRESS_PROMPT = """
根据用户问题，从以下文档片段中只保留与问题直接相关的句子，
删除无关的背景信息和过渡性语句。保持原文表达，不要改写。

用户问题：{query}

文档片段：
{chunk}

只输出保留的句子，用换行分隔：
"""

async def compress_chunk(query: str, chunk: str, llm) -> str:
    compressed = await llm.generate(
        COMPRESS_PROMPT.format(query=query, chunk=chunk)
    )
    # 压缩失败时退回原文
    return compressed.strip() if compressed.strip() else chunk
```

**实现方式二：句子相似度过滤（不用 LLM，更快）**

把 chunk 切成句子，只保留与 query 向量相似度超过阈值的句子：

```python
async def compress_by_similarity(
    query: str,
    chunk: str,
    embedder,
    threshold: float = 0.5,
) -> str:
    sentences = split_sentences(chunk)
    if len(sentences) <= 2:
        return chunk   # 太短不压缩

    # 批量计算句子与 query 的相似度
    query_vec = await embedder.embed([query])
    sent_vecs = await embedder.embed(sentences)
    scores = cosine_similarity(query_vec[0], sent_vecs)

    # 只保留相关句子
    kept = [s for s, score in zip(sentences, scores) if score >= threshold]
    return " ".join(kept) if kept else chunk
```

**压缩效果示意：**

```
原始 chunk（480 tokens）：
  "根据《中华人民共和国合同法》的相关规定，合同是平等主体的自然人、
   法人、其他组织之间设立、变更、终止民事权利义务关系的协议。婚姻、
   收养、监护等有关身份关系的协议，适用其他法律的规定。
   【违约金条款】当事人可以约定一方违约时应当根据违约情况向对方支付
   一定数额的违约金，也可以约定因违约产生的损失赔偿额的计算方法。
   违约金低于造成的损失的，当事人可以请求人民法院或者仲裁机构予以
   增加；违约金过分高于造成的损失的，当事人可以请求适当减少。"

压缩后（与问题"违约金标准"相关，约 200 tokens）：
  "当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金，
   也可以约定因违约产生的损失赔偿额的计算方法。违约金低于造成的损失的，
   当事人可以请求增加；违约金过分高于造成的损失的，可以请求适当减少。"
```

token 减少 58%，且保留了所有关键信息。

**何时用哪种方式：**

| 方式 | 延迟 | 成本 | 适用场景 |
|------|------|------|---------|
| 句子相似度过滤 | 低（+50ms） | 极低（只用 Embedding） | 对延迟敏感，chunk 结构清晰 |
| LLM 抽取压缩 | 高（+200~500ms） | 中（额外 LLM 调用） | 对质量要求高，chunk 含大量噪声 |

实践中多数场景用**句子相似度过滤**就够了，效果与 LLM 方式接近，延迟低一个数量级。

---

← [第四章：查询改写](ch04-query-rewrite.md) | → [第六章：分块策略](ch06-chunking.md)
