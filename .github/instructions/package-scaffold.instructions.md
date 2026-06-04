---
description: "Use when creating or changing workspace member scaffolds or package metadata."
applyTo:
  - "templates/python-package/**"
  - "src/*/pyproject.toml"
  - "src/*/README.md"
  - "src/*/src/*/__init__.py"
  - "src/*/tests/test_*.py"
---

# Package Scaffolding Guidance

- Use [Start Package From Template](../prompts/start-package.prompt.md) for
  full new-member scaffolding, and link to the
  [template guide](../../templates/python-package/README.md) for placeholder
  meanings and target layout.
- Keep the repository root as workspace tooling and docs only. Runtime code,
  runtime dependencies, and packaging metadata belong under `src/<member>/`.
- Preserve the naming split: `member_name` is the workspace directory,
  `distribution_name` is the published package name, and `import_package` is
  the Python package under `src/<member>/src/`.
- Check the member `pyproject.toml` before changing packaging. Current members
  use different build backends (`uv_build` and `hatchling`), so do not assume
  one backend applies everywhere.
- Add package-local tests under `src/<member>/tests/` for new packages unless
  the behavior is explicitly cross-package or integration-oriented.
- Update the root [README.md](../../README.md) when a new package changes the
  user-visible package inventory, setup workflow, or release guidance.
- Keep scaffold edits mechanical and minimal. Avoid unrelated package refactors
  while adding or adjusting a workspace member skeleton.
