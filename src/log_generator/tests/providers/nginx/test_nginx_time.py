"""Time-focused tests for nginx log generation."""

from __future__ import annotations

import pytest

from ._nginx_test_helpers import FIXED_TIMESTAMP
from log_generator.providers.nginx.pools import generate_log_entry


@pytest.mark.unit
def test_fixed_timestamp_renders_expected_time_variables() -> None:
    entry = generate_log_entry(
        variables=["$time_local", "$time_iso8601", "$msec"],
        timestamp=FIXED_TIMESTAMP,
    )

    expected_msec = f"{FIXED_TIMESTAMP.timestamp():.3f}"

    assert entry == {
        "$time_local": "29/Mar/2026:07:31:26 +0000",
        "$time_iso8601": "2026-03-29T07:31:26+0000",
        "$msec": expected_msec,
    }


@pytest.mark.unit
def test_time_variables_are_string_values() -> None:
    entry = generate_log_entry(
        variables=["$time_local", "$time_iso8601", "$msec"],
        timestamp=FIXED_TIMESTAMP,
    )

    assert all(isinstance(value, str) for value in entry.values())
