# Optional local shortcuts layered over the existing uv workflows.

set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

help:
    @just --list

# --- Package Management ---
sync +args="":
    uv sync --all-groups --all-packages {{args}}

check-vulns:
    uv export --frozen --no-hashes --no-editable --no-emit-project | uvx pip-audit -r /dev/stdin

upgrade-deps:
    uvx uv-upgrade

# --- Development ---
lint path="." +args="":
    uv run ruff check {{path}} {{args}}

lint-fix path="." +args="":
    uv run ruff check --fix {{path}} {{args}}

format path="." +args="":
    uv run ruff format {{path}} {{args}}

format-check path="." +args="":
    uv run ruff format --check {{path}} {{args}}

typecheck path="." +args="":
    uv run ty check --project {{path}} {{args}}
    uvx pyright --pythonpath "$(uv run python -c 'import sys; print(sys.executable)')" --threads {{path}}

#  --- Testing ---
test path="tests/" +args="":
    uv run pytest -q {{path}} {{args}}

test-all path="tests/" +args="":
    uv run pytest --runslow -q {{path}} {{args}}

coverage path="tests/" +args="":
    uv run pytest -q {{path}} --skip-integration --cov=mde_client --cov-branch --cov-report=term-missing --cov-report=html:build/htmlcov {{args}}

# --- Quality CI/CD Gate ---
quality: sync
    if ! just lint; then just lint-fix; fi
    if ! just format-check; then just format; fi
    just typecheck
    just test --skip-integration

# --- Git Hooks ---
hooks-install:
    uv run pre-commit install

hooks-run +args="":
    uv run pre-commit run --all-files {{args}}

# Similar to Quality, but only targets schema validation
quality-schema schemas="src/mde_client/schemas" models="src/mde_client/models" schemas_tests="tests/mde_client/test_schema_validator.py" models_tests="tests/mde_client/test_investigation_models.py":
    if ! just lint {{schemas}} {{models}}; then just lint-fix {{schemas}} {{models}}; fi
    if ! just format-check {{schemas}} {{models}}; then just format {{schemas}} {{models}}; fi
    just typecheck {{schemas}} {{models}}
    just test {{schemas_tests}} {{models_tests}} --skip-integration

# Like Quality, but also includes integration tests that require Azure credentials. Use with caution in CI/CD pipelines.
quality-full:
    if ! just lint; then just lint-fix; fi
    if ! just format-check; then just format; fi
    just typecheck
    just test

# --- Documentation ---
docs-build:
    uv run --group docs mkdocs build --strict

docs-serve:
    uv run --group docs mkdocs serve

docs-validate:
    uv run --group docs mkdocs build --strict

# --- Profiling (manual; not part of `quality`) ---
profile-http-to-arrow rows="1000000" +args="":
    uv run --group profiling python scripts/profile_http_to_arrow.py --rows {{rows}} {{args}}

profile-http-to-arrow-scalene rows="1000000" out="profiles/http_to_arrow/scalene_nested.html" +args="":
    mkdir -p "$(dirname {{out}})"
    uv run --group profiling scalene --html --outfile {{out}} scripts/profile_http_to_arrow.py --rows {{rows}} {{args}}

profile-http-to-arrow-pyinstrument rows="1000000" out="profiles/http_to_arrow/pyinstrument_nested.html" +args="":
    mkdir -p "$(dirname {{out}})"
    uv run --group profiling python -m pyinstrument --html -o {{out}} scripts/profile_http_to_arrow.py --rows {{rows}} {{args}}

# Compare current branch against another git ref (default origin/main) using a temporary worktree.
profile-http-to-arrow-vs ref="origin/main" rows="1000000" +args="":
    uv run --group profiling python scripts/compare_http_to_arrow.py --ref {{ref}} --rows {{rows}} {{args}}

# Run the http_to_arrow profiler across the full configuration matrix (5 configs x 3 scenarios)
# against another git ref and emit benchmarks/http_to_arrow/COMPARISON_MATRIX.md (+ .csv).
profile-http-to-arrow-matrix ref="origin/main" rows="1000000" +args="":
    uv run --group profiling python scripts/benchmark_http_to_arrow_matrix.py --ref {{ref}} --rows {{rows}} {{args}}
