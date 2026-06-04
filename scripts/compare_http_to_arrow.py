"""Compare ``http_to_arrow`` profile results against another git ref.

This orchestrator creates a temporary git worktree at a target ref
(default ``origin/main``), copies the *current* profiler script into it so
the measurement code is identical on both sides, runs the baseline there,
then runs the current branch with ``--compare-to`` to print deltas.

The worktree is cleaned up automatically unless ``--keep-worktree`` is set.

Example::

    uv run --group profiling python scripts/compare_http_to_arrow.py \
        --rows 1000000 --scenario nested-http \
        --branch-extra "--dictionary-encode --compact-on-materialize --eager-clear-accumulator"

Only the ``http_to_arrow`` package code differs between runs; identical
profiler logic, identical seed, identical scenario, identical row count,
identical batch size.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILER_SCRIPT = REPO_ROOT / "scripts" / "profile_http_to_arrow.py"

DEFAULT_BRANCH_EXTRA = (
    "--dictionary-encode --compact-on-materialize --eager-clear-accumulator"
)


# ----------------------------------- git -----------------------------------


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print(
        f"$ {' '.join(shlex.quote(c) for c in cmd)}"
        + (f"   (cwd={cwd})" if cwd else "")
    )
    # Strip any inherited VIRTUAL_ENV so `uv` in a worktree picks up that
    # worktree's own .venv rather than warning about a parent-shell venv.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=capture,
        env=env,
    )


def resolve_commit(ref: str, *, use_merge_base: bool) -> str:
    """Resolve ``ref`` to a commit SHA, optionally via merge-base with HEAD."""
    if use_merge_base:
        result = _run(["git", "merge-base", "HEAD", ref], cwd=REPO_ROOT, capture=True)
    else:
        result = _run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=REPO_ROOT,
            capture=True,
        )
    sha = result.stdout.strip()
    if not sha:
        raise RuntimeError(f"Could not resolve commit for ref={ref!r}")
    return sha


def add_worktree(worktree_dir: Path, commit: str) -> None:
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)
    _run(
        ["git", "worktree", "add", "--detach", str(worktree_dir), commit],
        cwd=REPO_ROOT,
    )


def remove_worktree(worktree_dir: Path) -> None:
    try:
        _run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=REPO_ROOT,
            check=False,
        )
    finally:
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)


# --------------------------- worktree preparation ---------------------------


def install_profiler_into_worktree(worktree_dir: Path) -> Path:
    """Copy the current profiler script into the worktree.

    The target ref may predate the profiler, or carry an older copy. Using
    the current copy on both sides keeps measurement logic identical so
    differences reflect ``http_to_arrow`` changes only.
    """
    target_dir = worktree_dir / "scripts"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / PROFILER_SCRIPT.name
    shutil.copy2(PROFILER_SCRIPT, target)
    return target


def sync_worktree_env(worktree_dir: Path) -> None:
    # --all-packages is required so the workspace member ``http_to_arrow``
    # is installed into the worktree's .venv (otherwise the profiler will
    # fail with ModuleNotFoundError).
    _run(
        ["uv", "sync", "--all-packages", "--group", "profiling"],
        cwd=worktree_dir,
    )


# ------------------------------ profiler runs ------------------------------


def _common_args(args: argparse.Namespace) -> list[str]:
    return [
        "--rows",
        str(args.rows),
        "--scenario",
        args.scenario,
        "--seed",
        str(args.seed),
        "--batch-size",
        str(args.batch_size),
    ]


def run_profiler(
    cwd: Path,
    *,
    common: list[str],
    extra: str,
    summary_out: Path,
    compare_to: Path | None = None,
) -> None:
    cmd = [
        "uv",
        "run",
        "--group",
        "profiling",
        "python",
        "scripts/profile_http_to_arrow.py",
        *common,
        "--summary-out",
        str(summary_out),
    ]
    if extra.strip():
        cmd.extend(shlex.split(extra))
    if compare_to is not None:
        cmd.extend(["--compare-to", str(compare_to)])
    _run(cmd, cwd=cwd)


# ----------------------------------- CLI -----------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run scripts/profile_http_to_arrow.py against another git ref "
            "and the current working tree, then print deltas."
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
        help=(
            "Use the merge-base of HEAD and --ref instead of the ref tip. "
            "Recommended to isolate this branch's changes from unrelated "
            "main-branch movement."
        ),
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip `git fetch` before resolving --ref.",
    )

    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument(
        "--scenario",
        choices=("nested-http", "dictionary-friendly", "high-cardinality"),
        default="nested-http",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=128_000)

    parser.add_argument(
        "--baseline-extra",
        default="",
        help="Extra args appended to the baseline (ref) profiler invocation.",
    )
    parser.add_argument(
        "--branch-extra",
        default=DEFAULT_BRANCH_EXTRA,
        help=(
            "Extra args appended to the current-branch profiler invocation. "
            f"Default: {DEFAULT_BRANCH_EXTRA!r}"
        ),
    )

    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=REPO_ROOT / "profiles" / "http_to_arrow",
        help="Directory for summary JSON files (default: profiles/http_to_arrow).",
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
        help="Skip `uv sync --group profiling` inside the worktree.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not PROFILER_SCRIPT.exists():
        parser.error(f"Profiler script not found at {PROFILER_SCRIPT}")
    if args.rows <= 0:
        parser.error("--rows must be positive")

    if not args.no_fetch:
        # Best-effort fetch so origin/main is up to date; ignore failure
        # (offline runs should pass --no-fetch).
        _run(["git", "fetch", "--quiet", "origin"], cwd=REPO_ROOT, check=False)

    commit = resolve_commit(args.ref, use_merge_base=args.merge_base)
    print(f"Baseline commit resolved: {commit}")

    if args.worktree_dir is not None:
        worktree_dir = args.worktree_dir.resolve()
        if worktree_dir.exists():
            parser.error(f"--worktree-dir already exists: {worktree_dir}")
        created_tempdir: Path | None = None
    else:
        created_tempdir = Path(tempfile.mkdtemp(prefix="proxay-pylibs-baseline-"))
        worktree_dir = created_tempdir / "repo"

    args.summary_dir.mkdir(parents=True, exist_ok=True)
    short_sha = commit[:8]
    baseline_summary = args.summary_dir / f"baseline_{short_sha}.json"
    branch_summary = args.summary_dir / f"branch_HEAD_{args.scenario}.json"

    try:
        add_worktree(worktree_dir, commit)
        install_profiler_into_worktree(worktree_dir)
        if not args.skip_uv_sync:
            sync_worktree_env(worktree_dir)

        common = _common_args(args)

        print()
        print("#" * 72)
        print(f"# Running BASELINE at {commit} in {worktree_dir}")
        print("#" * 72)
        run_profiler(
            cwd=worktree_dir,
            common=common,
            extra=args.baseline_extra,
            summary_out=baseline_summary,
        )

        print()
        print("#" * 72)
        print("# Running BRANCH (current working tree)")
        print("#" * 72)
        run_profiler(
            cwd=REPO_ROOT,
            common=common,
            extra=args.branch_extra,
            summary_out=branch_summary,
            compare_to=baseline_summary,
        )

        print()
        print(f"Baseline summary: {baseline_summary}")
        print(f"Branch summary:   {branch_summary}")
    finally:
        if not args.keep_worktree:
            print()
            print(f"Cleaning up worktree at {worktree_dir}")
            remove_worktree(worktree_dir)
            if created_tempdir is not None and created_tempdir.exists():
                shutil.rmtree(created_tempdir, ignore_errors=True)
        else:
            print()
            print(f"Worktree retained at {worktree_dir} (cleanup skipped)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
