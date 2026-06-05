"""Incremental Arrow IPC stream serialization for ``http_to_arrow``.

``IPCStreamSink`` wraps :func:`pyarrow.ipc.new_stream` around a
:class:`~http_to_arrow._drain.DrainableOutputStream` so that each written
``RecordBatch`` can be serialized to Arrow IPC stream bytes and yielded
immediately, keeping peak memory close to a single batch.
"""

from __future__ import annotations

from typing import Any, cast

import pyarrow as pa

from http_to_arrow._drain import DrainableOutputStream


class IPCStreamSink:
    """Serialize ``RecordBatch`` objects into Arrow IPC stream byte chunks.

    The schema is written into the stream header on construction; call
    :meth:`header_bytes` to retrieve it, :meth:`write_batch` for each batch, and
    :meth:`close` to emit the end-of-stream marker.

    Example:
        sink = IPCStreamSink(schema, compression="zstd")
        chunks = [sink.header_bytes()]
        chunks.append(sink.write_batch(batch))
        chunks.append(sink.close())
        table = pa.ipc.open_stream(pa.BufferReader(b"".join(chunks))).read_all()
    """

    def __init__(self, schema: pa.Schema, *, compression: str | None = None) -> None:
        self._sink = DrainableOutputStream()
        options = (
            pa.ipc.IpcWriteOptions(compression=cast("Any", compression))
            if compression is not None
            else None
        )
        # ``DrainableOutputStream`` is a duck-typed write-only sink; PyArrow wraps
        # it through its Python file interface even though the stubs only admit
        # native files.
        self._writer = pa.ipc.new_stream(
            cast("Any", self._sink), schema, options=options
        )
        self._header = self._sink.drain()
        self._closed = False

    def header_bytes(self) -> bytes:
        """Return the Arrow IPC stream header bytes captured at construction.

        PyArrow may buffer the schema message until the first ``write_batch`` or
        ``close``, so this can be empty. The bytes are always emitted in stream
        order, so concatenating ``header_bytes()`` with every ``write_batch``
        result and ``close`` produces a valid Arrow IPC stream.
        """
        return self._header

    def write_batch(self, batch: pa.RecordBatch) -> bytes:
        """Serialize *batch* and return its Arrow IPC stream bytes."""
        if self._closed:
            raise RuntimeError("IPCStreamSink is closed")
        self._writer.write_batch(batch)
        return self._sink.drain()

    def close(self) -> bytes:
        """Close the writer and return the trailing end-of-stream bytes."""
        if not self._closed:
            self._writer.close()
            self._closed = True
        return self._sink.drain()

    @property
    def closed(self) -> bool:
        """Whether the stream writer has been closed."""
        return self._closed


__all__ = ["IPCStreamSink"]
