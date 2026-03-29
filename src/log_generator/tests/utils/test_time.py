"""Coverage for shared time helpers."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from log_generator.utils import jittered_now
from log_generator.utils import time as time_utils


@pytest.mark.unit
def test_jittered_now_returns_timezone_aware_datetime() -> None:
    value = jittered_now(max_offset_seconds=0)

    assert value.tzinfo is timezone.utc


@pytest.mark.unit
def test_historical_jittered_now_delegates_to_jittered_now(monkeypatch) -> None:
    expected = datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc)
    captured: dict[str, int] = {}

    def fake_jittered_now(max_offset_seconds: int) -> datetime:
        captured["max_offset_seconds"] = max_offset_seconds
        return expected

    monkeypatch.setattr(time_utils, "jittered_now", fake_jittered_now)

    assert time_utils.historical_jittered_now(months_back=2) == expected
    assert captured["max_offset_seconds"] == 2 * 730 * 3600
