# 第十五章：Prompt Engineering for RAG
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：03-production-and-advanced.md，第十五章（第26-236行）。本章讲解 RAG 系统中 Prompt 的五层结构、强 Prompt 的关键要素、Context 注入格式设计（带编号标注 / XML 结构化）、Few-Shot 示例引导、Chain-of-Thought for RAG，以及 Prompt 膨胀问题与动态压缩方案。

---

**🔬 研究员**

RAG 系统中 Prompt 的设计直接决定生成质量。很多团队花大量时间优化检索，却用一个随意写的 Prompt——这是严重的不均衡。

Prompt 在 RAG 中承担三个职责：

1. **角色定义**：告诉模型它是谁、有什么能力边界
2. **约束设定**：告诉模型如何使用检索结果、何时说不知道
3. **格式控制**：告诉模型回答的结构和风格

### Prompt 的五层结构

```
┌─────────────────────────────────┐
│  1. System Role（角色 + 能力边界）│
├─────────────────────────────────┤
│  2. 行为规则（约束 + 优先级）     │
├─────────────────────────────────┤
│  3. 上下文注入（检索到的 chunks） │
├─────────────────────────────────┤
│  4. 格式指令（输出结构）          │
├─────────────────────────────────┤
│  5. 用户问题                     │
└─────────────────────────────────┘
```

### System Prompt 的关键要素

**弱 Prompt（常见错误写法）：**

```python
system = "你是一个助手，根据文档回答问题。"
```

问题：角色模糊、约束缺失、格式不定，LLM 自由发挥空间太大。

**强 Prompt（生产级写法）：**

```python
SYSTEM_PROMPT = """
# 角色
你是 ArcKnowledge 的智能问答助手，专门基于用户提供的知识库文档回答问题。

# 核心规则
1. **只使用文档内容**：所有回答必须有文档依据，禁止使用训练知识补充
2. **明确引用来源**：回答中注明信息来源的文档名称，格式：（来源：{文档名}）
3. **无答案时的处理**：若文档中无法找到足够信息，回答："根据现有知识库，
   暂无关于此问题的相关信息。建议补充相关文档。"
4. **置信度标注**：对不确定的信息使用"文档中提到..."而非"确实是..."
5. **不推断原文没有的结论**：即使逻辑上可以推断，也需说明"文档未明确说明"

# 回答质量要求
- 直接回答问题，不要重复问题内容
- 长答案使用结构化格式（标题、列表）
- 数字、日期、专有名词直接引用原文，不做改写

# 文档内容
{context}
"""
```

---

**🔧 工程师**

### Context 注入的格式设计

Context 的格式直接影响 LLM 对来源的感知能力：

**方式1：纯文本拼接（最简单，但来源不清晰）**

```python
context = "\n\n".join(chunk["content"] for chunk in chunks)
```

**方式2：带编号的来源标注（推荐）**

```python
def format_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[文档{i}] 来源：{chunk['original_name']}\n"
            f"{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)
```

LLM 生成时可以引用"文档1"，方便前端展示引用角标。

**方式3：XML 结构化（对强模型效果更好）**

```python
def format_context_xml(chunks: list[dict]) -> str:
    docs = []
    for i, chunk in enumerate(chunks, 1):
        docs.append(
            f'<document index="{i}" source="{chunk["original_name"]}">\n'
            f'{chunk["content"]}\n'
            f'</document>'
        )
    return "\n".join(docs)
```

Claude 系列对 XML 格式有更好的结构感知，能更准确地引用来源。

### Few-Shot：用示例引导输出格式

对于需要特定格式的场景（如法律问答、财务分析），加入 Few-Shot 示例比写格式指令更有效：

```python
FEW_SHOT_EXAMPLES = """
# 示例问答

问：合同中关于保密义务的期限是多久？
答：根据合同第8.3条，保密义务自合同签订之日起持续5年，即使合同提前终止，
    保密义务仍然有效。（来源：保密协议2024版.pdf）

问：项目验收标准是什么？
答：文档中未明确规定具体的验收标准数值。第6章提到"验收需经甲方技术负责人
    书面确认"，但具体标准需参考附件A（附件A未在知识库中）。
    （来源：项目合同.docx）
"""
```

两个示例覆盖了两种情况：**有答案时如何引用**，**无答案时如何诚实表达**。

### Chain-of-Thought（思维链）for RAG

对于需要推理的问题，引导 LLM 先分析再回答：

```python
COT_PROMPT = """
请按以下步骤回答：

1. **理解问题**：用一句话概括用户真正在问什么
2. **查找依据**：在文档中找到相关内容，逐条列出
3. **综合分析**：基于找到的内容进行推理
4. **给出答案**：明确、简洁地回答问题

问题：{query}
"""
```

---

**❓ 提问者**

Prompt 越写越长，加了角色、规则、示例、CoT……最后 system prompt 本身就有几百 token。这会不会占用太多 context window，反而挤占了检索内容的空间？

---

**🔬 研究员**

这是 RAG Prompt Engineering 中真实存在的 **"Prompt 膨胀"** 问题。

量化影响对比：

```
GPT-4o（128K context）：
  System Prompt：     500 tokens（0.4%）
  Few-Shot 示例：     300 tokens（0.2%）
  对话历史：        2,000 tokens（1.6%）
  检索 chunks：     5,000 tokens（3.9%）
  响应缓冲：          500 tokens（0.4%）
  ─────────────────────────────────────
  可用于检索内容：119,700 tokens（93.5%）  ← 几乎无压力

Ollama mistral（8K context）：
  System Prompt：     500 tokens（6.3%）
  Few-Shot：          300 tokens（3.8%）
  对话历史：        1,500 tokens（18.8%）
  检索 chunks：     3,000 tokens（37.5%）
  响应缓冲：          500 tokens（6.3%）
  ─────────────────────────────────────
  实际可用：        2,200 tokens（27.5%）  ← 只剩 3~4 个 chunk
```

**解决方案：动态 Prompt 压缩**

```python
def build_prompt(
    system_base: str,
    few_shots: list[str],
    context: str,
    query: str,
    model_context_window: int,
    reserve_for_response: int = 500,
) -> str:
    available = model_context_window - reserve_for_response
    system_tokens = count_tokens(system_base)
    query_tokens = count_tokens(query)
    budget = available - system_tokens - query_tokens

    # 小模型（8K）：精简 prompt，保留检索空间
    if budget < 4000:
        return build_minimal_prompt(system_base, context, query)

    # 中等模型（16K）：加 few-shot，不加 CoT
    if budget < 8000:
        return build_standard_prompt(system_base, few_shots, context, query)

    # 大模型（128K+）：完整 prompt
    return build_full_prompt(system_base, few_shots, context, query)
```

---

← [第十四章：元数据过滤](ch14-metadata-filtering.md) | → [第十六章：ColBERT 与 SPLADE](ch16-colbert-splade.md)
