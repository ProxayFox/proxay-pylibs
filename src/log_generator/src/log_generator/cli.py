"""Command-line interface for ``log_generator``."""

from __future__ import annotations

from pathlib import Path

import click

from .core import LogEngine, all_providers, get_provider


def _build_engine(provider_name: str) -> LogEngine:
    """Return an engine for a registered provider name."""
    try:
        return LogEngine.from_provider(provider_name)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group(help="Generate synthetic log lines from supported providers.")
def main() -> None:
    """Top-level CLI group for ``log_generator``."""


def _echo_providers() -> None:
    """Render the registered provider list to standard output."""
    for provider_name, provider in all_providers().items():
        presets = ", ".join(provider.available_presets())
        click.echo(f"{provider_name}: {presets}")


@main.command("providers")
def providers_command() -> None:
    """List registered providers and their available presets."""
    _echo_providers()


@main.command("sources")
def sources_command() -> None:
    """Backward-compatible alias for ``providers``."""
    _echo_providers()


@main.command("generate")
@click.option(
    "--provider",
    "provider_name",
    default="nginx",
    show_default=True,
    help="Provider to use for log generation.",
)
@click.option(
    "--count",
    "count",
    "-n",
    default=1,
    show_default=True,
    type=click.IntRange(min=1),
    help="Number of log lines to generate.",
)
@click.option(
    "--format",
    "log_format",
    "-f",
    help="Custom provider-specific log format string.",
)
@click.option(
    "--preset",
    "preset",
    "-p",
    help="Named preset exposed by the selected provider.",
)
@click.option(
    "--output",
    "output_path",
    "-o",
    type=click.Path(path_type=Path, dir_okay=False, writable=True),
    help="Optional file path to write generated lines to.",
)
def generate_command(
    provider_name: str,
    count: int,
    log_format: str | None,
    preset: str | None,
    output_path: Path | None,
) -> None:
    """Generate rendered log lines from a provider."""
    engine = _build_engine(provider_name)

    try:
        if output_path is not None:
            engine.write(
                count,
                output_path,
                preset=preset,
                log_format=log_format,
            )
            return

        for line in engine.stream(count, preset=preset, log_format=log_format):
            click.echo(line)
    except (KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":
    main()
