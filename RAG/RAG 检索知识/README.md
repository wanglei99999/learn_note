# RAG 检索质量完全指南
### —— 三方深度对话：研究员 × 工程师 × 提问者

本指南以**研究员**（原理推导）× **工程师**（落地实现）× **提问者**（批判质疑）三方对话的形式，系统讲解 RAG 检索质量优化的完整知识体系，覆盖从基础算法到生产工程的 19 个核心主题。

---

## 基础篇（第 1-7 章）

| 章节 | 主题 | 核心内容 |
|------|------|---------|
| [第一章](ch01-bm25.md) | BM25 与概率检索 | TF-IDF 的本质局限、BM25 公式推导（BIM 模型、RSJ 权重、精英假设、TF 饱和函数、长度归一化），ES 工程调优 |
| [第二章](ch02-vector-retrieval.md) | 向量检索与 ANN 索引 | Embedding 原理、余弦相似度、HNSW（小世界类比、分层结构、M/efConstruction 参数）、IVF、模型选型 |
| [第三章](ch03-hybrid-rrf.md) | 混合检索与 RRF 融合 | BM25 与向量互补性、双路召回示例、RRF 公式（k=60 的由来）、Python 实现、加权 RRF 与分数归一化融合 |
| [第四章](ch04-query-rewrite.md) | 查询改写 | Multi-Query（并行异步）、HyDE 假设文档、意图分类、多跳查询（ReAct 模式、串行 vs 并行） |
| [第五章](ch05-rerank.md) | 精排与上下文压缩 | Cross-Encoder vs Bi-Encoder、BGE-Reranker 本地部署、Cohere / DashScope API、长文档滑动窗口、LLM 上下文压缩 |
| [第六章](ch06-chunking.md) | 分块策略 | 固定分块、语义分块、父子分块、结构感知分块、表格/代码处理、增量更新（文档级替换 vs chunk 级哈希） |
| [第七章](ch07-evaluation.md) | 检索评估与优化路线图 | Precision@K / Recall@K / MRR / NDCG@K、评估集构建、A/B 测试、完整检索管道图、10 项优化优先级表 |

---

## 进阶篇（第 8-14 章）

| 章节 | 主题 | 核心内容 |
|------|------|---------|
| [第八章](ch08-lost-in-middle.md) | Lost in the Middle | Stanford 2023 U 型注意力曲线、两大成因、chunk 排列策略（头部最相关、尾部次相关），长上下文模型的局限 |
| [第九章](ch09-failure-modes.md) | RAG 六大失效模式 | 召回失效/精度失效/时效失效/幻觉/问题对齐失效/上下文忽视，RAGTrace 可观测性，幻觉抑制与知识边界感知 |
| [第十章](ch10-multi-hop.md) | 多跳推理 | 单跳 vs 多跳示例、迭代检索流程图、ReAct 框架、`iterative_rag()` 实现、查询分解并行子问题检索 |
| [第十一章](ch11-graphrag.md) | GraphRAG | 实体/关系抽取、知识图谱示例、Local vs Global 查询类型、GraphRAG 成本表、轻量 Chunk 级邻居替代方案 |
| [第十二章](ch12-rag-vs-finetuning.md) | RAG vs 微调 | 核心差异对比表、2×2 决策矩阵（知识时效 × 引用需求）、RAG+Fine-tuning 组合、生产延迟拆解与 SLA 优化 |
| [第十三章](ch13-conversational-rag.md) | 对话式 RAG | 3 类上下文依赖（指代/省略/话题延续）、查询改写架构、历史管理三策略（滑动窗口/摘要压缩/相关性过滤） |
| [第十四章](ch14-metadata-filtering.md) | 元数据过滤 | 预过滤/后过滤/混合过滤（compensation_factor）、Milvus/ES 过滤表达式、自然语言过滤抽取、知识体系全景 |

---

## 生产篇（第 15-19 章）

| 章节 | 主题 | 核心内容 |
|------|------|---------|
| [第十五章](ch15-prompt-engineering.md) | Prompt Engineering | Prompt 五层结构、强/弱 System Prompt 对比、Context 注入格式（带编号/XML）、Few-Shot、CoT、动态压缩 |
| [第十六章](ch16-colbert-splade.md) | ColBERT 与 SPLADE | ColBERT 多向量 MaxSim 延迟交互、三架构对比表、存储成本（3GB vs 102GB）、SPLADE 学习稀疏表示与语义扩展 |
| [第十七章](ch17-ragas.md) | RAGAS 评估框架 | Context Precision/Recall/Faithfulness/Answer Relevancy 四指标、无 ground_truth 评估、CI 阈值门控、自我偏袒缓解 |
| [第十八章](ch18-agentic-rag.md) | Agentic RAG | Self-RAG 控制 token、ReAct 框架、Tool Use API 实现（安全正则白名单）、CRAG 质量路由、SafeAgent 生产约束 |
| [第十九章](ch19-production.md) | 生产环境工程 | 语义缓存（30-60% 命中率）、监控指标体系、Prompt Injection 三层防御、Streaming RAG（SSE）、多租户数据隔离 |

---

## 学习路线

### 快速入门（2-4 小时）

适合初次接触 RAG，希望快速建立系统认知：

```
第一章（BM25）→ 第二章（向量检索）→ 第三章（混合检索）→ 第七章（评估）
```

建立基础后，按需深入具体方向。

### 工程实践路线（按需阅读）

- **提升检索质量**：第四章（查询改写）→ 第五章（精排）→ 第十六章（ColBERT/SPLADE）
- **解决生产问题**：第九章（失效模式）→ 第十五章（Prompt）→ 第十九章（生产工程）
- **构建对话系统**：第十三章（对话 RAG）→ 第十四章（元数据过滤）→ 第十八章（Agentic RAG）
- **评估与度量**：第七章（检索评估）→ 第十七章（RAGAS）

### 深度研究路线（顺序阅读）

按章节顺序完整阅读全部 19 章，系统掌握 RAG 检索质量优化的完整知识体系。

---

← [返回上级目录](../)
