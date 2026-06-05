# Memory Tuning

The default settings preserve straightforward ingestion behavior. Enable memory
tuning options only when your workload benefits from the tradeoff.

!!! note
    These options tune in-memory batching and materialization. They do not write
    data to disk or change how callers fetch upstream records.

## Batch size

`batch_size` controls how many records stay in Python lists before conversion
to an Arrow `RecordBatch`.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("id", pa.int64())]),
    batch_size=10_000,
)
```

Lower values reduce accumulator size but create more batches. Higher values can
reduce batch overhead but increase peak memory before each flush.

## Incremental materialization

Use `incremental_flush()` during long streams to merge pending batches into the
cached table when pending rows exceed a threshold.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("id", pa.int64())]),
    batch_size=10_000,
)
records = ({"id": value} for value in range(250_000))

for record in records:
    container.append(record)
    if container.incremental_flush(threshold=100_000):
        print(container.total_rows)
```

## Dictionary encoding

Set `dictionary_encode=True` for explicit schemas when string columns are often
low cardinality.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(
    schema=pa.schema([pa.field("tenant", pa.string())]),
    dictionary_encode=True,
    dictionary_cardinality_threshold=0.25,
)
```

Once a column is encoded, later batches are encoded too so batch schemas remain
compatible during materialization.

## Chunk compaction

`compact_on_materialize=True` calls `pyarrow.Table.combine_chunks()` after
materializing pending batches.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

schema = pa.schema([pa.field("id", pa.int64())])

container = ArrowRecordContainer(
    schema=schema,
    compact_on_materialize=True,
)
```

This can reduce chunk fragmentation when many batches are produced.

## Eager accumulator clearing

`eager_clear_accumulator=True` releases each accumulator column list after its
Arrow array is built during `flush()`.

```python
import pyarrow as pa

from http_to_arrow import ArrowRecordContainer

schema = pa.schema([pa.field("id", pa.int64())])

container = ArrowRecordContainer(
    schema=schema,
    eager_clear_accumulator=True,
)
```

This is opt in because it changes failure semantics. If a later column fails
mid-flush, earlier cleared columns cannot be converted again from the same
in-flight rows.

## Profiling utilities

Manual profiling scripts live under `scripts/` and are not part of the package
distribution. See [Performance And Profiling](performance-and-profiling.md) for
the full workflow. For a smoke run:

```bash
uv run --group profiling python scripts/profile_http_to_arrow.py \
  --rows 1000 \
  --scenario nested-http
```

Use profiling results as advisory data. Peak memory and timings vary by machine
and runtime environment.
