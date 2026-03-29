# proxay-pylibs

`proxay-pylibs` is a `uv`-managed Python monorepo for reusable packages that can
be shared across different projects.

## What lives here

- The repository root holds shared tooling, workspace configuration, and docs.
- Each reusable library lives in its own workspace member under `src/`.
- Tests are collected from the root `tests/` directory.

## Current packages

### `proxay-utils`

The first workspace package lives in `src/proxay_utils` and provides lightweight
collection helpers:

- `chunked(iterable, size)`
- `flatten_once(iterables)`

## Repository layout

- `pyproject.toml` - shared workspace and test configuration
- `src/` - workspace members, one package per subdirectory
- `tests/` - repository-level tests for workspace packages
- `.devcontainer/` - development container setup
- `flake.nix` - optional Nix development shell

## Quick start

1. Sync the shared development environment with
   `uv sync --all-packages --extra dev`.
2. Run tests with `uv run pytest`.
3. Add new packages under `src/<package_name>/` with their own `pyproject.toml`.

## Development container

The devcontainer is built from `.devcontainer/Dockerfile` and uses the base
image `mcr.microsoft.com/devcontainers/python:3-3.14-trixie`.

The post-create setup also:

- installs shared development dependencies
- creates `uv-sync-dev` and `uv-sync-all` helper commands

## Adding packages

When you add a new reusable library:

1. Create a new workspace member under `src/`.
2. Give it its own `pyproject.toml` and package code.
3. Add tests under `tests/`.
4. Update this README if the new package should be discoverable by other users.
