# log-generator

`log-generator` is a workspace package in `proxay-pylibs` focused on synthetic
NGINX access-log generation.

## Implemented now

The current shipped slice provides a pool-driven NGINX generator that can:

- generate realistic variable dictionaries for common NGINX log fields,
- render shipped format strings into complete log lines,
- support composite and conditional values such as request lines, forwarded-for
    chains, and TLS fields,
- render time fields from a fixed timestamp for deterministic tests,
- expose a thin provider registry and engine layer for future providers,
- generate lines from a test-backed CLI.

The root package now exposes provider namespaces rather than provider-specific
helpers directly. Today that means:

- `log_generator.basic`
- `log_generator.core`
- `log_generator.nginx`
- `log_generator.providers.basic`
- `log_generator.providers.nginx`

The current shipped providers are:

- `basic` — a lightweight application-log provider used to validate the
  multi-provider abstraction and CLI
- `nginx` — the pool-driven NGINX access-log provider

Within the NGINX provider namespace, the shipped surface includes:

- `generate_log_entry`
- `format_log_line`
- `NginxProvider`
- `NGINX_PROVIDER`
- `PRESETS`
- `PRESET_DETAILS`
- format constants:
  - `DEFAULT_FORMAT`
  - `JSON_FORMAT`
  - `EXAMPLE_FORMAT`
  - `PRODUCTION_FORMAT`
  - `SHIPPED_FORMATS`

Within `log_generator.core`, the shipped surface includes:

- `BaseProvider`
- `LogEngine`
- `get_provider`
- `all_providers`
- `provider_names`

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

You can also generate rendered lines through the thin engine layer.

```python
from log_generator.core import LogEngine

engine = LogEngine.from_provider("nginx")
print(engine.generate_line(preset="production"))
```

## CLI usage

The package now ships a Click-based CLI through the `log_generator` command.

```text
uv run log_generator providers
uv run log_generator presets
uv run log_generator presets --provider basic
uv run log_generator generate -n 5
uv run log_generator generate --provider basic -p kv -n 2
uv run log_generator generate -p production -n 2
uv run log_generator generate -f '$remote_addr [$time_iso8601] "$request" $status'
uv run log_generator generate -p json -n 10 -o /tmp/fake_nginx.log
```

Current CLI commands:

- `providers` — list registered providers and their shipped presets
- `presets` — list preset names and labels for a provider, optionally with raw formats
- `sources` — backward-compatible alias for `providers`
- `generate` — emit lines for a preset or custom format

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

- YAML configuration
- formal parser for arbitrary `log_format` strings
- dynamic plugin discovery for providers
- additional provider implementations beyond NGINX

## Development notes

- Runtime package code lives in `src/log_generator/`.
- Package-specific tests live in `tests/`.
- Focused validation currently uses package-local pytest files such as:
  - `tests/test_cli.py`
  - `tests/core/test_registry.py`
  - `tests/core/test_engine.py`
  - `tests/providers/nginx/test_nginx_shipping_rules.py`

## Inspirations and goals

- ["josesolisrosales/logforge"](https://github.com/josesolisrosales/logforge)
- ["cybersecurity-log-generator"](https://pypi.org/project/cybersecurity-log-generator/)

Longer term, the package is intended to support richer synthetic logging
workflows, including ClickSIEM-oriented demos and test data generation, but the
current release slice is deliberately NGINX-only and test-backed. Additional
providers should plug into the same namespace-oriented API rather than adding
provider-specific helpers to the root package.
