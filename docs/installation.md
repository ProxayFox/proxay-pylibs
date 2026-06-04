# Installation

## Requirements

`http-to-arrow` requires Python `>=3.14`.

The package runtime dependencies are:

- `pyarrow>=23.0.1`
- `polars>=1.39.3`

## Install from PyPI

```bash
pip install http-to-arrow
```

!!! note
    The PyPI distribution name uses hyphens. Python imports use underscores.

Import the package with the underscore module name:

```python
from http_to_arrow import ArrowRecordContainer
```

## Install from source

Clone the monorepo and sync the workspace with `uv`:

```bash
git clone https://github.com/ProxayFox/proxay-pylibs.git
cd proxay-pylibs
uv sync --all-packages --group dev --group docs
```

Run a quick import check:

```bash
uv run python -c "from http_to_arrow import ArrowRecordContainer; print(ArrowRecordContainer.__name__)"
```

## Documentation dependencies

Documentation dependencies live in the root workspace `docs` dependency group.
Install them with:

```bash
uv sync --all-packages --group docs
```

!!! tip
    Run documentation commands from the repository root so `mkdocs.yml` and the
    nested `src/http_to_arrow/src` import path resolve correctly.

Serve the site locally:

```bash
just docs-serve
```

Build the site in strict mode:

```bash
just docs-build
```

## Optional extras

The `http-to-arrow` package does not currently define package-level optional
extras. The repository uses `uv` dependency groups for development,
documentation, and profiling tooling.

## Configuration and secrets

No authentication, credentials, environment variables, or secret-bearing config
files are required to use `http-to-arrow`.
