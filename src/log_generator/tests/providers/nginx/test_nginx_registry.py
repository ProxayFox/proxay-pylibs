"""Registry-focused tests for nginx variable definitions."""

from __future__ import annotations

import pytest

from ._nginx_test_helpers import extract_variables
from log_generator.providers.nginx.examples.main import SHIPPED_FORMATS
from log_generator.providers.nginx.pools import all_pools


@pytest.mark.unit
@pytest.mark.parametrize(("format_name", "log_format"), SHIPPED_FORMATS)
def test_shipped_format_variables_are_registered(
    format_name: str,
    log_format: str,
) -> None:
    registered = all_pools()
    required_variables = extract_variables(log_format)

    assert required_variables <= set(registered), format_name
