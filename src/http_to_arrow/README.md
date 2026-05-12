# http-to-arrow

`http-to-arrow` provides Arrow-backed containers for streaming HTTP and ETL-style
ingestion workflows.

The package uses a standard source layout so code lives under
`src/http_to_arrow/` rather than the project root.

Package-specific tests live under `tests/` inside this workspace member, while
the monorepo root can still host shared integration tests when needed.

## Included exports

- `ArrowRecordContainer`
- `UnknownFieldPolicy`
- `MissingFieldPolicy`
- `CoercionPolicy`

## Explicit schema

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([
        pa.field("id", pa.int64()),
        pa.field("name", pa.string()),
    ])
)

container.append({"id": 1, "name": "alpha"})
```

## Inferred schema

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

## Notes

- `schema=None` enables inferred mode.
- Inferred mode widens as new fields appear and backfills older rows with nulls.
- Conflicting inferred field types widen when possible and otherwise fall back to `string`.
- `to_table()` raises when inferred mode has neither an explicit schema nor any appended records.
