"""Smoke tests for log_generator."""

from __future__ import annotations

import pytest

from log_generator import basic, core, nginx, providers


@pytest.mark.unit
def test_package_imports() -> None:
    module = __import__("log_generator")

    assert module is not None


@pytest.mark.unit
def test_public_api_exports_expected_generation_helpers() -> None:
    assert providers.basic is basic
    assert providers.nginx is nginx
    assert core.get_provider("basic") is basic.BASIC_PROVIDER
    assert core.get_provider("nginx") is nginx.NGINX_PROVIDER
    assert callable(nginx.generate_log_entry)
    assert callable(nginx.format_log_line)
    assert basic.DEFAULT_FORMAT
    assert basic.KV_FORMAT
    assert basic.JSON_FORMAT
    assert basic.SHIPPED_FORMATS
    assert nginx.PRODUCTION_FORMAT == nginx.EXAMPLE_FORMAT
    assert nginx.DEFAULT_FORMAT
    assert nginx.JSON_FORMAT
    assert nginx.SHIPPED_FORMATS


@pytest.mark.unit
def test_root_package_exposes_core_namespace() -> None:
    assert callable(core.LogEngine.from_provider)
    assert "basic" in core.provider_names()
    assert "nginx" in core.provider_names()


@pytest.mark.unit
def test_public_api_can_render_a_shipped_format() -> None:
    entry = nginx.generate_log_entry()
    rendered = nginx.format_log_line(entry, nginx.PRODUCTION_FORMAT)

    assert isinstance(rendered, str)
    assert rendered


@pytest.mark.unit
def test_basic_provider_can_render_a_shipped_format() -> None:
    engine = core.LogEngine.from_provider("basic")
    rendered = engine.generate_line(preset="default")

    assert isinstance(rendered, str)
    assert rendered
