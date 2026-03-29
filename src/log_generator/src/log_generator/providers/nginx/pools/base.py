"""Base pool types for nginx log variable generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class PoolType(Enum):
    """Classification of how a variable's value is generated."""

    WEIGHTED = auto()  # Finite set with probabilities
    NUMERIC = auto()  # Statistical distribution
    TEMPORAL = auto()  # Time-based formatting
    COMPOSITE = auto()  # Derived from other variables
    NETWORK = auto()  # IPs, ports, CIDRs
    COUNTER = auto()  # Monotonically increasing
    CONDITIONAL = auto()  # Depends on another variable's value
    SAMPLE = auto()  # Large string sample pool


@dataclass
class PoolMeta:
    """Metadata for a pool — the 'name and wait' from docstring."""

    nginx_variable: str  # e.g., "$remote_addr"
    description: str
    module: str  # e.g., "ngx_http_core_module"
    contexts: list[str]  # e.g., ["http", "server", "location"]
    pool_type: PoolType
    wait: float = 0.0  # Delay/weight for generation scheduling
    conditional_on: Optional[str] = None  # e.g., "$scheme" for SSL vars


class BasePool(ABC):
    """Abstract base for all variable generation pools."""

    def __init__(self, meta: PoolMeta):
        self.meta = meta

    @abstractmethod
    def generate(self, context: dict[str, Any] | None = None) -> str:
        """Generate a single value, optionally using shared context."""
        ...

    @abstractmethod
    def get_config(self) -> dict[str, Any]:
        """Return serializable config for inspection/debugging."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} var={self.meta.nginx_variable}>"


# ─── Global Registry ───────────────────────────────────────────────
_POOL_REGISTRY: dict[str, BasePool] = {}


def register_pool(pool: BasePool) -> BasePool:
    """Register a pool by its nginx variable name."""
    _POOL_REGISTRY[pool.meta.nginx_variable] = pool
    return pool


def get_pool(variable: str) -> BasePool:
    """Get a registered pool by its nginx variable name."""
    return _POOL_REGISTRY[variable]


def all_pools() -> dict[str, BasePool]:
    """Return a dictionary of all registered pools."""
    return dict(_POOL_REGISTRY)
