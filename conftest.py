"""Workspace-level pytest options."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--skip-integration",
        action="store_true",
        default=False,
        help="Skip tests marked with @pytest.mark.integration.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not config.getoption("--skip-integration"):
        return

    skip_integration = pytest.mark.skip(reason="skipped by --skip-integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
