> **译文** | 原文：[`packages/coding-agent/docs/containerization.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/containerization.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

# 容器化

Pi 默认以完整权限运行，但在某些场景下，你会希望更精细地控制 Pi 能写入哪些目录、拥有哪些访问权限。

总体上有两种选择。你可以：
1. 把整个 `pi` 进程放在隔离环境中运行，或者
2. 在宿主机上运行 `pi`，把工具的执行路由到隔离环境中。

## 选择模式

| 模式 | 隔离的内容 | 适用场景 | 备注 |
| --- | --- | --- | --- |
| Gondolin extension | 内置工具与 `!` 命令 | 本地 micro-VM 隔离，同时把认证保留在宿主机 | 参见 [`examples/extensions/gondolin/`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/gondolin/)。 |
| 纯 Docker | 整个 `pi` 进程在本地容器中 | 简单的本地隔离 | Provider API key 会进入容器。 |
| OpenShell | 整个 `pi` 进程在策略控制型沙箱中 | 本地或远程的托管沙箱 | 需要一个 OpenShell 网关 |

Extension 在 `pi` 进程所在的地方运行。如果你在宿主机上运行带工具路由 extension 的 `pi`，其它自定义 extension 工具仍会在宿主机上运行，除非它们也把自己的操作委托出去。

## Gondolin

[Gondolin](https://github.com/earendil-works/gondolin) 是一个本地 Linux micro-VM。
当你想让 `pi` 留在宿主机、但所有内置工具都路由进 VM 时，使用这个[示例 extension](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/gondolin)。

配置：

```bash
cp -R packages/coding-agent/examples/extensions/gondolin ~/.pi/agent/extensions/gondolin
cd ~/.pi/agent/extensions/gondolin
npm install --ignore-scripts
```

在你希望被挂载的项目目录中运行：

```bash
cd /path/to/project
pi -e ~/.pi/agent/extensions/gondolin
```

该 extension 把宿主机当前工作目录挂载到 VM 内的 `/workspace`，并覆盖 `read`、`write`、`edit`、`bash`、`grep`、`find` 和 `ls`。
用户的 `!` 命令同样会被路由进 VM。
`/workspace` 下的文件改动会直接写穿到宿主机。

要求：`@earendil-works/gondolin` 需要 Node.js >= 23.6.0，另外需要 QEMU（须通过你的包管理器安装）。

## 纯 Docker

当你想要最简单的本地容器边界时，把整个 `pi` 进程放进 Docker 运行。

`Dockerfile.pi`：

```dockerfile
FROM node:24-bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends bash ca-certificates git ripgrep \
  && rm -rf /var/lib/apt/lists/*
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent

WORKDIR /workspace
ENTRYPOINT ["pi"]
```

构建并运行：

```bash
docker build -t pi-sandbox -f Dockerfile.pi .

docker run --rm -it \
  -e ANTHROPIC_API_KEY \
  -v "$PWD:/workspace" \
  -v pi-agent-home:/root/.pi/agent \
  pi-sandbox
```

`-v "$PWD:/workspace"` 把你的当前目录挂载到容器内的 /workspace，因此 Docker 内对 `/workspace` 的读写会直接作用于宿主机文件，与 Gondolin 示例中一样。

如果想要容器本地的设置与 session，请为 `/root/.pi/agent` 使用命名卷。挂载宿主机的 `~/.pi/agent` 会把宿主机的认证与 session 文件暴露给容器。

## OpenShell

当你需要一个带文件系统、进程、网络、凭据与推理管控的策略控制型沙箱时，使用 [NVIDIA OpenShell](https://docs.nvidia.com/openshell/about/overview)。
OpenShell 可以通过由 Docker、Podman 或 VM 运行时支撑的本地网关运行沙箱，也可以通过远程 Kubernetes 网关运行。

每个沙箱都需要一个处于活动状态的网关。
在创建沙箱之前先注册并选择一个：

```bash
openshell gateway add <gateway-url> --name <name>
openshell gateway select <name>
```

在 OpenShell 沙箱中启动 `pi`：

```bash
openshell sandbox create --name pi-sandbox --from pi -- pi
```

在这种模式下，整个 `pi` 进程都运行在沙箱内。
内置工具、`!` 命令以及 extension 工具都在 OpenShell 边界内执行。

如果网关是远程的，项目文件不会从宿主机 bind-mount，也就是说沙箱内的写入不会反映到你的机器上。
请在沙箱内克隆仓库，或使用 OpenShell 的文件传输命令：

```bash
openshell sandbox upload pi-sandbox ./repo /workspace
openshell sandbox download pi-sandbox /workspace/repo ./repo-out
```

OpenShell provider 可以把原始的模型 API key 留在沙箱之外。
配置了推理路由后，沙箱内的代码可以调用 `https://inference.local`，由网关向上游注入所配置的 provider 凭据。
如果希望模型流量走这条路由，请把 Pi 配置为使用对应的 OpenAI 兼容或 Anthropic 兼容端点。
