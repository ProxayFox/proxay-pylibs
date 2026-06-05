# http-to-arrow

`http-to-arrow` provides Arrow-backed containers for streaming HTTP and ETL-style
ingestion workflows.

The package uses a standard source layout so code lives under
`src/http_to_arrow/` rather than the project root.

Package-specific tests live under `tests/` inside this workspace member, while
the monorepo root can still host shared integration tests when needed.

## Included exports

- `ArrowRecordContainer`
- `ArrowIPCStream`
- `IPCStreamSink`
- `UnknownFieldPolicy`
- `MissingFieldPolicy`
- `CoercionPolicy`

## Explicit schema

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([
        pa.field("id", pa.int64()),
        pa.field("name", pa.string()),
    ])
)

container.append({"id": 1, "name": "alpha"})
```

## Inferred schema

```python
from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=None)

container.append({"ID": 1})
container.append({"id": 2, "name": "beta"})

table = container.to_table()
assert table.to_pydict() == {
    "ID": [1, 2],
    "name": [None, "beta"],
}
```

## Notes

- `schema=None` enables inferred mode.
- Inferred mode widens as new fields appear and backfills older rows with nulls.
- Conflicting inferred field types widen when possible and otherwise fall back to `string`.
- `to_table()` raises when inferred mode has neither an explicit schema nor any appended records.

## Memory tuning

For high-volume ingestion paths (for example streaming large HTTP responses
into a single materialized Arrow table) the container exposes a few opt-in
knobs to bound peak memory. All defaults preserve the historical behavior.

- `dictionary_encode=True` (explicit schemas only): low-cardinality `string`
  and `large_string` columns are dictionary-encoded at flush time, producing
  dictionary-typed Arrow columns. Once a column is encoded, subsequent
  batches stay encoded so `pa.Table.from_batches` accepts them.
- `dictionary_cardinality_threshold` (default `0.5`): a column is only
  encoded when `len(dictionary) / len(array) <= threshold` on the first
  qualifying batch. Must be in `[0.0, 1.0]`.
- `compact_on_materialize=True`: runs `pa.Table.combine_chunks()` after
  materializing pending batches in `to_table()` or `incremental_flush()`,
  reducing the chunk fragmentation that builds up across many flushes.
- `eager_clear_accumulator=True`: each accumulator column list is released
  as soon as its Arrow array is built during `flush()`. This is opt-in
  because it changes failure semantics: if a later column raises mid-flush
  the cleared earlier columns cannot be re-converted from the same in-flight
  rows.
- For memory-constrained runtimes, lowering `batch_size` (default
  `128_000`) reduces the size of the Python accumulator held between
  flushes at the cost of more frequent batch construction.

## Streaming IPC

For memory-constrained runtimes (for example a 2 GiB Azure Function exporting
millions of rows) you can stream completed batches out as Arrow IPC stream bytes
instead of materializing one large table. `ArrowIPCStream` runs an async
producer (such as HTTP pagination) and a consumer that serializes each completed
`RecordBatch` to Arrow IPC bytes and releases it immediately, so peak memory
stays close to a single batch. A bounded `asyncio.Queue` applies backpressure so
the producer never outruns serialization.

Streaming requires an explicit schema because the IPC stream header is written
before any rows arrive. Inferred-schema mode and `dictionary_encode=True` are
rejected for streaming.

```python
import pyarrow as pa

from http_to_arrow import ArrowIPCStream

schema = pa.schema([pa.field("id", pa.int64()), pa.field("name", pa.string())])

async def stream_rows():
    stream = ArrowIPCStream(schema=schema, batch_size=128_000, compression="zstd")

    async def produce() -> None:
        async for page in fetch_pages():  # your async paginator
            await stream.extend(page)

    async for chunk in stream.ipc_chunks(producer=produce):
        yield chunk  # forward each chunk to the streaming HTTP response
```

Consume the stream on the client with `pyarrow.ipc.open_stream`:

```python
import pyarrow as pa

reader = pa.ipc.open_stream(pa.BufferReader(response_bytes))
table = reader.read_all()
```

For advanced composition, `IPCStreamSink` exposes the per-batch IPC
serialization directly without the async orchestration.

The helper modules `_policies`, `_coercion`, `_schema`, `_encoding`, `_drain`,
and `_ipc` are private implementation details. The public surface is
`ArrowRecordContainer`, `ArrowIPCStream`, `IPCStreamSink`, and the three policy
aliases.
