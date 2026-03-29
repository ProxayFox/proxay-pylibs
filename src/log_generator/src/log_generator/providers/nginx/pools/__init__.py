from importlib import import_module
from typing import Any, TYPE_CHECKING

from . import definitions as _definitions

# Lazy imports for all pool types and utilities to avoid circular dependencies and reduce initial load time
if TYPE_CHECKING:
    from .base import PoolType, PoolMeta, BasePool, register_pool, get_pool, all_pools
    from .composite import CompositePool
    from .conditional import ConditionalPool
    from .counter import CounterPool
    from .network import IPv4Pool, PortPool
    from .numeric import NumericDistribution, NumericPool
    from .orchestrator import generate_log_entry, format_log_line
    from .temporal import TemporalPool
    from .weighted import WeightedPool

# Mapping of public names to their respective modules for lazy loading
_EXPORTS: dict[str, str] = {
    "PoolType": ".base",
    "PoolMeta": ".base",
    "BasePool": ".base",
    "register_pool": ".base",
    "get_pool": ".base",
    "all_pools": ".base",
    "CompositePool": ".composite",
    "ConditionalPool": ".conditional",
    "CounterPool": ".counter",
    "IPv4Pool": ".network",
    "PortPool": ".network",
    "NumericDistribution": ".numeric",
    "NumericPool": ".numeric",
    "generate_log_entry": ".orchestrator",
    "format_log_line": ".orchestrator",
    "TemporalPool": ".temporal",
    "WeightedPool": ".weighted",
}

# __all__ is defined dynamically in __getattr__ to include all keys from _EXPORTS
__all__ = list(_EXPORTS.keys())


# Dynamic attribute access for lazy loading of pool classes and utilities
def __getattr__(name: str) -> Any:
    """Lazy import CosmosDB clients to avoid eager dependency loading."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


# Optional: define __dir__ to include all exported names for better IDE support and introspection
def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
