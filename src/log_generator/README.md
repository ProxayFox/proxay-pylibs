# log-generator

`log-generator` is a workspace package in `proxay-pylibs` focused on synthetic
NGINX access-log generation.

## Implemented now

The current shipped slice provides a pool-driven NGINX generator that can:

- generate realistic variable dictionaries for common NGINX log fields,
- render shipped format strings into complete log lines,
- support composite and conditional values such as request lines, forwarded-for
    chains, and TLS fields,
- render time fields from a fixed timestamp for deterministic tests.

The root package now exposes provider namespaces rather than provider-specific
helpers directly. Today that means:

- `log_generator.nginx`
- `log_generator.providers.nginx`

Within the NGINX provider namespace, the shipped surface includes:

- `generate_log_entry`
- `format_log_line`
- format constants:
  - `DEFAULT_FORMAT`
  - `JSON_FORMAT`
  - `EXAMPLE_FORMAT`
  - `PRODUCTION_FORMAT`
  - `SHIPPED_FORMATS`

## Example usage

```python
from log_generator import nginx

entry = nginx.generate_log_entry()
line = nginx.format_log_line(entry, nginx.PRODUCTION_FORMAT)

print(line)
```

You can also import through the provider package explicitly:

```python
from log_generator.providers import nginx

line = nginx.format_log_line(
  nginx.generate_log_entry(),
  nginx.DEFAULT_FORMAT,
)
```

You can also request only a subset of variables when you want to test specific
derived fields.

```python
from datetime import datetime, timezone

from log_generator import nginx

entry = nginx.generate_log_entry(
  variables=["$request_method", "$uri", "$args", "$request_uri", "$request"],
  timestamp=datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc),
)

print(entry["$request_uri"])
print(entry["$request"])
```

## Shipped formats

The package currently treats these as shipped, test-backed formats:

- default access-log style format
- compact JSON-ish pipe-separated format
- production-style example format with forwarded-for and TLS fields

Those shipped formats are validated in pytest to ensure:

- every referenced variable is registered,
- rendered output contains no unresolved `$variable` placeholders,
- delimiter shape remains stable after rendering.

## Deferred for later

These items are intentionally not shipped yet:

- CLI entry point
- YAML configuration
- formal parser for arbitrary `log_format` strings
- multi-provider architecture beyond NGINX

## Development notes

- Runtime package code lives in `src/log_generator/`.
- Package-specific tests live in `tests/`.
- Focused validation currently uses package-local pytest files rather than a
    broad repo-wide acceptance gate.

## Inspirations and goals

- ["josesolisrosales/logforge"](https://github.com/josesolisrosales/logforge)
- ["cybersecurity-log-generator"](https://pypi.org/project/cybersecurity-log-generator/)

Longer term, the package is intended to support richer synthetic logging
workflows, including ClickSIEM-oriented demos and test data generation, but the
current release slice is deliberately NGINX-only and test-backed. Additional
providers should plug into the same namespace-oriented API rather than adding
provider-specific helpers to the root package.
