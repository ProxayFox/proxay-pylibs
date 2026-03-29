"""Smoke tests for log_generator."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_package_imports() -> None:
    module = __import__("log_generator")

    assert module is not None
