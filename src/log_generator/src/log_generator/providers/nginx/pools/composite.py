"""Composite pool for variables built from other variable values."""

from typing import Any, Callable
from .base import BasePool, PoolMeta


class CompositePool(BasePool):
    """Pool whose value is computed from other variables in context."""

    def __init__(self, meta: PoolMeta, builder: Callable[[dict[str, Any]], str]):
        super().__init__(meta)
        self.builder = builder

    def generate(self, context: dict[str, Any] | None = None) -> str:
        return self.builder(context or {})

    def get_config(self) -> dict[str, Any]:
        return {
            "type": "composite",
            "builder": getattr(self.builder, "__name__", "composite"),
        }
