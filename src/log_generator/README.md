# log-generator

`log-generator` is a workspace package in `proxay-pylibs`.

## Purpose

Configurable synthetic log generator with format-driven templates.

The initial package outline is aimed at building reusable generators for log
formats such as NGINX access logs, including workflows that can derive emitted
fields from an `log_format`-style template string.

## Public API

Document the main public classes, functions, or modules here.

Potential directions for the first implementation pass:

- format string parsing for `log_format`-style definitions
- pluggable field generators backed by `faker`
- presets for common formats such as NGINX access logs
- deterministic seeding for reproducible fixtures and tests

## Development notes

- Runtime package code lives in `src/log_generator/`.
- Package-specific tests live in `tests/`.

## Inspirations

- ["josesolisrosales/logforge"](https://github.com/josesolisrosales/logforge)
- ["cybersecurity-log-generator"](https://pypi.org/project/cybersecurity-log-generator/)

## Goals differantiating from inspirations

- The goal would be to have logs far more flexamble, e.g. generating nginx logs with log_format templates,
  or even more complex formats with conditional fields.
- The goal of the project is to work with ["ClickSIEM"](https://github.com/ProxayFox/ClickSIEM),
  with the idea of having a companion package that can generate ClickSIEM-compatible logs for testing and demos.
