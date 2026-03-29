"""Registry-focused tests for nginx variable definitions."""

from __future__ import annotations

import pytest

from log_generator.providers.nginx.examples.main import SHIPPED_FORMATS
from log_generator.providers.nginx.pools import all_pools


def _extract_variables(log_format: str) -> set[str]:
    variables: set[str] = set()
    current = []
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


@pytest.mark.unit
@pytest.mark.parametrize(("format_name", "log_format"), SHIPPED_FORMATS)
def test_shipped_format_variables_are_registered(
    format_name: str,
    log_format: str,
) -> None:
    registered = all_pools()
    required_variables = _extract_variables(log_format)

    assert required_variables <= set(registered), format_name
