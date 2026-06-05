# http-to-arrow

`http-to-arrow` is a small Python library for turning streaming mapping records
into Apache Arrow data. It gives ETL and HTTP ingestion code a predictable place
to batch records, apply schema-aware coercion, and materialize the result as a
PyArrow table or Polars data frame.

!!! note "Library scope"
  `http-to-arrow` does not make HTTP requests. Bring your own client,
  parser, queue consumer, or stream reader, then pass decoded records into
  `ArrowRecordContainer`.

## Key features

- Explicit PyArrow schemas for predictable ingestion contracts.
- Inferred schemas that widen as new fields or compatible types appear.
- Field policies for unknown fields, missing fields, coercion, and key casing.
- Batch flushing and incremental materialization for high-volume streams.
- Async Arrow IPC streaming for memory-constrained producers and consumers.
- Optional memory controls for dictionary encoding, chunk compaction, and eager
  accumulator cleanup.
- Conversion helpers for PyArrow and Polars consumers.

## When to use it

Use `http-to-arrow` when you already have Python mapping records and want to
stage them efficiently for Arrow-native analytics. It is especially useful for
API ingestion, JSON-like ETL payloads, and test-backed pipelines that need a
small, explicit boundary between record collection and columnar processing.

## Quick install

```bash
pip install http-to-arrow
```

!!! tip "Import name"
  Install the distribution as `http-to-arrow`, then import it as
  `http_to_arrow`.

## Minimal example

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

container.extend(
    [
        {"id": 1, "name": "alpha"},
        {"id": 2, "name": "beta"},
    ]
)

table = container.to_table()
print(table.to_pydict())
```

Expected output:

```python
{"id": [1, 2], "name": ["alpha", "beta"]}
```

## Documentation map

- [Getting Started](getting-started.md) walks through the first explicit and
  inferred schema examples.
- [Usage](usage.md) covers the common ingestion and materialization workflows.
- [Configuration](configuration.md) documents constructor options and defaults.
- [Streaming IPC](streaming-ipc.md) explains async Arrow IPC chunk streaming.
- [Performance And Profiling](performance-and-profiling.md) covers profiling
  scripts and benchmark matrix artifacts.
- [API Reference](api/index.md) contains generated reference pages from the
  current Python modules.
- [Development](development.md) explains the repository workflow for
  contributors.

## Status

The current package version is `0.2.0` and requires Python `>=3.14`. The public
library surface is intentionally small: `ArrowRecordContainer`,
`ArrowIPCStream`, `IPCStreamSink`, and the policy aliases exported by
`http_to_arrow`.

See [Changelog](changelog.md) for the current release notes.
