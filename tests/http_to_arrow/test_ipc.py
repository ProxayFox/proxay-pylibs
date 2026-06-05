"""Tests for the drainable output stream and the Arrow IPC stream sink."""

from __future__ import annotations

import pyarrow as pa
import pytest

from http_to_arrow._drain import DrainableOutputStream
from http_to_arrow._ipc import IPCStreamSink


@pytest.mark.unit
def test_drainable_output_stream_drain_returns_and_clears_bytes() -> None:
    sink = DrainableOutputStream()

    assert sink.write(b"hello") == 5
    assert sink.bytes_buffered == 5
    assert sink.drain() == b"hello"
    # Buffer is cleared after draining.
    assert sink.bytes_buffered == 0
    assert sink.drain() == b""


@pytest.mark.unit
def test_drainable_output_stream_joins_multiple_chunks() -> None:
    sink = DrainableOutputStream()

    sink.write(b"ab")
    sink.write(b"cd")
    sink.write(b"ef")

    assert sink.drain() == b"abcdef"


@pytest.mark.unit
def test_drainable_output_stream_accepts_buffer_and_memoryview_inputs() -> None:
    sink = DrainableOutputStream()

    sink.write(b"a")
    sink.write(bytearray(b"bc"))
    sink.write(memoryview(b"de"))
    sink.write(pa.py_buffer(b"f"))

    assert sink.drain() == b"abcdef"


@pytest.mark.unit
def test_drainable_output_stream_tell_tracks_absolute_position() -> None:
    sink = DrainableOutputStream()

    sink.write(b"abcd")
    assert sink.tell() == 4
    # Draining flushes the buffer but does not rewind the absolute position.
    sink.drain()
    assert sink.tell() == 4
    sink.write(b"ef")
    assert sink.tell() == 6
    assert sink.bytes_buffered == 2


@pytest.mark.unit
def test_drainable_output_stream_close_preserves_buffered_bytes() -> None:
    sink = DrainableOutputStream()
    sink.write(b"tail")

    sink.close()

    assert sink.closed is True
    # close() must not discard pending bytes.
    assert sink.drain() == b"tail"


@pytest.mark.unit
def test_drainable_output_stream_write_after_close_raises() -> None:
    sink = DrainableOutputStream()
    sink.close()

    with pytest.raises(ValueError):
        sink.write(b"x")


@pytest.mark.unit
def test_drainable_output_stream_capability_flags() -> None:
    sink = DrainableOutputStream()

    assert sink.readable() is False
    assert sink.writable() is True
    assert sink.seekable() is False
    assert sink.flush() is None


_SCHEMA = pa.schema([pa.field("id", pa.int64()), pa.field("name", pa.string())])


def _batch(ids: list[int], names: list[str]) -> pa.RecordBatch:
    return pa.record_batch(
        [pa.array(ids, type=pa.int64()), pa.array(names, type=pa.string())],
        schema=_SCHEMA,
    )


@pytest.mark.unit
def test_ipc_stream_sink_header_bytes_are_part_of_the_stream() -> None:
    sink = IPCStreamSink(_SCHEMA)

    # PyArrow may buffer the schema header until the first write or close, so
    # header_bytes() can be empty. The bytes are still emitted in stream order,
    # so concatenating header + batches + close yields a valid IPC stream.
    header = sink.header_bytes()
    assert isinstance(header, bytes)

    body = sink.write_batch(_batch([1], ["a"]))
    tail = sink.close()

    reader = pa.ipc.open_stream(pa.BufferReader(header + body + tail))
    assert reader.read_all().column("id").to_pylist() == [1]


@pytest.mark.unit
def test_ipc_stream_sink_roundtrip_reads_back_all_batches() -> None:
    sink = IPCStreamSink(_SCHEMA)

    chunks = [sink.header_bytes()]
    chunks.append(sink.write_batch(_batch([1, 2], ["a", "b"])))
    chunks.append(sink.write_batch(_batch([3], ["c"])))
    chunks.append(sink.close())

    reader = pa.ipc.open_stream(pa.BufferReader(b"".join(chunks)))
    table = reader.read_all()

    assert table.schema.equals(_SCHEMA)
    assert table.column("id").to_pylist() == [1, 2, 3]
    assert table.column("name").to_pylist() == ["a", "b", "c"]


@pytest.mark.unit
def test_ipc_stream_sink_empty_stream_is_valid() -> None:
    sink = IPCStreamSink(_SCHEMA)

    data = sink.header_bytes() + sink.close()

    reader = pa.ipc.open_stream(pa.BufferReader(data))
    table = reader.read_all()

    assert table.num_rows == 0
    assert table.schema.equals(_SCHEMA)


@pytest.mark.unit
def test_ipc_stream_sink_write_after_close_raises() -> None:
    sink = IPCStreamSink(_SCHEMA)
    sink.close()

    assert sink.closed is True
    with pytest.raises(RuntimeError):
        sink.write_batch(_batch([1], ["a"]))


@pytest.mark.unit
def test_ipc_stream_sink_close_is_idempotent() -> None:
    sink = IPCStreamSink(_SCHEMA)

    first = sink.close()
    second = sink.close()

    assert isinstance(first, bytes)
    # A second close emits no further bytes and does not raise.
    assert second == b""


@pytest.mark.unit
def test_ipc_stream_sink_compression_roundtrips_and_shrinks_output() -> None:
    if not pa.Codec.is_available("zstd"):
        pytest.skip("zstd codec is not available in this PyArrow build")

    schema = pa.schema([pa.field("text", pa.string())])
    # Highly compressible payload so zstd output is reliably smaller.
    values = ["repeated-value"] * 10_000
    batch = pa.record_batch([pa.array(values, type=pa.string())], schema=schema)

    uncompressed = IPCStreamSink(schema)
    uncompressed_bytes = (
        uncompressed.header_bytes()
        + uncompressed.write_batch(batch)
        + uncompressed.close()
    )

    compressed = IPCStreamSink(schema, compression="zstd")
    compressed_bytes = (
        compressed.header_bytes() + compressed.write_batch(batch) + compressed.close()
    )

    assert len(compressed_bytes) < len(uncompressed_bytes)

    reader = pa.ipc.open_stream(pa.BufferReader(compressed_bytes))
    table = reader.read_all()
    assert table.column("text").to_pylist() == values
