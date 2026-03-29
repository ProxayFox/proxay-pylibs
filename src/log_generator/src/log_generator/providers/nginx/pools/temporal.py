"""Temporal pool for time-formatted variables."""

from datetime import datetime, timezone
from typing import Any
from .base import BasePool, PoolMeta


class TemporalPool(BasePool):
    """Pool for time variables — generates from shared context timestamp."""

    def __init__(self, meta: PoolMeta, fmt: str, use_epoch: bool = False):
        super().__init__(meta)
        self.fmt = fmt  # strftime format or "epoch" / "epoch_ms"
        self.use_epoch = use_epoch

    def generate(self, context: dict[str, Any] | None = None) -> str:
        # Use shared timestamp from context, or now
        ts: datetime = (context or {}).get("_timestamp", datetime.now(timezone.utc))

        if self.use_epoch:
            epoch = ts.timestamp()
            if self.fmt == "epoch_ms":
                return f"{epoch:.3f}"
            return str(int(epoch))

        return ts.strftime(self.fmt)

    def get_config(self) -> dict[str, Any]:
        return {"type": "temporal", "fmt": self.fmt, "use_epoch": self.use_epoch}
