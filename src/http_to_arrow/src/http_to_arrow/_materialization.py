"""Materialization helpers for ``ArrowRecordContainer``.

These helpers own the stateful conversion from accumulated Python values to
Arrow batches, cached tables, and Polars frames. They accept the container
instance to keep the public dataclass and compatibility methods in
``http_to_arrow.main``.
"""

from __future__ import annotations

from typing import Any, cast

import polars as pl
import pyarrow as pa

from http_to_arrow._coercion import coerce_inferred_value
from http_to_arrow._encoding import maybe_dictionary_encode_array


def flush(container: Any) -> None:
    """Convert the current accumulator into a pending RecordBatch."""
    if container._current_count == 0:
        return

    if container.schema is None:
        raise ValueError("Cannot flush records without an explicit or inferred schema.")

    encoding_active = container.dictionary_encode and container._schema_explicit
    if encoding_active:
        effective_schema = container._effective_schema()
        assert effective_schema is not None  # noqa: S101
        effective_fields = tuple(effective_schema)
    else:
        effective_fields = container._schema_fields

    arrays: list[pa.Array] = []
    new_field_types: dict[str, pa.DataType] = {}
    for index, arrow_field in enumerate(container._schema_fields):
        values = container._accumulator[arrow_field.name]
        if not container._schema_explicit and container.coercion_policy == "coerce":
            values = [
                coerce_inferred_value(value, arrow_field.type) for value in values
            ]

        try:
            array = pa.array(
                values,
                type=arrow_field.type,
                from_pandas=False,
            )
        except pa.ArrowInvalid as exc:
            raise ValueError(
                f"Invalid data for column '{arrow_field.name}': {exc}"
            ) from exc
        except Exception as exc:
            raise ValueError(
                f"Error processing column '{arrow_field.name}': {exc}"
            ) from exc

        if encoding_active:
            existing_effective_type = effective_fields[index].type
            array = maybe_dictionary_encode_array(
                array,
                arrow_field.type,
                existing_effective_type,
                container.dictionary_cardinality_threshold,
            )
            if not array.type.equals(existing_effective_type):
                new_field_types[arrow_field.name] = array.type

        arrays.append(array)
        if container.eager_clear_accumulator:
            container._accumulator[arrow_field.name] = []

    if new_field_types:
        container._update_materialized_field_types(new_field_types)

    batch_schema = container._effective_schema()
    container.batches.append(pa.RecordBatch.from_arrays(arrays, schema=batch_schema))
    container._pending_batch_rows += container.batches[-1].num_rows
    container._init_accumulator()


def _merge_pending_batches(container: Any, effective_schema: pa.Schema) -> pa.Table:
    """Merge pending batches into the cached table and clear batch state."""
    batch_table = pa.Table.from_batches(container.batches, schema=effective_schema)
    container.batches.clear()
    container._pending_batch_rows = 0
    if container.table is not None:
        merged_table = pa.concat_tables([container.table, batch_table])
    else:
        merged_table = batch_table
    del batch_table
    if container.compact_on_materialize:
        merged_table = merged_table.combine_chunks()
    container.table = merged_table
    return container.table


def to_table(container: Any) -> pa.Table:
    """Materialize pending records and batches into a cached Arrow table."""
    with container._lock:
        container.flush()

        if container.schema is None:
            raise ValueError(
                "Cannot materialize a table without a schema or appended records."
            )

        container._align_materialized_state_to_schema()
        effective_schema = container._effective_schema()

        if not container.batches:
            if container.table is None:
                container.table = pa.Table.from_batches([], schema=effective_schema)
            return container.table

        return _merge_pending_batches(container, effective_schema)


def incremental_flush(container: Any, threshold: int = 0) -> bool:
    """Flush accumulated batches into the cached table when above *threshold*."""
    with container._lock:
        container.flush()

        if container._pending_batch_rows <= threshold:
            return False

        if container.schema is None:
            raise ValueError(
                "Cannot materialize a table without a schema or appended records."
            )

        container._align_materialized_state_to_schema()
        effective_schema = container._effective_schema()
        _merge_pending_batches(container, effective_schema)
        return True


def to_polars_frame(container: Any) -> pl.DataFrame:
    """Materialize the container as a Polars DataFrame."""
    if (
        container.table is not None
        and not container.batches
        and container._current_count == 0
    ):
        return cast(pl.DataFrame, pl.from_arrow(container.table))

    return cast(pl.DataFrame, pl.from_arrow(container.to_table()))


def reset(container: Any) -> None:
    """Clear accumulated data, batches, cached table, extras, and caches."""
    if not container._schema_explicit:
        container.schema = None
        container._refresh_schema_cache()

    container._init_accumulator()
    container.batches.clear()
    container._pending_batch_rows = 0
    container.captured_extras.clear()
    container.table = None
    container._materialized_schema = None


__all__ = [
    "flush",
    "incremental_flush",
    "reset",
    "to_polars_frame",
    "to_table",
]
