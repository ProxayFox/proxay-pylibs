"""Lightweight application-log provider used to validate the core abstraction."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import random

from log_generator.core.base import BaseProvider
from log_generator.core.registry import register_provider


DEFAULT_FORMAT = "[{timestamp}] {level} {service}: {message}"
KV_FORMAT = (
    "timestamp={timestamp} level={level} service={service} "
    'request_id={request_id} message="{message}"'
)
JSON_FORMAT = (
    '{{"timestamp":"{timestamp}","level":"{level}","service":"{service}",'
    '"request_id":"{request_id}","message":"{message}"}}'
)

SHIPPED_FORMATS: tuple[tuple[str, str], ...] = (
    ("Default App Format", DEFAULT_FORMAT),
    ("Key Value App Format", KV_FORMAT),
    ("JSON App Format", JSON_FORMAT),
)

PRESETS: dict[str, str] = {
    "default": DEFAULT_FORMAT,
    "kv": KV_FORMAT,
    "json": JSON_FORMAT,
}

PRESET_DETAILS: tuple[tuple[str, str, str], ...] = (
    ("default", "Default App Format", DEFAULT_FORMAT),
    ("kv", "Key Value App Format", KV_FORMAT),
    ("json", "JSON App Format", JSON_FORMAT),
)

LEVELS = ("INFO", "WARN", "ERROR", "DEBUG")
SERVICES = ("api", "worker", "frontend", "scheduler")
MESSAGES = (
    "request completed",
    "cache miss",
    "user authenticated",
    "job queued",
    "configuration reloaded",
)


class _SafeFormatDict(dict[str, str]):
    """Preserve unknown placeholders rather than failing closed."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _normalize_field_name(name: str) -> str:
    """Normalize requested variable names for the basic provider."""
    if name.startswith("{") and name.endswith("}"):
        return name[1:-1]
    return name


class BasicProvider(BaseProvider):
    """Simple application-log provider used to exercise multi-provider support."""

    name = "basic"
    default_preset = "default"
    description = (
        "Simple application-log provider with plaintext, key-value, and JSON presets."
    )

    @property
    def presets(self) -> Mapping[str, str]:
        """Return CLI-friendly preset names for the basic provider."""
        return PRESETS

    @property
    def shipped_formats(self) -> tuple[tuple[str, str], ...]:
        """Return the shipped format labels used in docs and tests."""
        return SHIPPED_FORMATS

    def preset_details(self) -> tuple[tuple[str, str, str], ...]:
        """Return CLI-friendly preset names, labels, and format strings."""
        return PRESET_DETAILS

    def generate_entry(
        self,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, str]:
        """Generate a small application-log context dictionary."""
        ts = timestamp or datetime.now(timezone.utc)
        generated = {
            "timestamp": ts.isoformat(timespec="seconds"),
            "level": random.choice(LEVELS),
            "service": random.choice(SERVICES),
            "request_id": f"req-{random.randint(0, 0xFFFFFFFF):08x}",
            "message": random.choice(MESSAGES),
        }

        if variables is None:
            return generated

        requested = {_normalize_field_name(name) for name in variables}
        return {name: value for name, value in generated.items() if name in requested}

    def format_line(self, entry: dict[str, str], log_format: str) -> str:
        """Render a generated entry using ``str.format_map`` semantics."""
        return log_format.format_map(_SafeFormatDict(entry))


BASIC_PROVIDER = register_provider(BasicProvider())
