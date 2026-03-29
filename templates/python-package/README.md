# Python package starter template

Use this starter when creating a new workspace member under `src/`.
The template is intentionally kept outside `src/` so it does not become a
workspace package by accident.

## What this template includes

- `pyproject.toml.template` for package metadata
- `PACKAGE_README.md.template` for package-level docs
- `src/package_name/\_\_init\_\_.py.template` for the public import package
- `tests/test_package_name.py.template` for a minimal package-local smoke test

## Recommended workflow

1. Create a new member directory at `src/<member>/`.
2. Copy the template files into that member.
3. Rename `package_name` to your real import package name.
4. Replace all `{{ ... }}` placeholders.
5. Run `uv sync --all-packages --extra dev`.
6. Run `uv run pytest`.

## Placeholder meanings

- `{{ member_name }}`: workspace member directory such as `http_to_arrow`
- `{{ distribution_name }}`: published package name such as `http-to-arrow`
- `{{ import_package }}`: Python import package such as `http_to_arrow`
- `{{ description }}`: short package description
- `{{ author_name }}` and `{{ author_email }}`: package author metadata

## Target layout

- `src/{{ member_name }}/pyproject.toml`
- `src/{{ member_name }}/README.md`
- `src/{{ member_name }}/src/{{ import_package }}/\_\_init\_\_.py`
- `src/{{ member_name }}/tests/test_{{ import_package }}.py`
