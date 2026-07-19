# 第八章：Lost in the Middle——上下文位置的影响
### —— 三方深度对话：研究员 × 工程师 × 提问者

> 原始来源：02-advanced-retrieval.md，第八章（第22-141行）。本章讲解 LLM 对 context 中不同位置的注意力分配不均匀问题，以及缓解策略（chunk 排列优化、Contextual Compression）。

---

> **📌 本章核心**
>
> - 【必须掌握】**U 形注意力曲线**：LLM 对 context 首部和尾部注意力强、中间弱——最相关的 chunk 放首位，第二相关放末位，其余放中间
> - 【理解即可】**RoPE 距离衰减**：位置差越大，query-key 内积各维度振荡相互抵消趋向于零；中间 chunk 距首尾都远，双向衰减叠加
> - 【理解即可】**Attention Sink 机制**：Softmax 归一化约束下注意力权重之和恒为 1，首部 token 成为"垃圾桶"吸收多余权重，进一步强化首部优势
> - 【查阅即可】**缓解策略**：首尾排列法（代码见工程师部分）或倒序排列（最相关放最后）——在评估集上 A/B 决定哪种更好

---

**🔬 研究员**

Rerank 之后，我们把 Top-K 的 chunk 拼进 LLM 的 context。但有一个反直觉的研究结论：**LLM 对 context 中不同位置的内容，注意力分配是不均匀的。**

2023 年斯坦福的研究论文《Lost in the Middle》发现：

```
context 位置 vs LLM 性能（多文档问答任务）：

性能
 ▲
高│█████                           █████
  │     ████                   ████
  │         ████           ████
低│             ████████████
  └──────────────────────────────────→
   开头                              结尾
         context 中的位置
```

**LLM 对 context 首部和尾部的内容注意力最强，中间部分注意力显著下降。**

这意味着即使检索到了正确的 chunk，如果它被放在 context 的中间，LLM 可能"视而不见"，给出错误答案。

### 【理解即可】为什么会出现这种现象：机制分析

> **为什么要理解这个机制？** 它解释了"为什么最相关 chunk 必须放首位而不是第二位"——首部同时获得语义注意力 + Attention Sink 双重加持，中间只有语义注意力。理解这两层机制后，chunk 排列策略从"经验做法"变成有理论支撑的工程决策。

表面解释是"训练数据偏置"——人类写作时重要信息倾向于出现在开头和结尾。但这只是现象层面的描述，更深层的机制来自 Transformer 的位置编码和注意力计算本身。

**机制一：RoPE 的位置距离衰减**

现代 LLM 几乎都使用 RoPE（旋转位置嵌入）来编码位置信息。RoPE 的核心思想是：将 token 的 query/key 向量视为复数，在位置 $m$ 的 query $q_m$ 和位置 $n$ 的 key $k_n$ 之间的内积，通过旋转角度 $\theta(m-n)$ 来编码相对距离：

$$\langle q_m, k_n \rangle = \text{Re}\left[\sum_i q_m^{(i)*} k_n^{(i)} e^{i(m-n)\theta_i}\right]$$

其中 $\theta_i$ 是第 $i$ 维的旋转频率，$e^{i(m-n)\theta_i}$ 是位置差 $(m-n)$ 引入的相位。

**关键性质：** 当 $|m-n|$ 很大时，$e^{i(m-n)\theta_i}$ 在不同维度上快速振荡，各维度的贡献相互抵消：

$$\sum_i q_m^{(i)*} k_n^{(i)} e^{i(m-n)\theta_i} \xrightarrow{|m-n| \to \infty} 0$$

这意味着 **位置距离越大，query-key 内积越趋向于零**，注意力权重（经过 Softmax 后）也相应降低。

对于一个 10000 token 的 context，中间位置（5000 token 处）的 chunk：
- 距离开头的 token：~5000 位置差 → RoPE 强衰减
- 距离结尾的 token：~5000 位置差 → RoPE 强衰减
- 结尾位置的 chunk 距离生成 token 近 → 衰减小 → 注意力强

**机制二：注意力汇聚效应（Attention Sink）**

Xiao et al.（2023，"Efficient Streaming Language Models with Attention Sinks"）发现：**某些特定位置的 token（尤其是序列最前面的 1-4 个 token）会吸收远超其语义价值的注意力权重**，这些 token 被称为"注意力汇聚（attention sink）"。

为什么会有注意力汇聚？Softmax 的归一化约束：

$$\text{softmax}(QK^T/\sqrt{d})_{ij} \geq 0, \quad \sum_j \text{softmax}(\cdot)_{ij} = 1$$

当模型在长上下文中对某个 token 不确定"应该关注哪里"时，注意力权重不能全部为零——它必须分配到某处。首 token（通常是特殊符号或起始词）成为"垃圾桶"——接收大量无语义内容的注意力权重。

**对"Lost in the Middle"的影响：**
- 首部 token 受益于注意力汇聚（sink attention）+ 语义注意力的双重加持
- 末尾 token 受益于 RoPE 距离近（衰减小）的优势
- 中间 token 只有语义注意力，两种优势都没有

```
注意力来源分析：

首部内容：   语义注意力 ✅ + Attention Sink ✅         → 高注意力
末尾内容：   语义注意力 ✅ + RoPE 近距离优势 ✅         → 高注意力
中间内容：   语义注意力 ✅ + Sink ❌ + 近距离 ❌         → 低注意力
```

这两个机制叠加，产生了 U 形的注意力曲线。

**训练数据偏置的叠加效应：**

除了上述两个机制性原因，训练数据中重要信息确实倾向于出现在文本的开头（摘要、导语）和结尾（结论、总结），模型在 RLHF 过程中进一步强化了对首尾的关注。这是第三层强化，与前两个机制共同作用。

---

**🔧 工程师**

### 【必须掌握】缓解策略：重要 chunk 放首尾

```python
def arrange_chunks_for_context(
    chunks: list[dict],
    rerank_scores: list[float],
) -> list[dict]:
    """
    将最相关的 chunk 放在 context 的首部和尾部，
    次要 chunk 放中间，缓解 Lost in the Middle 问题。
    """
    sorted_chunks = sorted(
        zip(chunks, rerank_scores),
        key=lambda x: x[1],
        reverse=True,
    )
    top_chunks = [c for c, _ in sorted_chunks]

    if len(top_chunks) <= 2:
        return top_chunks

    # 最相关放首位，第二相关放末位，其余放中间
    arranged = (
        [top_chunks[0]]   # 最相关：首部
        + top_chunks[2:]  # 其余：中间
        + [top_chunks[1]] # 第二相关：尾部
    )
    return arranged
```

### 另一种策略：倒序排列（Reverse）

部分实验表明，把 Rerank 结果**倒序**放入 context（最相关的放最后），效果反而比正序好——因为 LLM 生成时"刚读完"的内容影响更强：

```python
# 正序：最相关在前（通常做法）
context = "\n\n".join(chunk["content"] for chunk in reranked_chunks)

# 倒序：最相关在后（部分场景更好）
context = "\n\n".join(chunk["content"] for chunk in reversed(reranked_chunks))
```

实践建议：在评估集上 A/B 测试，两种都试。

---

**❓ 提问者**

如果 context 很长，比如塞了 10 个 chunk，Lost in the Middle 问题会很严重。但如果 chunk 数量少，比如只取 Top-3，又担心召回不全。有没有更根本的解法？

---

**🔬 研究员**

有两个更根本的方向：

**1. 长上下文模型（Long Context Models）**

GPT-4o（128K context）、Claude 3.5（200K context）的长 context 性能比早期模型好得多，Lost in the Middle 问题有所缓解，但并未完全消除——128K 中间段仍然比首尾弱。

**2. Contextual Compression（上下文压缩）**

不是把原始 chunk 塞进去，而是先用 LLM 把多个 chunk **压缩成一段精华摘要**再传给生成模型：

```
检索到的 5 个 chunk（2000 tokens）
  ↓ LLM 压缩
"根据以上文档，关于违约赔偿的核心内容是：..."（200 tokens）
  ↓
传给生成 LLM
```

代价是多一次 LLM 调用（延迟 + 成本），好处是：
- context 变短，Lost in the Middle 问题减轻
- 无关信息被过滤，生成质量提升
- 长文档的关键信息被提炼出来

LangChain 中有现成的 `ContextualCompressionRetriever` 实现。

---

← [第七章：评估](ch07-evaluation.md) | → [第九章：RAG 的失败模式](ch09-failure-modes.md)
