# Profiling scripts

Manual profiling and benchmarking utilities. These are intentionally outside
of `src/` and `tests/` so they do not participate in package distribution,
pytest discovery, or the coverage gate.

Install the optional profiling dependencies once:

```bash
uv sync --group profiling
```

## `profile_http_to_arrow.py`

Generates a deterministic stream of complex JSON-like records, ingests them
through `ArrowRecordContainer` with an explicit Arrow schema, and emits a
human-readable summary plus an optional JSON summary suitable for
side-by-side regression comparison.

### Scenarios

- `nested-http` (default): mixed low/medium/high cardinality strings,
  nested `request`/`response` structs, ISO timestamp coercion, mapping
  headers coerced to `list<struct<key, value>>`, and a `timings` list of
  structs.
- `dictionary-friendly`: same schema, but user/request identifiers are kept
  low-cardinality so `--dictionary-encode` should produce visible wins.
- `high-cardinality`: tenant ids are pushed into the millions so string
  columns mostly fail the dictionary cardinality threshold; useful for
  catching dictionary-encoding regressions or wasted overhead.

### Baseline run

```bash
uv run --group profiling python scripts/profile_http_to_arrow.py \
  --rows 1000000 \
  --scenario nested-http \
  --summary-out profiles/http_to_arrow/baseline_nested_1m.json
```

### Optimized comparison run

```bash
uv run --group profiling python scripts/profile_http_to_arrow.py \
  --rows 1000000 \
  --scenario nested-http \
  --dictionary-encode \
  --compact-on-materialize \
  --eager-clear-accumulator \
  --summary-out profiles/http_to_arrow/optimized_nested_1m.json \
  --compare-to profiles/http_to_arrow/baseline_nested_1m.json
```

### Scalene memory attribution

```bash
uv run --group profiling scalene \
  --html \
  --outfile profiles/http_to_arrow/scalene_nested_1m.html \
  scripts/profile_http_to_arrow.py \
  --rows 1000000 \
  --scenario nested-http
```

### Pyinstrument CPU profile

```bash
uv run --group profiling python -m pyinstrument \
  --html \
  -o profiles/http_to_arrow/pyinstrument_nested_1m.html \
  scripts/profile_http_to_arrow.py \
  --rows 1000000 \
  --scenario nested-http
```

### Smoke run

```bash
uv run --group profiling python scripts/profile_http_to_arrow.py \
  --rows 1000 \
  --scenario nested-http
```

## Interpreting the summary

The script reports:

- `ingest_seconds`, `materialize_seconds`, `total_seconds`, and
  `rows_per_second` measured via `time.perf_counter`.
- `peak_rss_mib` from `resource.getrusage(RUSAGE_SELF)`. This is a coarse
  process-wide peak that is most useful for comparing two runs on the same
  machine.
- `table_num_bytes` and `max_chunks` (per-column chunk count) from the
  materialized `pyarrow.Table`.
- `dictionary_columns` listing which schema fields ended up dictionary-typed
  in the final table.
- Python, PyArrow, package, platform, and git commit metadata for
  reproducibility.

Summaries are written under `profiles/http_to_arrow/` which is git-ignored.
Treat comparisons as advisory rather than pass/fail: peak RSS and timings
are machine-dependent and will vary inside devcontainers vs. CI runners.
