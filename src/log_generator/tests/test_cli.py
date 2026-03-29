"""CLI coverage for the ``log_generator`` package."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
import pytest

from log_generator.cli import main
from tests.providers.nginx._nginx_test_helpers import UNRESOLVED_VARIABLE_PATTERN


@pytest.mark.unit
def test_providers_command_lists_nginx_and_presets() -> None:
    result = CliRunner().invoke(main, ["providers"])

    assert result.exit_code == 0
    assert "nginx:" in result.output
    assert "default" in result.output
    assert "production" in result.output


@pytest.mark.unit
def test_sources_alias_lists_registered_providers() -> None:
    result = CliRunner().invoke(main, ["sources"])

    assert result.exit_code == 0
    assert "nginx:" in result.output


@pytest.mark.unit
def test_generate_command_emits_requested_number_of_lines() -> None:
    result = CliRunner().invoke(
        main, ["generate", "--count", "3", "--preset", "default"]
    )

    rendered_lines = result.output.splitlines()

    assert result.exit_code == 0
    assert len(rendered_lines) == 3
    assert all(rendered_lines)
    assert all(
        UNRESOLVED_VARIABLE_PATTERN.search(line) is None for line in rendered_lines
    )


@pytest.mark.unit
def test_generate_command_supports_custom_formats() -> None:
    custom_format = '$remote_addr [$time_iso8601] "$request" $status'

    result = CliRunner().invoke(main, ["generate", "-f", custom_format])

    rendered = result.output.strip()

    assert result.exit_code == 0
    assert rendered
    assert UNRESOLVED_VARIABLE_PATTERN.search(rendered) is None
    assert rendered.count("[") == 1
    assert rendered.count('"') == 2


@pytest.mark.unit
def test_generate_command_supports_output_files(tmp_path: Path) -> None:
    output_path = tmp_path / "nginx.log"

    result = CliRunner().invoke(
        main,
        ["generate", "--count", "2", "--preset", "json", "--output", str(output_path)],
    )

    rendered_lines = output_path.read_text(encoding="utf-8").splitlines()

    assert result.exit_code == 0
    assert result.output == ""
    assert len(rendered_lines) == 2
    assert all("|" in line for line in rendered_lines)


@pytest.mark.unit
def test_generate_command_rejects_conflicting_preset_and_format() -> None:
    result = CliRunner().invoke(
        main,
        ["generate", "--preset", "default", "--format", "$remote_addr"],
    )

    assert result.exit_code != 0
    assert "preset" in result.output


@pytest.mark.unit
def test_generate_command_rejects_unknown_provider() -> None:
    result = CliRunner().invoke(main, ["generate", "--provider", "apache"])

    assert result.exit_code != 0
    assert "Unknown provider" in result.output
