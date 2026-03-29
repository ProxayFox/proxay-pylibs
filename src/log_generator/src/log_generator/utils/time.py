"""Shared time helpers."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone


def jittered_now(max_offset_seconds: int = 1800) -> datetime:
    """Return ``datetime.now(UTC)`` shifted backward by a random jitter.

    Useful for generating log timestamps that look recent but are not
    all identical.
    """
    offset = random.randint(0, max_offset_seconds)
    return datetime.now(tz=timezone.utc) - timedelta(seconds=offset)


def historical_jittered_now(months_back: int = 6) -> datetime:
    """Return a jittered datetime within the past `months_back` months."""
    max_offset_seconds = int(
        # Approximate month length in seconds (~730 hours per month)
        months_back * 730 * 3600
    )
    return jittered_now(max_offset_seconds)
