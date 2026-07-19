# 第六章：分块策略——被忽视的基础
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：01-retrieval-fundamentals.md，第六章（第1513-1713行）。本章讲解固定大小 / 语义 / 父子 Chunk 策略、Overlap 的作用，以及增量更新策略（文档级替换与 chunk 级哈希比对）。

---

> **📌 本章核心**
>
> - 【必须掌握】**Chunk 大小按查询类型选**：单问题事实查询用 256~512 tokens（信噪比峰值），多文档综合问题用 512~1024；父子 Chunk 兼顾两种需求
> - 【必须掌握】**Overlap 保证短语覆盖**：O=64 tokens（12.5%，+14% 存储）覆盖大多数专有名词和短句；法律/学术文本建议 O=128（+33% 存储）
> - 【理解即可】**跨主题 Chunk 的信号稀释**：一个 chunk 含 n 个主题时，向量是各主题向量的加权平均，对任何单一查询的相似度都下降——这是语义切块的理论依据
> - 【理解即可】**语义切块算法**：计算相邻句子 Embedding 相似度，在相似度低谷（断点）处切割；代价是入库速度慢 3~5 倍，但检索质量持久提升
> - 【查阅即可】**增量更新策略**：文档级替换（简单，先写新后删旧）适合大多数场景；chunk 级哈希比对适合频繁局部小修改

---

**🔬 研究员**

检索质量的天花板由**分块（Chunking）策略**决定。再好的检索算法，如果 chunk 边界切在句子中间，关键信息被劈开，也无法召回。

### 【必须掌握】分块的核心矛盾

| | Chunk 太大 | Chunk 太小 |
|--|-----------|-----------|
| 问题 | 超过 Embedding 模型限制被截断；向量是整段平均语义，精确信息被稀释 | 缺少上下文，无法理解语义；chunk 数量爆炸 |

### 主流分块策略

**1. 固定大小切块（Token Chunking）**

最简单，按 token 数切，加重叠避免信息断层。我们目前用的就是这种。

```
chunk 1: [0, 512]
chunk 2: [256, 768]   ← 前 256 token 与 chunk 1 重叠
chunk 3: [512, 1024]
```

**2. 语义切块（Semantic Chunking）**

计算相邻句子的向量相似度，在语义突变处切割。适合长文档，但需要额外的 Embedding 计算，入库慢。

语义切块的算法原理见下方"语义切块理论"一节。

**3. 父子 Chunk（Parent-Child Chunking）**

入库时同时存储两个粒度：
- **子 chunk（小，128 tokens）**：用于向量检索，细粒度定位
- **父 chunk（大，512 tokens）**：用于 LLM 生成，完整上下文

检索时用子 chunk 找位置，返回时扩展为父 chunk。

**4. 文档结构感知切块**

利用文档层次结构（标题、段落、列表）作为自然切割点：

```
# 第三章 违约责任        ← 标题，可作为 chunk 边界
## 3.1 违约金计算        ← 二级标题
一方违约时，应按合同金额... ← 正文 chunk
```

---

**🔧 工程师**

### 为什么 overlap 很重要

没有 overlap 的切块：

```
chunk 1: "...本合同有效期为三年，自签订之日起"
chunk 2: "计算，任何一方均不得提前解除合同..."
```

"自签订之日起计算"被切断，两个 chunk 都不完整。

加了 overlap（重叠 64 tokens）后，两个 chunk 都包含完整语义，检索时有冗余保障。

**我们代码中的参数建议：**

```python
CHUNK_SIZE = 512    # tokens
OVERLAP = 64        # tokens，约 12.5% 重叠率
```

重叠率建议 10~20%，太高会导致 chunk 数量暴增。Overlap 大小的数学分析见下方"Overlap 比例分析"一节。

### 表格和代码块的特殊处理

普通文本切块会破坏表格结构，建议对表格和代码块整体保留：

```python
def smart_chunk(text: str) -> list[str]:
    # 检测表格块（Markdown 格式）
    table_pattern = r'\|.+\|[\s\S]+?\n\n'
    tables = re.findall(table_pattern, text)

    for table in tables:
        if len(table) <= MAX_CHUNK_SIZE:
            yield table
            text = text.replace(table, "")

    yield from token_chunk(text)
```

---

**❓ 提问者**

父子 chunk 策略中，多个不同位置的小 chunk 都命中了，对应的大 chunk 可能是同一个，会不会导致 LLM context 里有大量重复内容？

---

**🔬 研究员**

是的，标准解法是**按父 chunk ID 去重**：

```python
def expand_to_parent_chunks(
    child_chunks: list[dict],
    parent_repo,
) -> list[dict]:
    seen_parent_ids = set()
    parent_chunks = []

    for child in child_chunks:
        parent_id = child["parent_chunk_id"]
        if parent_id not in seen_parent_ids:
            parent = parent_repo.get(parent_id)
            parent_chunks.append(parent)
            seen_parent_ids.add(parent_id)

    return parent_chunks
```

多个子 chunk 命中同一父 chunk，反而是**强相关信号**——说明这个父 chunk 与查询高度相关，排序时可以提权。

---

**🔬 研究员**

### 【理解即可】语义切块理论：为什么在语义边界切比在 token 边界切效果更好

固定 token 切块的根本问题：**完全忽视文本的语义结构**，像一把尺子无视内容地均匀切割。

**Embedding 模型的信息压缩瓶颈：**

Embedding 模型将一段文本压缩为固定维度的向量（通常 768 或 1536 维）。这个过程从信息论角度看是有损压缩——如果一个 chunk 横跨两个主题 A 和 B，那么：

$$\vec{v}_{\text{chunk}} \approx \alpha \vec{v}_A + (1-\alpha) \vec{v}_B$$

生成的向量是两个主题向量的加权平均，查询主题 A 时，相似度：

$$\cos(q_A, \vec{v}_{\text{chunk}}) < \cos(q_A, \vec{v}_A)$$

即：跨主题的 chunk 比单主题 chunk 对任何主题的查询都**有更低的相似度**，导致召回率下降。

**语义切块的算法原理：**

```
输入：文档 D = [s₁, s₂, s₃, ..., sₙ]（按句子分割）

1. 为每个位置 i 计算"局部语义"：
   context(i) = [s_{i-w}, ..., s_i, ..., s_{i+w}]
   ctx_vec(i) = Embed(context(i))

   （使用滑动窗口 w=1 或 w=2 提供上下文，避免单句 embedding 噪声太大）

2. 计算相邻位置的语义相似度：
   sim(i, i+1) = cos(ctx_vec(i), ctx_vec(i+1))

3. 识别语义断点（breakpoints）——选择相似度最低的位置：
   方法A（固定阈值）：sim < θ（如 0.75）的位置为断点
   方法B（百分位数）：相似度最低的 p% 位置为断点（p ≈ 10）
   方法C（梯度法）：sim(i) - sim(i+1) 最大的位置为断点（捕捉最陡的跌落）

4. 在断点处切割，合并断点之间的句子为一个 chunk
```

**数值示例（合同文档）：**

```
句子1："合同有效期为三年，自签订之日起计算"
句子2："违约金按合同金额的10%计算"
句子3："双方如发生争议，应先协商解决"
句子4："协商不成，提交深圳仲裁委员会仲裁"

相邻相似度：
  sim(s1, s2) = 0.72  ← 从"期限"跳到"违约"，语义有跳变
  sim(s2, s3) = 0.68  ← 从"违约金"跳到"争议解决"，最低点
  sim(s3, s4) = 0.91  ← 同一主题（争议解决流程）

断点识别（阈值=0.75）：
  位置(s1,s2) 和 位置(s2,s3) 都低于阈值 → 切割

结果：
  Chunk 1: [s1]           → 主题：合同期限
  Chunk 2: [s2]           → 主题：违约责任
  Chunk 3: [s3, s4]       → 主题：争议解决（两句高度相关，合为一块）
```

**语义切块的代价：**

每个句子需要一次 Embedding 调用，入库速度比 token 切块慢 3-5 倍。但这是**一次性成本**，检索质量的提升是持久的。对检索精度要求高且文档更新不频繁的场景，语义切块是最优选择。

---

### Chunk 大小的信息论分析：512 token 从哪来

512 token 不是拍脑袋的，有两层理由：

**理由一：Embedding 模型的训练上下文限制**

主流 Embedding 模型的最大输入长度：
- BGE 系列（`bge-large-zh`）：512 tokens
- OpenAI `text-embedding-3-small/large`：8191 tokens（但精度在长文本上下降）
- GTE（`gte-Qwen2-7B-instruct`）：32768 tokens

对于 512 token 限制的模型，超过限制的 chunk 会被截断，截断部分的语义信息完全丢失。

**理由二：精确率与完整性的信息论权衡**

设查询词对应的关键信息占 $p$ 比例，chunk 的平均信息密度为均匀分布。检索相关信号的信噪比（SNR）为：

$$\text{SNR}(C) = \frac{p}{\text{noise}} \propto \frac{p \cdot C}{C} = p$$

等等，这个简化分析说明 SNR 与 chunk 大小无关——但实际上噪声不是线性的。当 chunk 包含 $n$ 个独立话题时，Embedding 向量是 $n$ 个话题向量的平均，对目标查询的相似度约为 $1/n$ 倍单话题 chunk 的相似度。

所以真正的 SNR：

$$\text{SNR}(C) \propto \frac{1}{\text{avg topics in chunk of size C}}$$

chunk 越大，包含的话题数量越多，检索信噪比越低。Barnett et al.（2024）在多个 QA 基准上的实测结果：

| Chunk 大小（tokens） | Recall@5（单问题 QA） | 多文档综合 QA |
|---------------------|---------------------|--------------|
| 128 | 72% | 45% |
| 256 | 79% | 52% |
| **512** | **82%** | **59%** |
| 1024 | 80% | 62% |
| 2048 | 75% | 65% |

单问题 QA 在 512 达到峰值（大了信号稀释），多文档综合需要更大上下文（需要完整的事实）。这说明 **chunk 大小应该根据你的查询类型选择**，而不是固定用 512。

**实践建议：**

```
简单事实问答（"合同期限是多少年"）
  → 128-256 tokens，精确匹配最重要

分析理解型问题（"违约处理流程是什么"）
  → 512-1024 tokens，需要完整的段落上下文

跨章节综合问题（"整个合同的风险条款有哪些"）
  → 父子 Chunk：子 chunk 256 token 检索，父 chunk 1024 token 生成
```

---

### Overlap 比例的数学分析

Overlap 的目的是保证任何长度为 $L \leq O$ 的文本片段都完整出现在至少一个 chunk 中。

**覆盖保证（Coverage Guarantee）：**

设 chunk 大小为 $C$，overlap 为 $O$。对于长度为 $L$ 的关键短语：
- 若 $L \leq O$：该短语一定完整出现在某个 chunk 中（因为相邻 chunk 有 $O$ tokens 的重叠区域）
- 若 $O < L \leq C$：该短语可能出现在 chunk 边界处，被截断

所以 $O$ 应该 ≥ 你预期的最长关键短语。

**实际关键短语长度分布（中文文本）：**
- 专有名词/实体：5-20 字（≈ 10-40 tokens）
- 关键句（含主谓宾）：15-40 字（≈ 30-80 tokens）
- 复合条件（"在...情况下，...应当..."）：30-80 字（≈ 60-160 tokens）

所以 O=64 tokens 覆盖了大多数专有名词和短句，O=128 tokens 覆盖了大多数复合条件。

**存储开销分析：**

chunk 总数（不重叠时）：$N_0 = \lceil \text{DocLen} / C \rceil$

加 overlap 后的 chunk 总数：$N_O = \lceil (\text{DocLen} - O) / (C - O) \rceil$

存储开销比（≈存储成本倍数）：

$$\text{Overhead} = \frac{N_O}{N_0} \approx \frac{C}{C - O}$$

| C=512, O | 重叠率 | 存储开销 |
|----------|--------|---------|
| O=0 | 0% | 1.00× |
| **O=64** | **12.5%** | **1.14×** |
| O=128 | 25% | 1.33× |
| O=256 | 50% | 2.00× |

O=64（12.5% 重叠）：只增加 14% 存储，覆盖大多数短语 → **推荐默认值**
O=128（25% 重叠）：增加 33% 存储，覆盖复合长句 → 适合法律/合同文本
O=256（50% 重叠）：存储翻倍，基本没有新增覆盖收益 → 通常不必要

**何时加大 Overlap：**
- 文档以长句子为主（学术论文、法律条文）→ O=128
- 关键信息跨句（如"上述条款"引用前面内容）→ O=128-200
- 文档很短（< 1000 tokens）→ 直接用一个 chunk，不必切割

---

**❓ 提问者**

文档入库之后如果原文更新了怎么办？全部重新切块、重新 Embedding 成本太高，有没有更聪明的方式？

---

**🔬 研究员**

### 【必须掌握】增量更新策略

文档更新是生产系统的高频需求。全量重建代价高，但增量更新需要解决两个核心问题：**怎么判断哪些 chunk 变了**，以及**变了的 chunk 如何替换而不影响检索**。

**方案一：文档级替换（最简单，适合大多数场景）**

把文档视为原子单位，更新时整个文档的所有 chunk 一起替换：

```python
async def update_document(document_id: str, new_content: str) -> None:
    # 1. 标记旧 chunks 为 STALE（不立即删除，避免检索空窗）
    await chunk_repo.mark_stale(document_id)

    # 2. 重新切块 + Embedding + 写入新 chunks（状态 CURRENT）
    new_chunks = chunker.chunk(new_content)
    embeddings = await embedder.embed(new_chunks)
    await chunk_repo.save_chunks(document_id, new_chunks, embeddings)

    # 3. 删除旧的 STALE chunks（新 chunks 已就绪后再删）
    await chunk_repo.delete_stale(document_id)
    await milvus.delete_by_document(document_id + "_stale")
    await es.delete_by_document(document_id + "_stale")
```

关键点：先写新数据再删旧数据，保证检索不出现空窗期。我们系统的 `embedding_status` 字段（`pending / current / stale`）正是为这个设计的。

**方案二：chunk 级哈希比对（精细，适合文档频繁小修改）**

对每个 chunk 计算内容哈希，更新时只处理哈希变化的 chunk：

```python
async def incremental_update(document_id: str, new_content: str) -> dict:
    # 切块并计算哈希
    new_chunks = chunker.chunk(new_content)
    new_hashes = {chunk["index"]: md5(chunk["content"]) for chunk in new_chunks}

    # 读取旧的哈希
    old_chunks = await chunk_repo.get_chunks_by_document(document_id)
    old_hashes = {chunk["index"]: chunk["content_hash"] for chunk in old_chunks}

    # 比对差异
    to_add    = [c for c in new_chunks if new_hashes[c["index"]] != old_hashes.get(c["index"])]
    to_delete = [c for c in old_chunks if c["index"] not in new_hashes]

    # 只处理变化的部分
    if to_add:
        embeddings = await embedder.embed([c["content"] for c in to_add])
        await chunk_repo.save_chunks(document_id, to_add, embeddings)

    if to_delete:
        await chunk_repo.delete_chunks([c["chunk_id"] for c in to_delete])

    return {"added": len(to_add), "deleted": len(to_delete), "unchanged": len(new_chunks) - len(to_add)}
```

**两种方案的对比：**

| | 文档级替换 | chunk 级哈希比对 |
|-|-----------|----------------|
| 实现复杂度 | 低 | 高 |
| Embedding 调用次数 | 全量（所有 chunk） | 只有变化的 chunk |
| 适用场景 | 文档整体改动 / 格式调整 | 文档局部小修改（如纠错、追加段落） |
| 风险 | 短暂的 STALE 状态 | chunk 边界变化时哈希全变，退化为全量 |

**实践建议：** 先用文档级替换，简单可靠。当某类文档更新非常频繁（如实时更新的知识条目），再引入 chunk 级哈希比对降低 Embedding 成本。

---

← [第五章：重排序](ch05-rerank.md) | → [第七章：评估](ch07-evaluation.md)
