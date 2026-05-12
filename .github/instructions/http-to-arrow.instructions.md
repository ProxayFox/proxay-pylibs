---
description: "Use when editing the http_to_arrow workspace member or its tests. Covers the ArrowRecordContainer-centered API and main behavioral test surface."
applyTo:
  - "src/http_to_arrow/**"
  - "tests/http_to_arrow/**"
---

# HTTP To Arrow Guidance

- Start with `src/http_to_arrow/src/http_to_arrow/main.py`. The package
  behavior is centered on `ArrowRecordContainer`, and
  `src/http_to_arrow/src/http_to_arrow/__init__.py` mainly re-exports that
  surface.
- Use `tests/http_to_arrow/test_arrow_record_container.py` as the behavioral
  source of truth. It covers constructor validation, record append paths,
  coercion behavior, incremental flushing, reset aliases, Arrow and Polars
  conversion helpers, and row-count properties.
- Keep changes local to the container behavior unless the public re-export
  surface must change too.
- The package README is a high-level overview only. For the full current
  surface, rely on source and tests rather than assuming the README lists every
  supported helper or alias.
- Prefer narrow validation against
  `tests/http_to_arrow/test_arrow_record_container.py` when touching container
  behavior.
