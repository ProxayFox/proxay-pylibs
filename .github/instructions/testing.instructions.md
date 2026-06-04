---
description: "Use when editing tests, pytest config, or package coverage in this uv workspace."
applyTo:
  - "tests/**"
  - "src/*/tests/**"
  - "src/*/pyproject.toml"
  - "pyproject.toml"
---

# Testing And Coverage Guidance

- Use the root [pyproject.toml](../../pyproject.toml) for shared pytest
  discovery, markers, and the current default coverage behavior.
- Pytest discovers both root `tests/` slices and package-local
  `src/<member>/tests/` slices. Prefer the nearest behavioral tests for the
  package or feature being changed.
- Root `uv run pytest` currently reports coverage for `http_to_arrow`. For
  other members, check the member `pyproject.toml` before assuming the active
  coverage source, branch setting, or `fail_under` value.
- Use package-scoped commands for focused validation, such as
  `uv run pytest tests/log_generator/ -q` or
  `uv run pytest tests/http_to_arrow/test_arrow_record_container.py -q`.
- Use existing markers from the root config: `unit`, `integration`,
  `performance`, and `slow`. Include slow tests only when the change requires
  it, using `--runslow`.
- Prefer [justfile](../../justfile) shortcuts when they fit the scope:
  `just test`, `just lint`, `just format`, and `just typecheck`.
- Do not use `just quality-schema` in this repository state; it references
  missing `mde_client` paths.
- If package docs disagree with the current tree or tests, trust source and
  tests first, then update docs or instructions after verifying behavior.
