"""Weighted choice pool for finite enumerated values."""

import random
from typing import Any
from .base import BasePool, PoolMeta


class WeightedPool(BasePool):
    """Pool for variables with a finite set of weighted possible values."""

    def __init__(self, meta: PoolMeta, choices: dict[str | int, float]):
        super().__init__(meta)
        self.choices = choices
        self._values = list(choices.keys())
        self._weights = list(choices.values())

    def generate(self, context: dict[str, Any] | None = None) -> str:
        return str(random.choices(self._values, weights=self._weights, k=1)[0])

    def get_config(self) -> dict[str, Any]:
        return {"type": "weighted", "choices": self.choices}
