> **译文** | 原文：[`packages/protocol/README.md`](https://github.com/earendil-works/pi/blob/main/packages/protocol/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# @earendil-works/pi-protocol

实验性 pi 协议的 runtime-neutral schema、类型、CBOR 编码和字节流帧格式。

协议版本 `1` 使用二进制消息，wire layout 如下：

1. 四字节无符号大端 payload 长度。
2. 一个包含消息、长度确定的 CBOR item。

客户端第一条消息始终是包含 `PROTOCOL_VERSION` 的 `hello`。后续消息使用相互关联的请求/响应 envelope 和服务端 event envelope。Session 与服务端 snapshot 是权威状态。Progress event 只是瞬时 UI 提示，不能归并进权威状态。Transport 在交换协议字节前完成认证。

Session 列表包含 `SessionMetadata`，即无需获取 session runtime 就能访问的规范化持久元信息。只有 `id` 和 `createdAt` 是必填字段；底层存储支持时还会包含 `updatedAt`、`parentSessionId`、`sessionName` 和 `cwd`。Phase、model、thinking level、attachment 和 lock 等运行时状态只会出现在已经获取的 `SessionSnapshot` 中。

## 验证过的消息 API

`encodeClientMessage()` 和 `encodeServerMessage()` 会验证消息并返回完整的 framed `Uint8Array`。增量 decoder 接受任意分片或合并，因此适用于 stream、socket 和自定义字节 transport。

```ts
import {
  PROTOCOL_VERSION,
  createServerMessageDecoder,
  encodeClientMessage,
  type ClientHello,
} from "@earendil-works/pi-protocol";

const hello: ClientHello = {
  type: "hello",
  version: PROTOCOL_VERSION,
};

transport.send(encodeClientMessage(hello));

const decoder = createServerMessageDecoder({ maxFrameLength: 1024 * 1024 });
for (const message of decoder.push(incomingChunk)) {
  handleServerMessage(message);
}
decoder.end(); // 字节流关闭时调用，以检测截断。
```

也可以直接使用 `ClientMessageDecoder` 和 `ServerMessageDecoder`。Schema 违规、畸形 CBOR 和无效帧格式会抛出 `ProtocolValidationError`。验证错误不会保留被拒绝的 payload。

`parseClientMessage()` 和 `parseServerMessage()` 只验证已经解码的值，不解析 JSON 字符串。

## Transport 支持

所有 transport 都承载相同的完整字节：`[uint32-be CBOR length][CBOR payload]`。Transport 可以任意拆分或合并这些字节。

该包不内置 transport。使用者需要提供保持字节顺序并报告 stream 关闭的字节流 transport。自定义 transport 必须处理任意 frame 分片和合并。

所有 transport 都是不可信的。配置一致的 frame 限制，并在向协议暴露连接前实施适合该 transport 的访问控制。Unix socket 可以使用文件系统权限，网络 transport 可以在建立连接时认证。

## 编码与帧格式

`encodeCbor()` 和 `decodeCbor()` 实现协议所用的严格 RFC 8949 子集。`encodeFrame()` 和 `FrameDecoder` 独立于 schema 与 CBOR 处理帧格式。

CBOR 子集支持：

- `null` 和布尔值
- 有限数值；整数限制在 JavaScript 安全范围内，非整数编码为 float64
- UTF-8 字符串
- `Uint8Array` 字节字符串
- 长度确定的数组
- 由具有唯一字符串 key 的对象表示、长度确定的 map

未定义的对象属性会被省略。JSON 值类型的协议字段会拒绝 CBOR 字节字符串和非 plain object。顶层 undefined、数组中的 undefined、稀疏数组、非有限数值或非安全数值、tag、长度不确定的 item、畸形 UTF-8、尾随数据、过深嵌套和过大值都会被拒绝。

默认限制为每个 CBOR payload/frame 16 MiB、1,000,000 个数组元素或 map entry，以及 64 层 item 嵌套。可以通过选项配置这些限制。Frame decoder 会在缓冲 payload 字节前验证声明的长度。

所有 schema 都拒绝未知对象属性。该协议仍处于实验阶段，不提供兼容性保证。
