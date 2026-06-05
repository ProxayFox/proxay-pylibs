"""Shared Arrow-backed record containers for ETL-style ingestion flows."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Iterator, Mapping

import polars as pl
import pyarrow as pa

from http_to_arrow import _appending
from http_to_arrow import _materialization
from http_to_arrow.base import BaseArrowRecordContainer, ArrowRecordContainerSettings
from http_to_arrow._coercion import (
    coerce_inferred_value,
    coerce_timestamp_value,
    coerce_value,
)
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


@dataclass(init=False)
class ArrowRecordContainer(BaseArrowRecordContainer, ArrowRecordContainerSettings):
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

    # --- lifecycle ---

    def __init__(
        self,
        schema: pa.Schema | None = None,
        table: pa.Table | None = None,
        batch_size: int = 128000,  # Results in ~700MB batches in profiler test
        unknown_field_policy: UnknownFieldPolicy = "drop",
        missing_field_policy: MissingFieldPolicy = "null",
        coercion_policy: CoercionPolicy = "coerce",
        case_insensitive_keys: bool = True,
        eager_clear_accumulator: bool = False,
        dictionary_encode: bool = False,
        dictionary_cardinality_threshold: float = 0.5,
        compact_on_materialize: bool = False,
        batches: list[pa.RecordBatch] | None = None,
    ) -> None:
        self.schema = schema
        self.table = table
        self.batch_size = batch_size
        self.unknown_field_policy = unknown_field_policy
        self.missing_field_policy = missing_field_policy
        self.coercion_policy = coercion_policy
        self.case_insensitive_keys = case_insensitive_keys
        self.eager_clear_accumulator = eager_clear_accumulator
        self.dictionary_encode = dictionary_encode
        self.dictionary_cardinality_threshold = dictionary_cardinality_threshold
        self.compact_on_materialize = compact_on_materialize
        self.batches = [] if batches is None else batches
        self.captured_extras = []
        self._schema_fields = ()
        self._schema_field_names = frozenset()
        self._uses_default_normalizer = False
        self._schema_explicit = False
        self._inferred_name_map = {}
        self._accumulator = {}
        self._current_count = 0
        self._pending_batch_rows = 0
        self._materialized_schema = None
        self._lock = threading.Lock()
        self.__post_init__()

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
        """Return the schema used for flushed batches and cached tables.

        When dictionary encoding has not yet promoted any columns this is
        identical to ``self.schema``. When encoding has been applied the
        cached materialized schema carries the chosen dictionary types so
        subsequent batches stay schema-compatible.
        """
        return self._materialized_schema or self.schema

    def _update_materialized_field_types(
        self, new_field_types: dict[str, pa.DataType]
    ) -> None:
        """Record encoded field types in the effective schema cache."""
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
            updated_fields.append(
                pa.field(
                    arrow_field.name,
                    field_type,
                    nullable=arrow_field.nullable,
                    metadata=arrow_field.metadata,
                )
            )
        self._materialized_schema = pa.schema(
            updated_fields,
            metadata={k: v for k, v in base.metadata.items()}
            if base.metadata is not None
            else None,
        )

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
        """Initialize empty lists for each schema field and reset the row count."""
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
        return _appending.resolve_field_key(
            self,
            field_name,
            record,
            lower_key_map,
        )

    def _handle_unknown_fields(self, extras: dict[str, Any]) -> None:
        """Apply the configured explicit-schema policy for extra keys."""
        _appending.handle_unknown_fields(self, extras)

    def _append_exact_key_record(self, record: Mapping[str, Any]) -> bool:
        """Fast path for records that contain no keys outside the schema."""
        return _appending.append_exact_key_record(self, record)

    def _append_inferred_record(self, record: Mapping[str, Any]) -> None:
        """Append a record while inferring and widening schema over time."""
        _appending.append_inferred_record(self, record)

    def append(self, record: Mapping[str, Any]) -> None:
        """Append a single record to the container."""
        _appending.append(self, record)

    def extend(self, records: Iterable[Mapping[str, Any]]) -> None:
        """Append multiple records to the container."""
        _appending.extend(self, records)

    # --- flush / materialize ---

    def flush(self) -> None:
        """Convert the current accumulator into a pending RecordBatch."""
        _materialization.flush(self)

    def _flush_batch(self) -> None:
        """Backward-compatible alias for flushing the active batch."""
        self.flush()

    def to_table(self) -> pa.Table:
        """Materialize pending records and batches into a cached Arrow table."""
        return _materialization.to_table(self)

    def incremental_flush(self, threshold: int = 0) -> bool:
        """Flush accumulated batches into the cached table when above *threshold* rows.

        Unlike ``to_table()`` this is designed to be called periodically during
        streaming ingestion to bound memory. When the pending batch row count
        exceeds *threshold*, the batches are materialised into the cached table
        and the batch list is cleared.

        Returns ``True`` when batches were actually flushed, ``False`` otherwise.
        """
        return _materialization.incremental_flush(self, threshold)

    # --- streaming batch access ---

    def drain_batches(self) -> list[pa.RecordBatch]:
        """Return completed pending batches and remove them from the container.

        This releases ownership of every flushed ``RecordBatch`` without
        touching the in-flight accumulator or the cached table. After draining,
        :attr:`batch_total_rows` reflects only the rows still held in the
        accumulator.

        Returns an empty list when no batches are pending.
        """
        with self._lock:
            batches = self.batches
            self.batches = []
            self._pending_batch_rows = 0
        return batches

    def flush_partial(self) -> pa.RecordBatch | None:
        """Flush the in-flight accumulator and return the resulting batch.

        Unlike :meth:`flush`, this returns the newly created ``RecordBatch`` and
        removes it from the pending batch list so a later :meth:`to_table` call
        does not materialize it a second time. Returns ``None`` when the
        accumulator holds no rows.
        """
        with self._lock:
            if self._current_count == 0:
                return None
            self.flush()
            batch = self.batches.pop()
            self._pending_batch_rows -= batch.num_rows
        return batch

    def iter_batches(self) -> Iterator[pa.RecordBatch]:
        """Yield completed batches one at a time, releasing each as it is yielded.

        Batches are yielded in FIFO order and removed from the container as they
        are produced, so memory is not retained for already-yielded batches. The
        in-flight accumulator is left untouched; call :meth:`flush_partial`
        first to emit a trailing short batch.
        """
        while True:
            with self._lock:
                if not self.batches:
                    break
                batch = self.batches.pop(0)
                self._pending_batch_rows -= batch.num_rows
            yield batch

    def to_polars_frame(self) -> pl.DataFrame:
        """Materialize the container as a Polars DataFrame."""
        return _materialization.to_polars_frame(self)

    def reset(self) -> None:
        """Clear accumulated data, batches, cached table, extras, and caches."""
        _materialization.reset(self)

    # --- compatibility aliases ---

    def to_arrow(self) -> pa.Table:
        """Backward-compatible alias for materializing an Arrow table."""
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
