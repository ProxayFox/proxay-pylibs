"""Engine coverage for the wrapper-oriented log_generator core."""

from __future__ import annotations

from io import StringIO
from os import PathLike

import pytest

from log_generator.core import LogEngine, get_provider
from log_generator.providers.nginx import DEFAULT_FORMAT, JSON_FORMAT
from tests.providers.nginx._nginx_test_helpers import (
    FIXED_TIMESTAMP,
    assert_no_unresolved_placeholders,
    assert_stable_shape,
)


@pytest.mark.unit
def test_engine_can_generate_line_from_named_provider() -> None:
    engine = LogEngine.from_provider("nginx")

    rendered = engine.generate_line(timestamp=FIXED_TIMESTAMP, preset="default")

    assert_no_unresolved_placeholders(rendered)
    assert_stable_shape(DEFAULT_FORMAT, rendered)


class _SyntheticPath(PathLike[str]):
    def __init__(self, value: str) -> None:
        self.value = value

    def __fspath__(self) -> str:
        return self.value


@pytest.mark.unit
def test_engine_can_generate_entry_from_provider_instance() -> None:
    provider = get_provider("basic")
    engine = LogEngine.from_provider(provider)

    entry = engine.generate_entry(
        variables=["timestamp", "level"], timestamp=FIXED_TIMESTAMP
    )

    assert set(entry) == {"timestamp", "level"}


@pytest.mark.unit
def test_engine_stream_returns_requested_number_of_lines() -> None:
    engine = LogEngine.from_provider("nginx")

    rendered_lines = list(engine.stream(3, preset="json", timestamp=FIXED_TIMESTAMP))

    assert len(rendered_lines) == 3
    assert all("|" in line for line in rendered_lines)
    assert all(line.count("|") == JSON_FORMAT.count("|") for line in rendered_lines)


@pytest.mark.unit
def test_engine_write_supports_text_stream_destinations() -> None:
    engine = LogEngine.from_provider("nginx")
    buffer = StringIO()

    written = engine.write(2, buffer, preset="default", timestamp=FIXED_TIMESTAMP)

    assert written == 2
    rendered_lines = buffer.getvalue().splitlines()
    assert len(rendered_lines) == 2
    assert all(rendered_lines)


@pytest.mark.unit
def test_engine_write_supports_file_paths(tmp_path) -> None:
    engine = LogEngine.from_provider("nginx")
    output_path = tmp_path / "synthetic-nginx.log"

    written = engine.write(
        2, output_path, preset="production", timestamp=FIXED_TIMESTAMP
    )

    assert written == 2
    rendered_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(rendered_lines) == 2
    assert all(rendered_lines)


@pytest.mark.unit
def test_engine_write_supports_string_paths(tmp_path) -> None:
    engine = LogEngine.from_provider("basic")
    output_path = str(tmp_path / "synthetic-basic-string.log")

    written = engine.write(1, output_path, preset="default", timestamp=FIXED_TIMESTAMP)

    assert written == 1
    rendered_lines = (
        (tmp_path / "synthetic-basic-string.log")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(rendered_lines) == 1
    assert rendered_lines[0]


@pytest.mark.unit
def test_engine_write_supports_generic_pathlike_objects(tmp_path) -> None:
    engine = LogEngine.from_provider("basic")
    output_path = _SyntheticPath(str(tmp_path / "synthetic-basic.log"))

    written = engine.write(1, output_path, preset="json", timestamp=FIXED_TIMESTAMP)

    assert written == 1
    rendered_lines = (
        (tmp_path / "synthetic-basic.log").read_text(encoding="utf-8").splitlines()
    )
    assert len(rendered_lines) == 1
    assert rendered_lines[0].startswith("{")


@pytest.mark.unit
def test_engine_rejects_negative_stream_counts() -> None:
    engine = LogEngine.from_provider("nginx")

    with pytest.raises(ValueError, match="count"):
        list(engine.stream(-1, preset="default"))


@pytest.mark.unit
def test_engine_rejects_conflicting_preset_and_log_format_inputs() -> None:
    engine = LogEngine.from_provider("nginx")

    with pytest.raises(ValueError, match="preset"):
        engine.generate_line(
            preset="default",
            log_format=DEFAULT_FORMAT,
            timestamp=FIXED_TIMESTAMP,
        )
