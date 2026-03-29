"""Thin provider adapter for the pool-based NGINX implementation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from log_generator.core.base import BaseProvider
from log_generator.core.registry import register_provider

from .examples.main import (
    DEFAULT_FORMAT,
    EXAMPLE_FORMAT,
    JSON_FORMAT,
    PRODUCTION_FORMAT,
    SHIPPED_FORMATS,
)
from .pools import format_log_line, generate_log_entry


PRESETS: dict[str, str] = {
    "default": DEFAULT_FORMAT,
    "json": JSON_FORMAT,
    "example": EXAMPLE_FORMAT,
    "production": PRODUCTION_FORMAT,
}


class NginxProvider(BaseProvider):
    """Provider adapter that delegates to the existing NGINX pools layer."""

    name = "nginx"
    default_preset = "default"

    @property
    def presets(self) -> Mapping[str, str]:
        """Return CLI-friendly preset names for shipped NGINX formats."""
        return PRESETS

    @property
    def shipped_formats(self) -> tuple[tuple[str, str], ...]:
        """Return the shipped format labels used in docs and tests."""
        return SHIPPED_FORMATS

    def generate_entry(
        self,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, str]:
        """Delegate entry generation to the pool orchestrator."""
        return generate_log_entry(variables=variables, timestamp=timestamp)

    def format_line(self, entry: dict[str, str], log_format: str) -> str:
        """Delegate line rendering to the pool orchestrator."""
        return format_log_line(entry, log_format)


NGINX_PROVIDER = register_provider(NginxProvider())
