> **译文** | 原文：[`packages/session-backends/sqlite-node/README.md`](https://github.com/earendil-works/pi/blob/main/packages/session-backends/sqlite-node/README.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-23

# @earendil-works/pi-session-backend-sqlite-node

用于 `@earendil-works/pi-agent-core` session 的 Node SQLite backend。提供 `node:sqlite` adapter（`SqliteDatabase` 实现）、SQLite session repository、migration、materialized view，以及可选的 FTS search。

```ts
await using repository = new SqliteSessionRepository(options);
const search = createSqliteSessionSearch(options);
const session = await repository.create({ cwd });
await session.appendMessage(message);

const hits = [];
for await (const hit of search.search("needle")) hits.push(hit);
```

Repository 惰性持有一个共享 database connection。Search 是作用于同一 canonical database 的独立 service：repository 不暴露 `search()`。FTS table 和 trigger 在第一次非空 search 时惰性创建；首次创建 FTS 时，search 会从 canonical entry 执行一次 rebuild。之后，SQLite trigger 会让 FTS 与 canonical entry 的 insert、delete 和 payload update 保持同步。
