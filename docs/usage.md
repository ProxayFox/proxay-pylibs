# Usage

`ArrowRecordContainer` is designed for synchronous ingestion of Python mapping
records. It does not perform HTTP requests itself; callers provide records from
their own client, parser, stream, or ETL layer.

## Append records

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("id", pa.int64())]),
    batch_size=2,
)

container.append({"id": 1})
container.extend([{"id": 2}, {"id": 3}])

assert container.total_rows == 3
```

`batch_size` controls when the in-memory accumulator is converted to a pending
Arrow `RecordBatch`. It does not force materialization into the cached table;
use `to_table()` or `incremental_flush()` for that.

## Materialize Arrow and Polars outputs

```python
table = container.to_table()
arrow_again = container.to_arrow()

polars_frame = container.to_polars_frame()
polars_again = container.to_polars()

assert table is arrow_again
assert polars_frame.shape == polars_again.shape
```

`to_arrow()` and `to_polars()` are compatibility aliases for `to_table()` and
`to_polars_frame()`.

## Flush incrementally

For long streams, call `incremental_flush()` periodically to merge pending
batches into the cached table and clear the batch list.

!!! tip
    Use `incremental_flush()` inside the loop that reads your upstream records.
    This keeps pending Arrow batches bounded without forcing every append to
    rebuild the cached table.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("id", pa.int64())]),
    batch_size=2,
)

container.extend([{"id": 1}, {"id": 2}, {"id": 3}])

assert container.incremental_flush(threshold=2) is True
assert container.batch_total_rows == 0
assert container.total_rows == 3
```

`incremental_flush(threshold=N)` returns `True` only when pending batch rows are
greater than `N`.

## Reset state

```python
container.reset()
assert container.total_rows == 0

container.clear()
assert container.batch_total_rows == 0
```

`clear()` is a compatibility alias for `reset()`.

## Normalize records before ingestion

Subclass `ArrowRecordContainer` to normalize incoming records before schema
matching and coercion.

```python
from typing import Any, Mapping

import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

class LowerKeyContainer(ArrowRecordContainer):
    def normalize_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {key.lower(): value for key, value in record.items()}

container = LowerKeyContainer(schema=pa.schema([pa.field("id", pa.int64())]))
container.append({"ID": 7})

assert container.to_table().column("id").to_pylist() == [7]
```

## Concurrency model

`to_table()` and `incremental_flush()` synchronize their materialization paths.
Direct `append()` and direct `flush()` calls are not synchronized, so coordinate
multi-threaded appenders outside the container.

!!! warning
    Do not share one container across multiple append threads unless your
    application provides the synchronization around `append()` and `flush()`.

## Not provided by this package

`http-to-arrow` has no retry, pagination, authentication, HTTP client, or async
API layer. Compose it with the networking or streaming library that owns those
concerns in your application.
