"""Tests for the async ``ArrowIPCStream`` orchestrator."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import cast

import pyarrow as pa
import pytest

from http_to_arrow import ArrowIPCStream


def _read_table(data: bytes) -> pa.Table:
    return pa.ipc.open_stream(pa.BufferReader(data)).read_all()


@pytest.mark.unit
def test_ipc_chunks_manual_producer_roundtrip() -> None:
    schema = pa.schema([pa.field("id", pa.int64()), pa.field("name", pa.string())])

    async def scenario() -> bytes:
        stream = ArrowIPCStream(schema=schema, batch_size=2)

        async def feed() -> None:
            await stream.extend([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
            await stream.put({"id": 3, "name": "c"})
            await stream.end()

        feed_task = asyncio.create_task(feed())
        chunks = [chunk async for chunk in stream.ipc_chunks()]
        await feed_task
        return b"".join(chunks)

    table = _read_table(asyncio.run(scenario()))

    assert table.column("id").to_pylist() == [1, 2, 3]
    assert table.column("name").to_pylist() == ["a", "b", "c"]


@pytest.mark.unit
def test_ipc_chunks_with_producer_task_roundtrip() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    async def scenario() -> bytes:
        stream = ArrowIPCStream(schema=schema, batch_size=10)

        async def produce() -> None:
            for value in range(5):
                await stream.extend([{"id": value}])

        return b"".join([chunk async for chunk in stream.ipc_chunks(producer=produce)])

    table = _read_table(asyncio.run(scenario()))

    assert table.column("id").to_pylist() == [0, 1, 2, 3, 4]


@pytest.mark.unit
def test_extend_applies_backpressure_when_queue_is_full() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    async def scenario() -> None:
        stream = ArrowIPCStream(schema=schema, queue_maxsize=1)

        # First page fills the bounded queue.
        await stream.extend([{"id": 1}])

        # The second page must block because the consumer has not drained yet.
        second = asyncio.create_task(stream.extend([{"id": 2}]))
        await asyncio.sleep(0)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(second), timeout=0.05)

        # Draining one queue item lets the blocked producer proceed.
        assert stream._queue.get_nowait() == [{"id": 1}]
        await asyncio.wait_for(second, timeout=1.0)
        assert stream._queue.get_nowait() == [{"id": 2}]

    asyncio.run(scenario())


@pytest.mark.unit
def test_empty_stream_is_valid() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    async def scenario() -> bytes:
        stream = ArrowIPCStream(schema=schema)

        async def produce() -> None:
            return None

        return b"".join([chunk async for chunk in stream.ipc_chunks(producer=produce)])

    table = _read_table(asyncio.run(scenario()))

    assert table.num_rows == 0
    assert table.schema.equals(schema)


@pytest.mark.unit
def test_single_row_stream() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    async def scenario() -> bytes:
        stream = ArrowIPCStream(schema=schema)

        async def produce() -> None:
            await stream.put({"id": 42})

        return b"".join([chunk async for chunk in stream.ipc_chunks(producer=produce)])

    table = _read_table(asyncio.run(scenario()))

    assert table.column("id").to_pylist() == [42]


@pytest.mark.unit
def test_exact_batch_boundary_emits_single_batch() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    async def scenario() -> bytes:
        stream = ArrowIPCStream(schema=schema, batch_size=4)

        async def produce() -> None:
            await stream.extend([{"id": value} for value in range(4)])

        return b"".join([chunk async for chunk in stream.ipc_chunks(producer=produce)])

    reader = pa.ipc.open_stream(pa.BufferReader(asyncio.run(scenario())))
    batches = list(reader)

    assert len(batches) == 1
    assert batches[0].num_rows == 4


@pytest.mark.unit
def test_producer_error_propagates_after_partial_stream() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    class BoomError(RuntimeError):
        pass

    async def scenario() -> None:
        stream = ArrowIPCStream(schema=schema, batch_size=2)

        async def produce() -> None:
            await stream.extend([{"id": 1}, {"id": 2}])
            raise BoomError("upstream failed")

        collected: list[bytes] = []
        with pytest.raises(BoomError):
            async for chunk in stream.ipc_chunks(producer=produce):
                collected.append(chunk)

        # The batch produced before the failure was still emitted.
        assert b"".join(collected) != b""

    asyncio.run(scenario())


@pytest.mark.unit
def test_async_iteration_protocol_streams_rows() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    async def scenario() -> bytes:
        stream = ArrowIPCStream(schema=schema, batch_size=2)

        async def feed() -> None:
            await stream.extend([{"id": 1}, {"id": 2}])
            await stream.end()

        feed_task = asyncio.create_task(feed())
        chunks = [chunk async for chunk in stream]
        await feed_task
        return b"".join(chunks)

    table = _read_table(asyncio.run(scenario()))

    assert table.column("id").to_pylist() == [1, 2]


@pytest.mark.unit
def test_early_close_cancels_producer_task() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    async def scenario() -> None:
        stream = ArrowIPCStream(schema=schema, batch_size=1, queue_maxsize=1)
        cancelled = asyncio.Event()

        async def produce() -> None:
            try:
                value = 0
                while True:
                    await stream.extend([{"id": value}])
                    value += 1
            except asyncio.CancelledError:
                cancelled.set()
                raise

        agen = cast(AsyncGenerator[bytes, None], stream.ipc_chunks(producer=produce))
        # Pull the first emitted batch chunk, then close the stream early.
        first = await agen.__anext__()
        assert first
        await agen.aclose()

        # The still-running producer task was cancelled during cleanup.
        await asyncio.wait_for(cancelled.wait(), timeout=1.0)

    asyncio.run(scenario())


@pytest.mark.unit
def test_schema_none_raises_value_error() -> None:
    with pytest.raises(ValueError, match="explicit schema"):
        ArrowIPCStream(schema=None)  # type: ignore


@pytest.mark.unit
def test_dictionary_encode_raises_value_error() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])

    with pytest.raises(ValueError, match="dictionary_encode"):
        ArrowIPCStream(schema=schema, dictionary_encode=True)


@pytest.mark.unit
def test_compression_produces_smaller_valid_stream() -> None:
    if not pa.Codec.is_available("zstd"):
        pytest.skip("zstd codec is not available in this PyArrow build")

    schema = pa.schema([pa.field("text", pa.string())])
    rows = [{"text": "repeated-value"} for _ in range(5_000)]

    async def run(compression: str | None) -> bytes:
        stream = ArrowIPCStream(
            schema=schema, batch_size=5_000, compression=compression
        )

        async def produce() -> None:
            await stream.extend(rows)

        return b"".join([chunk async for chunk in stream.ipc_chunks(producer=produce)])

    plain = asyncio.run(run(None))
    compressed = asyncio.run(run("zstd"))

    assert len(compressed) < len(plain)
    table = _read_table(compressed)
    assert table.num_rows == 5_000
