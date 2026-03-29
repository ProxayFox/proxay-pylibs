"""Static provider registry for ``log_generator``."""

from __future__ import annotations

from importlib import import_module

from .base import BaseProvider


_PROVIDERS: dict[str, BaseProvider] = {}
_BUILTIN_PROVIDER_MODULES: tuple[str, ...] = ("log_generator.providers.nginx.provider",)
_BUILTINS_LOADED = False


def _load_builtin_providers() -> None:
    """Import built-in provider modules exactly once."""
    global _BUILTINS_LOADED

    if _BUILTINS_LOADED:
        return

    for module_name in _BUILTIN_PROVIDER_MODULES:
        import_module(module_name)

    _BUILTINS_LOADED = True


def register_provider(provider: BaseProvider) -> BaseProvider:
    """Register a provider instance by its normalized name."""
    normalized_name = provider.name.strip().lower()
    if not normalized_name:
        raise ValueError("Provider name must not be empty.")

    existing = _PROVIDERS.get(normalized_name)
    if existing is not None and existing is not provider:
        raise ValueError(f"Provider {normalized_name!r} is already registered.")

    _PROVIDERS[normalized_name] = provider
    return provider


def get_provider(name: str) -> BaseProvider:
    """Return a provider instance by name."""
    _load_builtin_providers()

    normalized_name = name.strip().lower()
    try:
        return _PROVIDERS[normalized_name]
    except KeyError as exc:
        available = ", ".join(sorted(_PROVIDERS)) or "<none>"
        raise KeyError(
            f"Unknown provider {normalized_name!r}. Available providers: {available}"
        ) from exc


def all_providers() -> dict[str, BaseProvider]:
    """Return a copy of the current provider registry."""
    _load_builtin_providers()
    return dict(sorted(_PROVIDERS.items()))


def provider_names() -> tuple[str, ...]:
    """Return the registered provider names in sorted order."""
    return tuple(all_providers())
