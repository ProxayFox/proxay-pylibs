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

## Example

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([
        pa.field("id", pa.int64()),
        pa.field("name", pa.string()),
    ])
)
```
