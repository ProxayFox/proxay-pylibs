"""Counter pool for monotonically increasing variables."""

import threading
from typing import Any
from .base import BasePool, PoolMeta


class CounterPool(BasePool):
    """Thread-safe monotonic counter for $connection etc."""

    def __init__(self, meta: PoolMeta, start: int = 1, step: int = 1):
        super().__init__(meta)
        self._value = start
        self._step = step
        self._lock = threading.Lock()

    def generate(self, context: dict[str, Any] | None = None) -> str:
        with self._lock:
            val = self._value
            self._value += self._step
            return str(val)

    def get_config(self) -> dict[str, Any]:
        return {"type": "counter", "current": self._value, "step": self._step}
