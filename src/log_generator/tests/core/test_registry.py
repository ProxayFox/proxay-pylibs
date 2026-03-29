"""Registry coverage for the wrapper-oriented log_generator core."""

from __future__ import annotations

import pytest

from log_generator.core import (
    all_providers,
    get_provider,
    provider_names,
    register_provider,
)
from log_generator.core.base import BaseProvider
from log_generator.providers import basic, nginx
from tests.providers.nginx._nginx_test_helpers import (
    FIXED_TIMESTAMP,
    assert_no_unresolved_placeholders,
)


class _RegistryTestProvider(BaseProvider):
    name = "registry-test"
    default_preset = "default"

    @property
    def presets(self) -> dict[str, str]:
        return {"default": "value={value}"}

    @property
    def shipped_formats(self) -> tuple[tuple[str, str], ...]:
        return (("Registry Test Format", "value={value}"),)

    def generate_entry(self, variables=None, timestamp=None) -> dict[str, str]:
        return {"value": "ok"}

    def format_line(self, entry: dict[str, str], log_format: str) -> str:
        return log_format.format_map(entry)


@pytest.mark.unit
def test_nginx_provider_is_registered() -> None:
    provider = get_provider("nginx")

    assert provider is nginx.NGINX_PROVIDER
    assert provider.name == "nginx"
    assert provider.description
    assert provider.default_preset == "default"
    assert provider.available_presets() == ("default", "json", "example", "production")


@pytest.mark.unit
def test_basic_provider_is_registered() -> None:
    provider = get_provider("basic")

    assert provider is basic.BASIC_PROVIDER
    assert provider.name == "basic"
    assert provider.description
    assert provider.default_preset == "default"
    assert provider.available_presets() == ("default", "kv", "json")


@pytest.mark.unit
def test_registered_provider_exposes_preset_details() -> None:
    provider = get_provider("nginx")

    preset_names = tuple(name for name, _, _ in provider.preset_details())

    assert preset_names == provider.available_presets()
    assert any(
        label == "Production Format Example"
        for _, label, _ in provider.preset_details()
    )


@pytest.mark.unit
def test_registry_lists_builtin_provider_names() -> None:
    providers = all_providers()

    assert "basic" in providers
    assert "nginx" in providers
    assert provider_names() == tuple(providers)


@pytest.mark.unit
def test_registered_provider_can_generate_a_shipped_line() -> None:
    provider = get_provider("nginx")

    rendered = provider.generate_line(timestamp=FIXED_TIMESTAMP, preset="production")

    assert_no_unresolved_placeholders(rendered)
    assert '"' in rendered


@pytest.mark.unit
def test_basic_provider_can_generate_a_shipped_line() -> None:
    provider = get_provider("basic")

    rendered = provider.generate_line(timestamp=FIXED_TIMESTAMP, preset="json")

    assert "{timestamp}" not in rendered
    assert '"level":' in rendered


@pytest.mark.unit
def test_get_provider_rejects_unknown_provider() -> None:
    with pytest.raises(KeyError, match="Unknown provider"):
        get_provider("does-not-exist")


@pytest.mark.unit
def test_register_provider_rejects_duplicate_names() -> None:
    provider = _RegistryTestProvider()
    provider.name = "basic"

    with pytest.raises(ValueError, match="already registered"):
        register_provider(provider)


@pytest.mark.unit
def test_register_provider_rejects_empty_names() -> None:
    provider = _RegistryTestProvider()
    provider.name = "  "

    with pytest.raises(ValueError, match="must not be empty"):
        register_provider(provider)
