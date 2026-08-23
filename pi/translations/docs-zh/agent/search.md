> **译文** | 原文：[`packages/agent/docs/search.md`](https://github.com/earendil-works/pi/blob/main/packages/agent/docs/search.md) · 版本：v0.84.2（`5cd93f688`）· 译于 2026-08-21

# Session 搜索

Pi search 是针对已提交 session entry 的精简查询接口。共享契约只返回稳定的命中标识；实现可以使用后端专用的显示数据扩展命中结果。

## 核心 API

```ts
export interface SessionSearchHit {
  /** 拥有该 entry 的 session 逻辑标识符。 */
  readonly sessionId: string;

  /** 该 entry 在 session 内的逻辑标识符。 */
  readonly entryId: string;
}

export interface SessionSearchOptions {
  /** 将结果限制为指定的规范 entry 类型。 */
  readonly entryTypes?: readonly Entry["type"][];

  /** 最大返回命中数。后端可以少返回，但不能多返回。 */
  readonly limit?: number;

  /** 用于取消的 abort signal，例如边输入边搜索。 */
  readonly signal?: AbortSignal;
}

export interface SessionSearch<T extends SessionSearchHit = SessionSearchHit> {
  search(text: string, options?: SessionSearchOptions): AsyncIterable<T>;
}
```

基础命中有意保持最小化：`(sessionId, entryId)` 是 JSONL、memory、SQLite FTS 和远程索引之间可移植的标识。Snippet、时间戳、分数、元信息、offset 和排名语义由具体实现负责。

## 为什么使用 async iterable

`AsyncIterable` 允许使用者尽早渲染结果，在结果足够时停止迭代，并通过 `AbortSignal` 取消进行中的工作。Debounce 仍由 UI/调用方负责；API 只提供取消原语。

```ts
let currentAbortController: AbortController | undefined;

async function updateResults(query: string) {
  currentAbortController?.abort();
  const controller = new AbortController();
  currentAbortController = controller;

  try {
    for await (const hit of search.search(query, { limit: 10, signal: controller.signal })) {
      render(hit);
    }
  } catch (error) {
    if (!(error instanceof Error) || error.name !== "AbortError") throw error;
  }
}
```

## 默认实现

### 扫描搜索

可复用 scanner 将类似 session 的 readable（`getMetadata`、`findEntries` 和 `getLabel`）适配为投影 entry：

```ts
export interface SessionSearchCandidate {
  readonly entryId: string;
  readonly seq: number;
  readonly type: Entry["type"];
  readonly timestamp: number;
  readonly text: string;
  readonly fields?: Record<string, unknown>;
}

export interface ScanningSessionSearchHit extends SessionSearchHit {
  readonly timestamp: number;
  readonly snippet: string;
}
```

`SessionSearchCandidate` 是匹配前的 scanner 输入：它包含可搜索文本、类型、序列和可选投影字段。Scanner 将匹配的 candidate 转换为公开命中结果。

已经打开的 session 或 storage 可以直接扫描：

```ts
const search = createScanningSessionSearch(sessions);

for await (const hit of search.search("authentication", { limit: 10 })) {
  const session = sessionsById.get(hit.sessionId)!;
  const entry = await session.getEntry(hit.entryId);
  console.log(entry);
}
```

JSONL 不需要单独的公开 search adapter。基于 JSONL 的代码可以在本地完成发现/加载，再把加载的 storage 传给同一个 scanner：

```ts
async function* jsonlReadables(jsonl: JsonlSessionRepoOptions, query: JsonlSessionListOptions = {}) {
  for (const metadata of await listJsonlSessionMetadata(jsonl, query)) {
    yield loadJsonlSessionStorage(jsonl, metadata);
  }
}

const search = createScanningSessionSearch((query) => jsonlReadables(jsonl, query));
```

如果在 harness 拥有的 session 上调用 `SessionRepo.open()` 可能取得 writer lease，扫描源就不得调用它。JSONL 应使用只读加载 helper；已经打开的 session/storage 可以直接扫描。

### SQLite FTS

SQLite search 暴露扩展命中结果：

```ts
export interface SqliteSessionSearchHit extends SessionSearchHit {
  readonly metadata: SqliteSessionMetadata;
  readonly timestamp: number;
  readonly score: number;
}
```

```ts
const search = createSqliteSessionSearch({ env, sqlite, databasePath });

for await (const hit of search.search("auth", {
  entryTypes: ["message", "compaction"],
  limit: 20,
})) {
  console.log(hit.sessionId, hit.entryId, hit.score);
}
```

FTS 表和 trigger 会在首次非空白搜索时惰性创建。首次创建 FTS 时，SQLite 会从规范 `entries` 执行一次性 rebuild；之后由 SQLite trigger 让 FTS 与规范 entry 的插入、删除和 payload 更新保持同步。这样 SQLite 搜索会在 commit 后立即更新，但也意味着对该数据库启用 search 后，FTS trigger 失败可能回滚规范 SQLite 写入。

## 索引后端

Search 索引是由后端拥有的派生状态。共享包只导出查询 API；需要显式维护索引时，应用或后端包可以定义自己的 writer/feed 契约。

### 使用 Elasticsearch 的 JSONL session

这是由应用拥有的 glue code。Core 提供查询契约和 JSONL session 发现；Elastic writer 契约只属于该 adapter。

```ts
import { Client } from "@elastic/elasticsearch";
import {
  scanningEntries,
  type JsonlSessionMetadata,
  type JsonlSessionRepoOptions,
  type SessionSearch,
  type SessionSearchHit,
  type SessionSearchOptions,
} from "@earendil-works/pi-agent-core";

// 基于 JSONL 的代码可以用现有 JSONL list/load helper 在本地提供该函数。
async function* jsonlReadables(jsonl: JsonlSessionRepoOptions, options: { cwd?: string } = {}) {
  for (const metadata of await listJsonlSessionMetadata(jsonl, options)) {
    yield loadJsonlSessionStorage(jsonl, metadata);
  }
}

interface SearchIndexWriter<TItem> {
  apply(items: TItem[]): Promise<void>;
  flush?(): Promise<void>;
}

interface IndexedSessionSearch<T extends SessionSearchHit, TItem>
  extends SessionSearch<T>, SearchIndexWriter<TItem> {}

type ElasticSessionFeedItem =
  | { type: "upsert"; id: string; body: ElasticSessionDoc }
  | { type: "delete"; id: string };

interface ElasticSessionDoc {
  sessionId: string;
  entryId: string;
  seq: number;
  timestamp: number;
  cwd: string;
  text: string;
  metadata: JsonlSessionMetadata;
  fields?: Record<string, unknown>;
}

interface ElasticSessionSearchHit extends SessionSearchHit {
  readonly timestamp: number;
  readonly snippet: string;
  readonly score?: number;
}

class ElasticSessionSearch
  implements IndexedSessionSearch<ElasticSessionSearchHit, ElasticSessionFeedItem>
{
  constructor(
    private readonly client: Client,
    private readonly index: string,
  ) {}

  async apply(items: ElasticSessionFeedItem[]): Promise<void> {
    const operations = items.flatMap((item) => {
      if (item.type === "delete") {
        return [{ delete: { _index: this.index, _id: item.id } }];
      }
      return [{ index: { _index: this.index, _id: item.id } }, item.body];
    });

    if (operations.length > 0) await this.client.bulk({ operations });
  }

  async flush(): Promise<void> {
    await this.client.indices.refresh({ index: this.index });
  }

  async *search(
    text: string,
    options: SessionSearchOptions = {},
  ): AsyncIterable<ElasticSessionSearchHit> {
    const result = await this.client.search<ElasticSessionDoc>({
      index: this.index,
      size: options.limit ?? 20,
      query: {
        bool: {
          must: [{ match: { text } }],
        },
      },
    });

    for (const hit of result.hits.hits) {
      if (!hit._source) continue;
      if (options.signal?.aborted) throw options.signal.reason;
      yield {
        sessionId: hit._source.sessionId,
        entryId: hit._source.entryId,
        timestamp: hit._source.timestamp,
        snippet: hit._source.text,
        score: hit._score ?? undefined,
      };
    }
  }
}
```

Catch-up/rebuild job 可以在不取得 writer lease 的情况下，把 JSONL projection 写入 Elasticsearch：

```ts
async function indexJsonlSessionsIntoElastic(
  jsonl: JsonlSessionRepoOptions,
  elastic: ElasticSessionSearch,
  options: { cwd?: string } = {},
): Promise<void> {
  for await (const session of jsonlReadables(jsonl, { cwd: options.cwd })) {
    const metadata = await session.getMetadata();
    for await (const candidate of scanningEntries(session)) {
      await elastic.apply([{
        type: "upsert",
        id: `${metadata.id}:${candidate.entryId}`,
        body: {
          sessionId: metadata.id,
          entryId: candidate.entryId,
          seq: candidate.seq,
          timestamp: candidate.timestamp,
          cwd: metadata.cwd,
          text: candidate.text,
          metadata,
          fields: candidate.fields,
        },
      }]);
    }
  }

  await elastic.flush();
}
```

## 正确性与失败边界

对于共享 API，search index 是派生状态：应用可以重试、rebuild 或将 search 标记为 stale。特定后端可以选择不同的权衡；SQLite FTS 使用同位置 trigger，因此 search 初始化 trigger 后，FTS 失败可能回滚规范 SQLite 写入。

如果扫描源产生重复的 `sessionId`，应快速失败，因为基础命中标识是 `(sessionId, entryId)`。索引后端通常在其存储/索引层强制唯一性。

选择启用 search 仍需要一个同步/索引层。后续应添加默认 no-op 的 search index sink（例如 `NOOP_SEARCH_INDEX_SINK`），让规范写入点可以无条件发出索引事件，类似 telemetry 禁用时使用 no-op 实现。
