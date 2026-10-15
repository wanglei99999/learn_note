# 深度学习

深度学习原理笔记，按主题分为四类。每类目录下的 `assets/` 存放配图，配图源码在 `assets/` 下的 `src/` 中。

---

## 神经网络基础

网络怎么搭、怎么学。三篇按顺序读，Transformer 系列里用到的激活函数、交叉熵、残差连接、AdamW、归一化，都在这里讲清楚。

| 顺序 | 笔记 | 核心内容 |
|------|------|---------|
| 1 | [线性层与激活函数](神经网络基础/01-线性层与激活函数.md) | 线性层与矩阵乘法；为什么必须有非线性（XOR 手算）；sigmoid、tanh、ReLU、GELU、SiLU 的形状与导数；门控：GLU 到 SwiGLU |
| 2 | [损失函数与反向传播](神经网络基础/02-损失函数与反向传播.md) | 均方误差与交叉熵，为什么分类不用 MSE；语言模型损失与困惑度；手算反向传播、矩阵形式、6N 估算；梯度消失与爆炸、初始化、残差连接 |
| 3 | [优化器与训练技巧](神经网络基础/03-优化器与训练技巧.md) | SGD 与学习率上限；动量、Adam、AdamW；预热与余弦衰减；LayerNorm/RMSNorm、Pre-Norm 与残差流尺度问题；Llama 2 的训练配置 |

---

## Transformer 与大模型

从一个 attention 的计算讲起，到完整的 Transformer 结构，再到生成时的 KV Cache。前三篇按顺序读，后一篇以前一篇为基础；第 4 篇是 encoder-decoder 结构的专题，读完第 2 篇即可读。

| 顺序 | 笔记 | 核心内容 |
|------|------|---------|
| 1 | [Attention 与 QKV 入门](Transformer与大模型/01-Attention与QKV入门.md) | 词向量、点积、softmax；为什么要分成 Q、K、V 三个向量；手算"它 → 猫"；矩阵形式、$\sqrt{d}$ 缩放与因果 mask |
| 2 | [Transformer 结构详解](Transformer与大模型/02-Transformer结构详解.md) | 沿一次前向传播讲 tokenizer、embedding、RoPE、多头注意力、残差流、RMSNorm 与 Pre-Norm、SwiGLU FFN、LM head 与采样、训练目标、三种架构、Llama-2-7B 参数拆分 |
| 3 | [KV Cache 与 Attention QKV 的关系](Transformer与大模型/03-KV-Cache与Attention-QKV.md) | MHA / GQA / MQA、因果注意力为什么让缓存成立、为什么只缓存 K 和 V、缓存大小估算与部署影响、主流优化方法 |
| 4 | [Encoder-Decoder 与交叉注意力](Transformer与大模型/04-Encoder-Decoder与交叉注意力.md) | 编码器与解码器的分工；交叉注意力的 Q、K、V 来源与手算；teacher forcing、编码器只跑一次、两种 KV Cache；BERT 的 MLM、T5 的 span corruption、BART；与 decoder-only 的比较，Whisper、Stable Diffusion 中的应用 |

几篇之间有少量重叠：

- 第 3 篇的第 1 节"从 QKV 开始"是第 1 篇的浓缩版。读过第 1 篇，可以从第 3 篇的第 2 节读起。
- 第 2 篇的 5.2 节简要介绍了多头和 GQA，第 3 篇的第 2 节讲得更细，并配有 MHA / GQA / MQA 对比图。

只关心推理部署，想知道 KV Cache 为什么是关键指标，可以直接读第 3 篇；遇到 QKV 和多头的概念再回到第 1、2 篇。vLLM、量化、多卡并行等工程内容在 [LLM部署](../LLM部署/大模型推理与昇腾部署学习笔记.md) 中。

---

## 大模型训练

Transformer 系列讲的是模型怎么算，这一类讲权重是怎么训练出来的：一个只会续写文本的预训练模型，经过哪些步骤变成能听指令、按模板对话、调用工具、多步推理的助手。建议读完 Transformer 系列第 2 篇再读，按顺序读。配图源码在 `大模型训练/assets/src/`，风格与前两类不同，用的是 Anthropic 风格。

| 顺序 | 笔记 | 核心内容 |
|------|------|---------|
| 1 | [预训练与 Scaling Law](大模型训练/01-预训练与Scaling-Law.md) | Common Crawl 的清洗流程与 LLaMA 数据配比；$C pprox 6ND$ 与 MFU 手算；Kaplan 幂律、Chinchilla IsoFLOP 与“每参数 20 token”；为什么现在的小模型都训过头；base 模型能做什么 |
| 2 | [SFT 与 Chat 模板](大模型训练/02-SFT与Chat模板.md) | SFT 数据的规模与表面对齐假说；ChatML 与 special token；loss mask 手算、结束符为什么要算 loss；工具调用在序列里的样子；system prompt 与指令层级 |
| 3 | [RLHF 与 DPO](大模型训练/03-RLHF与DPO.md) | InstructGPT 三步；Bradley–Terry 奖励模型；PPO 的四个模型；β 与 KL 约束的数值例子、过度优化、变长与谄媚；DPO 推导与手算；Constitutional AI |
| 4 | [推理模型与强化学习](大模型训练/04-推理模型与强化学习.md) | 可验证奖励与只看结果；GRPO 组内优势手算、DAPO 的改进；DeepSeek-R1-Zero 与 R1 的训练流程、蒸馏；test-time compute、pass@k 与 RL 的能力边界；思考过程是否可信 |
| 5 | [LoRA 与参数高效微调](大模型训练/05-LoRA与参数高效微调.md) | 全参数微调的显存账；内在维度；LoRA 结构、秩 1 手算与参数量计算；QLoRA；多 LoRA 部署；LoRA 与全参数微调的差距；何时微调、何时 RAG |

第 5 篇和前四篇相对独立，读完第 2 篇就能读。"微调还是 RAG"的取舍在 [RAG 系列第 12 章](../RAG/RAG%20检索知识/ch12-rag-vs-finetuning.md) 中也有讨论。

---

## 生成模型与数据几何

| 笔记 | 核心内容 |
|------|---------|
| [从流形假说到深度学习](生成模型与数据几何/从流形假说到深度学习.md) | 流形假说与内在维数、维度灾难、分层空间；分布距离为什么会失去方向信息（JS 与 Wasserstein）；加噪与 score；扩散模型、Flow Matching 与潜空间扩散 |

---

← [返回上级目录](../)
