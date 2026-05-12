"""Rule-oriented tests for shipped nginx formats."""

from __future__ import annotations

import pytest

from ._nginx_test_helpers import (
    assert_no_unresolved_placeholders,
    assert_registered_variables,
    assert_stable_shape,
    render_with_fixed_timestamp,
)
from log_generator.providers.nginx.examples.main import (
    EXPLORATORY_FORMATS,
    PRINT,
    SHIPPED_FORMATS,
)


@pytest.mark.unit
def test_shipped_format_names_are_unique() -> None:
    names = [name for name, _ in SHIPPED_FORMATS]

    assert len(names) == len(set(names))


@pytest.mark.unit
def test_print_keeps_shipped_formats_first() -> None:
    assert PRINT[: len(SHIPPED_FORMATS)] == list(SHIPPED_FORMATS)


@pytest.mark.unit
def test_exploratory_formats_are_not_marked_as_shipped() -> None:
    shipped_names = {name for name, _ in SHIPPED_FORMATS}

    assert all(name not in shipped_names for name, _ in EXPLORATORY_FORMATS)


@pytest.mark.unit
@pytest.mark.parametrize(("format_name", "log_format"), SHIPPED_FORMATS)
def test_shipped_formats_follow_registration_and_rendering_rules(
    format_name: str,
    log_format: str,
) -> None:
    assert_registered_variables(log_format)

    rendered = render_with_fixed_timestamp(log_format)

    assert_no_unresolved_placeholders(rendered)
    assert_stable_shape(log_format, rendered)


@pytest.mark.unit
@pytest.mark.parametrize(("format_name", "log_format"), EXPLORATORY_FORMATS)
def test_exploratory_formats_still_render_without_placeholders(
    format_name: str,
    log_format: str,
) -> None:
    rendered = render_with_fixed_timestamp(log_format)

    assert_no_unresolved_placeholders(rendered)
