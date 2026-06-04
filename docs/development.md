# Development

This repository is a `uv` workspace. The root `pyproject.toml` owns shared
tooling, while `http-to-arrow` lives under `src/http_to_arrow`.

## Setup

```bash
git clone https://github.com/ProxayFox/proxay-pylibs.git
cd proxay-pylibs
uv sync --all-packages --group dev --group docs
```

The devcontainer also provides `uv-sync-dev` and `uv-sync-all` helper commands.

## Tests

Run the focused `http-to-arrow` tests:

```bash
uv run pytest -q tests/http_to_arrow/test_arrow_record_container.py
```

Run the shared test suite:

```bash
uv run pytest
```

## Linting, formatting, and type checking

Use the repository shortcuts when possible:

```bash
just lint
just format
just typecheck
```

The full quality target runs sync, lint, format checks, type checks, and tests:

```bash
just quality
```

Do not use `just quality-schema` for this package. That target is a stale
schema-specific helper for paths that are not part of the current package.

## Documentation

Install docs dependencies:

```bash
uv sync --all-packages --group docs
```

Serve the docs locally:

```bash
just docs-serve
```

Build docs in strict mode:

```bash
just docs-build
```

Equivalent direct command:

```bash
uv run --group docs mkdocs build --strict
```

## Markdown linting

```bash
uvx --from markdownlint-rs mdlint check --respect-ignore --exclude '.github/prompts/**'
```

## Contribution workflow

1. Keep behavior changes close to `src/http_to_arrow/src/http_to_arrow/main.py`
   unless the public re-export surface must change.
2. Add or update focused tests in `tests/http_to_arrow/` for behavior changes.
3. Update docs when user-visible behavior, configuration, or examples change.
4. Run the focused tests and docs build before opening a pull request.

Package releases are independent and use tags like `http-to-arrow-vX.Y.Z`.
