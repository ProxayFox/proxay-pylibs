"""Shared test helpers for nginx log_generator coverage."""

from __future__ import annotations

from datetime import datetime, timezone
import re


FIXED_TIMESTAMP = datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc)

UNRESOLVED_VARIABLE_PATTERN = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")


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
