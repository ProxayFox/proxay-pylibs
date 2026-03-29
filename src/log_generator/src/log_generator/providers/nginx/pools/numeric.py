"""Numeric distribution pool for continuous/integer variables."""

import random
from dataclasses import dataclass
from typing import Any, Literal
from .base import BasePool, PoolMeta


@dataclass
class NumericDistribution:
    """Configurable statistical distribution."""

    kind: Literal["log_normal", "normal", "uniform", "exponential"]
    # For log_normal / normal:
    mu: float = 0.0
    sigma: float = 1.0
    # For uniform:
    low: float = 0.0
    high: float = 1.0
    # For exponential:
    lambd: float = 1.0
    # Common constraints:
    minimum: float = 0.0
    maximum: float = float("inf")
    precision: int = 3  # decimal places
    as_int: bool = False  # truncate to integer


class NumericPool(BasePool):
    """Pool for variables that are numeric with statistical distributions."""

    def __init__(self, meta: PoolMeta, distribution: NumericDistribution):
        super().__init__(meta)
        self.dist = distribution

    def generate(self, context: dict[str, Any] | None = None) -> str:
        d = self.dist
        match d.kind:
            case "log_normal":
                val = random.lognormvariate(d.mu, d.sigma)
            case "normal":
                val = random.gauss(d.mu, d.sigma)
            case "uniform":
                val = random.uniform(d.low, d.high)
            case "exponential":
                val = random.expovariate(d.lambd)
            case _:
                raise ValueError(f"Unknown distribution: {d.kind}")

        val = max(d.minimum, min(d.maximum, val))

        if d.as_int:
            return str(int(val))
        return f"{val:.{d.precision}f}"

    def get_config(self) -> dict[str, Any]:
        return {"type": "numeric", "distribution": self.dist.__dict__}
