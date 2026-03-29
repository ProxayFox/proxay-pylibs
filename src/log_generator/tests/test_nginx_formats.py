"""Format-focused regression tests for nginx shipped examples."""

from __future__ import annotations

from datetime import datetime, timezone
import re

import pytest

from log_generator.providers.nginx.examples.main import EXAMPLE_FORMAT, SHIPPED_FORMATS
from log_generator.providers.nginx.pools import (
    all_pools,
    format_log_line,
    generate_log_entry,
)


UNRESOLVED_VARIABLE_PATTERN = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")


@pytest.mark.unit
def test_http_x_forwarded_for_is_generated_from_remote_addr() -> None:
    header_value = all_pools()["$http_x_forwarded_for"].generate(
        {"$remote_addr": "203.0.113.10"}
    )

    assert header_value.startswith("203.0.113.10")


@pytest.mark.unit
def test_ssl_session_id_respects_https_condition() -> None:
    pool = all_pools()["$ssl_session_id"]

    assert pool.generate({"$scheme": "http"}) == "-"

    session_id = pool.generate({"$scheme": "https"})

    assert len(session_id) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", session_id) is not None


@pytest.mark.unit
def test_production_format_renders_without_unresolved_placeholders() -> None:
    entry = generate_log_entry(
        timestamp=datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc)
    )

    rendered = format_log_line(entry, EXAMPLE_FORMAT)

    assert UNRESOLVED_VARIABLE_PATTERN.search(rendered) is None
    assert '"' in rendered
    assert "[29/Mar/2026:07:31:26 +0000]" in rendered


@pytest.mark.unit
@pytest.mark.parametrize(("format_name", "log_format"), SHIPPED_FORMATS)
def test_all_shipped_formats_render_without_unresolved_placeholders(
    format_name: str,
    log_format: str,
) -> None:
    entry = generate_log_entry(
        timestamp=datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc)
    )

    rendered = format_log_line(entry, log_format)

    assert UNRESOLVED_VARIABLE_PATTERN.search(rendered) is None, format_name
