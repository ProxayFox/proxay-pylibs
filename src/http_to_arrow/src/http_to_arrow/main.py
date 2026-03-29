"""Shared Arrow-backed record containers for ETL-style ingestion flows."""

from __future__ import annotations

import pyarrow as pa
import polars as pl
import threading

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Mapping, cast


UnknownFieldPolicy = Literal["drop", "error", "capture"]
MissingFieldPolicy = Literal["null", "error"]
CoercionPolicy = Literal["coerce", "strict"]


@dataclass
class ArrowRecordContainer:
    """Batch incoming records into Arrow tables using a fixed schema."""

    schema: pa.Schema = field(
        init=True, doc="PyArrow schema for the container data.")
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
    _uses_default_normalizer: bool = field(
        default=False, init=False, repr=False)
    _accumulator: dict[str, list] = field(
        default_factory=dict, init=False, repr=False)
    _current_count: int = field(default=0, init=False, repr=False)
    _pending_batch_rows: int = field(default=0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.table is not None and not self.table.schema.equals(self.schema):
            raise ValueError(
                "Cached table schema must match the container schema."
            )

        self._schema_fields = tuple(self.schema)
        self._schema_field_names = frozenset(
            arrow_field.name for arrow_field in self._schema_fields
        )
        self._uses_default_normalizer = (
            type(self).normalize_record is ArrowRecordContainer.normalize_record
        )
        self._pending_batch_rows = sum(b.num_rows for b in self.batches)
        self._init_accumulator()

    def _init_accumulator(self) -> None:
        """Initialize empty lists for each schema field."""
        self._accumulator = {
            arrow_field.name: [] for arrow_field in self._schema_fields
        }
        self._current_count = 0

    def normalize_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Normalize records before schema matching and coercion."""
        return dict(record)

    def _prepare_record(self, record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Avoid copying plain dict records when using the default normalizer."""
        if self._uses_default_normalizer and isinstance(record, dict):
            return record
        return self.normalize_record(record)

    @classmethod
    def _coerce_timestamp_value(cls, value: Any) -> datetime | Any | None:
        """Parse ISO-8601 strings while preserving the represented instant."""
        if not isinstance(value, str):
            return value

        iso_value = value.strip()
        if iso_value.endswith("Z"):
            iso_value = f"{iso_value[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(iso_value)
        except (ValueError, TypeError):
            return None

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

        return parsed

    @classmethod
    def _coerce_value(cls, value: Any, arrow_type: pa.DataType):
        """Recursively coerce a value to match the given PyArrow type."""
        if value is None:
            return None

        if pa.types.is_timestamp(arrow_type):
            return cls._coerce_timestamp_value(value)

        if pa.types.is_struct(arrow_type):
            if not isinstance(value, Mapping):
                return value

            return {
                arrow_field.name: cls._coerce_value(
                    value.get(arrow_field.name), arrow_field.type
                )
                for arrow_field in arrow_type
            }

        if pa.types.is_list(arrow_type) or pa.types.is_large_list(arrow_type):
            item_type = cast(pa.DataType, arrow_type.value_type)
            if (
                isinstance(value, Mapping)
                and pa.types.is_struct(item_type)
                and item_type.num_fields == 2
            ):
                first_field = item_type.field(0).name
                second_field = item_type.field(1).name
                value = [
                    {first_field: key, second_field: item_value}
                    for key, item_value in value.items()
                ]

            if not isinstance(value, list):
                return value

            return [cls._coerce_value(item, item_type) for item in value]

        return value

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
            raise ValueError(
                f"Unexpected fields not present in schema: {extra_keys}")

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
                self._coerce_value(raw_value, arrow_field.type)
                if self.coercion_policy == "coerce"
                else raw_value
            )
            self._accumulator[arrow_field.name].append(value)

        self._current_count += 1
        if self._current_count >= self.batch_size:
            self.flush()

        return True

    def append(self, record: Mapping[str, Any]) -> None:
        """Append a single record to the container."""
        normalized_record = self._prepare_record(record)
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
                self._coerce_value(raw_value, arrow_field.type)
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

    def flush(self) -> None:
        """Convert accumulated records into a RecordBatch."""
        if self._current_count == 0:
            return

        arrays: list[pa.Array] = []
        for arrow_field in self._schema_fields:
            try:
                array = pa.array(
                    self._accumulator[arrow_field.name],
                    type=arrow_field.type,
                    from_pandas=False,
                )
            except pa.lib.ArrowInvalid as exc:
                raise ValueError(
                    f"Invalid data for column '{arrow_field.name}': {exc}"
                ) from exc
            except Exception as exc:
                raise ValueError(
                    f"Error processing column '{arrow_field.name}': {exc}"
                ) from exc

            arrays.append(array)

        self.batches.append(pa.RecordBatch.from_arrays(
            arrays, schema=self.schema))
        self._pending_batch_rows += self.batches[-1].num_rows
        self._init_accumulator()

    def _flush_batch(self) -> None:
        """Backward-compatible alias for flushing the active batch."""
        self.flush()

    def to_table(self) -> pa.Table:
        """Materialize any pending batches into a cached Arrow table."""
        with self._lock:
            self.flush()

            if not self.batches:
                if self.table is None:
                    self.table = pa.Table.from_batches([], schema=self.schema)
                return self.table

            batch_table = pa.Table.from_batches(
                self.batches, schema=self.schema)
            self.table = (
                pa.concat_tables([self.table, batch_table])
                if self.table is not None
                else batch_table
            )
            self.batches.clear()
            self._pending_batch_rows = 0
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

            batch_table = pa.Table.from_batches(
                self.batches, schema=self.schema)
            self.table = (
                pa.concat_tables([self.table, batch_table])
                if self.table is not None
                else batch_table
            )
            self.batches.clear()
            self._pending_batch_rows = 0
            return True

    def to_polars_frame(self) -> pl.DataFrame:
        """Materialize the container as a Polars DataFrame."""
        if self.table is not None and not self.batches and self._current_count == 0:
            return cast(pl.DataFrame, pl.from_arrow(self.table))

        return cast(pl.DataFrame, pl.from_arrow(self.to_table()))

    def reset(self) -> None:
        """Clear accumulated data, batches, cached table, and captured extras."""
        self._init_accumulator()
        self.batches.clear()
        self._pending_batch_rows = 0
        self.captured_extras.clear()
        self.table = None

    @property
    def to_arrow(self) -> pa.Table:
        """Backward-compatible alias for materializing the cached Arrow table."""
        return self.to_table()

    @property
    def to_polars(self) -> pl.DataFrame:
        """Backward-compatible alias for materializing a Polars DataFrame."""
        return self.to_polars_frame()

    @property
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
