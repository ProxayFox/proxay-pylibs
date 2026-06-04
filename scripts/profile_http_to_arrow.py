"""Manual performance and memory profiling harness for ``http_to_arrow``.

This script generates a deterministic stream of complex JSON-like records,
ingests them through the public :class:`ArrowRecordContainer` API with an
explicit Arrow schema, and writes a small machine-readable summary plus
human-readable metrics suitable for side-by-side comparison runs.

It is intentionally kept outside of ``src/`` and ``tests/`` so it does not
affect package distribution, pytest discovery, or the coverage gate.

Run with ``uv`` and the optional ``profiling`` dependency group::

    uv run --group profiling python scripts/profile_http_to_arrow.py \
        --rows 1000000 --scenario nested-http \
        --summary-out profiles/http_to_arrow/baseline_nested_1m.json

Pair with ``scalene`` for line-level memory attribution or ``pyinstrument``
for low-overhead CPU call-stack profiles. See ``scripts/README.md``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import platform
import random
import resource
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import pyarrow as pa

from http_to_arrow import ArrowRecordContainer


# ----------------------------- schema + fixtures -----------------------------

# Low and medium cardinality string vocabularies. These are intentionally
# small so the dictionary-encoding ratio stays well under 0.5 for the
# "nested-http" and "dictionary-friendly" scenarios.
SERVICES: tuple[str, ...] = (
    "api-gateway",
    "auth",
    "billing",
    "catalog",
    "checkout",
    "fulfillment",
    "notifications",
    "profile",
    "search",
    "telemetry",
)
METHODS: tuple[str, ...] = ("GET", "POST", "PUT", "PATCH", "DELETE")
STATUS_CODES: tuple[int, ...] = (200, 201, 204, 301, 302, 400, 401, 403, 404, 500, 503)
STATUS_FAMILIES: tuple[str, ...] = ("2xx", "3xx", "4xx", "5xx")
CACHE_STATUSES: tuple[str, ...] = ("HIT", "MISS", "BYPASS", "EXPIRED", "STALE")
ERROR_CODES: tuple[str, ...] = (
    "ok",
    "validation_failed",
    "auth_required",
    "permission_denied",
    "not_found",
    "rate_limited",
    "upstream_timeout",
    "internal_error",
)
CONTENT_TYPES: tuple[str, ...] = (
    "application/json",
    "application/xml",
    "text/html",
    "text/plain",
    "application/octet-stream",
)
TIMING_NAMES: tuple[str, ...] = (
    "dns_ms",
    "connect_ms",
    "tls_ms",
    "request_ms",
    "server_ms",
    "response_ms",
)
ROUTE_TEMPLATES: tuple[str, ...] = (
    "/v1/users/:id",
    "/v1/orders/:id",
    "/v1/orders/:id/items",
    "/v1/products",
    "/v1/products/:sku",
    "/v1/search",
    "/v1/sessions",
    "/internal/healthz",
)
TAG_VOCAB: tuple[str, ...] = (
    "prod",
    "canary",
    "experiment-a",
    "experiment-b",
    "retry",
    "deprecated",
    "v2",
    "legacy",
)


def build_http_event_schema() -> pa.Schema:
    """Schema for the default ``nested-http`` benchmark scenario.

    Exercises timestamp coercion, nested structs, lists of structs, the
    mapping-to-list-of-struct coercion path, and a mix of low/high cardinality
    string columns suitable for dictionary-encoding measurement.
    """
    request_struct = pa.struct(
        [
            pa.field("method", pa.string()),
            pa.field("path", pa.string()),
            pa.field("route", pa.string()),
            pa.field("query_params", pa.list_(pa.string())),
            pa.field(
                "headers",
                pa.list_(
                    pa.struct(
                        [
                            pa.field("key", pa.string()),
                            pa.field("value", pa.string()),
                        ]
                    )
                ),
            ),
        ]
    )
    response_struct = pa.struct(
        [
            pa.field("status", pa.int64()),
            pa.field("status_family", pa.string()),
            pa.field("content_type", pa.string()),
            pa.field("bytes_in", pa.int64()),
            pa.field("bytes_out", pa.int64()),
        ]
    )
    timing_struct = pa.struct(
        [
            pa.field("name", pa.string()),
            pa.field("value_ms", pa.float64()),
        ]
    )
    return pa.schema(
        [
            pa.field("event_id", pa.int64()),
            pa.field("event_at", pa.timestamp("us")),
            pa.field("tenant_id", pa.string()),
            pa.field("service", pa.string()),
            pa.field("trace_id", pa.string()),
            pa.field("request_id", pa.string()),
            pa.field("user_id", pa.string()),
            pa.field("cache_status", pa.string()),
            pa.field("error_code", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("request", request_struct),
            pa.field("response", response_struct),
            pa.field("timings", pa.list_(timing_struct)),
        ]
    )


# ----------------------------- record generators -----------------------------


def _iso_timestamp(rng: random.Random, base: datetime) -> str:
    """ISO-8601 string with a trailing ``Z`` to exercise timestamp coercion."""
    offset = timedelta(microseconds=rng.randint(0, 60 * 60 * 1_000_000))
    return (base + offset).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _tenant_id(rng: random.Random, scenario: str) -> str:
    if scenario == "high-cardinality":
        return f"tenant-{rng.randint(0, 2_000_000):07d}"
    return f"tenant-{rng.randint(0, 49):02d}"


def _user_id(rng: random.Random, scenario: str) -> str:
    if scenario == "dictionary-friendly":
        return f"usr-{rng.randint(0, 199):04d}"
    return f"usr-{rng.randint(0, 200_000):06d}"


def _trace_id(rng: random.Random) -> str:
    # Always high cardinality: 64-bit hex string.
    return f"{rng.getrandbits(64):016x}"


def _request_id(rng: random.Random, scenario: str) -> str:
    if scenario == "dictionary-friendly":
        return f"req-{rng.randint(0, 511):04d}"
    return f"req-{rng.getrandbits(48):012x}"


def _headers_mapping(rng: random.Random) -> dict[str, str]:
    """Headers as a mapping; ``ArrowRecordContainer`` coerces it to list<struct>."""
    headers: dict[str, str] = {
        "user-agent": rng.choice(
            (
                "Mozilla/5.0",
                "curl/8.5.0",
                "ProxayClient/1.2",
                "python-httpx/0.27",
            )
        ),
        "accept": rng.choice(CONTENT_TYPES),
    }
    if rng.random() < 0.6:
        headers["x-correlation-id"] = f"{rng.getrandbits(32):08x}"
    if rng.random() < 0.3:
        headers["x-feature-flag"] = rng.choice(("on", "off", "shadow"))
    return headers


def _query_params(rng: random.Random) -> list[str]:
    count = rng.randint(0, 4)
    return [f"k{rng.randint(0, 9)}=v{rng.randint(0, 99)}" for _ in range(count)]


def _tags(rng: random.Random) -> list[str]:
    count = rng.randint(0, 3)
    return rng.sample(TAG_VOCAB, k=count) if count else []


def _timings(rng: random.Random) -> list[dict[str, Any]]:
    return [
        {"name": name, "value_ms": round(rng.uniform(0.1, 250.0), 3)}
        for name in TIMING_NAMES
    ]


def _status_for_family(rng: random.Random, family: str) -> int:
    candidates = [code for code in STATUS_CODES if f"{code // 100}xx" == family]
    return rng.choice(candidates) if candidates else 200


def generate_record(index: int, rng: random.Random, scenario: str) -> dict[str, Any]:
    """Build a single complex record for the configured scenario."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    family = rng.choice(STATUS_FAMILIES)
    status = _status_for_family(rng, family)
    method = rng.choice(METHODS)
    route = rng.choice(ROUTE_TEMPLATES)
    path = route.replace(":id", str(rng.randint(1, 10_000))).replace(
        ":sku", f"sku-{rng.randint(1, 9999):04d}"
    )
    return {
        "event_id": index,
        "event_at": _iso_timestamp(rng, base),
        "tenant_id": _tenant_id(rng, scenario),
        "service": rng.choice(SERVICES),
        "trace_id": _trace_id(rng),
        "request_id": _request_id(rng, scenario),
        "user_id": _user_id(rng, scenario),
        "cache_status": rng.choice(CACHE_STATUSES),
        "error_code": rng.choice(ERROR_CODES),
        "tags": _tags(rng),
        "request": {
            "method": method,
            "path": path,
            "route": route,
            "query_params": _query_params(rng),
            # Passed as a Mapping; coerced to list<struct<key,value>> by the
            # container's mapping-to-list path.
            "headers": _headers_mapping(rng),
        },
        "response": {
            "status": status,
            "status_family": family,
            "content_type": rng.choice(CONTENT_TYPES),
            "bytes_in": rng.randint(0, 65_536),
            "bytes_out": rng.randint(0, 1_048_576),
        },
        "timings": _timings(rng),
    }


def iter_records(
    *, num_rows: int, scenario: str, seed: int
) -> Iterator[dict[str, Any]]:
    """Yield ``num_rows`` deterministic records lazily."""
    rng = random.Random(seed)
    for index in range(num_rows):
        yield generate_record(index, rng, scenario)


# --------------------------------- metrics ----------------------------------


@dataclasses.dataclass
class Metrics:
    """Captured wall-clock and resource metrics for a single run."""

    scenario: str
    rows: int
    batch_size: int
    dictionary_encode: bool
    dictionary_cardinality_threshold: float
    compact_on_materialize: bool
    eager_clear_accumulator: bool
    incremental_threshold: int | None

    ingest_seconds: float = 0.0
    materialize_seconds: float = 0.0
    total_seconds: float = 0.0
    rows_per_second: float = 0.0

    table_rows: int = 0
    table_num_bytes: int = 0
    max_chunks: int = 0
    dictionary_columns: tuple[str, ...] = ()

    peak_rss_mib: float = 0.0
    python_version: str = ""
    pyarrow_version: str = ""
    package_version: str = ""
    platform: str = ""
    git_commit: str | None = None
    captured_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["dictionary_columns"] = list(self.dictionary_columns)
        return data


def _peak_rss_mib() -> float:
    """Peak resident set size in MiB.

    ``ru_maxrss`` is reported in KiB on Linux and in bytes on macOS. The
    profiling harness targets Linux containers, so divide accordingly with a
    macOS fallback.
    """
    usage = resource.getrusage(resource.RUSAGE_SELF)
    raw = float(usage.ru_maxrss)
    if sys.platform == "darwin":
        return raw / (1024 * 1024)
    return raw / 1024


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "--short", "HEAD"),
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except FileNotFoundError, subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def _package_version() -> str:
    try:
        return version("http-to-arrow")
    except ImportError, Exception:  # noqa: BLE001 - best-effort metadata
        try:
            return version("http_to_arrow")  # type: ignore[name-defined]
        except PackageNotFoundError, Exception:  # noqa: BLE001
            return ""


# ----------------------------- ingestion driver ------------------------------


def _ingest(
    container: ArrowRecordContainer,
    records: Iterable[dict[str, Any]],
    *,
    incremental_threshold: int | None,
) -> None:
    if incremental_threshold is None:
        container.extend(records)
        return

    for record in records:
        container.append(record)
        if container.batch_total_rows >= incremental_threshold:
            container.incremental_flush(threshold=incremental_threshold)


def _summarize_table(table: pa.Table) -> tuple[int, tuple[str, ...]]:
    max_chunks = 0
    dictionary_columns: list[str] = []
    for name in table.schema.names:
        column = table.column(name)
        max_chunks = max(max_chunks, column.num_chunks)
        if pa.types.is_dictionary(column.type):
            dictionary_columns.append(name)
    return max_chunks, tuple(dictionary_columns)


def run_benchmark(args: argparse.Namespace) -> Metrics:
    """Execute one benchmark run and return the captured metrics."""
    schema = build_http_event_schema()
    container = ArrowRecordContainer(
        schema=schema,
        batch_size=args.batch_size,
        dictionary_encode=args.dictionary_encode,
        dictionary_cardinality_threshold=args.dictionary_cardinality_threshold,
        compact_on_materialize=args.compact_on_materialize,
        eager_clear_accumulator=args.eager_clear_accumulator,
    )

    records = iter_records(num_rows=args.rows, scenario=args.scenario, seed=args.seed)

    ingest_start = time.perf_counter()
    _ingest(container, records, incremental_threshold=args.incremental_threshold)
    ingest_seconds = time.perf_counter() - ingest_start

    materialize_start = time.perf_counter()
    table = container.to_table()
    materialize_seconds = time.perf_counter() - materialize_start

    total_seconds = ingest_seconds + materialize_seconds
    max_chunks, dictionary_columns = _summarize_table(table)

    return Metrics(
        scenario=args.scenario,
        rows=args.rows,
        batch_size=args.batch_size,
        dictionary_encode=args.dictionary_encode,
        dictionary_cardinality_threshold=args.dictionary_cardinality_threshold,
        compact_on_materialize=args.compact_on_materialize,
        eager_clear_accumulator=args.eager_clear_accumulator,
        incremental_threshold=args.incremental_threshold,
        ingest_seconds=ingest_seconds,
        materialize_seconds=materialize_seconds,
        total_seconds=total_seconds,
        rows_per_second=(args.rows / total_seconds) if total_seconds else 0.0,
        table_rows=table.num_rows,
        table_num_bytes=table.nbytes,
        max_chunks=max_chunks,
        dictionary_columns=dictionary_columns,
        peak_rss_mib=_peak_rss_mib(),
        python_version=platform.python_version(),
        pyarrow_version=pa.__version__,
        package_version=_package_version(),
        platform=platform.platform(),
        git_commit=_git_commit(),
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ------------------------------ reporting I/O --------------------------------


def _format_bytes(num_bytes: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:,.2f} {unit}"
        size /= 1024.0
    return f"{size:,.2f} {units[-1]}"


def print_summary(metrics: Metrics) -> None:
    print("=" * 72)
    print(f"http_to_arrow profile :: scenario={metrics.scenario}")
    print("=" * 72)
    print(f"  rows                          {metrics.rows:,}")
    print(f"  batch_size                    {metrics.batch_size:,}")
    print(f"  dictionary_encode             {metrics.dictionary_encode}")
    print(f"  dictionary_cardinality_thresh {metrics.dictionary_cardinality_threshold}")
    print(f"  compact_on_materialize        {metrics.compact_on_materialize}")
    print(f"  eager_clear_accumulator       {metrics.eager_clear_accumulator}")
    print(f"  incremental_threshold         {metrics.incremental_threshold}")
    print("-" * 72)
    print(f"  ingest seconds                {metrics.ingest_seconds:,.3f}")
    print(f"  materialize seconds           {metrics.materialize_seconds:,.3f}")
    print(f"  total seconds                 {metrics.total_seconds:,.3f}")
    print(f"  rows / second                 {metrics.rows_per_second:,.0f}")
    print("-" * 72)
    print(f"  table.num_rows                {metrics.table_rows:,}")
    print(
        f"  table.nbytes                  "
        f"{metrics.table_num_bytes:,} ({_format_bytes(metrics.table_num_bytes)})"
    )
    print(f"  max chunks per column         {metrics.max_chunks}")
    print(
        f"  dictionary-typed columns      "
        f"{', '.join(metrics.dictionary_columns) or '(none)'}"
    )
    print(f"  peak rss                      {metrics.peak_rss_mib:,.2f} MiB")
    print("-" * 72)
    print(f"  python {metrics.python_version}  pyarrow {metrics.pyarrow_version}")
    if metrics.package_version:
        print(f"  http_to_arrow {metrics.package_version}")
    if metrics.git_commit:
        print(f"  git commit {metrics.git_commit}")
    print(f"  captured_at {metrics.captured_at}")
    print("=" * 72)


def _delta(current: float, previous: float) -> str:
    if previous == 0:
        return f"{current:,.3f} (baseline=0)"
    diff = current - previous
    pct = (diff / previous) * 100.0
    sign = "+" if diff >= 0 else ""
    return f"{current:,.3f}  ({sign}{diff:,.3f}, {sign}{pct:,.2f}%)"


def print_comparison(current: Metrics, previous: dict[str, Any]) -> None:
    print()
    print("=" * 72)
    print(
        f"Comparison against previous summary captured_at={previous.get('captured_at')}"
    )
    print("=" * 72)
    fields = (
        ("total_seconds", float(previous.get("total_seconds", 0.0))),
        ("ingest_seconds", float(previous.get("ingest_seconds", 0.0))),
        ("materialize_seconds", float(previous.get("materialize_seconds", 0.0))),
        ("rows_per_second", float(previous.get("rows_per_second", 0.0))),
        ("table_num_bytes", float(previous.get("table_num_bytes", 0.0))),
        ("peak_rss_mib", float(previous.get("peak_rss_mib", 0.0))),
        ("max_chunks", float(previous.get("max_chunks", 0.0))),
    )
    current_values = current.to_dict()
    for name, prev_value in fields:
        current_value = float(current_values.get(name, 0.0))
        print(f"  {name:<22} {_delta(current_value, prev_value)}")
    print("=" * 72)


def write_summary(metrics: Metrics, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(metrics.to_dict(), fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------- CLI ------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Profile http_to_arrow ingestion of complex JSON-like records "
            "into a materialized PyArrow table."
        ),
    )
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument(
        "--scenario",
        choices=("nested-http", "dictionary-friendly", "high-cardinality"),
        default="nested-http",
    )
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--batch-size", type=int, default=128_000)
    parser.add_argument("--dictionary-encode", action="store_true")
    parser.add_argument("--dictionary-cardinality-threshold", type=float, default=0.5)
    parser.add_argument("--compact-on-materialize", action="store_true")
    parser.add_argument("--eager-clear-accumulator", action="store_true")
    parser.add_argument(
        "--incremental-threshold",
        type=int,
        default=None,
        help=(
            "When set, call container.incremental_flush(threshold=N) once the "
            "pending batch row count crosses N during ingestion."
        ),
    )

    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="Write a JSON summary to this path (parent dir auto-created).",
    )
    parser.add_argument(
        "--compare-to",
        type=Path,
        default=None,
        help="Path to a previous JSON summary to print deltas against.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.rows <= 0:
        parser.error("--rows must be positive")

    metrics = run_benchmark(args)
    print_summary(metrics)

    if args.summary_out is not None:
        write_summary(metrics, args.summary_out)
        print(f"\nWrote summary to {args.summary_out}")

    if args.compare_to is not None:
        if not args.compare_to.exists():
            print(
                f"\nCompare-to file not found: {args.compare_to}",
                file=sys.stderr,
            )
            return 1
        previous = load_summary(args.compare_to)
        print_comparison(metrics, previous)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
