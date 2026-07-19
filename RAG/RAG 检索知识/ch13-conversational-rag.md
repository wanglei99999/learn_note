# 第十三章：多轮对话 RAG——让检索感知对话历史
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：02-advanced-retrieval.md，第十三章（第723-1105行）。本章讲解多轮对话中的三种上下文依赖类型（指代消解、省略补全、主题延续）、核心解法（对话感知查询重写）、两阶段历史使用原则、三种历史管理策略（滑动窗口/摘要压缩/相关性过滤）、Token 预算分配，以及是否需要重写的判断方案。

---

**🔬 研究员**

单轮 RAG 假设每个查询都是独立的、自包含的。但在真实产品中，用户和 AI 的对话是连续的：

```
用户：合同中关于甲方违约的处理方式是什么？
AI：根据合同第七章，甲方违约需承担...

用户：那乙方呢？          ← 这句话单独送给向量库，会检索到什么？
AI：...

用户：赔偿金额怎么计算？  ← "赔偿"指的是哪种赔偿？
AI：...

用户：有上限吗？          ← 上限是什么的上限？
AI：...
```

这四个问题，任何一个单独拿出来给向量库检索，都会失败或得到错误结果。**根本原因是：多轮对话中的查询不是自包含的，它依赖对话历史才有完整含义。**

### 三种上下文依赖类型

**类型一：指代消解（Coreference Resolution）**

```
Q1: "告诉我甲方的违约责任"
Q2: "那乙方的呢？"       ← "乙方的" = 乙方的违约责任
Q3: "他们需要赔多少？"   ← "他们" = 乙方
```

代词"他们"、"乙方的"需要通过对话历史还原为完整实体。直接向量检索"他们需要赔多少"，语义极度模糊，召回结果几乎是随机的。

**类型二：省略补全（Ellipsis）**

```
Q1: "合同里有哪些付款节点？"
Q2: "第三个节点的金额是多少？"  ← 省略了"合同付款节点"
Q3: "怎么触发？"                ← 省略了"第三个付款节点的触发条件"
```

每个后续问题都省略了大量上下文。"怎么触发"单独检索，向量库不知道你在问什么"触发"。

**类型三：主题延续（Topic Continuation）**

```
Q1: "什么是不可抗力条款？"
Q2: "哪些情况属于不可抗力？"    ← 延续 Q1 主题
Q3: "发生后需要多少天内通知？"  ← 在 Q2 基础上深入
Q4: "通知方式有什么要求？"      ← 再深入一层
```

用户在探索同一话题的不同侧面。Q4 "通知方式有什么要求"单独检索，可能返回各种通知相关内容，但用户其实只关心不可抗力发生后的通知格式。

### 核心解法：对话感知查询重写

最直接、效果最稳定的解法：**在检索之前，先用 LLM 把当前问题结合历史重写成一个独立的、自包含的检索查询。**

```
输入：
  历史 = ["Q: 甲方违约怎么处理？", "A: 甲方违约需承担..."]
  当前 = "那乙方呢？"

重写输出：
  "合同中乙方违约时的处理方式和赔偿责任是什么？"
                    ↓
  独立的、完整的查询 → 送给向量检索
```

这一步把"依赖上下文的模糊问题"转化为"向量库能处理的独立查询"，是多轮对话 RAG 的核心设计。

重写之后，检索流程完全不变——它看到的仍然是一个正常的独立查询，不需要改动检索逻辑的任何部分。

### 两阶段历史使用原则

多轮 RAG 中，对话历史在两个地方使用，但用法不同：

```
检索阶段：使用重写后的查询（目的是让向量库能理解）
生成阶段：使用完整的原始历史 + 检索结果（目的是让 LLM 理解对话脉络）

                 ┌───────────────────────────┐
                 │         对话历史           │
                 └──────┬────────────────────┘
                        │
          ┌─────────────▼─────────────────┐
          │   查询重写（LLM）              │
          │   "那乙方呢？" → "乙方违约..."│
          └─────────────┬─────────────────┘
                        │ 重写后的查询（仅用于检索）
          ┌─────────────▼─────────────────┐
          │   检索（BM25 + 向量 + Rerank） │
          └─────────────┬─────────────────┘
                        │ 检索到的 chunks
          ┌─────────────▼─────────────────┐
          │   生成（原始历史 + chunks）    │
          │   LLM 看到完整的对话上下文     │
          └───────────────────────────────┘
```

---

**🔧 工程师**

### 查询重写实现

```python
REWRITE_PROMPT = """你是一个查询重写助手。给定对话历史和最新问题，
将最新问题重写为一个独立、完整的检索查询。

要求：
1. 重写后的查询不依赖对话历史也能被独立理解
2. 补全所有代词（他/她/它/他们）、省略引用和隐式指代
3. 保留问题的原始意图，不要添加额外假设
4. 如果最新问题本身已经完整独立，直接返回原问题
5. 只返回重写后的查询，不要解释或说明

对话历史：
{history}

最新问题：{current_query}

重写后的查询："""


async def rewrite_query_with_history(
    current_query: str,
    history: list[dict],  # [{"role": "user"/"assistant", "content": "..."}]
    llm: LLMProvider,
) -> str:
    if not history:
        return current_query  # 无历史，不需要重写

    history_text = _format_history_for_rewrite(history, max_turns=5)

    rewritten = await llm.generate(
        prompt=REWRITE_PROMPT.format(
            history=history_text,
            current_query=current_query,
        ),
        max_tokens=200,
        temperature=0,  # 重写任务要确定性，temperature 设 0
    )
    return rewritten.strip()


def _format_history_for_rewrite(history: list[dict], max_turns: int) -> str:
    # 只取最近 max_turns 轮，避免 token 浪费
    recent = history[-(max_turns * 2):]
    lines = []
    for msg in recent:
        role = "用户" if msg["role"] == "user" else "AI"
        lines.append(f"{role}：{msg['content']}")
    return "\n".join(lines)
```

### 完整多轮对话 RAG 流程

```python
async def conversational_rag(
    session_id: str,
    current_query: str,
    space_id: str,
) -> str:
    # ① 获取对话历史
    history = await get_session_history(session_id)

    # ② 查询重写（仅用于检索，不用于生成）
    retrieval_query = await rewrite_query_with_history(
        current_query=current_query,
        history=history,
        llm=llm,
    )

    # ③ 用重写后的查询检索
    chunks = await retrieve_and_rerank(
        query=retrieval_query,
        space_id=space_id,
    )
    context = build_context(chunks)

    # ④ 生成：给 LLM 完整历史 + 检索结果 + 原始问题
    #    注意这里用 current_query，不用 retrieval_query
    messages = [
        {"role": "system", "content": build_system_prompt(context)},
        *compress_history(history),   # 历史压缩（见下文）
        {"role": "user",   "content": current_query},
    ]
    answer = await llm.chat(messages=messages)

    # ⑤ 把本轮对话保存到历史
    await append_to_history(session_id, current_query, answer)
    return answer
```

### 对话历史管理：三种策略

随着对话增长，历史持续消耗 token 预算，必须主动管理：

**策略一：滑动窗口（最简单）**

```python
def sliding_window(history: list[dict], max_turns: int = 5) -> list[dict]:
    """只保留最近 max_turns 轮对话"""
    return history[-(max_turns * 2):]  # 每轮 = user + assistant 各一条
```

简单可靠，但丢失早期对话的重要信息。适合话题不连续、对话较短的场景。

**策略二：摘要压缩（长对话首选）**

```python
SUMMARIZE_PROMPT = """将以下对话历史压缩为一段简洁摘要，保留关键结论和重要实体。

对话历史：
{history}

摘要（200字以内）："""

async def compress_history(
    history: list[dict],
    keep_recent_turns: int = 3,
) -> list[dict]:
    """
    最近 keep_recent_turns 轮保留原文（保持对话自然性），
    更早的历史用 LLM 摘要替代（节省 token）。
    """
    if len(history) <= keep_recent_turns * 2:
        return history  # 历史不长，直接全用

    old_turns = history[:-(keep_recent_turns * 2)]
    recent_turns = history[-(keep_recent_turns * 2):]

    summary_text = await llm.generate(
        prompt=SUMMARIZE_PROMPT.format(
            history=_format_history_for_rewrite(old_turns, max_turns=999)
        )
    )

    # 摘要作为 system 消息注入，LLM 能感知早期对话的脉络
    return [
        {"role": "system", "content": f"[早期对话摘要]\n{summary_text}"},
        *recent_turns,
    ]
```

**策略三：相关性过滤（话题跳跃型对话）**

```python
async def relevant_history_selection(
    current_query: str,
    history: list[dict],
    top_k_turns: int = 3,
    embedding_model,
) -> list[dict]:
    """
    只保留与当前查询语义最相关的历史轮次。
    适合同一会话中话题切换频繁的场景。
    """
    query_vec = await embedding_model.embed(current_query)

    # 对每一轮（user + assistant 对）计算语义相似度
    scored_turns: list[tuple[float, int]] = []
    for i in range(0, len(history) - 1, 2):
        user_msg = history[i]["content"]
        asst_msg = history[i + 1]["content"] if i + 1 < len(history) else ""
        turn_vec = await embedding_model.embed(f"{user_msg} {asst_msg}")
        score = cosine_similarity(query_vec, turn_vec)
        scored_turns.append((score, i))

    # 取最相关的 top_k_turns 轮，按时间顺序重排（保持对话连贯）
    top_indices = sorted(
        [i for _, i in sorted(scored_turns, reverse=True)[:top_k_turns]]
    )

    result = []
    for i in top_indices:
        result.append(history[i])
        if i + 1 < len(history):
            result.append(history[i + 1])
    return result
```

### Token 预算分配参考

```
以 Qwen-Plus（32K context）为例：

固定成本（每次请求必须）：
  System Prompt：    500 token
  检索 chunks：    4,000 token
  当前问题：         100 token
  响应缓冲：       1,000 token
  ─────────────────────────────
  固定占用：       5,600 token
  剩余给历史：    26,400 token

历史 token 增长估算（每轮平均 200 token）：
   5 轮对话：  ~1,000 token   ← 无压力
  20 轮对话：  ~4,000 token   ← 开始关注
  50 轮对话：~10,000 token    ← 建议启用压缩
 100 轮对话：~20,000 token    ← 必须压缩，否则挤占检索空间

建议：超过 20 轮启用摘要压缩；话题跳跃明显时换用相关性过滤。
```

---

**❓ 提问者**

查询重写需要额外调一次 LLM，每个用户的每条消息都多一次 LLM 调用，延迟和成本都增加了。对于简单的独立问题，这次调用是纯浪费的。有没有办法只在"确实需要重写"时才调用？

---

**🔬 研究员**

"是否需要重写"是一个**查询依赖性检测**问题，有从零成本到高精度的多种解法：

**方案一：规则检测（零 LLM 开销，覆盖 70% 场景）**

```python
def needs_rewrite(query: str, history: list[dict]) -> bool:
    if not history:
        return False

    # 含代词 → 大概率需要重写
    pronouns = ["他", "她", "它", "他们", "这个", "那个", "这些", "那些",
                "上述", "刚才", "之前", "前面"]
    if any(p in query for p in pronouns):
        return True

    # 问题过短（< 8 字） → 大概率是追问
    if len(query.strip()) < 8:
        return True

    # 开头是追问词 → 大概率是延续
    followup_starters = ["那", "然后", "那么", "接着", "继续", "还有",
                         "另外", "此外", "同样", "类似的"]
    if any(query.startswith(s) for s in followup_starters):
        return True

    return False
```

**方案二：永远重写（最简单，效果最稳定）**

当问题已经是独立的，LLM 重写后返回的是原问题本身（或语义等价的表达），不影响检索结果。额外成本：约 1 次 Haiku 调用（< 0.1 分人民币/次）。

对于大多数产品，这个成本完全可以接受，且实现最简单、最不容易出 bug。

**方案三：并行执行（零额外延迟）**

重写和检索并行启动：重写用原始查询先发起一次检索，重写完成后再发起一次，取重写版本的结果。

```python
async def rewrite_and_retrieve_parallel(query, history, space_id):
    # 并行：用原始查询检索 + 重写
    raw_search_task = asyncio.create_task(
        retrieve(query, space_id)
    )
    rewrite_task = asyncio.create_task(
        rewrite_query_with_history(query, history, llm)
    )

    rewritten_query = await rewrite_task

    if rewritten_query == query:
        # 重写没有变化，用原始检索结果即可
        return await raw_search_task
    else:
        # 重写有变化，用新查询重新检索
        raw_search_task.cancel()
        return await retrieve(rewritten_query, space_id)
```

代价：大多数情况多消耗了一次原始检索（但检索比 LLM 便宜得多）。好处：TTFT 不增加。

**实践建议：** 先用方案一（规则）做初筛，规则命中则重写；不确定时默认重写（方案二）。这样兼顾了成本和准确率。

---

← [第十二章：RAG vs Fine-tuning](ch12-rag-vs-finetuning.md) | → [第十四章：元数据过滤](ch14-metadata-filtering.md)
