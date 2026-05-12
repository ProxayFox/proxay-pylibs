---
description: "Use when editing the log_generator workspace member, its CLI, provider registry, or tests. Covers the provider-oriented architecture and current validation paths."
applyTo:
  - "src/log_generator/**"
  - "tests/log_generator/**"
---

# Log Generator Guidance

- Start from the nearest behavior owner.
  `src/log_generator/src/log_generator/cli.py` owns CLI behavior,
  `src/log_generator/src/log_generator/core/registry.py` owns provider lookup
  and registration, and `src/log_generator/src/log_generator/core/engine.py`
  is a thin wrapper over providers.
- Keep the public package shape namespace-oriented. The root package exposes
  provider namespaces such as `log_generator.basic` and `log_generator.nginx`
  rather than flattening provider helpers into the top level.
- Treat `src/log_generator/src/log_generator/providers/nginx/` as the current
  complex slice. The provider adapter in `provider.py` maps presets and
  delegates generation and rendering to the pool-based implementation.
- When README guidance conflicts with the tree, trust the current tree and
  tests. The package README still mentions `src/log_generator/tests`, but the
  current behavioral source of truth is under `tests/log_generator/`.
- Prefer focused validation against the nearest tests for the touched slice,
  such as CLI tests in `tests/log_generator/test_cli.py`, core tests in
  `tests/log_generator/core/`, and NGINX tests in
  `tests/log_generator/providers/nginx/`.
- Preserve the thin-provider pattern: new providers should fit the
  `BaseProvider` and registry flow instead of bypassing `register_provider` or
  adding one-off CLI logic.
- Use the package README for examples and supported presets, but prefer source
  and tests for exact current behavior.
