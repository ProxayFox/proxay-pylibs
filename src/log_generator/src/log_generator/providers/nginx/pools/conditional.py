"""Conditional pool for variables that only exist under certain conditions."""

from typing import Any
from .base import BasePool, PoolMeta


class ConditionalPool(BasePool):
    """Pool that delegates to an inner pool only when a condition is met."""

    def __init__(
        self,
        meta: PoolMeta,
        inner_pool: BasePool,
        condition_var: str,
        condition_values: set[str],
        default: str = "-",
    ):
        super().__init__(meta)
        self.inner = inner_pool
        self.condition_var = condition_var
        self.condition_values = condition_values
        self.default = default

    def generate(self, context: dict[str, Any] | None = None) -> str:
        ctx = context or {}
        if ctx.get(self.condition_var) in self.condition_values:
            return self.inner.generate(context)
        return self.default

    def get_config(self) -> dict[str, Any]:
        return {
            "type": "conditional",
            "condition_var": self.condition_var,
            "condition_values": list(self.condition_values),
            "inner": self.inner.get_config(),
            "default": self.default,
        }
