"""Shared test helpers for nginx log_generator coverage."""

from __future__ import annotations

from datetime import datetime, timezone
import re

from log_generator.providers.nginx.pools import (
    all_pools,
    format_log_line,
    generate_log_entry,
)


FIXED_TIMESTAMP = datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc)

UNRESOLVED_VARIABLE_PATTERN = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")

SHAPE_MARKERS = ('"', "|", "[", "]")


def extract_variables(log_format: str) -> set[str]:
    """Extract nginx-style `$variable` tokens from a format string."""
    variables: set[str] = set()
    current: list[str] = []
    collecting = False

    for char in log_format:
        if char == "$":
            if current:
                variables.add("".join(current))
            current = ["$"]
            collecting = True
            continue

        if collecting and (char.isalnum() or char == "_"):
            current.append(char)
            continue

        if collecting and len(current) > 1:
            variables.add("".join(current))

        current = []
        collecting = False

    if collecting and len(current) > 1:
        variables.add("".join(current))

    return variables


def render_with_fixed_timestamp(log_format: str) -> str:
    """Render a format using the shared fixed timestamp test fixture."""
    entry = generate_log_entry(timestamp=FIXED_TIMESTAMP)
    return format_log_line(entry, log_format)


def marker_counts(
    value: str, *, markers: tuple[str, ...] = SHAPE_MARKERS
) -> dict[str, int]:
    """Count stable delimiter markers used to validate output shape."""
    return {marker: value.count(marker) for marker in markers}


def assert_no_unresolved_placeholders(rendered: str) -> None:
    """Assert that a rendered log line contains no unresolved `$variable` tokens."""
    assert UNRESOLVED_VARIABLE_PATTERN.search(rendered) is None


def assert_registered_variables(log_format: str) -> None:
    """Assert that every variable in a format is registered in the nginx pool registry."""
    required_variables = extract_variables(log_format)
    assert required_variables <= set(all_pools())


def assert_stable_shape(log_format: str, rendered: str) -> None:
    """Assert that stable delimiter markers from the format survive rendering unchanged."""
    assert marker_counts(rendered) == marker_counts(log_format)
