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

### Fixture caching

Generated records are cached as gzipped JSONL files keyed by
`(scenario, rows, seed)` so a 1M+ row run is generated once and reused on
every subsequent invocation (and across both sides of a comparison).

- Default cache directory: `profiles/http_to_arrow/fixtures/` (git-ignored).
- Filename pattern: `<scenario>_rows<N>_seed<S>.jsonl.gz`.
- The cache preserves the JSON-dict shape on purpose so the profiler still
  exercises the `ArrowRecordContainer` coercion path. JSON-parse cost is
  rolled into `ingest_seconds`; it's constant across runs reading the same
  file, so deltas remain meaningful.
- Pre-warm a cache without running the benchmark:

  ```bash
  uv run --group profiling python scripts/profile_http_to_arrow.py \
    --rows 1000000 --scenario nested-http \
    --generate-fixture-only
  ```

- Force a rebuild: `--regenerate-fixture`.
- Skip the cache entirely (stream from the in-memory generator):
  `--no-fixture-cache`.
- Custom location: `--fixture-cache-dir PATH` or `--fixture-path PATH`.

## `compare_http_to_arrow.py`

Orchestrates a two-sided comparison without leaving your feature branch.
It resolves a target git ref (default `origin/main`), creates a temporary
worktree at that commit, copies the *current* profiler script into the
worktree so measurement code is identical on both sides, runs the baseline,
then runs the current branch with `--compare-to` and prints deltas. The
worktree is cleaned up on exit unless `--keep-worktree` is set.

### Default comparison (current branch vs `origin/main`)

```bash
uv run --group profiling python scripts/compare_http_to_arrow.py \
  --rows 1000000 --scenario nested-http
```

By default the branch run enables
`--dictionary-encode --compact-on-materialize --eager-clear-accumulator`
so the comparison shows the memory-optimization deltas.

### Compare against the merge-base instead of the ref tip

This isolates *this branch's* changes from unrelated `main` movement:

```bash
uv run --group profiling python scripts/compare_http_to_arrow.py \
  --ref origin/main --merge-base \
  --rows 1000000 --scenario nested-http
```

### Customize per-side flags

```bash
uv run --group profiling python scripts/compare_http_to_arrow.py \
  --ref origin/main \
  --rows 1000000 --scenario dictionary-friendly \
  --baseline-extra "" \
  --branch-extra "--dictionary-encode --compact-on-materialize"
```

### Convenience just recipe

```bash
just profile-http-to-arrow-vs origin/main 1000000 --merge-base
```

### Notes

- The orchestrator runs `git fetch origin` once unless `--no-fetch` is
  passed. Use `--no-fetch` for offline runs.
- `uv sync --all-packages --group profiling` runs once inside the worktree
  (the `--all-packages` is required so the workspace member
  `http_to_arrow` is installed). Only pass `--skip-uv-sync` if you're
  reusing a pre-prepared worktree via `--worktree-dir` whose `.venv`
  already has the workspace installed; a fresh worktree will fail without
  the sync.
- Summaries land in `profiles/http_to_arrow/` (git-ignored). The baseline
  filename includes the resolved short SHA so repeated runs against
  different commits don't overwrite each other.
- The shared fixture is pre-generated once in the parent repo before either
  side runs, then both baseline and branch read the same bytes from
  `profiles/http_to_arrow/fixtures/`. Pass `--regenerate-fixture` to force
  a rebuild or `--no-fixture-cache` to skip caching entirely.

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
