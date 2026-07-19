# 第十八章：Agentic RAG——让检索有"思考"
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：03-production-and-advanced.md，第十八章（第598-793行）。本章讲解传统 RAG 固定管道的局限、Agentic RAG 的核心架构、Self-RAG（按需检索）、ReAct 框架、Tool Use API 实现、CRAG（纠正性 RAG），以及生产环境的工程化约束（SafeAgent）。

---

**🔬 研究员**

传统 RAG 是固定管道：**检索 → 生成**，没有反馈循环。Agentic RAG 引入 Agent 的决策能力，让系统能够：

- 判断是否需要检索（而不是每次都检索）
- 决定检索什么（动态生成查询）
- 判断结果是否足够（循环检索直到满意）
- 使用多种工具（向量库、计算器、API、代码执行等）

### Agentic RAG 的核心架构

```
用户问题
  ↓
Agent（LLM 驱动的决策者）
  ↓
  ├── [工具1] 知识库检索
  ├── [工具2] 网络搜索
  ├── [工具3] 数据库查询
  ├── [工具4] 代码执行
  └── [工具5] API 调用
  ↓
综合所有工具结果 → 最终回答
```

### Self-RAG：按需检索

传统 RAG 每次都检索，即使问题不需要外部知识（"1+1等于几？"也去检索，浪费资源且引入噪声）。

**Self-RAG**（Asai et al. 2023）训练模型生成特殊 token 来控制检索：

```
用户问：1+1等于几？
[Retrieve=No]  不需要检索
2。

用户问：深圳市2024年GDP是多少？
[Retrieve=Yes]  触发检索
[检索结果：深圳2024年GDP为3.68万亿元]
[IsRel=Yes]    检索结果相关
[IsSup=Yes]    答案有文档支撑
深圳市2024年GDP为3.68万亿元。
[IsUse=5]      答案质量5分
```

四种控制 token：`[Retrieve]`、`[IsRel]`、`[IsSup]`、`[IsUse]`

#### Self-RAG 训练过程：如何教会模型"自我反思"

这四个控制 token 不是 prompt engineering 的结果，而是通过**专门的训练流程**注入到模型中的。

**第一阶段：训练 Critic 模型**

Critic 是一个辅助模型（通常是较小的 LLM），专门用于标注训练数据。对于每个 (问题, 文档, 答案) 三元组，Critic 模型学会判断：

| 标注维度 | 问题 | 标签 |
|---------|------|------|
| [Retrieve] | 这个问题需要外部知识吗？ | Yes / No |
| [IsRel] | 检索到的文档与问题相关吗？ | Relevant / Irrelevant |
| [IsSup] | 答案中这个陈述有文档支撑吗？ | Fully / Partially / No |
| [IsUse] | 这个答案对用户有用吗？ | 1-5 |

Critic 模型用人工标注数据（约 10万条，部分用 GPT-4 辅助标注）做 supervised fine-tuning。

**第二阶段：生成带反思 token 的训练语料**

用训练好的 Critic 模型，对大规模原始训练数据（问答对）进行自动标注，将反思 token 插入文本序列中：

```
原始训练样本：
  问题："深圳市2024年GDP是多少？"
  答案："深圳2024年GDP为3.68万亿元。"

经 Critic 处理后的增强样本：
  "深圳市2024年GDP是多少？[Retrieve=Yes]
   [Retrieved Doc: 2024年深圳统计年鉴...]
   [IsRel=Yes] [IsSup=Fully]
   深圳2024年GDP为3.68万亿元。[IsUse=5]"
```

**第三阶段：训练生成模型（Generator）**

反思 token 被当作**普通词汇表 token** 加入词表，生成模型用标准语言模型损失（cross-entropy）在增强语料上训练：

$$\mathcal{L} = -\sum_t \log P(w_t | w_1, w_2, ..., w_{t-1})$$

训练目标中包含了反思 token，模型学会在适当位置生成它们。**不需要特殊的强化学习训练信号**——普通的 next-token prediction 就可以教会模型什么时候插入 `[Retrieve=Yes]`。

**第四阶段：推理时的段落级 Beam Search**

推理时，Self-RAG 使用**段落级 beam search**（而非普通的 token 级 beam search）：

```
步骤1：生成直到 [Retrieve=Yes] 出现
步骤2：调用检索器，获取 K 个候选文档 {d₁, d₂, ..., d_K}
步骤3：对每个文档 dᵢ，在以 dᵢ 为上下文的条件下生成后续文本
步骤4：对每个候选答案评分：
        score(答案 | dᵢ) = P([IsRel=Yes]) × P([IsSup=Fully]) × P([IsUse=5])
步骤5：选择得分最高的候选，继续生成
步骤6：循环直到生成终止符
```

**Self-RAG vs Prompt-Based RAG 的本质区别：**

| 维度 | Prompt-Based RAG | Self-RAG |
|------|-----------------|---------|
| 检索决策 | 每次都检索（规则） | 模型自己判断（学习到的行为） |
| 质量评估 | 外部评估器（额外调用） | 内嵌在生成 token 中（同一次 forward pass） |
| 推理开销 | 固定的一次检索 | 动态（可能 0 次或多次检索） |
| 训练需求 | 无需特殊训练 | 需要 Critic 标注 + Generator 微调 |

**局限性：** Self-RAG 需要对基础模型做微调，这意味着你不能直接用闭源 API（如 GPT-4）实现完整的 Self-RAG——只能用 GPT-4 做 prompt-based 的"近似 Self-RAG"（在 prompt 里加检索判断步骤）。

### ReAct 框架（推理 + 行动交错）

```
Thought: 需要先了解第3.2条的具体规定
Action: search("第3.2条交货期")
Observation: 甲方应在签约后30日内交货，逾期按日计违约金

Thought: 已知违约行为，需要找到违约金计算公式
Action: search("违约金计算方式 第7章")
Observation: 逾期交货违约金 = 合同金额 × 0.1% × 逾期天数

Thought: 现在可以综合计算了
Answer: 根据合同规定，...
```

---

**🔧 工程师**

### 用 Tool Use API 实现 Agentic RAG

```python
TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "在知识库中搜索相关信息。当问题需要查找具体文档内容时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询"},
                "top_k": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "calculate",
        "description": "执行数学计算。当问题涉及数字计算时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"}
            },
            "required": ["expression"]
        }
    }
]

async def agentic_rag(query: str) -> str:
    messages = [{"role": "user", "content": query}]

    while True:
        response = await llm.chat(messages=messages, tools=TOOLS)

        if response.stop_reason == "end_turn":
            return response.content

        messages.append({"role": "assistant", "content": response.content})

        for tool_call in response.tool_calls:
            if tool_call.name == "search_knowledge_base":
                result = await retriever.search(**tool_call.parameters)
                tool_result = format_chunks(result)
            elif tool_call.name == "calculate":
                # ⚠️ 安全警告：严禁在生产中直接 eval() 用户/LLM 传入的字符串（代码注入风险）
                # 正确做法：只允许纯数学字符，用正则白名单过滤
                import re
                expr = tool_call.parameters["expression"]
                if re.fullmatch(r"[\d\s\+\-\*\/\.\(\)\%]+", expr):
                    tool_result = str(eval(expr))
                else:
                    tool_result = "错误：不支持的表达式格式"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })
```

### CRAG：纠正性 RAG

```python
async def crag(query: str) -> str:
    chunks = await retrieve(query)
    quality_score = await evaluate_retrieval_quality(query, chunks)

    if quality_score > 0.8:
        # 高质量：直接生成
        return await generate(query, chunks)
    elif quality_score > 0.5:
        # 中等：过滤噪声后生成
        refined_chunks = await refine_chunks(query, chunks)
        return await generate(query, refined_chunks)
    else:
        # 低质量：补充网络搜索
        web_results = await web_search(query)
        combined = chunks + web_results
        return await generate(query, combined)
```

---

**❓ 提问者**

Agentic RAG 让 LLM 自己决定要不要检索——引入了很多不确定性。在生产环境中，Agent 的行为不可预测，会不会导致系统难以调试、不稳定？

---

**🔬 研究员**

你触及了 Agent 系统的核心工程挑战：**不可预测性 vs 灵活性的权衡**。

不可预测性的具体表现：
1. 工具调用路径不稳定：同一问题，不同时间可能走不同工具链
2. 无限循环风险：Agent 可能一直觉得"信息不够"，反复检索
3. 工具参数幻觉：LLM 可能生成无效的工具参数
4. 成本爆炸：多轮 LLM 调用，费用难以预估

**生产环境的工程化约束：**

```python
class SafeAgent:
    MAX_TOOL_CALLS = 5
    ALLOWED_TOOLS = {"search_knowledge_base", "calculate"}
    TIMEOUT_SECONDS = 30

    async def run(self, query: str) -> str:
        tool_call_count = 0
        async with asyncio.timeout(self.TIMEOUT_SECONDS):
            while tool_call_count < self.MAX_TOOL_CALLS:
                response = await self.llm.chat(...)
                if response.stop_reason == "end_turn":
                    return response.content
                for tool_call in response.tool_calls:
                    if tool_call.name not in self.ALLOWED_TOOLS:
                        raise ValueError(f"非法工具调用：{tool_call.name}")
                tool_call_count += len(response.tool_calls)

        return "抱歉，无法在规定时间内完成回答。"
```

**结论：** 在需要灵活性的场景（复杂查询、多步推理）用 Agentic RAG，在需要稳定性的场景（高并发、严格 SLA）用固定管道 RAG。两种模式可以共存，用查询复杂度做路由。

---

← [第十七章：RAGAS 评估框架](ch17-ragas.md) | → [第十九章：生产环境工程](ch19-production.md)
