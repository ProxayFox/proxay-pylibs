"""Drainable in-memory output stream for Arrow IPC serialization.

``DrainableOutputStream`` is a minimal write-only, file-like object that
PyArrow's IPC stream writer can target. Unlike a fixed buffer, it lets the
caller *drain* the bytes accumulated since the last drain, so completed Arrow
IPC messages can be yielded incrementally and then released to keep peak memory
close to a single batch.
"""

from __future__ import annotations

from collections import deque

import pyarrow as pa


class DrainableOutputStream:
    """A write-only sink that buffers bytes until they are drained.

    The sink is intended as the target of :func:`pyarrow.ipc.new_stream`. After
    each writer operation (header, ``write_batch``, ``close``) the caller can
    call :meth:`drain` to retrieve and clear the bytes produced by that
    operation.

    Example:
        sink = DrainableOutputStream()
        sink.write(b"abc")
        assert sink.drain() == b"abc"
        assert sink.drain() == b""
    """

    def __init__(self) -> None:
        self._chunks: deque[bytes] = deque()
        self._buffered_bytes = 0
        self._position = 0
        self._closed = False

    def write(self, data: bytes | bytearray | memoryview | pa.Buffer) -> int:
        """Append *data* to the buffer and return the number of bytes written."""
        if self._closed:
            raise ValueError("I/O operation on closed stream")
        if isinstance(data, pa.Buffer):
            raw = data.to_pybytes()
        elif isinstance(data, bytes):
            raw = data
        else:
            raw = bytes(data)
        size = len(raw)
        self._chunks.append(raw)
        self._buffered_bytes += size
        self._position += size
        return size

    def drain(self) -> bytes:
        """Return all buffered bytes and clear the internal buffer.

        The absolute stream position reported by :meth:`tell` is unaffected, so
        draining never disturbs the IPC writer's view of the stream offset.
        """
        if not self._chunks:
            return b""
        result = b"".join(self._chunks)
        self._chunks.clear()
        self._buffered_bytes = 0
        return result

    @property
    def bytes_buffered(self) -> int:
        """Number of bytes currently buffered and not yet drained."""
        return self._buffered_bytes

    @property
    def closed(self) -> bool:
        """Whether the stream has been closed."""
        return self._closed

    def tell(self) -> int:
        """Return the absolute number of bytes written to the stream."""
        return self._position

    def flush(self) -> None:
        """No-op flush provided for file-like compatibility."""
        return None

    def close(self) -> None:
        """Mark the stream closed without discarding buffered bytes."""
        self._closed = True

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return not self._closed

    def seekable(self) -> bool:
        return False


__all__ = ["DrainableOutputStream"]
