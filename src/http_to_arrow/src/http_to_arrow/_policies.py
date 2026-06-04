"""Policy literal aliases shared by ``ArrowRecordContainer``."""

from __future__ import annotations

from typing import Literal


UnknownFieldPolicy = Literal["drop", "error", "capture"]
MissingFieldPolicy = Literal["null", "error"]
CoercionPolicy = Literal["coerce", "strict"]


__all__ = [
    "UnknownFieldPolicy",
    "MissingFieldPolicy",
    "CoercionPolicy",
]
