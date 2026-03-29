"""Coverage for the lightweight basic provider."""

from __future__ import annotations

import re

import pytest

from log_generator.core import LogEngine, get_provider
from log_generator.providers import basic


UNRESOLVED_BASIC_FIELD_PATTERN = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


@pytest.mark.unit
def test_basic_provider_default_preset_renders_without_placeholders() -> None:
    rendered = get_provider("basic").generate_line(preset="default")

    assert UNRESOLVED_BASIC_FIELD_PATTERN.search(rendered) is None
    assert ": " in rendered


@pytest.mark.unit
def test_basic_provider_json_preset_renders_json_shape() -> None:
    rendered = get_provider("basic").generate_line(preset="json")

    assert rendered.startswith("{")
    assert rendered.endswith("}")
    assert '"timestamp":' in rendered
    assert UNRESOLVED_BASIC_FIELD_PATTERN.search(rendered) is None


@pytest.mark.unit
def test_basic_provider_can_filter_requested_fields() -> None:
    entry = get_provider("basic").generate_entry(variables=["timestamp", "level"])

    assert set(entry) == {"timestamp", "level"}


@pytest.mark.unit
def test_basic_provider_accepts_braced_variable_names() -> None:
    entry = get_provider("basic").generate_entry(variables=["{timestamp}", "{service}"])

    assert set(entry) == {"timestamp", "service"}


@pytest.mark.unit
def test_basic_engine_stream_supports_named_provider() -> None:
    rendered_lines = list(LogEngine.from_provider("basic").stream(2, preset="kv"))

    assert len(rendered_lines) == 2
    assert all("request_id=req-" in line for line in rendered_lines)


@pytest.mark.unit
def test_basic_provider_public_exports_are_available() -> None:
    assert basic.DEFAULT_FORMAT
    assert basic.KV_FORMAT
    assert basic.JSON_FORMAT
    assert basic.PRESETS
    assert basic.PRESET_DETAILS
