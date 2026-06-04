# Examples

These examples use APIs that are present in the current package and behavior
covered by the test suite.

## Explicit schema ingestion

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

container.append({"id": 1, "name": "alpha"})
container.append({"id": 2, "name": "beta"})

assert container.to_table().to_pydict() == {
    "id": [1, 2],
    "name": ["alpha", "beta"],
}
```

## Inferred schema with backfill

```python
from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=None, batch_size=1)

container.append({"id": 1})
container.append({"id": 2, "name": "beta"})

assert container.to_table().to_pydict() == {
    "id": [1, 2],
    "name": [None, "beta"],
}
```

## Capture unknown fields

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("id", pa.int64())]),
    unknown_field_policy="capture",
)

container.append({"id": 1, "extra": "kept"})

assert container.captured_extras == [{"extra": "kept"}]
assert container.to_table().column("id").to_pylist() == [1]
```

## Reject missing fields

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
    missing_field_policy="error",
)

try:
    container.append({"id": 1})
except ValueError as exc:
    assert "Missing required schema field 'name'" in str(exc)
```

## Case-insensitive keys

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("id", pa.int64())])
)

container.append({"ID": 42})
assert container.to_table().column("id").to_pylist() == [42]
```

## Incremental flushing

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("id", pa.int64())]),
    batch_size=2,
)

container.extend([{"id": 1}, {"id": 2}, {"id": 3}])

flushed = container.incremental_flush(threshold=2)

assert flushed is True
assert container.batch_total_rows == 0
assert container.total_rows == 3
```

## Convert to Polars

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=pa.schema([pa.field("id", pa.int64())]))
container.append({"id": 5})

frame = container.to_polars_frame()
assert frame.to_dict(as_series=False) == {"id": [5]}
```

## Custom record normalizer

```python
from typing import Any, Mapping

import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

class UpperSourceContainer(ArrowRecordContainer):
    def normalize_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {key.lower(): value for key, value in record.items()}

container = UpperSourceContainer(schema=pa.schema([pa.field("id", pa.int64())]))
container.append({"ID": 7})

assert container.to_table().column("id").to_pylist() == [7]
```
