# Optional local shortcuts layered over the existing uv workflows.

set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

help:
    @just --list

# --- Development ---
lint path="." +args="":
    uv run ruff check {{path}} {{args}}

lint-fix path="." +args="":
    uv run ruff check --fix {{path}} {{args}}

format path="." +args="":
    uv run ruff format {{path}} {{args}}

format-check path="." +args="":
    uv run ruff format --check {{path}} {{args}}

#  --- Testing ---
test path="tests/" +args="":
    uv run pytest -q {{path}} {{args}}

test-all path="tests/" +args="":
    uv run pytest --runslow -q {{path}} {{args}}

typecheck path="." +args="":
    uv run ty check --project {{path}} {{args}}
    uvx pyright --pythonpath "$(uv run python -c 'import sys; print(sys.executable)')" --threads

# --- Git Hooks ---
hooks-install:
    uv run pre-commit install

hooks-run +args="":
    uv run pre-commit run --all-files {{args}}

# --- Quality CI/CD Gate ---
quality:
    if ! just lint; then just lint-fix; fi
    if ! just format-check; then just format; fi
    just typecheck
    uv run pytest -q tests/ -m "not integration"

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
