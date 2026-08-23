> **译文** | 原文：[`packages/client/README.md`](https://github.com/earendil-works/pi/blob/main/packages/client/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# @earendil-works/pi-client

用于远程 pi session、与传输方式无关的客户端。`PiClient` 通过精简的 `ByteTransport` 接口交换带长度前缀的 CBOR 消息。该包不包含 Node 专用 import。

```ts
import { PiClient, type ByteTransportFactory } from "@earendil-works/pi-client";

const transportFactory: ByteTransportFactory = async (handlers) => {
  // 使用 WebSocket、Unix socket 或其他有序字节传输建立连接。
  return {
    async send(chunk) {
      // 按调用顺序发送数据块，并遵守背压。
    },
    close() {},
  };
};

const client = new PiClient({ transportFactory });
await client.connect();
const session = await client.createSession({ cwd: "/workspace" });
const unsubscribe = session.subscribe((snapshot) => render(snapshot));
await session.prompt("Inspect this project");
unsubscribe();
```

收到字节时调用 `handlers.onData(chunk)`，连接正常终止时调用 `handlers.onClose()`，传输失败时调用 `handlers.onError(error)`。每次尝试连接时，工厂都必须创建新的 transport，并在 resolve 前完成该 transport 特有的认证。例如，WebSocket 工厂可以在 upgrade 请求中提供凭据。

`PiClient` 不会自动重连。断开后请调用 `reconnect()`。一个连接可以 attach 多个 session。请求通过 ID 关联。服务端 snapshot 和成功响应中的 snapshot 是权威状态；progress event 不会以乐观方式修改 snapshot 状态。从 `client.snapshot?.sessions` 读取缓存的 session 元信息；调用 `listSessions()` 向服务端请求刷新后的持久化元信息。获取 session 后才能访问运行时状态。

`acquireSession()` 返回独立的 `SessionLease`；lease 不能直接构造。生命周期或变更协调器使用 `{ mode: "exclusive" }`；多个底层消费者有意共享 session 时使用 `{ mode: "shared" }`。只要存在任意 lease，独占获取就会以 `PiSessionOwnershipError` 失败；存在独占 lease 时，共享获取也会失败。`attachSession()` 是共享获取的便捷方法。`createSession()` 为新建 session 返回独占 lease。

调用 `dispose()` 或 `detach()` 只释放当前 lease。释放一开始，该 lease 就会拒绝命令。最后一个 lease 释放后，客户端会发送协议 detach 请求。如果显式 `detach()` 失败，lease 会恢复为活动状态以便重试。如果面向清理的 `dispose()` 失败，它会报告协议错误但放弃本地所有权；下次获取前，`PiClient` 会协调这次失败的协议清理。已释放的 lease 不再可用，但不会影响其他共享 lease。服务端删除 session 或断开连接时，该 attachment 的所有 lease 都会失效；dispose 已失效的 lease 不执行任何操作。客户端断开时，命令以 `PiDisconnectedError` 失败；客户端已连接但 lease 正在释放、已经释放或已经失效时，命令以 `PiSessionDetachedError` 失败。Lease 实现了 `AsyncDisposable`。

`subscribe()` 观察权威 snapshot。`onEvent()` 观察协议 event。两者都返回取消订阅函数。服务端返回的结构化错误以 `PiServerError` 暴露。

## 限制与安全

`PiClientOptions.maxFrameLength` 限制入站和出站 CBOR payload 的大小。客户端与服务端应配置相同的限制。Transport 还应单独限制排队的出站字节数，并保持发送顺序。

应将对端视为不可信。使用具备适当访问控制的安全传输，并在建立 transport 时完成认证。

订阅者抛出的异常与协议状态隔离。通过 `PiClientOptions` 的 `onListenerError` 将异常报告给应用日志或诊断系统。

## Unix-domain socket

Node.js 和 Bun 使用者可以使用单独导出的 Unix-domain socket transport：

```ts
import { PiClient } from "@earendil-works/pi-client";
import { createUnixTransportFactory } from "@earendil-works/pi-client/unix";

const client = new PiClient({
  transportFactory: createUnixTransportFactory({
    path: "/tmp/pi.sock",
  }),
});

await client.connect();
```

`maxPendingBytes` 限制排队的出站数据量，默认为协议 frame 限制的四倍。该 transport 保持发送顺序，并在每次 send resolve 前等待 socket 背压解除。

`@earendil-works/pi-client` 根入口保持与 transport 和 runtime 无关。导入兼容 Node 的 transport 时，必须显式使用 `@earendil-works/pi-client/unix` 子路径。
