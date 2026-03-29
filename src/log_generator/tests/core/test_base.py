"""Direct coverage for the base provider contract."""

from __future__ import annotations

import pytest

from log_generator.core.base import BaseProvider


class _DemoProvider(BaseProvider):
    name = "demo"
    default_preset = "default"

    @property
    def presets(self) -> dict[str, str]:
        return {"default": "value={value}"}

    @property
    def shipped_formats(self) -> tuple[tuple[str, str], ...]:
        return (("Demo Format", "value={value}"),)

    def generate_entry(self, variables=None, timestamp=None) -> dict[str, str]:
        return {"value": "demo"}

    def format_line(self, entry: dict[str, str], log_format: str) -> str:
        return log_format.format_map(entry)


@pytest.mark.unit
def test_base_provider_default_preset_details_are_derived_from_presets() -> None:
    provider = _DemoProvider()

    assert provider.preset_details() == (("default", "default", "value={value}"),)


@pytest.mark.unit
def test_base_provider_resolve_format_rejects_unknown_preset() -> None:
    provider = _DemoProvider()

    with pytest.raises(KeyError, match="Unknown preset"):
        provider.resolve_format(preset="missing")
