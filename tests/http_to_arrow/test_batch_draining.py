"""Tests for the additive batch-draining helpers on ``ArrowRecordContainer``."""

from __future__ import annotations

import pyarrow as pa
import pytest

from http_to_arrow import ArrowRecordContainer


@pytest.mark.unit
def test_drain_batches_returns_batches_and_clears_pending_state() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        batch_size=2,
    )
    container.extend([{"id": 1}, {"id": 2}, {"id": 3}])

    # One full batch flushed at batch_size; one row still in the accumulator.
    assert len(container.batches) == 1
    assert container.batch_total_rows == 3

    drained = container.drain_batches()

    assert len(drained) == 1
    assert drained[0].num_rows == 2
    assert drained[0].column("id").to_pylist() == [1, 2]
    assert container.batches == []
    # Accumulator row remains untouched.
    assert container.batch_total_rows == 1


@pytest.mark.unit
def test_drain_batches_on_empty_container_returns_empty_list() -> None:
    container = ArrowRecordContainer(schema=pa.schema([pa.field("id", pa.int64())]))

    assert container.drain_batches() == []
    assert container.batch_total_rows == 0


@pytest.mark.unit
def test_flush_partial_returns_short_batch_and_clears_accumulator() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        batch_size=100,
    )
    container.extend([{"id": 1}, {"id": 2}])

    batch = container.flush_partial()

    assert batch is not None
    assert batch.num_rows == 2
    assert batch.column("id").to_pylist() == [1, 2]
    # Returned batch must not linger in pending state.
    assert container.batches == []
    assert container.batch_total_rows == 0


@pytest.mark.unit
def test_flush_partial_batch_is_not_materialized_again_by_to_table() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        batch_size=100,
    )
    container.extend([{"id": 1}, {"id": 2}])

    batch = container.flush_partial()
    assert batch is not None

    # No pending rows remain, so to_table yields an empty table rather than
    # re-materializing the already-drained partial batch.
    table = container.to_table()
    assert table.num_rows == 0


@pytest.mark.unit
def test_flush_partial_returns_none_when_accumulator_is_empty() -> None:
    container = ArrowRecordContainer(schema=pa.schema([pa.field("id", pa.int64())]))

    assert container.flush_partial() is None
    assert container.batch_total_rows == 0


@pytest.mark.unit
def test_iter_batches_yields_in_order_and_releases_each_batch() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        batch_size=1,
    )
    container.extend([{"id": 1}, {"id": 2}, {"id": 3}])

    assert len(container.batches) == 3
    assert container.batch_total_rows == 3

    collected: list[object] = []
    for batch in container.iter_batches():
        collected.extend(batch.column("id").to_pylist())
        # Each yielded batch is removed from pending storage as it is produced.
        assert len(container.batches) == 3 - len(collected)

    assert collected == [1, 2, 3]
    assert container.batches == []
    assert container.batch_total_rows == 0


@pytest.mark.unit
def test_iter_batches_does_not_flush_the_accumulator() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        batch_size=2,
    )
    container.extend([{"id": 1}, {"id": 2}, {"id": 3}])

    # One flushed batch (2 rows) plus one accumulator row.
    drained = list(container.iter_batches())

    assert len(drained) == 1
    assert drained[0].num_rows == 2
    # Accumulator row is still pending and was not flushed by iter_batches.
    assert container.batches == []
    assert container.batch_total_rows == 1

    # The remaining row still materializes correctly afterwards.
    table = container.to_table()
    assert table.column("id").to_pylist() == [3]


@pytest.mark.unit
def test_to_table_still_materializes_without_using_drain_helpers() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64()), pa.field("name", pa.string())]),
        batch_size=2,
    )
    container.extend(
        [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
            {"id": 3, "name": "gamma"},
        ]
    )

    table = container.to_table()

    assert table.num_rows == 3
    assert table.column("id").to_pylist() == [1, 2, 3]
    assert table.column("name").to_pylist() == ["alpha", "beta", "gamma"]


@pytest.mark.unit
def test_container_lock_is_reentrant() -> None:
    container = ArrowRecordContainer(schema=pa.schema([pa.field("id", pa.int64())]))

    # The container lock must be reentrant so a method that already holds it (for
    # example flush_partial) can call helpers that also acquire it without
    # deadlocking. A reentrant lock grants a same-thread re-acquire immediately;
    # a plain threading.Lock would block and time out here.
    with container._lock:
        reacquired = container._lock.acquire(timeout=0.5)
        try:
            assert reacquired is True
        finally:
            if reacquired:
                container._lock.release()
