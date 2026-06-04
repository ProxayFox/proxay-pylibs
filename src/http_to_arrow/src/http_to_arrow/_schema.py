"""Schema inference, type merging, casting, and alignment helpers.

These functions are pure and operate only on PyArrow objects plus a coercer
callable for the Python-fallback cast path. They are kept module-level so they
can be reused without depending on ``ArrowRecordContainer`` state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping, cast

import pyarrow as pa

from http_to_arrow._coercion import coerce_inferred_value


InferredValueCoercer = Callable[[Any, pa.DataType], Any]


def infer_arrow_type(value: Any) -> pa.DataType:
    """Infer a reasonable Arrow type for a Python value."""
    if value is None:
        return pa.null()

    if isinstance(value, bool):
        return pa.bool_()

    if isinstance(value, int):
        return pa.int64()

    if isinstance(value, float):
        return pa.float64()

    if isinstance(value, datetime):
        return pa.timestamp("us")

    if isinstance(value, bytes):
        return pa.binary()

    if isinstance(value, Mapping):
        return pa.struct(
            [
                pa.field(str(key), infer_arrow_type(item_value))
                for key, item_value in value.items()
            ]
        )

    if isinstance(value, list):
        item_type: pa.DataType = pa.null()
        for item in value:
            item_type = merge_arrow_types(item_type, infer_arrow_type(item))
        return pa.list_(item_type)

    return pa.string()


def merge_struct_fields(
    existing: pa.StructType, observed: pa.StructType
) -> list[pa.Field]:
    """Merge struct members while preserving first-seen order."""
    ordered_names = [f.name for f in existing]
    merged_fields: dict[str, pa.Field] = {
        f.name: pa.field(f.name, f.type) for f in existing
    }

    for f in observed:
        if f.name in merged_fields:
            merged_type = merge_arrow_types(
                merged_fields[f.name].type,
                f.type,
            )
            merged_fields[f.name] = pa.field(f.name, merged_type)
            continue

        ordered_names.append(f.name)
        merged_fields[f.name] = pa.field(f.name, f.type)

    return [merged_fields[name] for name in ordered_names]


def merge_arrow_types(existing: pa.DataType, observed: pa.DataType) -> pa.DataType:
    """Merge two Arrow types for schema widening in inferred mode."""
    if existing.equals(observed):
        return existing

    if pa.types.is_null(existing):
        return observed

    if pa.types.is_null(observed):
        return existing

    if pa.types.is_string(existing) or pa.types.is_string(observed):
        return pa.string()

    if pa.types.is_boolean(existing) and pa.types.is_boolean(observed):
        return pa.bool_()

    if pa.types.is_integer(existing) and pa.types.is_integer(observed):
        return pa.int64()

    if (pa.types.is_integer(existing) or pa.types.is_floating(existing)) and (
        pa.types.is_integer(observed) or pa.types.is_floating(observed)
    ):
        return pa.float64()

    if pa.types.is_binary(existing) and pa.types.is_binary(observed):
        return pa.binary()

    if pa.types.is_timestamp(existing) and pa.types.is_timestamp(observed):
        return pa.timestamp("us")

    if (pa.types.is_list(existing) or pa.types.is_large_list(existing)) and (
        pa.types.is_list(observed) or pa.types.is_large_list(observed)
    ):
        return pa.list_(
            merge_arrow_types(
                cast(pa.DataType, existing.value_type),
                cast(pa.DataType, observed.value_type),
            )
        )

    if pa.types.is_struct(existing) and pa.types.is_struct(observed):
        return pa.struct(merge_struct_fields(existing, observed))

    return pa.string()


def cast_array_to_type(
    array: pa.Array,
    target_type: pa.DataType,
    coercer: InferredValueCoercer = coerce_inferred_value,
) -> pa.Array:
    """Cast an Arrow array to *target_type*, falling back to Python-level conversion."""
    if array.type.equals(target_type):
        return array

    if pa.types.is_null(array.type):
        return pa.array([None] * len(array), type=target_type, from_pandas=False)

    try:
        return array.cast(target_type)
    except NotImplementedError, TypeError, ValueError, pa.ArrowInvalid:
        return pa.array(
            [coercer(value, target_type) for value in array.to_pylist()],
            type=target_type,
            from_pandas=False,
        )


def cast_column_to_type(
    column: pa.ChunkedArray,
    target_type: pa.DataType,
    coercer: InferredValueCoercer = coerce_inferred_value,
) -> pa.ChunkedArray:
    """Cast a chunked column to *target_type*."""
    if column.type.equals(target_type):
        return column

    if not column.chunks:
        return pa.chunked_array(
            [pa.array([], type=target_type)],
        )

    return pa.chunked_array(
        [cast_array_to_type(chunk, target_type, coercer) for chunk in column.chunks]
    )


def align_batch_to_schema(
    batch: pa.RecordBatch,
    schema: pa.Schema,
    coercer: InferredValueCoercer = coerce_inferred_value,
) -> pa.RecordBatch:
    """Align a batch to the supplied schema, adding null columns as needed."""
    if batch.schema.equals(schema):
        return batch

    arrays: list[pa.Array] = []
    index_by_name = {name: idx for idx, name in enumerate(batch.schema.names)}

    for arrow_field in schema:
        if arrow_field.name in index_by_name:
            array = batch.column(index_by_name[arrow_field.name])
            if not array.type.equals(arrow_field.type):
                array = cast_array_to_type(array, arrow_field.type, coercer)
        else:
            array = pa.nulls(batch.num_rows, type=arrow_field.type)
        arrays.append(array)

    return pa.RecordBatch.from_arrays(arrays, schema=schema)


def align_table_to_schema(
    table: pa.Table,
    schema: pa.Schema,
    coercer: InferredValueCoercer = coerce_inferred_value,
) -> pa.Table:
    """Align a table to the supplied schema, adding null columns as needed."""
    if table.schema.equals(schema):
        return table

    arrays: list[pa.ChunkedArray] = []
    source_names = frozenset(table.schema.names)

    for arrow_field in schema:
        if arrow_field.name in source_names:
            column = table.column(arrow_field.name)
            if not column.type.equals(arrow_field.type):
                column = cast_column_to_type(column, arrow_field.type, coercer)
        else:
            column = pa.chunked_array(
                [pa.nulls(table.num_rows, type=arrow_field.type)],
                type=arrow_field.type,
            )
        arrays.append(column)

    return pa.Table.from_arrays(arrays, schema=schema)


__all__ = [
    "InferredValueCoercer",
    "infer_arrow_type",
    "merge_arrow_types",
    "merge_struct_fields",
    "cast_array_to_type",
    "cast_column_to_type",
    "align_batch_to_schema",
    "align_table_to_schema",
]
