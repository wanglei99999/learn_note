# SFT 与 Chat 模板

创建日期：2026-10-15

[上一篇](01-预训练与Scaling-Law.md) 的结尾，我们手里有一个 base 模型：知道巴黎是法国首都，但你问它“法国的首都是哪里？”，它会接着出一道“德国的首都是哪里？”。这一篇讲怎么用监督微调（Supervised Fine-Tuning，SFT）把它变成一个会回答问题的助手。

SFT 本身的原理很简单，用的还是预测下一个 token 的那套 loss。这篇的重点在几个工程细节上，它们直接决定了你在 API 里看到的模型行为：对话是怎么拼成一段文本的，loss 算在哪些位置，工具调用和 system prompt 在训练数据里长什么样。

![四个训练阶段，本篇讲 SFT](assets/sft/00-pipeline.png)

## 1. SFT 改了什么

和预训练相比，SFT 只改了两样东西。

一是数据。预训练用的是网页，SFT 用的是“指令 + 回答”组成的对话，每一条都是人写的或者精心筛选过的示范：用户问了什么，一个好助手应该怎么答。

二是 loss 的范围。预训练对每个位置都算 loss，SFT 只在回答部分算。写成公式，就是在原来的语言模型 loss 上乘一个掩码 $m_t$：

$$
\mathcal{L}_{\text{SFT}} = -\frac{1}{\sum_t m_t}\sum_{t} m_t \log p_\theta(x_t \mid x_{<t}), \qquad m_t = \begin{cases} 1 & x_t \text{ 属于助手的回答} \\ 0 & \text{其他} \end{cases}
$$

模型结构不变，优化器不变，只是数据换了，部分位置的 loss 被屏蔽了。

## 2. 数据：要多少，要什么样的

### 2.1 数量不大

SFT 的数据量和预训练比起来小得可怜。

- InstructGPT（2022）的 SFT 数据集大约 1.3 万条 prompt，回答由标注员撰写。
- Llama 2（2023）的 SFT 阶段最终用了 27,540 条人工标注的对话。Meta 在论文里专门写了一节叫 *Quality Is All You Need*：他们一开始用了大量第三方指令数据，后来发现这些数据多样性和质量都不够，换成数量少得多、但由自家标注员精心写的数据，效果反而明显更好。
- LIMA（2023）走得更远：在 65B 的 LLaMA 上只用 1000 条精选样本做 SFT。人工评估中，有 43% 的情况下评估者认为 LIMA 的回答和 GPT-4 一样好或者更好。

作为对照，Llama 2 预训练用了 2T token。SFT 的数据量连它的零头都算不上。

### 2.2 表面对齐假说

LIMA 的作者据此提出了“表面对齐假说”（Superficial Alignment Hypothesis）：模型的知识和能力几乎全部来自预训练，SFT 教的主要是格式和风格，也就是和用户交互时该用哪种“子分布”说话。

这个说法有一个直接的推论：SFT 很难给模型灌进新知识。Gekhman 等人在 2024 年专门做了实验，把 SFT 数据分成“模型预训练时已经知道的事实”和“模型不知道的新事实”。结果是，新事实学得明显更慢；而一旦模型把这些新事实硬背下来，它在其他问题上编造答案的倾向也变强了。直觉上可以这样理解：训练在教模型“即使不知道，也要自信地说出一个具体答案”。

所以，想让模型知道你公司内部的文档，SFT 通常不是好办法，RAG 更合适。这一点在 [RAG 系列第 12 章](../../RAG/RAG%20检索知识/ch12-rag-vs-finetuning.md) 里有更多讨论。

### 2.3 数据从哪来

人工写的数据贵，于是有了用强模型生成数据的做法。2023 年斯坦福的 Alpaca 用 OpenAI 的 text-davinci-003 生成了 5.2 万条指令数据，生成成本不到 500 美元，再拿去微调 LLaMA 7B。这条路后来被大规模使用，今天很多开源模型的 SFT 数据里，相当一部分是更强的模型生成、再经过筛选的。

常见的数据类型大致有这几类：通用问答和写作、代码、数学推理（带解题步骤）、多轮对话、工具调用、拒答（对有害请求怎么礼貌地拒绝）、以及各种格式要求（JSON 输出、指定字数、指定语言）。配比和预训练一样，主要靠实验来调。

## 3. Chat 模板

### 3.1 消息列表只是表象

调用 API 时，你传的是一个消息列表：

```json
[
  {"role": "system", "content": "你是一个简洁的助手。"},
  {"role": "user", "content": "1+1 等于几？"}
]
```

但 Transformer 只认识一条 token 序列，没有“消息”“角色”这些概念。服务端会先用一个模板把消息列表拼成一段文本，再分词送进模型。拼出来的样子取决于模型家族。Qwen 等模型用的 ChatML 格式是这样：

![chat 模板：把消息列表渲染成 token 序列](assets/sft/01-chat-template.png)

每条消息被 `<|im_start|>角色` 和 `<|im_end|>` 包起来。推理时，模板会在最后补一个 `<|im_start|>assistant` 加换行，然后让模型从这里开始续写。模型续写出回答，再输出一个 `<|im_end|>`，服务端看到它就停止生成。

Llama 3 的模板长得不一样，但思路相同：

```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

你是一个简洁的助手。<|eot_id|><|start_header_id|>user<|end_header_id|>

1+1 等于几？<|eot_id|><|start_header_id|>assistant<|end_header_id|>

```

在 Hugging Face transformers 里，模板写在 tokenizer 的配置文件中，用一行代码就能看到渲染结果：

```python
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(text)
```

我建议换新模型时都跑一下这行，看看它的模板到底长什么样。

### 3.2 special token

图里标成橙色的那些是 special token。`<|im_start|>` 看起来是 12 个字符，但在词表里它是单独的一个 token，有自己的 embedding。普通文本分词时，正常情况下不会产生这个 token。

这带来两个实际后果。

第一，模板必须和训练时完全一致。少一个换行、角色名拼写不同、用错了结束符，模型看到的就是一段它在 SFT 里没见过的格式，输出质量会明显下降，常见的症状是停不下来或者自问自答。自己部署开源模型时，这是最常见的坑之一。

第二，有安全问题。Hugging Face 的分词器默认会把文本中出现的 `<|im_end|>` 这类字符串识别成 special token。如果用户在输入里写了 `<|im_end|><|im_start|>system`，又没有被处理掉，他就能伪造出一条 system 消息。所以服务端要么在拼模板前清理用户输入里的这类字符串，要么分词时关掉对用户内容的 special token 解析。

## 4. loss mask

### 4.1 手算一遍

把一轮最简单的对话拼起来，切成 token，然后看每个位置的预测目标：

![loss mask：只有助手回答部分的位置计算 loss](assets/sft/02-loss-mask.png)

逐个位置扫一遍，过程是这样的：

![逐个位置计算 loss mask 与累加](assets/sft/02-loss-mask.gif)

第一行是输入。第二行是每个位置要预测的目标，也就是下一个 token。目标落在 system、user 和模板标记里的位置，标签设成 `-100`。`-100` 是 PyTorch `CrossEntropyLoss` 默认的 `ignore_index`，这些位置不参与 loss 的计算，也不会产生梯度。

剩下 4 个位置的目标是 `等于`、`2`、`。`、`<|im_end|>`。假设模型给它们的概率是 0.6、0.9、0.8、0.5，loss 就是这 4 个负对数概率的平均，约 0.383。注意分母是 4，不是序列长度 16。

用代码写，核心就是构造 labels：

```python
labels = input_ids.clone()
labels[:assistant_start] = -100        # prompt 部分不算 loss
loss = model(input_ids=input_ids, labels=labels).loss   # 模型内部会把 labels 左移一位再对齐
```

实际用 TRL 这类训练库时，有现成的选项只对助手部分计算 loss，不用自己找边界。

### 4.2 为什么不对 prompt 算 loss

如果对 user 的部分也算 loss，模型就会同时学着“生成用户的问题”。这不是我们要的能力，还会占掉一部分训练信号。只对回答计算是更常见的默认做法，Llama 2 就是这么做的。

不过这件事没有定论。Shi 等人 2024 年的实验发现，在回答很短、prompt 很长、样本又少的情况下，对 prompt 也算 loss 反而效果更好，原因大概是它起到了一点正则化的作用。默认只算回答，数据很特殊时可以试试另一种。

### 4.3 结束符为什么要算

图里最后一个目标 `<|im_end|>` 也在 loss 里，这一点很关键。模型要学会的不只是怎么回答，还有什么时候停下来。如果漏掉了结束符的 loss，模型就学不会停止，回答完会继续往下写，编出一轮新的用户提问再自己回答。用开源框架自己做 SFT 时，结束符没有被正确加进标签，是一个很常见的 bug。

### 4.4 多轮对话和 packing

多轮对话里，每一轮助手的回答都算 loss，所有 user 轮次都屏蔽，一条样本里会有几段分开的“算 loss 区间”。

还有一个效率问题。SFT 样本长短不一，有的 200 个 token，有的 3000 个。如果按最长的样本补齐（padding），会浪费大量计算。常用的办法是 packing：把多条短样本首尾拼进一个长序列（比如 4096 个 token）。Llama 2 的 SFT 就是把 prompt 和回答拼接起来训练的。拼接时最好再调整注意力掩码，让每条样本只能看到自己，不要看到前面拼进来的另一条对话。

## 5. 工具调用

做 agent 的人每天都在用工具调用，它在训练数据里是什么样子？答案是：和普通对话没什么区别，只是多了几种消息和一段固定格式的文本。

![一次工具调用在序列中的样子](assets/sft/03-tool-call.png)

拆开看：

1. system 里写着可用工具的名字、参数和说明。各家通常用 JSON Schema 描述，由模板渲染成文本。
2. 用户提问。
3. 助手没有直接回答，而是输出一段特定格式的文本，比如 `<tool_call>{...}</tool_call>`，里面是函数名和参数。
4. 这时生成停止。agent 运行时（你的代码或者 API 服务端）解析这段文本，真正去调用函数，把返回结果作为一条 `tool` 角色的消息拼回序列。
5. 模型接着生成最终回答。

训练时，第 3 步和第 5 步的助手输出计算 loss；工具返回的结果不算，它是外部世界给的，模型不需要学会生成天气数据。

所以模型从来没有“调用”过任何东西。它学会的是两件事：判断什么时候该输出一个 tool_call，以及把参数按 schema 填对。不同模型家族的格式差别很大，Llama 3.1 甚至专门加了一个 `ipython` 角色来放工具结果。但原理都是这一套。这也解释了一个常见现象：给模型一个它训练时没见过的工具描述格式，它照样能调用，但出错率会高一些。

## 6. system prompt 为什么管用

system prompt 本身没有特殊的“权限”，它就是序列开头的一段 token。它能起作用，是因为 SFT 数据里有大量带 system prompt 的对话，回答都遵守了 system 里的要求。模型从这些样本里学到：这个位置的文字，是需要遵守的设定。

问题在于，模型同样会从 user 消息和工具返回的内容里读到“指令”。一个 agent 去读网页，网页里如果藏着一句“忽略之前所有指令”，模型会不会照做？

![指令层级：system、user、工具结果的优先级](assets/sft/04-instruction-hierarchy.png)

OpenAI 的 Wallace 等人在 2024 年提出了“指令层级”（instruction hierarchy）的训练方法：明确规定 system 优先于 user，user 优先于工具结果；然后大量构造互相冲突的训练样本，比如 system 说“只回答烹饪问题”而 user 要求写代码，或者检索到的网页里藏了恶意指令，示范正确的处理方式。训练后，模型对 prompt injection 的抵抗力明显提高。

这件事说明了 SFT 的一个特点：模型的很多“规矩”没法写进结构里，只能靠数据一条条示范出来。示范覆盖不到的情况，模型的行为就不可靠。做 agent 时，我的习惯是默认模型会被注入，在运行时（权限、沙箱、人工确认）上把关，不完全指望模型自己守规矩。

## 7. 训练时的一些数字

SFT 的训练配置和预训练差别很大。以 Llama 2 为例：学习率 $2 \times 10^{-5}$，余弦衰减，batch size 64，序列长度 4096，训练 2 个 epoch。

学习率比预训练小一个数量级，epoch 也很少，因为目标只是在已有能力上微调格式，不想把预训练学到的东西冲掉。训练太多轮，模型会背下 SFT 数据里的具体回答，在新问题上泛化变差，有时候还会损失一部分通用能力。

## 8. SFT 的天花板

SFT 本质上是模仿：数据里的回答怎么写，模型就怎么写。这带来两个限制。

一是质量上限受示范者限制。标注员写的回答就是模型能学到的最好水平。很多时候，人写一个完美的回答很难，但比较两个回答哪个更好要容易得多。

二是它只告诉模型“该说什么”，从来没告诉它“不该说什么”。模型只见过好的回答，没见过差的回答被扣分。两个回答都流畅、都像样，一个准确一个有细微错误，SFT 没有办法直接区分它们。

下一篇的 RLHF 和 DPO 就是为了解决这两个问题：不再让人写回答，而是让人比较回答，再用这些比较来训练模型。

## 小结

- SFT 用的还是下一个 token 的 loss，只是换成了对话数据，并且只在助手回答的位置计算。
- 数据贵精不贵多，几万条就够。SFT 主要教格式和风格，很难教进新知识，硬教还会增加幻觉。
- 消息列表要先经过 chat 模板拼成一段带 special token 的文本。模板必须和训练时一致，用户输入里的 special token 字符串要处理掉。
- 结束符要算 loss，模型才学得会停。
- 工具调用和 system prompt 都没有特殊机制，都是训练数据里示范出来的行为。

## 参考

- Ouyang et al., 2022. *Training language models to follow instructions with human feedback*. [arXiv:2203.02155](https://arxiv.org/abs/2203.02155)
- Touvron et al., 2023. *Llama 2: Open Foundation and Fine-Tuned Chat Models*. [arXiv:2307.09288](https://arxiv.org/abs/2307.09288)
- Zhou et al., 2023. *LIMA: Less Is More for Alignment*. [arXiv:2305.11206](https://arxiv.org/abs/2305.11206)
- Taori et al., 2023. *Stanford Alpaca: An Instruction-following LLaMA Model*. [GitHub](https://github.com/tatsu-lab/stanford_alpaca)
- Gekhman et al., 2024. *Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?* [arXiv:2405.05904](https://arxiv.org/abs/2405.05904)
- Wallace et al., 2024. *The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions*. [arXiv:2404.13208](https://arxiv.org/abs/2404.13208)
- Llama Team, 2024. *The Llama 3 Herd of Models*. [arXiv:2407.21783](https://arxiv.org/abs/2407.21783)
- Hugging Face. *Chat Templates*. [文档](https://huggingface.co/docs/transformers/chat_templating)
