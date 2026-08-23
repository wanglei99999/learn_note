> **译文** | 原文：[`packages/server/README.md`](https://github.com/earendil-works/pi/blob/main/packages/server/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# @earendil-works/pi-server

实验性功能。该包正在积极开发，可能随时更改或删除，恕不另行通知。其 API 和行为尚不稳定。

Pi 的服务端包。

## Session server 核心

该包导出 `PiServer` session server。

```ts
import type { PiServerService } from "@earendil-works/pi-server";
import { createUnixServer } from "@earendil-works/pi-server/unix";

const service: PiServerService = {
  async listSessions() {
    return storage.listSessions();
  },
  async listModels() {
    return modelRegistry.listModels();
  },
  async createSession(options) {
    return storage.createAndOpen(options);
  },
  async openSession(sessionId) {
    return storage.open(sessionId);
  },
};

const server = createUnixServer(service, {
  path: "/tmp/pi/server.sock",
});
await server.start();
```

`PiServer` 通过 `PiServerListener` 接口组合 transport listener。每个 listener 都必须先完成该 transport 特有的认证和授权，再把连接交给 `PiServer`。例如，WebSocket listener 可以在 HTTP upgrade 时验证凭据，Unix listener 则依赖 socket 的文件系统权限。Unix 子模块导出 `createUnixListener()` 构建块和 `createUnixServer()` 预设，让常见用法保持简洁，同时避免主 server 与 Unix socket 耦合。Listener 使用 `@earendil-works/pi-protocol` 中带长度前缀的 CBOR 消息。

该包不提供独立 CLI 或 coding-agent service。应用需要提供 `PiServerService` 实现。

`PiServerService.listSessions()` 返回协议的 `SessionMetadata`，而不是已获取的运行时状态。Service 应映射其存储支持的持久字段，可以省略 `updatedAt`、`parentSessionId`、`sessionName` 和 `cwd`。`PiServer` 从实时 snapshot 刷新可用元信息，不要求存储的 session 伪造 phase、model、thinking level、attachment 或 lock 值。

## Transport 测试

自定义 transport 可以使用 `@earendil-works/pi-server/testing` 进行确定性的协议一致性测试。它导出 `createTestServer()`、`TestServerService`、`ProtocolTestClient` 和与 transport 无关的 `WireChannel` 契约。Unix transport 测试还可使用 `connectUnixTestClient()`。

## `pi-ai` 协议桥接

`@earendil-works/pi-ai` 领域对象与 `@earendil-works/pi-protocol` wire DTO 相互独立。该包负责两者的边界，并导出 `toProtocolModelMetadata()`、`toProtocolAssistantMessage()`、`toProtocolUserMessage()` 和 `toProtocolToolResultMessage()`。

Adapter 会拒绝无效工具输入、标识符、时间戳和不匹配的工具结果；`toProtocolToolResultMessage()` 要求提供原始 `ToolCall`，以便验证关联并自行转换参数。诊断细节会被显式清理。封闭的 `pi-ai` union 会被穷尽映射，编译期字段清单会枚举当前 `pi-ai` 属性，因此新增属性必须经过显式审查。在语义相同时，协议沿用 `pi-ai` 的 `toolCall` 和 `toolUse` 等词汇。协议 schema 强制生命周期状态保持一致；测试会用运行时 schema 编码 adapter 输出，因此不兼容变更会在桥接包中失败。
