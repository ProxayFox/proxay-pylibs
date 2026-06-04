"""Shared Arrow-backed record containers for ETL-style ingestion flows."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, cast

import polars as pl
import pyarrow as pa

from http_to_arrow._coercion import (
    coerce_inferred_value,
    coerce_timestamp_value,
    coerce_value,
)
from http_to_arrow._encoding import maybe_dictionary_encode_array
from http_to_arrow._policies import (
    CoercionPolicy,
    MissingFieldPolicy,
    UnknownFieldPolicy,
)
from http_to_arrow._schema import (
    align_batch_to_schema,
    align_table_to_schema,
    cast_array_to_type,
    cast_column_to_type,
    infer_arrow_type,
    merge_arrow_types,
    merge_struct_fields,
)


@dataclass
class ArrowRecordContainer:
    """Batch incoming records into Arrow tables using an explicit or inferred schema."""

    schema: pa.Schema | None = field(
        init=True,
        default=None,
        doc="PyArrow schema for the container data, or None to infer it from records.",
    )

    table: pa.Table | None = field(
        default=None,
        init=True,
        doc="Cached PyArrow table holding materialized records.",
    )
    batch_size: int = field(
        default=128000,
        doc="Number of records to process in a batch during extraction.",
    )
    unknown_field_policy: UnknownFieldPolicy = field(
        default="drop",
        doc="How to handle keys that are not present in the schema.",
    )
    missing_field_policy: MissingFieldPolicy = field(
        default="null",
        doc="How to handle schema fields missing from incoming records.",
    )
    coercion_policy: CoercionPolicy = field(
        default="coerce",
        doc="Whether to coerce values into schema-compatible Arrow shapes.",
    )
    case_insensitive_keys: bool = field(
        default=True,
        doc="Resolve incoming keys case-insensitively when exact matches are absent.",
    )
    eager_clear_accumulator: bool = field(
        default=False,
        doc=(
            "Free each accumulator column list immediately after its array is built "
            "during flush(). Opt-in memory mode; do not enable when flush() failures "
            "need to be retried on the same in-flight rows."
        ),
    )
    dictionary_encode: bool = field(
        default=False,
        doc=(
            "Opt-in dictionary encoding for low-cardinality string columns when an "
            "explicit schema is supplied. Encoded columns return dictionary-typed "
            "Arrow arrays."
        ),
    )
    dictionary_cardinality_threshold: float = field(
        default=0.5,
        doc=(
            "Maximum unique/row ratio at which a string column will be dictionary "
            "encoded. Must be in [0.0, 1.0]. Ignored when dictionary_encode is False."
        ),
    )
    compact_on_materialize: bool = field(
        default=False,
        doc=(
            "Run pa.Table.combine_chunks() after materializing pending batches into "
            "the cached table to reduce chunk fragmentation across flushes."
        ),
    )
    batches: list[pa.RecordBatch] = field(
        default_factory=list,
        doc="List of record batches pending materialization into the cached table.",
    )
    captured_extras: list[dict[str, Any]] = field(
        default_factory=list,
        init=False,
        repr=False,
        doc="Optional capture area for extra fields when unknown_field_policy='capture'.",
    )
    _schema_fields: tuple[pa.Field, ...] = field(
        default_factory=tuple,
        init=False,
        repr=False,
    )
    _schema_field_names: frozenset[str] = field(
        default_factory=frozenset,
        init=False,
        repr=False,
    )
    _uses_default_normalizer: bool = field(default=False, init=False, repr=False)
    _schema_explicit: bool = field(default=False, init=False, repr=False)
    _inferred_name_map: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )
    _accumulator: dict[str, list] = field(default_factory=dict, init=False, repr=False)
    _current_count: int = field(default=0, init=False, repr=False)
    _pending_batch_rows: int = field(default=0, init=False, repr=False)
    _materialized_schema: pa.Schema | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # --- lifecycle ---

    def __post_init__(self) -> None:
        if not 0.0 <= self.dictionary_cardinality_threshold <= 1.0:
            raise ValueError(
                "dictionary_cardinality_threshold must be between 0.0 and 1.0."
            )

        self._schema_explicit = self.schema is not None

        if self.table is not None:
            if self.schema is not None and not self.table.schema.equals(self.schema):
                raise ValueError("Cached table schema must match the container schema.")
            if self.schema is None:
                self.schema = self.table.schema

        if self.schema is None and self.batches:
            self.schema = self.batches[0].schema

        self._refresh_schema_cache()
        self._uses_default_normalizer = (
            type(self).normalize_record is ArrowRecordContainer.normalize_record
        )
        self._pending_batch_rows = sum(b.num_rows for b in self.batches)
        self._init_accumulator()

    def _effective_schema(self) -> pa.Schema | None:
        """Return the schema used for flushed batches and the cached table.

        When dictionary encoding has not yet promoted any columns this is
        identical to ``self.schema``. When encoding has been applied the
        cached materialized schema carries the chosen dictionary types so
        subsequent batches stay schema-compatible.
        """
        return self._materialized_schema or self.schema

    def _update_materialized_field_types(
        self, new_field_types: dict[str, pa.DataType]
    ) -> None:
        """Record encoded field types in the materialized schema cache."""
        if not new_field_types or self.schema is None:
            return

        base = self._materialized_schema or self.schema
        if all(
            base.field(name).type.equals(new_field_types[name])
            for name in new_field_types
        ):
            return

        updated_fields: list[pa.Field] = []
        for arrow_field in base:
            promoted = new_field_types.get(arrow_field.name)
            field_type = promoted if promoted is not None else arrow_field.type
            updated_fields.append(pa.field(arrow_field.name, field_type))
        self._materialized_schema = pa.schema(updated_fields)

    def _refresh_schema_cache(self) -> None:
        """Refresh cached schema metadata after schema changes."""
        if self.schema is None:
            self._schema_fields = ()
            self._schema_field_names = frozenset()
            self._inferred_name_map = {}
            return

        self._schema_fields = tuple(self.schema)
        self._schema_field_names = frozenset(
            arrow_field.name for arrow_field in self._schema_fields
        )
        self._inferred_name_map = {
            arrow_field.name.lower(): arrow_field.name
            for arrow_field in self._schema_fields
        }

    def _init_accumulator(self) -> None:
        """Initialize empty lists for each schema field."""
        self._accumulator = {
            arrow_field.name: [] for arrow_field in self._schema_fields
        }
        self._current_count = 0

    def _rebuild_accumulator_for_schema(self, schema: pa.Schema) -> None:
        """Apply an updated schema while preserving in-flight rows."""
        existing_rows = self._current_count
        existing_accumulator = self._accumulator

        self.schema = schema
        self._refresh_schema_cache()
        self._accumulator = {
            arrow_field.name: list(existing_accumulator.get(arrow_field.name, []))
            for arrow_field in self._schema_fields
        }
        for values in self._accumulator.values():
            if len(values) < existing_rows:
                values.extend([None] * (existing_rows - len(values)))

    def _canonicalize_inferred_key(self, key: str) -> str:
        """Resolve inferred column names while preserving the first-seen spelling."""
        if not self.case_insensitive_keys:
            return key

        return self._inferred_name_map.get(key.lower(), key)

    def normalize_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Normalize records before schema matching and coercion."""
        return dict(record)

    def _prepare_record(self, record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Avoid copying plain dict records when using the default normalizer."""
        if self._uses_default_normalizer and isinstance(record, dict):
            return record
        return self.normalize_record(record)

    # ---------------------------------------------------- pure helper delegations

    @classmethod
    def _coerce_timestamp_value(cls, value: Any) -> datetime | Any | None:
        return coerce_timestamp_value(value)

    @classmethod
    def _coerce_value(cls, value: Any, arrow_type: pa.DataType) -> Any:
        return coerce_value(value, arrow_type)

    @classmethod
    def _coerce_inferred_value(cls, value: Any, arrow_type: pa.DataType) -> Any:
        return coerce_inferred_value(value, arrow_type)

    @classmethod
    def _infer_arrow_type(cls, value: Any) -> pa.DataType:
        return infer_arrow_type(value)

    @classmethod
    def _merge_struct_fields(
        cls, existing: pa.StructType, observed: pa.StructType
    ) -> list[pa.Field]:
        return merge_struct_fields(existing, observed)

    @classmethod
    def _merge_arrow_types(
        cls, existing: pa.DataType, observed: pa.DataType
    ) -> pa.DataType:
        return merge_arrow_types(existing, observed)

    def _cast_array_to_type(
        self, array: pa.Array, target_type: pa.DataType
    ) -> pa.Array:
        return cast_array_to_type(array, target_type, coerce_inferred_value)

    def _cast_column_to_type(
        self, column: pa.ChunkedArray, target_type: pa.DataType
    ) -> pa.ChunkedArray:
        return cast_column_to_type(column, target_type, coerce_inferred_value)

    def _align_batch_to_schema(
        self, batch: pa.RecordBatch, schema: pa.Schema
    ) -> pa.RecordBatch:
        return align_batch_to_schema(batch, schema, coerce_inferred_value)

    def _align_table_to_schema(self, table: pa.Table, schema: pa.Schema) -> pa.Table:
        return align_table_to_schema(table, schema, coerce_inferred_value)

    # ------------------------------------------------------ inferred-mode growth

    def _ensure_inferred_schema_for_record(self, record: Mapping[str, Any]) -> None:
        """Grow or widen the inferred schema to accommodate *record*."""
        ordered_names = [arrow_field.name for arrow_field in self._schema_fields]
        fields_by_name: dict[str, pa.Field] = {
            arrow_field.name: pa.field(arrow_field.name, arrow_field.type)
            for arrow_field in self._schema_fields
        }
        schema_changed = False

        for key, value in record.items():
            observed_type = infer_arrow_type(value)
            existing_field = fields_by_name.get(key)

            if existing_field is None:
                ordered_names.append(key)
                fields_by_name[key] = pa.field(key, observed_type)
                schema_changed = True
                continue

            merged_type = merge_arrow_types(existing_field.type, observed_type)
            if not merged_type.equals(existing_field.type):
                fields_by_name[key] = pa.field(key, merged_type)
                schema_changed = True

        if schema_changed:
            self._rebuild_accumulator_for_schema(
                pa.schema([fields_by_name[name] for name in ordered_names])
            )

    def _align_materialized_state_to_schema(self) -> None:
        """Realign cached batches and tables to the current effective schema."""
        effective_schema = self._effective_schema()
        if effective_schema is None:
            return

        if self.table is not None and not self.table.schema.equals(effective_schema):
            self.table = self._align_table_to_schema(self.table, effective_schema)

        if any(not batch.schema.equals(effective_schema) for batch in self.batches):
            self.batches = [
                self._align_batch_to_schema(batch, effective_schema)
                for batch in self.batches
            ]

    # ----------------------------------------------------------------- appending

    def _resolve_field_key(
        self,
        field_name: str,
        record: Mapping[str, Any],
        lower_key_map: dict[str, str],
    ) -> str | None:
        """Resolve an incoming key for a schema field."""
        if field_name in record:
            return field_name

        if not self.case_insensitive_keys:
            return None

        return lower_key_map.get(field_name.lower())

    def _handle_unknown_fields(self, extras: dict[str, Any]) -> None:
        """Apply configured policy for extra keys not present in the schema."""
        if not extras:
            return

        if self.unknown_field_policy == "error":
            extra_keys = ", ".join(sorted(extras))
            raise ValueError(f"Unexpected fields not present in schema: {extra_keys}")

        if self.unknown_field_policy == "capture":
            self.captured_extras.append(extras)

    def _append_exact_key_record(self, record: Mapping[str, Any]) -> bool:
        """Fast path for records whose keys already match the schema exactly."""
        if any(key not in self._schema_field_names for key in record):
            return False

        for arrow_field in self._schema_fields:
            if arrow_field.name in record:
                raw_value = record.get(arrow_field.name)
            else:
                if self.missing_field_policy == "error":
                    raise ValueError(
                        f"Missing required schema field '{arrow_field.name}'."
                    )
                raw_value = None

            value = (
                coerce_value(raw_value, arrow_field.type)
                if self.coercion_policy == "coerce"
                else raw_value
            )
            self._accumulator[arrow_field.name].append(value)

        self._current_count += 1
        if self._current_count >= self.batch_size:
            self.flush()

        return True

    def _append_inferred_record(self, record: Mapping[str, Any]) -> None:
        """Append a record while inferring and widening schema over time."""
        resolved_record = {
            self._canonicalize_inferred_key(key): value for key, value in record.items()
        }

        if not resolved_record and self.schema is None:
            raise ValueError("Cannot infer schema from an empty record.")

        self._ensure_inferred_schema_for_record(resolved_record)

        for arrow_field in self._schema_fields:
            if arrow_field.name in resolved_record:
                raw_value = resolved_record.get(arrow_field.name)
            else:
                if self.missing_field_policy == "error":
                    raise ValueError(
                        f"Missing required schema field '{arrow_field.name}'."
                    )
                raw_value = None

            value = (
                coerce_inferred_value(raw_value, arrow_field.type)
                if self.coercion_policy == "coerce"
                else raw_value
            )
            self._accumulator[arrow_field.name].append(value)

        self._current_count += 1
        if self._current_count >= self.batch_size:
            self.flush()

    def append(self, record: Mapping[str, Any]) -> None:
        """Append a single record to the container."""
        normalized_record = self._prepare_record(record)
        if not self._schema_explicit:
            self._append_inferred_record(normalized_record)
            return

        if self._append_exact_key_record(normalized_record):
            return

        lower_key_map = {key.lower(): key for key in normalized_record}
        matched_keys: set[str] = set()

        for arrow_field in self._schema_fields:
            resolved_key = self._resolve_field_key(
                arrow_field.name,
                normalized_record,
                lower_key_map,
            )

            if resolved_key is None:
                if self.missing_field_policy == "error":
                    raise ValueError(
                        f"Missing required schema field '{arrow_field.name}'."
                    )

                raw_value = None
            else:
                matched_keys.add(resolved_key)
                raw_value = normalized_record.get(resolved_key)

            value = (
                coerce_value(raw_value, arrow_field.type)
                if self.coercion_policy == "coerce"
                else raw_value
            )
            self._accumulator[arrow_field.name].append(value)

        extras = {
            key: value
            for key, value in normalized_record.items()
            if key not in matched_keys
        }
        self._handle_unknown_fields(extras)

        self._current_count += 1
        if self._current_count >= self.batch_size:
            self.flush()

    def extend(self, records: Iterable[Mapping[str, Any]]) -> None:
        """Append multiple records to the container."""
        for record in records:
            self.append(record)

    # --- flush / materialize ---

    def flush(self) -> None:
        """Convert accumulated records into a RecordBatch."""
        if self._current_count == 0:
            return

        if self.schema is None:
            raise ValueError(
                "Cannot flush records without an explicit or inferred schema."
            )

        encoding_active = self.dictionary_encode and self._schema_explicit
        if encoding_active:
            effective_schema = self._effective_schema()
            assert effective_schema is not None  # noqa: S101
            effective_fields = tuple(effective_schema)
        else:
            effective_fields = self._schema_fields

        arrays: list[pa.Array] = []
        new_field_types: dict[str, pa.DataType] = {}
        for index, arrow_field in enumerate(self._schema_fields):
            values = self._accumulator[arrow_field.name]
            if not self._schema_explicit and self.coercion_policy == "coerce":
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
                    self.dictionary_cardinality_threshold,
                )
                if not array.type.equals(existing_effective_type):
                    new_field_types[arrow_field.name] = array.type

            arrays.append(array)
            if self.eager_clear_accumulator:
                self._accumulator[arrow_field.name] = []

        if new_field_types:
            self._update_materialized_field_types(new_field_types)

        batch_schema = self._effective_schema()
        self.batches.append(pa.RecordBatch.from_arrays(arrays, schema=batch_schema))
        self._pending_batch_rows += self.batches[-1].num_rows
        self._init_accumulator()

    def _flush_batch(self) -> None:
        """Backward-compatible alias for flushing the active batch."""
        self.flush()

    def to_table(self) -> pa.Table:
        """Materialize any pending batches into a cached Arrow table."""
        with self._lock:
            self.flush()

            if self.schema is None:
                raise ValueError(
                    "Cannot materialize a table without a schema or appended records."
                )

            self._align_materialized_state_to_schema()
            effective_schema = self._effective_schema()

            if not self.batches:
                if self.table is None:
                    self.table = pa.Table.from_batches([], schema=effective_schema)
                return self.table

            batch_table = pa.Table.from_batches(self.batches, schema=effective_schema)
            self.batches.clear()
            self._pending_batch_rows = 0
            if self.table is not None:
                merged_table = pa.concat_tables([self.table, batch_table])
            else:
                merged_table = batch_table
            del batch_table
            if self.compact_on_materialize:
                merged_table = merged_table.combine_chunks()
            self.table = merged_table
            return self.table

    def incremental_flush(self, threshold: int = 0) -> bool:
        """Flush accumulated batches into the cached table when above *threshold* rows.

        Unlike ``to_table()`` this is designed to be called periodically during
        streaming ingestion to bound memory. When the pending batch row count
        exceeds *threshold*, the batches are materialised into the cached table
        and the batch list is cleared.

        Returns ``True`` when batches were actually flushed, ``False`` otherwise.
        """
        with self._lock:
            self.flush()

            if self._pending_batch_rows <= threshold:
                return False

            if self.schema is None:
                raise ValueError(
                    "Cannot materialize a table without a schema or appended records."
                )

            self._align_materialized_state_to_schema()
            effective_schema = self._effective_schema()

            batch_table = pa.Table.from_batches(self.batches, schema=effective_schema)
            self.batches.clear()
            self._pending_batch_rows = 0
            if self.table is not None:
                merged_table = pa.concat_tables([self.table, batch_table])
            else:
                merged_table = batch_table
            del batch_table
            if self.compact_on_materialize:
                merged_table = merged_table.combine_chunks()
            self.table = merged_table
            return True

    def to_polars_frame(self) -> pl.DataFrame:
        """Materialize the container as a Polars DataFrame."""
        if self.table is not None and not self.batches and self._current_count == 0:
            return cast(pl.DataFrame, pl.from_arrow(self.table))

        return cast(pl.DataFrame, pl.from_arrow(self.to_table()))

    def reset(self) -> None:
        """Clear accumulated data, batches, cached table, and captured extras."""
        if not self._schema_explicit:
            self.schema = None
            self._refresh_schema_cache()

        self._init_accumulator()
        self.batches.clear()
        self._pending_batch_rows = 0
        self.captured_extras.clear()
        self.table = None
        self._materialized_schema = None

    # --- compatibility aliases ---

    def to_arrow(self) -> pa.Table:
        """Backward-compatible alias for materializing the cached Arrow table."""
        return self.to_table()

    def to_polars(self) -> pl.DataFrame:
        """Backward-compatible alias for materializing a Polars DataFrame."""
        return self.to_polars_frame()

    def clear(self) -> None:
        """Backward-compatible alias for resetting container state."""
        self.reset()

    @property
    def batch_total_rows(self) -> int:
        """Total rows across pending batches plus the in-flight accumulator."""
        return self._pending_batch_rows + self._current_count

    @property
    def total_rows(self) -> int:
        """Total rows across the cached table, pending batches, and accumulator."""
        total = self.batch_total_rows
        if self.table is not None:
            total += self.table.num_rows
        return total


__all__ = [
    "ArrowRecordContainer",
    "CoercionPolicy",
    "MissingFieldPolicy",
    "UnknownFieldPolicy",
]
