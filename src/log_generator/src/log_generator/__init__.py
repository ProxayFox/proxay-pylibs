"""Public API for the ``log_generator`` package.

The root package exposes provider namespaces so future providers can be added
without forcing provider-specific helpers into the top-level import surface.
"""

from log_generator import core, providers

nginx = providers.nginx

__all__ = ["core", "nginx", "providers"]
