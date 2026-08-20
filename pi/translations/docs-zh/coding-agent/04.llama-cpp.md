> **译文** | 原文：[`packages/coding-agent/docs/llama-cpp.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/llama-cpp.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# llama.cpp

Pi 支持 [llama.cpp](https://github.com/ggml-org/llama.cpp) 的路由器（router）服务器。路由器会发现多个 GGUF 模型，并按需加载或卸载它们。

请使用带路由器支持的最新版 llama.cpp。按照[构建说明](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)编译，或为你的平台安装[预构建发布版](https://github.com/ggml-org/llama.cpp/releases)。

## 启动路由器

启动 `llama-server` 时不要带 `--model` 或 `-m`。传入模型会进入单模型模式而不是路由器模式。

```bash
llama-server \
  --models-dir ~/models \
  --no-models-autoload \
  --jinja \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl 999 \
  -c 32768
```

重要选项：

- `--models-dir ~/models` 发现本地的 GGUF 文件。
- `--no-models-autoload` 让加载动作只通过 `/llama` 显式进行。
- `--jinja` 启用兼容的聊天模板与工具调用。
- `-ngl 999` 尽可能多地把层卸载到 GPU 上。
- `-c 32768` 设置每个已加载模型的上下文窗口。省略则使用模型的原生上下文，这可能需要多得多的内存。

单文件模型可以直接放在模型目录中。多模态与多分片模型放到各自的子目录里：

```text
~/models/
├── llama-3.2-1b-Q4_K_M.gguf
├── gemma-3-4b-it-Q4_K_M/
│   ├── gemma-3-4b-it-Q4_K_M.gguf
│   └── mmproj-F16.gguf
└── large-model-Q4_K_M/
    ├── large-model-Q4_K_M-00001-of-00003.gguf
    ├── large-model-Q4_K_M-00002-of-00003.gguf
    └── large-model-Q4_K_M-00003-of-00003.gguf
```

手动添加文件后需要重启路由器。要为每个模型设置上下文大小及其它选项，请使用 [llama.cpp 模型预设](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#model-presets)。

## 配置 Pi

启动 Pi 并配置该 provider：

```text
/login llama.cpp
```

输入路由器 URL 和可选的 API key。默认 URL 是 `http://127.0.0.1:8080`。

同样的值也可以通过环境变量配置，无需 `/login`：

```bash
export LLAMA_BASE_URL=http://127.0.0.1:8080
export LLAMA_API_KEY=optional-secret
pi
```

如果服务器使用 API key，启动 `llama-server` 时要带上匹配的 `--api-key` 值。保持 `--host 127.0.0.1` 以限制仅本机访问。

## 管理模型

运行：

```text
/llama
```

- 选择一个未加载的模型即可加载它。
- 选择一个已加载的模型即可卸载它。
- 选择 **Download model…**，搜索 Hugging Face，然后选择仓库与量化版本。也可以直接输入精确的 `owner/repository[:quant]`。
- 在加载或下载过程中按 Escape 可确认取消。

Hugging Face 搜索优先使用已设置的 `HF_TOKEN`，然后依次检查 `$HF_TOKEN_PATH`、`$HF_HOME/token`、`$XDG_CACHE_HOME/huggingface/token` 和 `~/.cache/huggingface/token`。不认证也可以搜索，但会受到更低的速率限制。下载受限（gated）仓库前 Pi 会发出警告并给出其访问申请页面的链接。下载由 llama.cpp 服务器执行，因此当所选仓库需要访问权限时，该服务器进程也必须有 `HF_TOKEN`。

如果已有其它模型处于加载状态，Pi 会询问是先卸载它们还是保持加载。Pi 不会悄悄卸载模型，也绝不会删除模型文件。路由器可能被其它客户端共享，因此 `/llama` 总是显示路由器的当前状态。

只有已加载的模型才会出现在 `/model` 中。加载模型后，运行 `/model` 将其选为当前 Pi session 的模型。

如果路由器断开连接，`/llama` 会显示 **Retry** 和 **Close**。Retry 会重新连接并刷新模型状态，但不会重放被中断的操作。

## 故障排查

检查路由器是否可达：

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/models
```

- **`/llama` 中没有模型：** 检查 `--models-dir` 和目录布局，然后重启路由器。
- **`/model` 中缺少某个模型：** 先用 `/llama` 加载它。
- **加载失败或占用内存过多：** 调低 `-c`，或卸载另一个模型。
- **服务器不在路由器模式：** 启动时不要带 `--model`、`-m` 或 `-hf`。
