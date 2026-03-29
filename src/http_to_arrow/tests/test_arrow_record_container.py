"""Tests for the http_to_arrow workspace package."""

from __future__ import annotations

from typing import get_args

import pyarrow as pa
import pytest

from http_to_arrow import ArrowRecordContainer
from http_to_arrow.collections import CoercionPolicy


def test_append_materializes_rows_into_an_arrow_table() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([
            pa.field("id", pa.int64()),
            pa.field("name", pa.string()),
        ]),
        batch_size=2,
    )

    container.append({"id": 1, "name": "alpha"})
    container.append({"id": 2, "name": "beta"})

    table = container.to_table()

    assert table.num_rows == 2
    assert table.column("id").to_pylist() == [1, 2]
    assert table.column("name").to_pylist() == ["alpha", "beta"]


@pytest.mark.unit
def test_unknown_fields_raise_when_policy_is_error() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        unknown_field_policy="error",
    )

    with pytest.raises(ValueError, match="Unexpected fields"):
        container.append({"id": 1, "extra": "boom"})


@pytest.mark.unit
def test_to_polars_frame_returns_dataframe_with_expected_shape() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )
    container.append({"id": 10})
    container.append({"id": 11})

    frame = container.to_polars_frame()

    assert frame.shape == (2, 1)
    assert frame["id"].to_list() == [10, 11]


@pytest.mark.unit
def test_public_collections_module_re_exports_policy_types() -> None:
    assert get_args(CoercionPolicy) == ("coerce", "strict")
