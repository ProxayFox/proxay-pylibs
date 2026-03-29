"""Coverage for the shipped NGINX example module."""

from __future__ import annotations

import builtins
from pathlib import Path
import runpy

import pytest

import log_generator.providers.nginx.examples.main as example_main
import log_generator.providers.nginx.pools as nginx_pools


@pytest.mark.unit
def test_example_main_prints_rendered_lines(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        example_main,
        "PRINT",
        [("Test Format", "$remote_addr")],
    )
    monkeypatch.setattr(
        example_main, "generate_log_entry", lambda: {"$remote_addr": "203.0.113.1"}
    )
    monkeypatch.setattr(
        example_main, "format_log_line", lambda entry, fmt: entry["$remote_addr"]
    )

    example_main.main()

    output = capsys.readouterr().out
    assert "Format: Test Format" in output
    assert output.count("203.0.113.1") == 5


@pytest.mark.unit
def test_example_script_supports_direct_execution_path() -> None:
    namespace = runpy.run_path(
        str(Path(example_main.__file__).resolve()),
        run_name="example_script_test",
    )

    assert "DEFAULT_FORMAT" in namespace
    assert "PRINT" in namespace


@pytest.mark.unit
def test_example_module_main_entrypoint_executes_when_run_as_main(monkeypatch) -> None:
    printed: list[str] = []

    monkeypatch.setattr(
        nginx_pools,
        "generate_log_entry",
        lambda: {"$remote_addr": "198.51.100.7"},
    )
    monkeypatch.setattr(
        nginx_pools,
        "format_log_line",
        lambda entry, fmt: entry["$remote_addr"],
    )
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )

    runpy.run_module("log_generator.providers.nginx.examples.main", run_name="__main__")

    assert any("Format:" in line for line in printed)
    assert any("198.51.100.7" in line for line in printed)
