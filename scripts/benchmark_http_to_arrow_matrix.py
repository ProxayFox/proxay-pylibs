"""Run the ``http_to_arrow`` profiler across a configuration matrix.

This driver orchestrates :mod:`profile_http_to_arrow` across multiple
scenarios and feature-flag combinations and compares the results against a
single baseline commit (default ``origin/main``). The output is a
checked-in markdown matrix plus a sibling CSV that future PRs can diff
against to spot regressions.

The matrix dimensions are fixed and explicit by design (5 configs that
isolate each opt-in memory knob plus an ``all-on`` preset), not a 2^N
truth table -- this gives us per-knob attribution without combinatorial
noise. See ``scripts/README.md`` for the rationale.

Example::

    uv run --group profiling python scripts/benchmark_http_to_arrow_matrix.py \
        --ref origin/main --merge-base --rows 1000000

The driver re-uses worktree + fixture infrastructure from
:mod:`compare_http_to_arrow` so behavior stays consistent with the
single-config ``profile-http-to-arrow-vs`` recipe.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import platform
import shutil
import sys
import tempfile
import importlib.util as _importlib_util
import types as _types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# `scripts/` is added to sys.path[0] when running this module as a script,
# so a sibling import of compare_http_to_arrow is sufficient. The helpers
# we re-use are private by convention but stable in practice; see plan.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_cmp_path = _SCRIPTS_DIR / "compare_http_to_arrow.py"
_cmp_spec = _importlib_util.spec_from_file_location("compare_http_to_arrow", _cmp_path)
assert _cmp_spec is not None and _cmp_spec.loader is not None
cmp: _types.ModuleType = _importlib_util.module_from_spec(_cmp_spec)
_cmp_spec.loader.exec_module(cmp)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE_CACHE_DIR = REPO_ROOT / "profiles" / "http_to_arrow" / "fixtures"
DEFAULT_RUN_DIR = REPO_ROOT / "profiles" / "http_to_arrow" / "matrix"
DEFAULT_OUT_DIR = REPO_ROOT / "benchmarks" / "http_to_arrow"

ALL_SCENARIOS: tuple[str, ...] = (
    "nested-http",
    "dictionary-friendly",
    "high-cardinality",
)


@dataclasses.dataclass(frozen=True)
class Config:
    """A single column in the comparison matrix."""

    label: str
    dictionary_encode: bool = False
    compact_on_materialize: bool = False
    eager_clear_accumulator: bool = False

    def to_extra_args(self) -> str:
        flags: list[str] = []
        if self.dictionary_encode:
            flags.append("--dictionary-encode")
        if self.compact_on_materialize:
            flags.append("--compact-on-materialize")
        if self.eager_clear_accumulator:
            flags.append("--eager-clear-accumulator")
        return " ".join(flags)


# Five explicit configs: off, three single-knob isolations, and the
# "recommended" combined preset. Order is preserved in the rendered tables.
DEFAULT_CONFIGS: tuple[Config, ...] = (
    Config("off"),
    Config("+dict", dictionary_encode=True),
    Config("+compact", compact_on_materialize=True),
    Config("+eager", eager_clear_accumulator=True),
    Config("all-on", True, True, True),
)


# --------------------------------- helpers ---------------------------------


def _safe_filename(value: str) -> str:
    """Make a label safe for use inside a filename."""
    return value.replace("+", "plus").replace(" ", "_").replace("/", "_")


def _scenario_summary_path(run_dir: Path, scenario: str, config_label: str) -> Path:
    return run_dir / f"{scenario}__{_safe_filename(config_label)}.json"


def _scenario_baseline_path(run_dir: Path, scenario: str) -> Path:
    return run_dir / f"{scenario}__baseline.json"


def _format_seconds(value: float) -> str:
    return f"{value:,.3f}"


def _format_int(value: int | float) -> str:
    return f"{int(value):,}"


def _format_mib(num_bytes: int | float) -> str:
    return f"{float(num_bytes) / (1024 * 1024):,.2f}"


def _format_pct(current: float, baseline: float) -> str:
    """Return a signed percentage delta string, or ``n/a`` if undefined."""
    if baseline == 0:
        return "n/a" if current == 0 else "+inf%"
    pct = (current - baseline) / baseline * 100.0
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:,.2f}%"


def _short_commit(value: str | None) -> str:
    if not value:
        return "unknown"
    return value[:8]


# ------------------------------ orchestration ------------------------------


def _build_common_args(
    *,
    rows: int,
    scenario: str,
    seed: int,
    batch_size: int,
    fixture_cache_dir: Path,
) -> list[str]:
    return [
        "--rows",
        str(rows),
        "--scenario",
        scenario,
        "--seed",
        str(seed),
        "--batch-size",
        str(batch_size),
        "--fixture-cache-dir",
        str(fixture_cache_dir.resolve()),
    ]


def _pregenerate_fixture(
    *,
    rows: int,
    scenario: str,
    seed: int,
    fixture_cache_dir: Path,
    regenerate: bool,
) -> None:
    cmd = [
        "uv",
        "run",
        "--group",
        "profiling",
        "python",
        "scripts/profile_http_to_arrow.py",
        "--rows",
        str(rows),
        "--scenario",
        scenario,
        "--seed",
        str(seed),
        "--fixture-cache-dir",
        str(fixture_cache_dir.resolve()),
        "--generate-fixture-only",
    ]
    if regenerate:
        cmd.append("--regenerate-fixture")
    cmp._run(cmd, cwd=REPO_ROOT)


def _run_baseline(
    *,
    worktree_dir: Path,
    scenario: str,
    common: list[str],
    summary_out: Path,
) -> None:
    cmp.run_profiler(
        cwd=worktree_dir,
        common=common,
        extra="",  # baseline ref does not understand the new flags
        summary_out=summary_out,
    )


def _run_branch_config(
    *,
    config: Config,
    scenario: str,
    common: list[str],
    summary_out: Path,
) -> None:
    cmp.run_profiler(
        cwd=REPO_ROOT,
        common=common,
        extra=config.to_extra_args(),
        summary_out=summary_out,
    )


def _load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------- matrix data structure --------------------------


@dataclasses.dataclass
class ScenarioResult:
    """Loaded summaries for one scenario across baseline + all configs."""

    scenario: str
    baseline: dict[str, Any]
    configs: list[tuple[Config, dict[str, Any]]]

    def baseline_off_summary(self) -> dict[str, Any]:
        """Return the ``off`` config summary, used as the deltas anchor.

        ``off`` is what we expect to be a parity reproduction of the
        baseline ref using the *current* profiler script. Deltas are
        anchored to ``off`` (not the baseline run) so per-knob columns
        show the cost of *enabling* a knob on the same code path.
        """
        for config, summary in self.configs:
            if config.label == "off":
                return summary
        msg = "Matrix is missing the required 'off' config."
        raise RuntimeError(msg)


# ------------------------------ markdown render ----------------------------


_ABS_HEADERS: tuple[str, ...] = (
    "config",
    "ingest s",
    "materialize s",
    "total s",
    "rows / s",
    "table MiB",
    "chunks",
    "dict cols",
    "peak RSS MiB",
)

_DELTA_HEADERS: tuple[str, ...] = (
    "config",
    "total s",
    "materialize s",
    "rows / s",
    "table bytes",
    "peak RSS",
    "chunks",
)


def _abs_row(label: str, summary: dict[str, Any]) -> tuple[str, ...]:
    dict_cols = summary.get("dictionary_columns") or []
    dict_cols_text = ", ".join(dict_cols) if dict_cols else "(none)"
    return (
        label,
        _format_seconds(float(summary.get("ingest_seconds", 0.0))),
        _format_seconds(float(summary.get("materialize_seconds", 0.0))),
        _format_seconds(float(summary.get("total_seconds", 0.0))),
        _format_int(float(summary.get("rows_per_second", 0.0))),
        _format_mib(summary.get("table_num_bytes", 0)),
        _format_int(summary.get("max_chunks", 0)),
        dict_cols_text,
        f"{float(summary.get('peak_rss_mib', 0.0)):,.2f}",
    )


def _delta_row(
    label: str,
    summary: dict[str, Any],
    anchor: dict[str, Any],
) -> tuple[str, ...]:
    return (
        label,
        _format_pct(
            float(summary.get("total_seconds", 0.0)),
            float(anchor.get("total_seconds", 0.0)),
        ),
        _format_pct(
            float(summary.get("materialize_seconds", 0.0)),
            float(anchor.get("materialize_seconds", 0.0)),
        ),
        _format_pct(
            float(summary.get("rows_per_second", 0.0)),
            float(anchor.get("rows_per_second", 0.0)),
        ),
        _format_pct(
            float(summary.get("table_num_bytes", 0.0)),
            float(anchor.get("table_num_bytes", 0.0)),
        ),
        _format_pct(
            float(summary.get("peak_rss_mib", 0.0)),
            float(anchor.get("peak_rss_mib", 0.0)),
        ),
        _format_pct(
            float(summary.get("max_chunks", 0.0)),
            float(anchor.get("max_chunks", 0.0)),
        ),
    )


def _render_markdown_table(
    headers: tuple[str, ...], rows: list[tuple[str, ...]]
) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _recommended_preset(result: ScenarioResult) -> tuple[str, str]:
    """Pick a recommended config for a scenario.

    Strategy: prefer the config with the largest ``table_num_bytes``
    reduction whose ``peak_rss_mib`` cost stays within +5% of the
    ``off`` baseline. If no enabled config qualifies, recommend
    ``off``.

    Returns ``(label, rationale)`` for the markdown callout.
    """
    anchor = result.baseline_off_summary()
    base_bytes = float(anchor.get("table_num_bytes", 0.0))
    base_rss = float(anchor.get("peak_rss_mib", 0.0))
    rss_budget = base_rss * 1.05 if base_rss else float("inf")

    best_label = "off"
    best_savings_mib = 0.0
    best_rss_cost_mib = 0.0
    for config, summary in result.configs:
        if config.label == "off":
            continue
        bytes_saved = base_bytes - float(summary.get("table_num_bytes", 0.0))
        if bytes_saved <= 0:
            continue
        config_rss = float(summary.get("peak_rss_mib", 0.0))
        if config_rss > rss_budget:
            continue
        savings_mib = bytes_saved / (1024 * 1024)
        if savings_mib > best_savings_mib:
            best_label = config.label
            best_savings_mib = savings_mib
            best_rss_cost_mib = config_rss - base_rss

    if best_label == "off":
        rationale = "no enabled config saved table bytes within a +5% peak-RSS budget."
    else:
        rationale = (
            f"saves {best_savings_mib:,.2f} MiB on the materialized table at "
            f"{best_rss_cost_mib:+,.2f} MiB peak-RSS cost."
        )
    return best_label, rationale


def render_markdown(
    *,
    results: list[ScenarioResult],
    branch_commit: str | None,
    baseline_ref: str,
    baseline_commit: str,
    rows: int,
    seed: int,
    batch_size: int,
    captured_at: str,
    just_command: str,
) -> str:
    """Render the full ``COMPARISON_MATRIX.md`` body."""
    # Pull versions from any summary; they're identical across runs.
    sample = results[0].baseline if results else {}
    python_version = sample.get("python_version", "")
    pyarrow_version = sample.get("pyarrow_version", "")
    package_version = sample.get("package_version", "")
    platform_str = sample.get("platform", "")

    parts: list[str] = []
    parts.append("# `http_to_arrow` Performance Comparison Matrix")
    parts.append("")
    parts.append(
        "Generated by `scripts/benchmark_http_to_arrow_matrix.py`. Each "
        "scenario row exercises the same fixture bytes through different "
        "feature-flag combinations so we can attribute cost to individual "
        "knobs (`dictionary_encode`, `compact_on_materialize`, "
        "`eager_clear_accumulator`)."
    )
    parts.append("")
    parts.append("## Run metadata")
    parts.append("")
    parts.append(f"- Captured at: `{captured_at}`")
    parts.append(f"- Branch commit: `{_short_commit(branch_commit)}`")
    parts.append(
        f"- Baseline ref: `{baseline_ref}` -> `{_short_commit(baseline_commit)}`"
    )
    parts.append(f"- Rows: `{rows:,}` Seed: `{seed}` Batch size: `{batch_size:,}`")
    parts.append(
        f"- Python: `{python_version}` PyArrow: `{pyarrow_version}` "
        f"http_to_arrow: `{package_version}`"
    )
    parts.append(f"- Platform: `{platform_str}`")
    parts.append("")
    parts.append("Configs:")
    parts.append("")
    parts.append(
        "| label | dictionary_encode | compact_on_materialize | eager_clear_accumulator |"
    )
    parts.append("| --- | --- | --- | --- |")
    for config in DEFAULT_CONFIGS:
        parts.append(
            f"| `{config.label}` | "
            f"{'T' if config.dictionary_encode else 'F'} | "
            f"{'T' if config.compact_on_materialize else 'F'} | "
            f"{'T' if config.eager_clear_accumulator else 'F'} |"
        )
    parts.append("")

    for result in results:
        anchor = result.baseline_off_summary()

        parts.append(f"## Scenario: `{result.scenario}`")
        parts.append("")
        parts.append("### Absolute metrics")
        parts.append("")
        abs_rows: list[tuple[str, ...]] = [
            _abs_row(f"baseline ({baseline_ref})", result.baseline),
        ]
        for config, summary in result.configs:
            abs_rows.append(_abs_row(f"`{config.label}`", summary))
        parts.append(_render_markdown_table(_ABS_HEADERS, abs_rows))
        parts.append("")

        parts.append("### Deltas vs `off`")
        parts.append("")
        delta_rows: list[tuple[str, ...]] = []
        for config, summary in result.configs:
            if config.label == "off":
                continue
            delta_rows.append(_delta_row(f"`{config.label}`", summary, anchor))
        parts.append(_render_markdown_table(_DELTA_HEADERS, delta_rows))
        parts.append("")

        label, rationale = _recommended_preset(result)
        parts.append(f"**Recommended preset:** `{label}` -- {rationale}")
        parts.append("")

    parts.append("## Reproducing")
    parts.append("")
    parts.append("```bash")
    parts.append(just_command)
    parts.append("```")
    parts.append("")
    parts.append(
        "Per-config JSON summaries are written under "
        "`profiles/http_to_arrow/matrix/<branch_commit>/` (gitignored). "
        "The committed artifact is this markdown file plus the sibling "
        "`comparison_matrix.csv`."
    )
    parts.append("")
    return "\n".join(parts)


# --------------------------------- CSV write -------------------------------


def write_csv(out_path: Path, results: list[ScenarioResult]) -> None:
    """Write a flat CSV of every (scenario, source) row for tooling.

    Columns are intentionally kept stable so future automation can
    `pandas.read_csv` it without parsing markdown.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "scenario",
        "source",  # "baseline" or config label
        "rows",
        "ingest_seconds",
        "materialize_seconds",
        "total_seconds",
        "rows_per_second",
        "table_num_bytes",
        "max_chunks",
        "dictionary_columns",
        "peak_rss_mib",
        "git_commit",
        "captured_at",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(_csv_row(result.scenario, "baseline", result.baseline))
            for config, summary in result.configs:
                writer.writerow(_csv_row(result.scenario, config.label, summary))


def _csv_row(scenario: str, source: str, summary: dict[str, Any]) -> dict[str, Any]:
    dict_cols = summary.get("dictionary_columns") or []
    return {
        "scenario": scenario,
        "source": source,
        "rows": summary.get("rows", 0),
        "ingest_seconds": summary.get("ingest_seconds", 0.0),
        "materialize_seconds": summary.get("materialize_seconds", 0.0),
        "total_seconds": summary.get("total_seconds", 0.0),
        "rows_per_second": summary.get("rows_per_second", 0.0),
        "table_num_bytes": summary.get("table_num_bytes", 0),
        "max_chunks": summary.get("max_chunks", 0),
        "dictionary_columns": "|".join(dict_cols),
        "peak_rss_mib": summary.get("peak_rss_mib", 0.0),
        "git_commit": summary.get("git_commit", "") or "",
        "captured_at": summary.get("captured_at", "") or "",
    }


# ----------------------------------- CLI -----------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the http_to_arrow profiler across a configuration matrix "
            "and emit a markdown + CSV comparison artifact."
        ),
    )
    parser.add_argument(
        "--ref",
        default="origin/main",
        help="Git ref to use for the baseline run (default: origin/main).",
    )
    parser.add_argument(
        "--merge-base",
        action="store_true",
        help="Use the merge-base of HEAD and --ref instead of the ref tip.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip `git fetch` before resolving --ref.",
    )

    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=128_000)
    parser.add_argument(
        "--scenarios",
        type=lambda s: tuple(item.strip() for item in s.split(",") if item.strip()),
        default=ALL_SCENARIOS,
        help=(f"Comma-separated scenarios to run. Default: {','.join(ALL_SCENARIOS)}"),
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=(
            "Directory for the committed markdown + CSV. Default: "
            f"{DEFAULT_OUT_DIR.relative_to(REPO_ROOT)}/"
        ),
    )
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
        help=(
            "Directory for per-config JSON summaries (gitignored). "
            f"Default: {DEFAULT_RUN_DIR.relative_to(REPO_ROOT)}/"
        ),
    )

    parser.add_argument(
        "--worktree-dir",
        type=Path,
        default=None,
        help=(
            "Path for the temporary worktree. Default: a sibling of the repo "
            "in $TMPDIR. Must not already exist."
        ),
    )
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="Skip cleanup of the temporary worktree on exit.",
    )
    parser.add_argument(
        "--skip-uv-sync",
        action="store_true",
        help="Skip `uv sync` inside the worktree (advanced).",
    )

    parser.add_argument(
        "--fixture-cache-dir",
        type=Path,
        default=DEFAULT_FIXTURE_CACHE_DIR,
        help=(
            "Shared fixture cache directory used by every run. Default: "
            f"{DEFAULT_FIXTURE_CACHE_DIR.relative_to(REPO_ROOT)}"
        ),
    )
    parser.add_argument(
        "--regenerate-fixture",
        action="store_true",
        help="Force fixture regeneration even on a cache hit.",
    )

    return parser


def _validate_scenarios(
    parser: argparse.ArgumentParser, scenarios: tuple[str, ...]
) -> None:
    unknown = [s for s in scenarios if s not in ALL_SCENARIOS]
    if unknown:
        parser.error(
            f"Unknown scenario(s): {', '.join(unknown)}. "
            f"Valid: {', '.join(ALL_SCENARIOS)}."
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.rows <= 0:
        parser.error("--rows must be positive")
    _validate_scenarios(parser, args.scenarios)

    if not args.no_fetch:
        cmp._run(["git", "fetch", "--quiet", "origin"], cwd=REPO_ROOT, check=False)

    baseline_commit = cmp.resolve_commit(args.ref, use_merge_base=args.merge_base)
    print(f"Baseline commit resolved: {baseline_commit}")

    branch_commit_proc = cmp._run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture=True, check=False
    )
    branch_commit = (branch_commit_proc.stdout or "").strip() or None

    # Worktree setup mirrors compare_http_to_arrow.main.
    if args.worktree_dir is not None:
        worktree_dir = args.worktree_dir.resolve()
        if worktree_dir.exists():
            parser.error(f"--worktree-dir already exists: {worktree_dir}")
        created_tempdir: Path | None = None
    else:
        created_tempdir = Path(tempfile.mkdtemp(prefix="proxay-pylibs-matrix-"))
        worktree_dir = created_tempdir / "repo"

    run_dir = (args.summary_dir / _short_commit(branch_commit)).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    just_command = f"just profile-http-to-arrow-matrix {args.ref} {args.rows}" + (
        " --merge-base" if args.merge_base else ""
    )

    results: list[ScenarioResult] = []
    try:
        cmp.add_worktree(worktree_dir, baseline_commit)
        cmp.install_profiler_into_worktree(worktree_dir)
        if not args.skip_uv_sync:
            cmp.sync_worktree_env(worktree_dir)

        for scenario in args.scenarios:
            print()
            print("#" * 72)
            print(f"# Scenario: {scenario}")
            print("#" * 72)

            _pregenerate_fixture(
                rows=args.rows,
                scenario=scenario,
                seed=args.seed,
                fixture_cache_dir=args.fixture_cache_dir,
                regenerate=args.regenerate_fixture,
            )
            common = _build_common_args(
                rows=args.rows,
                scenario=scenario,
                seed=args.seed,
                batch_size=args.batch_size,
                fixture_cache_dir=args.fixture_cache_dir,
            )

            baseline_path = _scenario_baseline_path(run_dir, scenario)
            print()
            print("-" * 72)
            print(f"-- Baseline ({args.ref}) :: scenario={scenario}")
            print("-" * 72)
            _run_baseline(
                worktree_dir=worktree_dir,
                scenario=scenario,
                common=common,
                summary_out=baseline_path,
            )

            config_summaries: list[tuple[Config, dict[str, Any]]] = []
            for config in DEFAULT_CONFIGS:
                summary_path = _scenario_summary_path(run_dir, scenario, config.label)
                print()
                print("-" * 72)
                print(f"-- Branch :: scenario={scenario} config={config.label}")
                print("-" * 72)
                _run_branch_config(
                    config=config,
                    scenario=scenario,
                    common=common,
                    summary_out=summary_path,
                )
                config_summaries.append((config, _load_summary(summary_path)))

            results.append(
                ScenarioResult(
                    scenario=scenario,
                    baseline=_load_summary(baseline_path),
                    configs=config_summaries,
                )
            )
    finally:
        if not args.keep_worktree:
            print()
            print(f"Cleaning up worktree at {worktree_dir}")
            cmp.remove_worktree(worktree_dir)
            if created_tempdir is not None and created_tempdir.exists():
                shutil.rmtree(created_tempdir, ignore_errors=True)
        else:
            print()
            print(f"Worktree retained at {worktree_dir} (cleanup skipped)")

    if not results:
        print("No scenarios executed; nothing to render.", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = args.out_dir / "COMPARISON_MATRIX.md"
    csv_path = args.out_dir / "comparison_matrix.csv"

    markdown = render_markdown(
        results=results,
        branch_commit=branch_commit,
        baseline_ref=args.ref,
        baseline_commit=baseline_commit,
        rows=args.rows,
        seed=args.seed,
        batch_size=args.batch_size,
        captured_at=captured_at,
        just_command=just_command,
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    write_csv(csv_path, results)

    print()
    print(f"Wrote markdown matrix: {markdown_path}")
    print(f"Wrote CSV matrix:      {csv_path}")
    print(f"Per-config summaries:  {run_dir}")
    print(f"Branch commit:         {_short_commit(branch_commit)}")
    print(f"Baseline:              {args.ref} -> {_short_commit(baseline_commit)}")
    print(
        "Note: 'platform' field carries host-machine info; matrix numbers "
        "are advisory across machines."
    )
    # Quiet platform import: we read it from summaries above, but keep the
    # import to silence linters that flag unused stdlib imports if removed.
    _ = platform.platform()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
