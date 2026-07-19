# 第十一章：知识图谱增强检索（GraphRAG）
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：02-advanced-retrieval.md，第十一章。本章讲解 GraphRAG 的数学基础（图表示、Louvain 社区检测、实体消歧）、Local/Global 查询模式的本质差异、图遍历 vs 向量检索的适用边界，以及知识图谱噪声传播的失效风险。

---

**🔬 研究员**

传统 RAG 把文档切成独立的 chunk，每个 chunk 是孤立的，丢失了文档之间的**关联关系**。

**示例：** 一个合同文档库：
- Chunk A："甲方是深圳某科技公司"
- Chunk B："乙方负责项目的技术实施"
- Chunk C："技术总监负责对乙方进行验收"

如果问"谁负责验收？"，需要推断链：技术总监 → 属于哪方？传统向量检索只能找到最相似的 chunk，无法沿关系链推理。

**GraphRAG（微软 2024）** 的解法：

1. 用 LLM 从文档中**抽取实体和关系**，构建知识图谱
2. 检索时不只找相似 chunk，还沿图谱遍历相关实体

---

### 知识图谱的数学表示

一个知识图谱是有向属性图，形式化定义为：

$$G = (V, E, \phi, \psi)$$

其中：
- $V$：**实体节点集合**。每个节点 $v \in V$ 代表一个真实世界的实体（人、公司、日期、法规条款等）
- $E \subseteq V \times V$：**关系边集合**。有向边 $(u, v) \in E$ 表示 $u$ 和 $v$ 之间存在某种关系
- $\phi: V \to \mathcal{T}_V$：**节点类型函数**，将每个节点映射到类型（PERSON, ORG, DATE, CONCEPT, ...）
- $\psi: E \to \mathcal{T}_E$：**边类型函数**，将每条边映射到关系类型（属于、负责、签署、引用、...）

节点和边都可以携带**属性（attribute）**：

```
节点示例：
  v₁ = {id: "entity_001", name: "深圳某科技公司", type: ORG, industry: "软件", founded: 2015}
  v₂ = {id: "entity_002", name: "技术总监", type: ROLE, level: "高管"}

边示例：
  e = (v₁, v₂, type: HAS_ROLE, since: "2022-01-01", source_chunk: "chunk_045")
```

**图的密度**决定了 GraphRAG 的价值：

$$\text{density} = \frac{|E|}{|V|(|V|-1)}$$

稀疏图（密度 < 0.01）：节点多但连接少，图遍历优势不明显。
稠密图（密度 > 0.1）：节点间关系丰富，图遍历能发现向量检索找不到的路径。

---

### 从文档到图谱：实体与关系抽取

#### 第一步：命名实体识别（NER）

从原始文本识别实体 mention（提及）：

```
原文："张伟总经理于2023年代表深圳某科技有限公司与乙方签署了服务协议"

提取的 mention：
  "张伟总经理" → PERSON（or ROLE+PERSON compound）
  "深圳某科技有限公司" → ORG
  "2023年" → DATE
  "乙方" → ORG（需要文档级消歧）
  "服务协议" → DOCUMENT
```

#### 第二步：关系抽取

识别 mention 之间的语义关系：

```
关系三元组（RDF triple）：
  (张伟总经理, 代表, 深圳某科技有限公司)
  (张伟总经理, 签署, 服务协议)
  (深圳某科技有限公司, 签署方角色, 甲方)
  (服务协议, 签署时间, 2023年)
```

这一步是 GraphRAG 最贵的步骤——每个 chunk 都要调用 LLM 提取三元组。

---

**🔬 研究员**

### 实体消歧：为什么"张总"可能是同一人

从不同 chunk 抽取的 mention 可能指向同一个真实实体。这个问题叫**实体链接（entity linking）**，也叫**指代消解（coreference resolution）**。

**问题示例：**
```
Chunk 1: "张总表示，项目将按时交付"       → mention: "张总"
Chunk 2: "张伟总经理批准了预算变更"        → mention: "张伟总经理"
Chunk 3: "甲方负责人张某签署了补充协议"   → mention: "张某"

问题：三个 mention 是同一个人吗？
```

**消歧的两个维度：**

**1. 字符串相似度（表层证据）**

$$\text{StringSim}(m_1, m_2) = \text{Jaccard}(\text{tokens}(m_1), \text{tokens}(m_2))$$

- "张总" vs "张伟总经理"：共享 token "张"、"总" → Jaccard ≈ 0.5，有一定相似性
- "张总" vs "李总"：共享 "总"，不共享主要字符 → Jaccard ≈ 0.25，相似度低

但字符串相似度只是弱信号，同一公司可能有两个"总监"，不同公司的"张总"是不同人。

**2. 上下文向量相似度（语义证据）**

把每个 mention 连同其周围 ±100 token 的上下文一起 embed，得到上下文向量：

$$\vec{c_i} = \text{Embed}(\text{context}(m_i))$$

$$\text{ContextSim}(m_1, m_2) = \cos(\vec{c_1}, \vec{c_2})$$

如果"张总"和"张伟总经理"的上下文都在讨论同一合同的甲方，两个上下文向量的余弦相似度会很高——因为周围的词汇（合同编号、项目名称、时间范围）会重叠。

**综合打分：**

$$\text{Score}(m_1, m_2) = \lambda_1 \cdot \text{StringSim}(m_1, m_2) + \lambda_2 \cdot \text{ContextSim}(m_1, m_2) + \lambda_3 \cdot \mathbb{1}[\phi(m_1) = \phi(m_2)]$$

- $\lambda_3$ 项：类型一致性约束——PERSON 类型的 mention 只能合并到 PERSON 节点，避免跨类型错误合并
- 实践中 $\lambda_1 \approx 0.3, \lambda_2 \approx 0.5, \lambda_3 \approx 0.2$，通过有标注的消歧数据集调优
- Score > 阈值（通常 0.8）则合并为同一实体节点

**为什么消歧困难：**

否定关系和修饰关系很容易混淆——"不是张总负责的"可能被误抽为"张总 → 负责"，这是 NLP 长期存在的否定识别难题。

---

### 社区检测：Louvain 算法

构建好知识图谱后，GraphRAG 的核心操作是**社区检测**——把高度连接的节点群划分为"社区"，为每个社区生成摘要，用于 Global 查询。

**为什么需要社区检测：**
- 一个知识图谱可能有 10 万个节点，无法为每个节点单独生成摘要
- 关联紧密的节点往往属于同一个主题或事件（同一份合同的所有实体）
- 社区摘要 = 对该主题的高层次概括，可以回答"这组文档讲什么"

**Louvain 算法的优化目标：模块度 Q**

$$Q = \frac{1}{2m} \sum_{i,j} \left[ A_{ij} - \frac{k_i k_j}{2m} \right] \delta(c_i, c_j)$$

其中：
- $A_{ij}$：邻接矩阵（若节点 $i$ 和 $j$ 之间有边则为 1，否则为 0）
- $k_i = \sum_j A_{ij}$：节点 $i$ 的**度**（连接的边数）
- $m = \frac{1}{2}\sum_{ij} A_{ij}$：图中总边数
- $\delta(c_i, c_j)$：若 $i$ 和 $j$ 在同一社区则为 1，否则为 0

**直觉理解 Q：**

$A_{ij}$ 是实际观察到的连接，$\frac{k_i k_j}{2m}$ 是**随机图中期望的连接数**（如果所有节点随机连接）。

- $A_{ij} - \frac{k_i k_j}{2m} > 0$：这对节点的连接比随机情况更紧密 → 说明它们可能属于同一社区
- Q 的范围在 $[-1, 1]$ 之间；实践中好的社区划分 Q > 0.3

**Louvain 算法的两阶段迭代：**

```
阶段一：局部移动（Local Moving）
  1. 每个节点初始化为独立社区
  2. 对每个节点 i，计算将其移入每个邻居 j 所在社区后的 ΔQ：
       ΔQ = Q(移入后) - Q(当前)
  3. 选择 ΔQ 最大的移动，若 ΔQ > 0 则执行
  4. 循环直到没有任何移动能提升 Q

阶段二：图聚合（Aggregation）
  1. 将阶段一产生的每个社区压缩为一个超级节点
  2. 社区之间的边权重 = 原来跨社区的所有边之和
  3. 在新的压缩图上重复阶段一

重复两个阶段，直到 Q 不再提升（通常 3-5 轮）
```

**ΔQ 的计算公式（实用版）：**

将节点 $i$ 移入社区 $C$ 的 ΔQ：

$$\Delta Q = \left[ \frac{\Sigma_{in} + 2k_{i,in}}{2m} - \left(\frac{\Sigma_{tot} + k_i}{2m}\right)^2 \right] - \left[ \frac{\Sigma_{in}}{2m} - \left(\frac{\Sigma_{tot}}{2m}\right)^2 - \left(\frac{k_i}{2m}\right)^2 \right]$$

- $\Sigma_{in}$：社区 $C$ 内部的边数之和
- $\Sigma_{tot}$：社区 $C$ 中所有节点的度之和
- $k_{i,in}$：节点 $i$ 连接到社区 $C$ 内节点的边数
- $k_i$：节点 $i$ 的度

这个公式让你用 O(|邻居|) 的计算量评估一次移动，而不是重新计算整个图。

**社区 → 摘要：**

每个社区检测完后，把该社区的所有实体和关系喂给 LLM，生成一段摘要文本：

```
社区包含：技术总监、深圳某科技公司、服务协议、乙方、2023年
社区摘要："深圳某科技公司（甲方）于2023年与乙方签署服务协议，由技术总监负责验收。"
```

Global 查询时，把所有社区摘要一起送入 LLM，让其做跨文档汇总分析。

---

**❓ 提问者**

你说的社区检测是给 Global 查询用的。那 Local 查询（"某个具体实体的某个属性"）和 Global 查询（"跨文档综合分析"）在实现上有什么本质区别？

---

**🔬 研究员**

### Local 查询 vs Global 查询：本质区别

| 维度 | Local 查询 | Global 查询 |
|------|-----------|------------|
| **示例** | "甲方的注册地址是什么？" | "这批合同中最常见的违约条款类型是什么？" |
| **需要的信息** | 某个实体的属性或一跳关系 | 所有实体/关系的统计分析 |
| **检索范围** | 局部（从某个节点出发遍历） | 全局（需要扫描整个图） |
| **实现方式** | 从实体节点出发，图遍历 1-3 跳 | 对所有社区摘要做 map-reduce |
| **类比** | SQL 的点查（SELECT WHERE id=X） | SQL 的聚合（GROUP BY + COUNT） |

**Local 查询的图遍历流程：**

```
1. 实体识别：从查询中提取目标实体 "甲方"
2. 节点定位：在图中找到 "甲方" 节点（可能是 "深圳某科技公司"）
3. 邻域展开：按关系类型过滤，找到属性 "注册地址" 或关系 "地址→某地"
4. 上下文注入：把该节点及其一跳邻居信息注入 LLM prompt
```

**Global 查询的 Map-Reduce 流程：**

```
Map 阶段：
  对每个社区摘要，单独让 LLM 回答"这个社区中有哪些违约条款类型？"
  → 每个社区得到一个局部答案

Reduce 阶段：
  把所有局部答案合并，让 LLM 做最终汇总
  → "跨所有合同，最常见的违约类型是..."
```

这就是 GraphRAG 贵的原因——Global 查询的 Map 阶段要对每个社区各调用一次 LLM，社区数量可能是几十到几百。

---

**🔧 工程师**

### GraphRAG 的实际代价

**构建阶段（一次性，但昂贵）：**

| 步骤 | 操作 | 成本来源 |
|------|------|---------|
| 实体抽取 | 每个 chunk 调用 LLM | chunk 数量 × LLM token 费用 |
| 关系抽取 | 每个 chunk 调用 LLM | 同上，通常和实体抽取合并一次调用 |
| 实体消歧 | 向量相似度计算 | Embedding 调用，相对便宜 |
| Louvain 社区检测 | 图算法 | CPU 密集，无 LLM 费用 |
| 社区摘要 | 每个社区调用 LLM | 社区数量 × LLM token 费用 |

微软论文（Edge et al. 2024）实测：对 **HotPotQA 数据集**（约 10k 文档），**构建图谱需要约 \$800~\$2500 的 GPT-4 API 费用**（取决于实体和社区密度）。

**查询阶段：**

- Local 查询：比传统 RAG 稍贵（多了图遍历 + 更多 context token）
- Global 查询：远比传统 RAG 贵（Map-Reduce 可能调用 LLM 几十次）

**什么时候值得用 GraphRAG：**

| 场景 | 建议 |
|------|------|
| 文档内有大量实体关系（合同、法规、知识百科） | ✅ 适合 |
| 需要跨文档综合分析（Global 查询） | ✅ 适合 |
| 文档更新频繁 | ❌ 不适合（图谱要重建） |
| 简单问答、文档相对独立 | ❌ 不适合，传统 RAG 更便宜 |
| 预算紧张的原型阶段 | ❌ 先用传统 RAG，验证场景后再考虑 |

### 完整 GraphRAG 本地查询实现

```python
import networkx as nx
from dataclasses import dataclass

@dataclass
class GraphEntity:
    entity_id: str
    name: str
    entity_type: str          # PERSON, ORG, LOCATION, CONCEPT, ...
    attributes: dict
    source_chunks: list[str]  # 来源 chunk IDs（用于溯源）

@dataclass
class GraphRelation:
    source_id: str
    target_id: str
    relation_type: str        # HAS_ROLE, SIGNED, RESPONSIBLE_FOR, ...
    confidence: float         # 抽取置信度
    source_chunk: str

class GraphRAGRetriever:
    def __init__(self, graph: nx.DiGraph, vector_retriever, llm_client):
        self.graph = graph
        self.vector_retriever = vector_retriever
        self.llm = llm_client

    async def local_query(self, query: str, max_hops: int = 2) -> str:
        # 1. 用向量检索找到种子实体（anchor entities）
        anchor_chunks = await self.vector_retriever.search(query, top_k=5)
        seed_entity_ids = self._extract_entity_ids_from_chunks(anchor_chunks)

        # 2. 从种子实体出发，展开 max_hops 跳的邻域
        subgraph_nodes = set(seed_entity_ids)
        frontier = set(seed_entity_ids)

        for _ in range(max_hops):
            next_frontier = set()
            for node_id in frontier:
                if node_id in self.graph:
                    neighbors = (
                        list(self.graph.successors(node_id)) +   # 出边
                        list(self.graph.predecessors(node_id))   # 入边
                    )
                    next_frontier.update(neighbors)
            subgraph_nodes.update(next_frontier)
            frontier = next_frontier

        # 3. 提取子图中的实体和关系
        subgraph = self.graph.subgraph(subgraph_nodes)
        context = self._format_subgraph(subgraph)

        # 4. 注入 LLM
        return await self.llm.complete(
            f"基于以下知识图谱信息，回答用户问题：\n{context}\n\n问题：{query}"
        )

    def _format_subgraph(self, subgraph: nx.DiGraph) -> str:
        lines = ["实体列表："]
        for node_id, attrs in subgraph.nodes(data=True):
            lines.append(f"  - {attrs.get('name', node_id)} [{attrs.get('type', 'UNKNOWN')}]")

        lines.append("\n关系列表：")
        for src, dst, attrs in subgraph.edges(data=True):
            src_name = subgraph.nodes[src].get('name', src)
            dst_name = subgraph.nodes[dst].get('name', dst)
            rel_type = attrs.get('relation_type', 'RELATED_TO')
            lines.append(f"  - {src_name} --[{rel_type}]--> {dst_name}")

        return "\n".join(lines)
```

---

**❓ 提问者**

向量检索不就能找到语义相似的内容吗？为什么还需要图遍历？有没有量化的比较？

---

**🔬 研究员**

### 图遍历 vs 向量检索：适用边界

两者的本质区别是**问题的性质**：

**向量检索擅长：语义相似问题**

$$\text{Vector:} \quad \text{argmax}_{d \in D} \cos(\text{Embed}(q), \text{Embed}(d))$$

找的是"和查询语义最像的文档"。适合：
- "什么是依赖注入？" → 找解释性内容
- "违约金计算方法" → 找包含这个话题的 chunk
- "合同风险条款" → 找语义相关的段落

**图遍历擅长：关系型问题**

```
图遍历路径：
  "张总" ──[WORKS_AT]──→ "深圳某科技公司"
         ──[IS_PARTY]──→ "甲方"
         ──[SIGNED]───→ "合同A"、"合同B"、"合同C"
```

适合：
- "张总签署了哪些合同？" → 遍历 SIGNED 边
- "甲方所有的供应商合作关系" → 遍历 HAS_SUPPLIER 边
- "哪些合同在2023年到期？" → 遍历 DATE 节点

**量化对比（来自 Edge et al. 2024 测试）：**

在 HotPotQA 多跳推理基准上（需要跨两个以上文档串联事实）：

| 方法 | Answer Correctness |
|------|-------------------|
| 标准 RAG（向量） | 45.2% |
| GraphRAG Local | 58.7%（+13.5%） |
| GraphRAG Global | 72.1%（+26.9%，对全局分析型问题） |

**但对单文档直接问答（不需要关系推理），向量检索反而更快、更准，图遍历的额外开销是浪费。**

**判断是否需要图检索的简单规则：**

```
问题包含以下特征之一 → 考虑图检索：
  ✓ 包含角色/关系词："谁负责"、"和谁合作"、"属于哪个部门"
  ✓ 要求枚举关联项："所有...的合同"、"所有参与方"
  ✓ 需要传递性推理："A 的上级的上级是谁"
  ✓ 需要跨文档汇总："最常见的X类型"、"总共有多少"

问题包含以下特征 → 向量检索足够：
  ✓ 解释性问题："什么是..."、"如何理解..."
  ✓ 内容检索："关于X的规定"、"X的计算方法"
  ✓ 相似性问题："和X类似的条款"
```

---

**❓ 提问者**

GraphRAG 用 LLM 抽取实体和关系，但 LLM 本身就会犯错——抽取的知识图谱如果有错误，会不会传播到检索结果中，产生比传统 RAG 更糟糕的幻觉？

---

**🔬 研究员**

### GraphRAG 的失败模式：图噪声传播

这是 GraphRAG 最核心的风险，而且**比传统 RAG 的幻觉更危险**。

**危险性来源：结构性错误 vs 局部错误**

传统 RAG 的幻觉：LLM 在生成阶段错误地综合了几个 chunk 的内容，错误**局限在一次回答**。

GraphRAG 的噪声传播：

```
错误抽取：
  原文："A 不负责 B"
  误抽为三元组：(A, 负责, B)    ← 否定关系识别失败

传播链：
  (A, 负责, B) 入图
  → 图遍历"B 的负责人"时命中 A
  → A 被当作证据注入 LLM prompt
  → LLM 生成"A 负责 B"的错误回答
  → 该回答可能被其他查询引用（如有 Memory 机制）
  → 错误随着查询次数不断放大
```

**错误来源的三个层次：**

1. **实体识别错误**："深圳某公司"被拆成两个实体，后续图遍历时找到的是碎片节点而非完整公司
2. **关系抽取错误**：否定关系（"A 不负责 B"）、修饰关系（"名义上A负责B"）被过度简化
3. **实体消歧错误**：不同公司里的两个"张总"被错误合并为同一人，跨文档信息发生污染

**缓解方案：**

1. **置信度过滤**：抽取时让 LLM 输出置信度，低于阈值（如 0.85）的关系不入图

```python
extraction_prompt = """
从以下文本中抽取实体和关系，以JSON格式输出。
对每条关系，输出 0-1 之间的置信度。
否定关系（"不"、"未"、"无"）请特别标注 negation=true，置信度设为 0。
"""

def filter_relations(relations: list[dict], min_confidence: float = 0.85) -> list[dict]:
    return [
        r for r in relations
        if r["confidence"] >= min_confidence and not r.get("negation", False)
    ]
```

2. **溯源标注（Provenance）**：每条图谱关系记录来源 chunk ID，生成时可回溯验证

```python
# 每条关系携带来源信息
relation = {
    "source": "entity_001",
    "target": "entity_002",
    "type": "RESPONSIBLE_FOR",
    "confidence": 0.92,
    "source_chunk": "chunk_045",   # 关键：来源 chunk
    "source_text": "技术总监负责对乙方进行验收",  # 原文片段
}
```

3. **图谱 → 原始 chunk 的双重验证**：LLM 生成时，把图谱路径和对应的原始 chunk 一起送入 prompt，要求 LLM 在图谱和原文之间发现矛盾时以原文为准

4. **人工审核关键实体**：核心实体（当事方、金额、日期、法律条款编号）人工核实，其他关系可以容忍一定错误率

**GraphRAG 是否值得承担这个风险？**

| 情况 | 建议 |
|------|------|
| 问题大多是"语义相似"型 | ❌ 用传统 RAG，不要引入图噪声 |
| 问题多是关系型/多跳推理 | ✅ GraphRAG 优势明显，且错误可以被溯源机制控制 |
| 文档内容高度可信（法律/合规） | ⚠️ 谨慎使用，建议人工审核核心实体 |
| 快速原型 / 成本敏感 | ❌ 先用 Chunk 级关联（下方轻量方案）验证需求 |

---

**🔧 工程师**

### 轻量替代方案——Chunk 级关联

在不建完整图谱的前提下，仍然能捕捉部分关系信息：

**方案一：同文档 Chunk 邻居扩展**

```python
async def retrieve_with_neighbors(chunk_id: str, repo, window: int = 1) -> list[dict]:
    chunk = await repo.get(chunk_id)
    neighbors = await repo.get_adjacent_chunks(
        document_id=chunk["document_id"],
        chunk_index=chunk["chunk_index"],
        window=window,  # 取前后各 window 个
    )
    # 去重并按位置排序
    all_chunks = [chunk] + neighbors
    return sorted(all_chunks, key=lambda c: c["chunk_index"])
```

**方案二：轻量实体索引（不建完整图谱）**

只抽取关键实体（人名、公司名、合同编号），建倒排索引：

```python
# 构建轻量实体索引
entity_to_chunks: dict[str, list[str]] = {}

for chunk in all_chunks:
    entities = extract_entities_lightweight(chunk["content"])  # 轻量 NER（无 LLM）
    for entity in entities:
        entity_to_chunks.setdefault(entity.normalized_form, []).append(chunk["id"])

# 查询时，找到所有包含目标实体的 chunk
def entity_search(entity_name: str) -> list[str]:
    normalized = normalize_entity(entity_name)
    return entity_to_chunks.get(normalized, [])
```

这个方案成本接近于零（用规则/字典的 NER，而不是 LLM），能解决"找到同一实体出现的所有位置"这类简单的关系查询。

**选择路线的决策树：**

```
问题是否涉及实体间的关系推理？
  否 → 使用标准向量/混合检索
  是 → 是否有预算建图谱 + 社区摘要？
        否 → 使用 Chunk 级邻居 + 轻量实体索引
        是 → 评估文档更新频率
              高频更新 → Chunk 级方案（图谱维护成本太高）
              低频更新 → GraphRAG（值得一次性建图）
```

---

← [第十章：多跳推理](ch10-multi-hop.md) | → [第十二章：RAG vs Fine-tuning](ch12-rag-vs-finetuning.md)
