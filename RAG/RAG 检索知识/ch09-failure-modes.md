# 第九章：RAG 的失败模式——诊断与修复
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：02-advanced-retrieval.md，第九章（第143-334行）。本章系统讲解 RAG 系统的六种失败模式（召回不全、精度不够、时效性过期、幻觉、答非所问、忽略检索结果）、可观测性追踪日志、幻觉抑制 Prompt 模板，以及知识边界感知的工程化解法。

---

> **📌 本章核心**
>
> - 【必须掌握】**六种失败模式分类**：检索失败（召回不全/精度不够/时效过期）vs 生成失败（幻觉/答非所问/忽略检索结果）——出了问题先定位是哪类，再对症下药
> - 【必须掌握】**RAGTrace 可观测性**：记录每个请求的改写查询、召回结果、Rerank 结果、context token 数和各阶段延迟；没有这个就无法追溯线上问题根因
> - 【必须掌握】**知识边界感知工程化**：用 Reranker 置信度阈值拒答（top chunk score < 0.5 直接返回"无相关信息"），比依赖 LLM 自律更稳定可靠
> - 【查阅即可】**幻觉抑制 Prompt 要素**：明确限制"只用以下文档信息"、要求标注来源、"无法回答时直说"——三条规则缺一不可

---

**🔬 研究员**

RAG 系统在生产中出现质量问题时，根因往往不同。有一套系统性的诊断框架：

```
RAG 失败模式分类：

┌─────────────────────────────────────────────┐
│             RAG 失败                         │
│                                             │
│  ┌──────────────┐    ┌────────────────────┐ │
│  │  检索失败     │    │    生成失败         │ │
│  │              │    │                    │ │
│  │ ① 召回不全   │    │ ④ 幻觉（凭空捏造） │ │
│  │ ② 精度不够   │    │ ⑤ 答非所问         │ │
│  │ ③ 时效性过期 │    │ ⑥ 忽略检索结果     │ │
│  └──────────────┘    └────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 【必须掌握】六种失败模式详解

**① 召回不全（Recall Failure）**

症状：用户问的答案在知识库里有，但没被检索到。

根因：
- 词汇鸿沟（用户用词 ≠ 文档用词）
- top_k 设置太小
- 向量模型领域偏移
- chunk 切割破坏了关键信息

诊断：直接搜索关键词看 chunk 是否存在，再看 embedding 相似度是否低于阈值。

**② 精度不够（Precision Failure）**

症状：检索到的 chunk 大量无关，生成时被噪声干扰。

根因：
- 没有 Rerank，RRF 结果质量差
- 查询过于宽泛，BM25 召回大量弱相关文档
- Embedding 模型对该领域质量差

**③ 时效性过期（Staleness）**

症状：回答了过时的信息，知识库未更新。

根因：文档更新了但知识库没有重新入库。解法：建立文档版本监控，变更时触发重新入库。

**④ 幻觉（Hallucination）**

症状：LLM 编造了知识库中不存在的信息。

根因：
- 检索失败后 LLM 用训练知识"补全"
- Prompt 没有明确限制"只基于以下内容回答"
- 模型倾向于给出确定性回答，而不是"我不知道"

**⑤ 答非所问（Misalignment）**

症状：回答了相关但不是用户真正想问的问题。

根因：
- 查询意图理解错误
- Prompt 中没有充分传递用户意图
- 多义词没有消歧

**⑥ 忽略检索结果（Context Neglect）**

症状：LLM 忽略了 context 中的信息，用自己的训练知识回答。

根因：
- Lost in the Middle 问题
- Context 太长，重要信息被淹没
- Prompt 没有强调"优先使用以下文档"

---

**🔧 工程师**

### 【必须掌握】诊断工具：RAG 可观测性日志

```python
from dataclasses import dataclass, field

@dataclass
class RAGTrace:
    query: str
    rewritten_queries: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)   # 含 chunk_id, score, content 片段
    reranked_chunks: list[dict] = field(default_factory=list)    # 含 rerank_score
    context_tokens: int = 0                                       # 实际送入 LLM 的 token 数
    answer: str = ""
    latency_ms: dict = field(default_factory=dict)               # 各阶段耗时

async def traced_rag(query: str) -> tuple[str, RAGTrace]:
    trace = RAGTrace(query=query)
    t0 = time.time()

    trace.rewritten_queries = await rewrite(query)
    trace.latency_ms["rewrite"] = (time.time() - t0) * 1000

    t1 = time.time()
    trace.retrieved_chunks = await retrieve(trace.rewritten_queries)
    trace.latency_ms["retrieve"] = (time.time() - t1) * 1000

    t2 = time.time()
    trace.reranked_chunks = await rerank(query, trace.retrieved_chunks)
    trace.latency_ms["rerank"] = (time.time() - t2) * 1000

    t3 = time.time()
    context = build_context(trace.reranked_chunks)
    trace.context_tokens = count_tokens(context)
    trace.answer = await generate(query, context)
    trace.latency_ms["generate"] = (time.time() - t3) * 1000

    return trace.answer, trace
```

把 `RAGTrace` 存到数据库或日志系统，当用户反馈"回答不对"时，可以追溯完整链路，定位是哪个环节出了问题。

### 幻觉抑制 Prompt 模板

```python
RAG_SYSTEM_PROMPT = """
你是一个专业的问答助手。请严格基于以下提供的文档内容回答用户问题。

规则：
1. 只使用文档中明确提到的信息
2. 如果文档中没有足够的信息回答问题，直接说"根据现有文档，无法回答此问题"
3. 不要用自己的知识补充文档中没有的内容
4. 回答时注明信息来源于哪个文档（文档名称）

文档内容：
{context}
"""
```

---

**❓ 提问者**

Prompt 里说"如果文档中没有足够信息就说不知道"——但 LLM 很难判断自己"是不是真的不知道"，这个边界怎么处理？

---

**🔬 研究员**

这是 RAG 系统中最难处理的问题之一，叫做 **"知识边界感知"（Knowledge Boundary Awareness）**。

工程化解法（不依赖模型自律）：

**方案1：检索置信度阈值**

```python
async def rag_with_confidence(query: str) -> str:
    chunks = await rerank(query, await retrieve(query))

    # 最高相关分低于阈值，直接拒绝
    if not chunks or chunks[0]["rerank_score"] < 0.5:
        return "抱歉，知识库中没有关于此问题的相关信息。"

    return await generate(query, build_context(chunks))
```

**方案2：答案忠实度验证（Answer Faithfulness Check）**

```python
FAITHFULNESS_PROMPT = """
给定以下 Context 和 Answer，判断 Answer 中的每个陈述是否能在 Context 中找到支撑。

Context：{context}
Answer：{answer}

输出 JSON：
{{"faithful": true/false, "unsupported_claims": ["..."]}}
"""
```

如果 `faithful=false`，触发重新生成或添加免责声明。

**方案3：混合知识策略**

明确区分两类问题：
- **知识库内问题**：用 RAG 回答，附引用来源
- **通用问题**：允许 LLM 用自身知识，但标注"此回答基于模型知识，非知识库内容"

---

← [第八章：Lost in the Middle](ch08-lost-in-middle.md) | → [第十章：多跳推理](ch10-multi-hop.md)
