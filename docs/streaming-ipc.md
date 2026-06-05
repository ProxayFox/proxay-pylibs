# Streaming IPC

`ArrowIPCStream` streams completed batches out as Arrow IPC stream bytes instead
of materializing one large table. It is designed for memory-constrained runtimes
such as a 2 GiB Azure Function exporting millions of rows.

!!! note "Explicit schema required"
    Streaming requires an explicit `pyarrow.Schema`. The IPC stream header is
    written before any rows arrive, so inferred-schema mode is not supported.
    `dictionary_encode=True` is also rejected because dictionary promotion can
    change batch types after the header schema is fixed.

## How it works

An async producer (for example HTTP pagination) feeds rows into a bounded
`asyncio.Queue`. A consumer drains the queue, appends rows into an
`ArrowRecordContainer`, serializes each completed `RecordBatch` to Arrow IPC
stream bytes, and releases the batch immediately. The bounded queue applies
backpressure so the producer never outruns serialization, keeping peak memory
close to a single batch.

## Server-side usage

```python
import pyarrow as pa

from http_to_arrow import ArrowIPCStream

schema = pa.schema(
    [
        pa.field("id", pa.int64()),
        pa.field("name", pa.string()),
    ]
)

async def stream_rows():
    stream = ArrowIPCStream(
        schema=schema,
        batch_size=128_000,
        queue_maxsize=4,
        compression="zstd",
    )

    async def produce() -> None:
        async for page in fetch_pages():  # your async paginator
            await stream.extend(page)

    async for chunk in stream.ipc_chunks(producer=produce):
        yield chunk  # forward each chunk to the streaming HTTP response
```

!!! tip "Producer ownership"
    When you pass `producer=...` to `ipc_chunks`, the stream signals completion
    for you, so the producer does not need to call `end()`. If you instead feed
    rows from a separate task without passing `producer`, that task must call
    `await stream.end()` when it is done.

## Backpressure

`queue_maxsize` (default `4`) bounds how many pages the producer can stage ahead
of the consumer. When the queue is full, `put()` and `extend()` await until the
consumer drains an item. Lower it for very large pages; raise it for many small
pages.

## Compression

Pass `compression="zstd"` (or another codec your PyArrow build supports) to
shrink the serialized output. Compression does not change schema compatibility.

## Producer errors

If the producer raises, the consumer flushes and closes the partial stream
cleanly, emits the trailing bytes, and then re-raises the producer exception.
The client receives a valid (if incomplete) IPC stream followed by the error.

## Client-side consumption

```python
import pyarrow as pa

reader = pa.ipc.open_stream(pa.BufferReader(response_bytes))
table = reader.read_all()
```

## Lower-level composition

`IPCStreamSink` exposes per-batch Arrow IPC serialization without the async
orchestration, for callers who manage their own producer/consumer loop.

```python
from http_to_arrow import IPCStreamSink

sink = IPCStreamSink(schema, compression="zstd")
chunks = [sink.header_bytes()]
chunks.append(sink.write_batch(batch))
chunks.append(sink.close())
data = b"".join(chunks)
```
