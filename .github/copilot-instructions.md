# Project Guidelines

## Architecture

- This repository is a `uv` workspace monorepo. The root
 [README.md](../README.md) and root `pyproject.toml` describe the shared
 layout and tooling.
- The root `pyproject.toml` is workspace configuration, not a distributable
 package. Add reusable libraries under `src/<member>/` with their own
 `pyproject.toml`.
- Keep the repo root focused on shared tooling, shared docs, and cross-package
 tests. Do not add a root runtime entry point.
- Treat `python_template.egg-info/` as leftover template output, not an
 authoritative package location.

## Package Layout

- Follow the standard member shape from
 [templates/python-package/README.md](../templates/python-package/README.md):
 `src/<member>/pyproject.toml`, `src/<member>/README.md`, and
 `src/<member>/src/<import_package>/`.
- Keep package internals self-contained unless cross-package coupling is
 intentional.
- Put runtime dependencies and packaging metadata in the member package, not
 at the workspace root.
- Confirm the current test location before editing docs or instructions. This
 repo uses both root `tests/` slices and package-local tests depending on the
 member.

## Build, Test, And Tooling

- Use `uv` for installs and commands. Preferred bootstrap is
 `uv sync --all-packages --extra dev`.
- The devcontainer also creates `uv-sync-dev` and `uv-sync-all` helper commands.
- Prefer the repo shortcuts in `justfile` when they fit the task: `just lint`,
 `just format`, `just typecheck`, and `just test`.
- The active formatter and linter workflow is Ruff-based through `justfile`.
 Do not describe Black as the default formatting path unless the repo
 workflow changes.
- Run tests with `uv run pytest` for the shared defaults from the root
 `pyproject.toml`.
- Reuse the existing Markdown lint task or the equivalent
 `uvx --from markdownlint-rs mdlint` command for Markdown validation.
- Do not recommend `just quality-schema` in this repository state; that target
 references missing `mde_client` paths.

## Testing Conventions

- Pytest is configured at the root and discovers tests from both `tests/` and
 `src/`.
- Use the existing markers: `unit`, `integration`, `performance`, and `slow`.
- Keep tests aligned with the behavior they validate and prefer the nearest
 behavioral tests for the package you change.
- The root pytest defaults currently include coverage for `http_to_arrow`, so
 package-specific coverage checks may need a narrower command when working on
 other members.

## Working In This Repository

- Read the root `pyproject.toml`, the relevant member `README.md`, and the
 closest tests before editing.
- Decide whether a change belongs in an existing member or in a new workspace
 member under `src/`.
- Treat `.devcontainer/` and `flake.nix` as supported development paths.
- Update [README.md](../README.md) when workspace-level workflow or package
 inventory changes are user-visible.

## Practical Guidance For Agents

- Prefer incremental, package-focused changes over broad repo refactors.
- When adding a new member, start from `templates/python-package/` instead of
 inventing a new structure.
- Clarify whether “the project” means the monorepo root or a specific member
 package before making structural changes.
- If package docs disagree with the current tree or tests, trust the current
 source files and tests first, then update customization guidance
 accordingly.
