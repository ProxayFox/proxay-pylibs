# Project Guidelines

## Architecture

- This repository is a Python monorepo managed as a `uv` workspace.
- The root `pyproject.toml` coordinates the workspace and is not a distributable package.
- Workspace members belong under `src/*`.
- Add each new library as its own directory under `src/` with its own `pyproject.toml`.
- Keep the repo root focused on shared tooling, shared dev dependencies, and shared docs.
- Treat the root `pyproject.toml` as the source of truth for shared tooling and pytest config.
- Do not assume there is a root `main.py` or root console entry point.
- Treat `python_template.egg-info/` as leftover template output, not authoritative project structure.

## Package Layout

- Prefer one independent library per workspace member under `src/<package-dir>/`.
- Each package should own its runtime dependencies and packaging metadata locally.
- Keep package internals self-contained unless cross-package coupling is intentional.
- Put package-specific scripts, examples, and docs with the package when possible.
- Choose directory, distribution, and import names that are easy to map to each other.

## Build, Test, And Tooling

- Use `uv` for dependency management and command execution.
- Preferred bootstrap command: `uv sync --all-packages --extra dev`.
- The devcontainer creates `uv-sync-dev` and `uv-sync-all`; reuse those helpers.
- Run tests with `uv run pytest`.
- Pytest is configured at the root and currently discovers tests from `tests/`.
- Keep shared tool configuration in the root `pyproject.toml` when supported.
- Reuse the existing Markdown lint task for Markdown validation.

## Code Style

- Target Python 3.14 or newer as declared in the root `pyproject.toml`.
- Black is the default formatter in the workspace.
- Respect existing formatting and avoid unrelated reformatting.
- Prefer clear, typed, maintainable Python over speculative abstractions.
- Favor small, composable libraries with explicit APIs.

## Testing Conventions

- Use the existing pytest markers: `unit`, `integration`, `performance`, and `slow`.
- Keep tests aligned with the behavior they validate.
- Add at least basic smoke or unit coverage for each new package.

## Working In This Repository

- Decide whether a change belongs in an existing package or a new workspace member.
- Consider the impact on every package before changing shared tooling.
- Treat the devcontainer and `flake.nix` as supported bootstrap paths.
- Use the existing root `.env` file for required environment variables.
- Update `README.md` when workflow or package inventory changes are user-visible.

## Practical Guidance For Agents

- Read the root `pyproject.toml` and relevant `src/` package before editing.
- Scaffold new libraries as workspace members instead of bolting code onto the root.
- Clarify whether “the project” means the monorepo root or a specific package.
- Prefer incremental, package-focused changes that preserve workspace conventions.
