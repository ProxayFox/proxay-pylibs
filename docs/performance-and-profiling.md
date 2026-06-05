# Performance And Profiling

Use the profiling tools when you need evidence for `http-to-arrow` memory or
throughput changes. They are manual developer utilities, not package runtime
features.

## Profiling scripts

The detailed script guide lives in `scripts/README.md` at the repository root.
Start with a smoke run before collecting large samples:

```bash
uv run --group profiling python scripts/profile_http_to_arrow.py \
  --rows 1000 \
  --scenario nested-http
```

The profiler records ingestion time, materialization time, rows per second,
peak RSS, Arrow table bytes, chunk counts, dictionary-encoded columns, and
environment metadata.

## Comparing refs

Use `compare_http_to_arrow.py` when you need a local branch-vs-ref comparison
with the same fixture bytes on both sides:

```bash
just profile-http-to-arrow-vs origin/main 1000000 --merge-base
```

The comparison command creates a temporary worktree for the baseline ref and
cleans it up after the run unless you ask it to keep the worktree.

## Benchmark matrix

Use the matrix benchmark when you need per-knob attribution for
`dictionary_encode`, `compact_on_materialize`, and `eager_clear_accumulator`:

```bash
just profile-http-to-arrow-matrix origin/main 1000000 --merge-base
```

The committed artifact lives in
`benchmarks/http_to_arrow/COMPARISON_MATRIX.md`, with a sibling CSV at
`benchmarks/http_to_arrow/comparison_matrix.csv`.

## Freshness policy

Treat benchmark artifacts as generated evidence. Do not manually update run
metadata such as package version, commit SHA, Python version, PyArrow version,
or captured timestamp. Regenerate the matrix when those values need to reflect a
new code state.

Performance numbers are machine-dependent. Use them to compare runs collected
under the same environment and fixture inputs, not as universal pass/fail
thresholds.
