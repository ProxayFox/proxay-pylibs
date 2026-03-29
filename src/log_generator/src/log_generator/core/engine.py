"""Thin engine wrapper over provider implementations."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import TextIO, cast

from .base import BaseProvider
from .registry import get_provider


class LogEngine:
    """Generate log lines through a provider-oriented interface."""

    def __init__(self, provider: BaseProvider | str) -> None:
        if isinstance(provider, str):
            provider = get_provider(provider)

        self.provider = provider

    @classmethod
    def from_provider(cls, provider: BaseProvider | str) -> "LogEngine":
        """Build a ``LogEngine`` from a provider instance or registered name."""
        return cls(provider)

    def generate_entry(
        self,
        *,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, str]:
        """Generate a provider-specific entry dictionary."""
        return self.provider.generate_entry(variables=variables, timestamp=timestamp)

    def generate_line(
        self,
        *,
        preset: str | None = None,
        log_format: str | None = None,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        """Generate a single rendered log line."""
        return self.provider.generate_line(
            preset=preset,
            log_format=log_format,
            variables=variables,
            timestamp=timestamp,
        )

    def stream(
        self,
        count: int,
        *,
        preset: str | None = None,
        log_format: str | None = None,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> Iterator[str]:
        """Yield ``count`` rendered log lines."""
        if count < 0:
            raise ValueError("count must be greater than or equal to zero.")

        for _ in range(count):
            yield self.generate_line(
                preset=preset,
                log_format=log_format,
                variables=variables,
                timestamp=timestamp,
            )

    def write(
        self,
        count: int,
        destination: TextIO | str | PathLike[str],
        *,
        preset: str | None = None,
        log_format: str | None = None,
        variables: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        """Write ``count`` rendered log lines to a file path or text stream."""
        if isinstance(destination, str):
            path = Path(destination)
            with path.open("w", encoding="utf-8") as handle:
                return self.write(
                    count,
                    handle,
                    preset=preset,
                    log_format=log_format,
                    variables=variables,
                    timestamp=timestamp,
                )

        if isinstance(destination, PathLike):
            path = Path(cast(PathLike[str], destination))
            with path.open("w", encoding="utf-8") as handle:
                return self.write(
                    count,
                    handle,
                    preset=preset,
                    log_format=log_format,
                    variables=variables,
                    timestamp=timestamp,
                )

        written = 0
        for line in self.stream(
            count,
            preset=preset,
            log_format=log_format,
            variables=variables,
            timestamp=timestamp,
        ):
            destination.write(f"{line}\n")
            written += 1

        return written
