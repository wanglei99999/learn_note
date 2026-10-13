# 深度学习

深度学习原理笔记，按主题分为两类。每类目录下的 `assets/` 存放配图，配图源码在各自的 `src/` 中。

---

## Transformer 与大模型

从一个 attention 的计算讲起，到完整的 Transformer 结构，再到生成时的 KV Cache。三篇按顺序读，后一篇以前一篇为基础。

| 顺序 | 笔记 | 核心内容 |
|------|------|---------|
| 1 | [Attention 与 QKV 入门](Transformer与大模型/01-Attention与QKV入门.md) | 词向量、点积、softmax；为什么要分成 Q、K、V 三个向量；手算"它 → 猫"；矩阵形式、$\sqrt{d}$ 缩放与因果 mask |
| 2 | [Transformer 结构详解](Transformer与大模型/02-Transformer结构详解.md) | 沿一次前向传播讲 tokenizer、embedding、RoPE、多头注意力、残差流、RMSNorm 与 Pre-Norm、SwiGLU FFN、LM head 与采样、训练目标、三种架构、Llama-2-7B 参数拆分 |
| 3 | [KV Cache 与 Attention QKV 的关系](Transformer与大模型/03-KV-Cache与Attention-QKV.md) | MHA / GQA / MQA、因果注意力为什么让缓存成立、为什么只缓存 K 和 V、缓存大小估算与部署影响、主流优化方法 |

几篇之间有少量重叠：

- 第 3 篇的第 1 节"从 QKV 开始"是第 1 篇的浓缩版。读过第 1 篇，可以从第 3 篇的第 2 节读起。
- 第 2 篇的 5.2 节简要介绍了多头和 GQA，第 3 篇的第 2 节讲得更细，并配有 MHA / GQA / MQA 对比图。

只关心推理部署，想知道 KV Cache 为什么是关键指标，可以直接读第 3 篇；遇到 QKV 和多头的概念再回到第 1、2 篇。

---

## 生成模型与数据几何

| 笔记 | 核心内容 |
|------|---------|
| [从流形假说到深度学习](生成模型与数据几何/从流形假说到深度学习.md) | 流形假说与内在维数、维度灾难、分层空间；分布距离为什么会失去方向信息（JS 与 Wasserstein）；加噪与 score；扩散模型、Flow Matching 与潜空间扩散 |

---

← [返回上级目录](../)
