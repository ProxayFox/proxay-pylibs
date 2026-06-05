"""Async Arrow IPC streaming for ``http_to_arrow``.

``ArrowIPCStream`` bridges an async row producer (for example an HTTP paginator)
to an Arrow IPC byte stream. Rows are buffered into an
:class:`~http_to_arrow.main.ArrowRecordContainer`, completed batches are
serialized to Arrow IPC stream bytes via
:class:`~http_to_arrow._ipc.IPCStreamSink`, and each serialized batch is released
immediately so peak memory stays close to a single batch.

A bounded :class:`asyncio.Queue` decouples the producer from the consumer so a
fast paginator never outruns batch serialization. Each :class:`ArrowIPCStream`
instance is single-use: create a fresh stream per response.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from typing import Any, cast

import pyarrow as pa

from http_to_arrow._ipc import IPCStreamSink
from http_to_arrow.main import ArrowRecordContainer

_SENTINEL = object()


class ArrowIPCStream:
    """Stream Arrow IPC bytes from an async row producer with backpressure.

    Streaming requires an explicit schema because the Arrow IPC stream header is
    written before any rows are available. Inferred-schema mode and
    ``dictionary_encode=True`` are rejected because they can change batch types
    after the header schema is fixed.

    Example:
        stream = ArrowIPCStream(schema=schema, compression="zstd")

        async def produce() -> None:
            async for page in fetch_pages():
                await stream.extend(page)

        async for chunk in stream.ipc_chunks(producer=produce):
            ...  # forward chunk to the HTTP response
    """

    def __init__(
        self,
        schema: pa.Schema,
        *,
        batch_size: int = 128_000,
        queue_maxsize: int = 4,
        compression: str | None = None,
        dictionary_encode: bool = False,
        dictionary_cardinality_threshold: float = 0.5,
        eager_clear_accumulator: bool = True,
    ) -> None:
        if schema is None:
            raise ValueError("ArrowIPCStream requires an explicit schema.")
        if dictionary_encode:
            raise ValueError(
                "ArrowIPCStream does not support dictionary_encode=True. The IPC "
                "stream header fixes the schema before batches are written, and "
                "dictionary promotion can change later batch types."
            )

        self._schema = schema
        self._compression = compression
        self._queue: asyncio.Queue[object] = asyncio.Queue(maxsize=queue_maxsize)
        self._ended = False
        self._container_kwargs: dict[str, Any] = {
            "schema": schema,
            "batch_size": batch_size,
            "dictionary_encode": dictionary_encode,
            "dictionary_cardinality_threshold": dictionary_cardinality_threshold,
            "eager_clear_accumulator": eager_clear_accumulator,
        }

    # --- producer-side API ---

    async def put(self, row: Mapping[str, Any]) -> None:
        """Enqueue a single row, awaiting when the queue is full."""
        await self._queue.put([row])

    async def extend(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Enqueue a page of rows, awaiting when the queue is full."""
        await self._queue.put(list(rows))

    async def end(self) -> None:
        """Signal that no more rows will be enqueued. Idempotent."""
        if not self._ended:
            self._ended = True
            await self._queue.put(_SENTINEL)

    # --- consumer-side API ---

    async def ipc_chunks(
        self,
        producer: Callable[[], Awaitable[None]] | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield Arrow IPC stream byte chunks until the producer signals end.

        When *producer* is provided it is run as a concurrent task and this
        method signals :meth:`end` on its behalf, so the producer never needs to
        call it. Otherwise rows must be fed from a separate task via
        :meth:`put`/:meth:`extend`, and that task must call :meth:`end` when done.

        If the producer raises, the partial stream is flushed and closed cleanly
        and the exception is re-raised after the trailing bytes are emitted.
        """
        container = ArrowRecordContainer(**self._container_kwargs)
        ipc_sink = IPCStreamSink(self._schema, compression=self._compression)
        producer_error: BaseException | None = None
        producer_task: asyncio.Task[None] | None = None

        async def _run_producer(run: Callable[[], Awaitable[None]]) -> None:
            nonlocal producer_error
            try:
                await run()
            except Exception as exc:  # surfaced to the consumer after cleanup
                producer_error = exc
            finally:
                await self.end()

        header = ipc_sink.header_bytes()
        if header:
            yield header

        if producer is not None:
            producer_task = asyncio.create_task(_run_producer(producer))

        try:
            while True:
                item = await self._queue.get()
                if item is _SENTINEL:
                    break

                for row in cast("list[Mapping[str, Any]]", item):
                    container.append(row)

                for batch in container.iter_batches():
                    chunk = ipc_sink.write_batch(batch)
                    del batch
                    if chunk:
                        yield chunk

                await asyncio.sleep(0)

            final_batch = container.flush_partial()
            if final_batch is not None:
                chunk = ipc_sink.write_batch(final_batch)
                del final_batch
                if chunk:
                    yield chunk

            closing = ipc_sink.close()
            if closing:
                yield closing

            if producer_error is not None:
                raise producer_error
        finally:
            if producer_task is not None and not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self.ipc_chunks()


__all__ = ["ArrowIPCStream"]
