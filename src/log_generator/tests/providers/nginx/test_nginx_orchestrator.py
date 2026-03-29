"""Orchestrator-focused tests for nginx log generation."""

from __future__ import annotations

import pytest

from ._nginx_test_helpers import FIXED_TIMESTAMP
from log_generator.providers.nginx.pools import generate_log_entry


@pytest.mark.unit
def test_generate_log_entry_can_return_requested_variables_only() -> None:
    requested_variables = [
        "$request_method",
        "$uri",
        "$args",
        "$request_uri",
        "$server_protocol",
        "$request",
        "$is_args",
    ]

    entry = generate_log_entry(
        variables=requested_variables,
        timestamp=FIXED_TIMESTAMP,
    )

    assert set(entry) == set(requested_variables)


@pytest.mark.unit
def test_request_composites_match_generated_dependencies() -> None:
    entry = generate_log_entry(
        variables=[
            "$request_method",
            "$uri",
            "$args",
            "$request_uri",
            "$server_protocol",
            "$request",
            "$is_args",
        ],
        timestamp=FIXED_TIMESTAMP,
    )

    expected_request_uri = (
        f"{entry['$uri']}?{entry['$args']}" if entry["$args"] else entry["$uri"]
    )
    expected_request = f"{entry['$request_method']} {entry['$request_uri']} {entry['$server_protocol']}"

    assert entry["$request_uri"] == expected_request_uri
    assert entry["$request"] == expected_request
    assert entry["$is_args"] == ("?" if entry["$args"] else "")


@pytest.mark.unit
def test_generate_log_entry_returns_only_registered_requested_variables() -> None:
    entry = generate_log_entry(
        variables=["$remote_addr", "$status", "$definitely_not_registered"],
        timestamp=FIXED_TIMESTAMP,
    )

    assert set(entry) == {"$remote_addr", "$status"}
