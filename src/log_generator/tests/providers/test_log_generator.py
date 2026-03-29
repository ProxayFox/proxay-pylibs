"""Smoke tests for log_generator."""

from __future__ import annotations

import pytest

from log_generator import nginx, providers


@pytest.mark.unit
def test_package_imports() -> None:
    module = __import__("log_generator")

    assert module is not None


@pytest.mark.unit
def test_public_api_exports_expected_generation_helpers() -> None:
    assert providers.nginx is nginx
    assert callable(nginx.generate_log_entry)
    assert callable(nginx.format_log_line)
    assert nginx.PRODUCTION_FORMAT == nginx.EXAMPLE_FORMAT
    assert nginx.DEFAULT_FORMAT
    assert nginx.JSON_FORMAT
    assert nginx.SHIPPED_FORMATS


@pytest.mark.unit
def test_public_api_can_render_a_shipped_format() -> None:
    entry = nginx.generate_log_entry()
    rendered = nginx.format_log_line(entry, nginx.PRODUCTION_FORMAT)

    assert isinstance(rendered, str)
    assert rendered
