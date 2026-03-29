# proxay-pylibs

`proxay-pylibs` is a `uv`-managed Python monorepo for reusable packages that can
be shared across different projects.

## What lives here

- The repository root holds shared tooling, workspace configuration, and docs.
- Each reusable library lives in its own workspace member under `src/`.
- Package-specific tests can live inside the package member, and shared tests can
   still live at the repository root.

## Current packages

### `http-to-arrow`

The current workspace package lives in `src/http_to_arrow` and provides
Arrow-backed ingestion containers.

- `ArrowRecordContainer`
- `UnknownFieldPolicy`
- `MissingFieldPolicy`
- `CoercionPolicy`

### `log-generator`

The `log-generator` workspace package lives in `src/log_generator` and is
intended for synthetic log generation from reusable, format-driven templates.

- template-based field generation
- reusable generators for structured log emission
- built-in presets for formats such as NGINX access logs

## Repository layout

- `pyproject.toml` - shared workspace and test configuration
- `src/` - workspace members, one package per subdirectory
- `templates/` - starter templates for new workspace members
- `tests/` - shared integration or multi-package tests when needed
- `.devcontainer/` - development container setup
- `flake.nix` - optional Nix development shell

## Standard package scaffold

New packages should follow this layout:

- `src/<member>/pyproject.toml`
- `src/<member>/README.md`
- `src/<member>/src/<import_package>/\_\_init\_\_.py`
- `src/<member>/src/<import_package>/...`
- `src/<member>/tests/test_*.py`

This keeps implementation code out of the package project root while still using
the standard Python `src` layout that tools like Hatch, pytest, and Pylance
handle well.

## Starter template

A reusable starter lives in `templates/python-package/`.

Use it when you want the fastest path to a new package member without needing to
remember the full scaffold from scratch.

The starter includes:

- a package `pyproject.toml` template
- a package README template
- a minimal `src/<import_package>/` starter
- a package-local smoke test template

## Quick start

1. Sync the shared development environment with
   `uv sync --all-packages --extra dev`.
2. Run tests with `uv run pytest`.
3. Review the default terminal coverage summary emitted by pytest-cov.
4. Add new packages under `src/<package_name>/` using the standard package
   scaffold described below.

## Testing and coverage

- The shared pytest configuration lives in the repository root `pyproject.toml`.
- `uv run pytest` includes coverage by default for the current `http_to_arrow`
   package while the workspace is still small and focused.
- Coverage is reported with branch tracking and a terminal summary of missing
   lines, so contributors can see gaps without extra flags.
- The current default coverage gate is set to 90% for the package under test;
   if more workspace members are added later, this can be widened or scoped per
   package as needed.

## Development container

The devcontainer is built from `.devcontainer/Dockerfile` and uses the base
image `mcr.microsoft.com/devcontainers/python:3-3.14-trixie`.

The post-create setup also:

- installs shared development dependencies
- creates `uv-sync-dev` and `uv-sync-all` helper commands

## Adding packages

When you add a new reusable library:

1. Create a new workspace member under `src/`.
2. Copy the starter files from `templates/python-package/`.
3. Replace the template placeholders and rename `package_name`.
4. Put runtime package code under `src/<member>/src/<import_package>/`.
5. Put package-specific tests under `src/<member>/tests/`.
6. Update this README if the new package should be discoverable by other users.
