# Configuration

`http-to-arrow` is configured through `ArrowRecordContainer` constructor
arguments. There is no config file format, environment variable contract, or
authentication system.

!!! note
  Constructor options are the complete runtime configuration surface for the
  package today.

## Constructor options

`schema`
: A `pyarrow.Schema`, or `None` to infer a schema from appended records.

`table`
: Optional cached `pyarrow.Table` to seed the container. If `schema=None`, the
  table schema is adopted.

`batch_size`
: Number of accumulated records that triggers conversion to a pending Arrow
  batch. Default: `128000`.

`unknown_field_policy`
: Explicit-schema behavior for record keys that are not schema fields.
  Supported values are `"drop"`, `"error"`, and `"capture"`. Default: `"drop"`.

`missing_field_policy`
: Behavior for schema fields missing from incoming records. Supported values
  are `"null"` and `"error"`. Default: `"null"`.

`coercion_policy`
: Whether values are coerced into schema-compatible Arrow shapes. Supported
  values are `"coerce"` and `"strict"`. Default: `"coerce"`.

`case_insensitive_keys`
: Resolve incoming keys case-insensitively when exact matches are absent.
  Default: `True`.

`dictionary_encode`
: Opt in to dictionary encoding for low-cardinality string columns when an
  explicit schema is supplied. Default: `False`.

`dictionary_cardinality_threshold`
: Maximum `unique_values / row_count` ratio at which string columns are
  dictionary-encoded. Must be between `0.0` and `1.0`. Default: `0.5`.

`compact_on_materialize`
: Run `pyarrow.Table.combine_chunks()` after materializing pending batches.
  Default: `False`.

`eager_clear_accumulator`
: Clear each accumulator column list as soon as its Arrow array is built during
  `flush()`. This can lower peak memory, but changes failure retry semantics.
  Default: `False`.

!!! warning "Memory tradeoff"
    `eager_clear_accumulator=True` can reduce peak memory, but if a later column
    fails during `flush()`, earlier cleared column lists cannot be retried from
    the same in-flight rows.

## Security-sensitive values

The package does not accept credentials, tokens, connection strings, or other
secret-bearing options. Do not add secrets to examples or serialized data unless
your surrounding application explicitly needs them and handles them securely.

## Logging

`http-to-arrow` does not configure logging. Add logging in the calling
application around ingestion, flushing, and materialization if you need
operational visibility.
