"""Shared Arrow-backed record containers for ETL-style ingestion flows."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

import polars as pl
import pyarrow as pa

from http_to_arrow import _appending
from http_to_arrow import _materialization
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
        doc="Number of accumulated records that triggers a flush to a RecordBatch.",
    )
    unknown_field_policy: UnknownFieldPolicy = field(
        default="drop",
        doc="How to handle explicit-schema record keys that are not schema fields.",
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
            "explicit schema is supplied. Qualifying columns are flushed as "
            "dictionary-typed Arrow arrays."
        ),
    )
    dictionary_cardinality_threshold: float = field(
        default=0.5,
        doc=(
            "Maximum unique/row ratio at which a string column will be dictionary "
            "encoded. Must be in [0.0, 1.0]. Ignored when dictionary_encode is False "
            "or no explicit schema is supplied."
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
        doc=(
            "Captured explicit-schema extra fields when unknown_field_policy='capture'."
        ),
    )
    _schema_fields: tuple[pa.Field, ...] = field(
        default_factory=tuple,
        init=False,
        repr=False,
        doc=(
            "Cached schema fields for quick access during appends. Kept in sync with "
            "self.schema and used for field order during flushes."
        ),
    )
    _schema_field_names: frozenset[str] = field(
        default_factory=frozenset,
        init=False,
        repr=False,
        doc="Cached schema field names for quick access during appends.",
    )
    _uses_default_normalizer: bool = field(
        default=False,
        init=False,
        repr=False,
        doc=(
            "Whether the normalizer method is the default no-op implementation, used to "
            "optimize record preparation by avoiding unnecessary copying of dict records."
        ),
    )
    _schema_explicit: bool = field(
        default=False,
        init=False,
        repr=False,
        doc=(
            "Whether the container schema was explicitly provided at initialization, as "
            "opposed to being inferred from appended records. This controls whether "
            "schema growth is allowed during appends and whether dictionary encoding can "
            "be applied."
        ),
    )
    _inferred_name_map: dict[str, str] = field(
        default_factory=dict,
        init=False,
        repr=False,
        doc=(
            "Mapping of lowercase field names to their first-seen canonical spelling, "
            "used by inferred-mode key resolution when case_insensitive_keys=True."
        ),
    )
    _accumulator: dict[str, list] = field(
        default_factory=dict,
        init=False,
        repr=False,
        doc=(
            "In-memory accumulator for incoming records, organized as lists of values "
            "for each schema field. Flushed into batches when batch_size is reached."
        ),
    )
    _current_count: int = field(
        default=0,
        init=False,
        repr=False,
        doc=(
            "Number of records currently held in the accumulator, used to determine "
            "when to flush into a batch."
        ),
    )
    _pending_batch_rows: int = field(
        default=0,
        init=False,
        repr=False,
        doc=(
            "Total number of rows across all batches that have been flushed but not yet "
            "materialized into the cached table, used to trigger incremental flushes."
        ),
    )
    _materialized_schema: pa.Schema | None = field(
        default=None,
        init=False,
        repr=False,
        doc=(
            "Cached effective schema reflecting any promoted dictionary types for "
            "flushed batches and the cached table. When dictionary encoding is enabled, "
            "this schema is used for subsequent batches to ensure type compatibility."
        ),
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        doc=(
            "Thread lock used by materialization paths that flush and merge pending "
            "batches. Direct appends and direct flush() calls are not synchronized and "
            "should be externally coordinated in multithreaded contexts."
        ),
    )

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
