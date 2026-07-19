# 第十四章：元数据过滤——让检索更精准
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：02-advanced-retrieval.md，第十四章及知识体系全景（第1107-1477行）。本章讲解元数据与向量的分工、前过滤 vs 后过滤 vs 混合策略、元数据字段设计、Milvus 和 ES 过滤语法、从自然语言提取过滤条件，以及时间语义歧义的处理策略。附录：知识体系全景（第二篇）。

---

**🔬 研究员**

向量检索回答的问题是："这段文本和查询**在语义上有多像**？"

但很多用户查询里的约束条件，向量根本无法理解：

```
"最近一个月签署的合同"
         ↑
   向量不知道"最近一个月"是什么时间范围，不知道今天是哪天

"只看 PDF 格式的文件"
         ↑
   向量不编码文件格式，除非文档内容里刚好提到了"PDF"

"项目 Alpha 相关的技术文档"
         ↑
   "项目 Alpha"是一个专有标签，它和文档的语义相似度无关

"不包含已归档的文档"
         ↑
   向量无法表达"不是什么"的否定约束
```

这些约束需要用**元数据（Metadata）** 来处理——附加在文档或 chunk 上的结构化属性字段，专门用于回答"这个 chunk 是什么类型、什么时间、属于哪个项目"这类结构性问题。

### 元数据和向量的分工

把一次检索请求拆成两个层次的约束：

```
用户查询："最近三个月签署的、关于违约赔偿的中文合同"
           ├── 结构化约束（元数据层）
           │    created_at >= 2024-01-23
           │    document_type == "contract"
           │    language == "zh"
           │
           └── 语义约束（向量层）
                maximize similarity("违约赔偿", chunk_embedding)

正确做法：先用元数据缩小候选集，再在候选集内做语义排序
```

向量检索擅长"找最像的"，元数据过滤擅长"排除不符合条件的"。两者不是竞争关系，而是互补关系。

### 前过滤 vs 后过滤 vs 混合——核心架构决策

**前过滤（Pre-filtering）：先过滤，再搜索**

```
全量 chunk（100 万条）
    ↓ 元数据过滤
    满足条件的子集（1,000 条）
    ↓ 向量 ANN 检索
    Top-20 结果
```

优点：向量检索在小规模集合上进行，速度快。
缺点：**子集太小时，ANN 退化为暴力扫描，速度反而变慢**；极端情况下子集为零，返回空结果。

**后过滤（Post-filtering）：先搜索，再过滤**

```
全量 chunk（100 万条）
    ↓ 向量 ANN 检索
    Top-200 候选（不考虑元数据）
    ↓ 元数据过滤
    最终结果（可能只剩 5 条）
```

优点：向量检索在全量数据上进行，语义质量最高。
缺点：**过滤可能使结果数量严重不足**——如果 Top-200 里只有 3 条满足元数据条件，最终只返回 3 个结果，可能不够用。

**混合策略（推荐）：前过滤 + 补偿系数**

```python
async def filtered_vector_search(
    query_vector: list[float],
    metadata_filter: dict,
    top_k: int = 20,
    compensation_factor: float = 3.0,
) -> list[dict]:
    """
    在过滤后的子集中，请求 top_k × compensation_factor 个候选，
    保证后续过滤后仍有足够的结果，最后截断到 top_k。
    """
    results = milvus_client.search(
        collection_name=COLLECTION_NAME,
        data=[query_vector],
        filter=build_milvus_filter(metadata_filter),
        limit=int(top_k * compensation_factor),
        output_fields=["chunk_id", "space_id", "content", "metadata"],
    )
    return results[0][:top_k]
```

补偿系数（compensation_factor）的选择：

| 过滤条件的选择性 | 推荐补偿系数 |
|----------------|------------|
| 宽泛（如 language == "zh"，大多数文档满足） | 1.5 |
| 中等（如 document_type == "contract"） | 2~3 |
| 严格（如 date_range 很窄 + 多个条件组合） | 3~5 |

---

**🔧 工程师**

### 元数据字段设计

在 chunk 入库时就应完整记录元数据，后期补充代价极高：

```python
@dataclass
class ChunkMetadata:
    # 系统字段（自动生成，不可修改）
    space_id: str           # 租户隔离
    document_id: str        # 所属文档
    chunk_index: int        # chunk 在文档中的位置
    ingested_at: float      # 入库时间戳（Unix）

    # 文档级字段（从原始文档属性继承）
    document_type: str      # "contract" / "policy" / "report" / "faq" / "manual"
    source_format: str      # "pdf" / "docx" / "markdown" / "txt" / "html"
    language: str           # "zh" / "en" / "mixed"
    created_at: float       # 文档创建时间（Unix）
    updated_at: float       # 文档最后修改时间（Unix）
    original_name: str      # 文件名（方便展示引用来源）

    # 用户自定义字段（由用户上传时填写）
    tags: list[str]         # 任意标签，如 ["project-alpha", "q4-review"]
    category: str           # 用户定义的分类

    # 质量字段（入库时自动计算）
    word_count: int         # chunk 字数
    quality_score: float    # 0~1，内容质量估计（可用困惑度或关键词密度）
```

### Milvus 过滤语法

Milvus 支持丰富的过滤表达式，直接在向量搜索时传入：

```python
# 简单等值
filter_expr = 'document_type == "contract"'

# 时间范围（传 Unix 时间戳）
filter_expr = 'created_at >= 1706000000 AND created_at <= 1714000000'

# 多条件 OR 组合
filter_expr = '(document_type == "contract" OR document_type == "amendment")'

# AND 组合多个条件
filter_expr = (
    'document_type == "contract" '
    'AND language == "zh" '
    'AND quality_score >= 0.6'
)

# 数组字段（tags）包含某元素
filter_expr = 'ARRAY_CONTAINS(tags, "project-alpha")'

# 字数范围（过滤过短/过长的 chunk）
filter_expr = 'word_count >= 50 AND word_count <= 1500'
```

### ES 过滤语法

ES 的 `bool` 查询把全文检索（`must`）和元数据过滤（`filter`）清晰分离：

```python
def build_es_filtered_query(query: str, metadata_filter: dict) -> dict:
    """
    must：全文检索，参与相关性评分（BM25）
    filter：元数据过滤，不参与评分，ES 会缓存 filter 结果，速度快
    """
    filters = [
        {"term": {"space_id": metadata_filter["space_id"]}}  # 租户隔离必须有
    ]

    if "document_type" in metadata_filter:
        filters.append({"term": {"document_type": metadata_filter["document_type"]}})

    if "language" in metadata_filter:
        filters.append({"term": {"language": metadata_filter["language"]}})

    if "date_range" in metadata_filter:
        filters.append({
            "range": {
                "created_at": {
                    "gte": metadata_filter["date_range"]["start"],
                    "lte": metadata_filter["date_range"]["end"],
                }
            }
        })

    if "tags" in metadata_filter:
        # 文档必须包含 tags 列表中的至少一个标签
        filters.append({"terms": {"tags": metadata_filter["tags"]}})

    return {
        "query": {
            "bool": {
                "must": [{"match": {"content": query}}],
                "filter": filters,
            }
        }
    }
```

### 从自然语言提取过滤条件

进阶能力：用户不需要手动设置过滤器，系统自动从查询中提取。

```python
FILTER_EXTRACTION_PROMPT = """从用户查询中提取结构化过滤条件。
今天的日期：{today}

时间词默认解释（上下文无明确时间时使用）：
  "最近" / "近期"  → 最近 30 天
  "近几个月"       → 最近 90 天
  "今年"           → 当前自然年
  "上个月"         → 上一个自然月
  "最近一周"       → 最近 7 天
  有明确数字则用明确数字（如"最近三个月" → 90 天）

可提取字段：
  document_type: "contract"（合同）/ "policy"（政策）/ "report"（报告）/ "faq"（问答）
  language: "zh" / "en"
  date_range: {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}
  tags: 字符串列表

用户查询：{query}

只输出 JSON，无法提取的字段省略，例如：
{{"document_type": "contract", "language": "zh", "date_range": {{"start": "2024-01-23", "end": "2024-04-23"}}}}
"""

async def extract_metadata_filter(query: str, llm: LLMProvider) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    result = await llm.generate_json(
        prompt=FILTER_EXTRACTION_PROMPT.format(today=today, query=query),
        temperature=0,
    )
    return result or {}
```

### 完整带过滤的检索流程

```python
async def filtered_rag(
    query: str,
    space_id: str,
    explicit_filters: dict | None = None,   # 用户在 UI 手动选择的过滤条件
) -> list[dict]:
    # ① 从查询中提取隐式过滤条件
    implicit_filters = await extract_metadata_filter(query, llm)

    # ② 合并：显式（UI 选择）覆盖隐式（自动提取）；space_id 强制注入
    filters = {
        **implicit_filters,
        **(explicit_filters or {}),
        "space_id": space_id,   # 租户隔离永远不能被覆盖
    }

    # ③ 向量检索（带过滤）
    query_vec = await embed(query)
    vector_results = await filtered_vector_search(query_vec, filters, top_k=20)

    # ④ BM25 检索（带过滤）
    bm25_results = await filtered_bm25_search(query, filters, top_k=20)

    # ⑤ RRF 融合 + Rerank
    merged = rrf_merge(vector_results, bm25_results)
    return await rerank(query, merged, top_k=5)
```

---

**❓ 提问者**

用 LLM 从查询里提取时间过滤条件，当用户说"最近的文档"时，"最近"是多久？三天？三个月？不同用户的理解完全不同，这个歧义怎么处理？

---

**🔬 研究员**

你发现了**时间语义歧义**——这是元数据过滤中最难处理的部分，也是很多 RAG 系统在生产中踩坑最多的地方。

"最近"的含义高度依赖语境和用户习惯：

```
"最近签署的合同"      → 用户可能指最近几个月（合同签署频率低）
"最近发布的系统通知"  → 用户可能指最近几天（通知频率高）
"最近更新的技术文档"  → 用户可能指最近几周
"最近一年的财务报告"  → 明确说了"一年"，无歧义
```

没有"正确"的默认值，但有合理的工程处理策略：

**策略一：提示词锚定默认规则（最简单）**

在提取 Prompt 里写死默认解释（如"最近 = 30 天"），并在系统层面统一。对大多数用户无感知。缺点：少数用户的期望不一致时无法发现。

**策略二：宽泛区间 + Rerank 兜底**

把不确定的时间词解析为较宽的区间（比如把"最近"解析为 90 天），确保不因过窄而漏掉重要文档，再让 Rerank 把真正相关的排到前面。

```
策略：宁可过滤太宽，也不要过滤太窄
原因：前过滤漏掉的文档永远找不回来；多召回的文档还有 Rerank 兜底
```

**策略三：多轮对话中主动追问**

当时间语义不明确时，AI 追问澄清：

```
用户：给我看最近签署的合同
AI：您说的"最近"是指多长时间范围？
    A. 最近一周
    B. 最近一个月
    C. 最近三个月
    D. 今年以内
```

适合精度要求高的业务场景（法律、财务），不适合追求流畅体验的通用问答。

**实践建议：**

三种策略不互斥。默认用策略一（给明确的 Prompt 规则）；同时用策略二（宽泛解析）作为保底；对于精度要求高的业务用策略三（追问）。绝大多数用户的查询在策略一下就能得到满意结果。

---

## 知识体系全景

```
检索质量知识体系

第一层：基础算法
  ├── BM25（关键词统计）—— 见 01 文档
  └── ANN 向量检索（语义相似度）—— 见 01 文档

第二层：融合策略
  ├── 混合检索（BM25 + 向量）—— 见 01 文档
  └── RRF 融合（基于排名，无量纲问题）—— 见 01 文档

第三层：召回优化
  ├── Query Rewrite（Multi-Query / HyDE / 意图识别）—— 见 01 文档
  └── 分块策略（Token / 语义 / 父子 / 结构感知）—— 见 01 文档

第四层：精排优化
  ├── Rerank（Cross-Encoder / BGE-Reranker）—— 见 01 文档
  └── Context 排列（Lost in the Middle 缓解）—— 本文第八章

第五层：复杂查询
  ├── 多跳推理（Iterative Retrieval / ReAct）—— 本文第十章
  └── 知识图谱（GraphRAG / 轻量 Chunk 关联）—— 本文第十一章

第六层：系统工程
  ├── 失败模式诊断（6 种模式 + 可观测性）—— 本文第九章
  ├── 幻觉抑制（置信度阈值 / 答案验证）—— 本文第九章
  ├── RAG vs Fine-tuning 选型—— 本文第十二章
  ├── 多轮对话 RAG（查询重写 / 历史压缩 / token 预算）—— 本文第十三章
  ├── 元数据过滤（前过滤 / 后过滤 / 自然语言条件提取）—— 本文第十四章
  └── 评估体系（P@K / MRR / NDCG + A/B）—— 见 01 文档
```

---

← [第十三章：多轮对话 RAG](ch13-conversational-rag.md) | → [第十五章：Prompt Engineering](ch15-prompt-engineering.md)
