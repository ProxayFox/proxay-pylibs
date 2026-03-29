"""Minimal provider contract for ``log_generator``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime


class BaseProvider(ABC):
    """Abstract provider contract used by the engine and CLI layers."""

    name: str
    default_preset: str
    description: str = ""

    @property
    @abstractmethod
    def presets(self) -> Mapping[str, str]:
        """Return provider preset names mapped to format strings."""

    @property
    @abstractmethod
    def shipped_formats(self) -> tuple[tuple[str, str], ...]:
        """Return shipped format labels and their format strings."""

    def available_presets(self) -> tuple[str, ...]:
        """Return the provider preset names in declaration order."""
        return tuple(self.presets)

    def preset_details(self) -> tuple[tuple[str, str, str], ...]:
        """Return ``(preset_name, display_label, format_string)`` tuples."""
        return tuple((name, name, fmt) for name, fmt in self.presets.items())

    def resolve_format(
        self, *, preset: str | None = None, log_format: str | None = None
    ) -> str:
        """Resolve a raw format string from a preset name or direct input."""
        if preset is not None and log_format is not None:
            raise ValueError("Pass either 'preset' or 'log_format', not both.")

        if log_format is not None:
            return log_format

        resolved_preset = preset or self.default_preset

        try:
            return self.presets[resolved_preset]
        except KeyError as exc:
            available = ", ".join(self.available_presets())
            raise KeyError(
                f"Unknown preset {resolved_preset!r} for provider {self.name!r}. "
                f"Available presets: {available}"
            ) from exc

    @abstractmethod
    def generate_entry(
        self,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, str]:
        """Generate a provider-specific context dictionary."""

    @abstractmethod
    def format_line(self, entry: dict[str, str], log_format: str) -> str:
        """Render a generated entry using a provider-specific format string."""

    def generate_line(
        self,
        *,
        preset: str | None = None,
        log_format: str | None = None,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        """Generate and render a single log line."""
        entry = self.generate_entry(variables=variables, timestamp=timestamp)
        resolved_format = self.resolve_format(preset=preset, log_format=log_format)
        return self.format_line(entry, resolved_format)
