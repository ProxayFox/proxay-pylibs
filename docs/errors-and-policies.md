# Errors And Policies

The container exposes policy aliases for explicit-schema ingestion behavior:

- `UnknownFieldPolicy = Literal["drop", "error", "capture"]`
- `MissingFieldPolicy = Literal["null", "error"]`
- `CoercionPolicy = Literal["coerce", "strict"]`

!!! tip
    Use `"error"` policies near trust boundaries where malformed records should
    fail fast. Use `"drop"`, `"capture"`, or `"null"` when ingestion should
    continue and the caller can inspect or tolerate the differences.

## Unknown fields

Unknown fields are extra record keys that are not present in an explicit schema.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

schema = pa.schema([pa.field("id", pa.int64())])

drop_container = ArrowRecordContainer(schema=schema)
drop_container.append({"id": 1, "extra": "ignored"})

capture_container = ArrowRecordContainer(
    schema=schema,
    unknown_field_policy="capture",
)
capture_container.append({"id": 2, "extra": "kept"})

assert capture_container.captured_extras == [{"extra": "kept"}]
```

Use `unknown_field_policy="error"` to reject records with extra keys.

!!! note
    `unknown_field_policy` applies to explicit schemas. In inferred mode, new
    fields grow the schema instead of being treated as unknown.

## Missing fields

Missing fields are schema fields absent from an incoming record. The default
policy fills them with nulls.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema(
        [
            pa.field("id", pa.int64()),
            pa.field("name", pa.string()),
        ]
    )
)

container.append({"id": 1})
assert container.to_table().to_pydict() == {"id": [1], "name": [None]}
```

Use `missing_field_policy="error"` when missing values should fail ingestion.

## Coercion

The default `coercion_policy="coerce"` converts values into shapes compatible
with the configured Arrow type where supported. For example, ISO timestamp
strings are parsed for timestamp fields, and mappings can be reshaped into
lists of two-field structs.

Use `coercion_policy="strict"` to pass values directly to PyArrow array
construction.

## Common ValueError cases

- Cached table schema does not match the explicit container schema.
- `dictionary_cardinality_threshold` is outside `[0.0, 1.0]`.
- Inferred mode receives an empty first record.
- Inferred mode is materialized before any schema or records exist.
- `missing_field_policy="error"` receives a record without a required field.
- `unknown_field_policy="error"` receives a record with extra fields.
- PyArrow rejects values while building a column during `flush()`.
