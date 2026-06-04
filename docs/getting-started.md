# Getting Started

The main entry point is `ArrowRecordContainer`. It accepts mapping records,
batches them into Arrow record batches, and materializes them as a PyArrow
table when requested.

!!! tip
    Start with an explicit schema when you know the output contract. Use
    inferred mode for exploratory ingestion or flexible upstream payloads.

## Explicit schema

Use an explicit schema when the target data shape is known ahead of time.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema(
        [
            pa.field("id", pa.int64()),
            pa.field("name", pa.string()),
        ]
    ),
    batch_size=2,
)

container.append({"id": 1, "name": "alpha"})
container.append({"id": 2, "name": "beta"})

table = container.to_table()
assert table.to_pydict() == {"id": [1, 2], "name": ["alpha", "beta"]}
```

## Inferred schema

Pass `schema=None` to infer the schema from appended records. Inferred mode
keeps the first-seen column spelling when `case_insensitive_keys=True`.

!!! note
    Inferred mode can add fields and widen compatible types as records arrive,
    but it still needs at least one non-empty record before materialization.

```python
from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=None)

container.append({"ID": 1})
container.append({"id": 2, "name": "beta"})

table = container.to_table()
assert table.to_pydict() == {
    "ID": [1, 2],
    "name": [None, "beta"],
}
```

The second record adds the `name` field, and the earlier row is backfilled with
`None`.

## Common first steps

1. Decide whether your input stream has a stable schema.
2. Use an explicit `pyarrow.Schema` when the contract is known.
3. Use `schema=None` for exploratory ingestion or flexible upstream payloads.
4. Append records with `append()` or `extend()`.
5. Materialize with `to_table()` for PyArrow or `to_polars_frame()` for Polars.

No authentication or external service configuration is required. The container
operates entirely in memory until you materialize or write the resulting table.
