"""Base classes and shared functionality for ArrowRecordContainer implementations."""

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from http_to_arrow._policies import (
    CoercionPolicy,
    MissingFieldPolicy,
    UnknownFieldPolicy,
)

if TYPE_CHECKING:
    import pyarrow as pa


@dataclass
class BaseArrowRecordContainer:
    """Base class for ArrowRecordContainer.

    This class is intended to be used as a base for the actual ArrowRecordContainer
    implementations, providing common functionality and structure.
    """

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


@dataclass
class ArrowRecordContainerSettings:
    """Settings for ArrowRecordContainer.

    This class is intended to be used as a base for the actual ArrowRecordContainer
    implementations, providing common settings and configuration options.
    """

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
