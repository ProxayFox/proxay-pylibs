---
name: Start Package From Template
description: "Create a new workspace Python package/member under src/ using the shared package template"
argument-hint: "Package idea or names (member, distribution, import package, description)"
agent: agent
---

# Start Package From Template

Create a new Python workspace member in this monorepo using the shared package template.

Use these repo rules and references:

- Follow the workspace conventions in [copilot instructions](../copilot-instructions.md).
- Use the starter workflow in [template guide](../../templates/python-package/README.md).
- Create the package as a new member under `src/<member>/` with the standard nested src layout.

## Inputs

Use the user's request to determine or confirm:

- `member_name`: workspace member directory, usually snake_case, e.g. `http_to_arrow`
- `distribution_name`: published package name, usually kebab-case, e.g. `http-to-arrow`
- `import_package`: Python import package, usually snake_case
- `description`: short package description
- optional package-specific dependencies

If any required name is missing or ambiguous, ask one concise clarification question before editing files.

## What to do

- Inspect the existing workspace structure before making changes.
- Scaffold a new package under `src/<member_name>/` using the files from
  `templates/python-package/`. Create `pyproject.toml`, `README.md`, the
  package initializer in `src/<import_package>/`, and
  `tests/test_<import_package>.py`.
- Replace every template placeholder: `{{ member_name }}`,
  `{{ distribution_name }}`, `{{ import_package }}`, `{{ description }}`,
  `{{ author_name }}`, and `{{ author_email }}`.
- Keep the new package aligned with the monorepo rules: Python `>=3.14`,
  package code in `src/<member_name>/src/<import_package>/`, package-local
  tests in `src/<member_name>/tests/`, and no unrelated edits elsewhere.

- Decide whether any shared docs should be updated. If the new package
   changes user-visible package inventory or workflow, update the relevant
   README entries.
- Validate the scaffold with the smallest useful checks, such as focused
   tests for the new package. If broader validation is appropriate, use the
   repo's `uv` workflow.

## Output expectations

In your final response:

- briefly summarize what you created
- list each file added or changed with a one-line purpose
- report validation performed and results
- call out any follow-up the user may want next, such as adding dependencies,
  public API exports, or package-specific examples

Keep the work focused on scaffolding a fresh package from the shared
template—no bonus side quests unless the user asks for them.
