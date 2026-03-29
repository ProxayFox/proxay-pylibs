"""Tests for the http_to_arrow workspace package."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, get_args

import pyarrow as pa
import pytest

from http_to_arrow import (
    ArrowRecordContainer,
    CoercionPolicy,
    MissingFieldPolicy,
    UnknownFieldPolicy,
)


@pytest.mark.unit
def test_constructor_rejects_cached_table_with_mismatched_schema() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])
    other_schema = pa.schema([pa.field("name", pa.string())])

    with pytest.raises(ValueError, match="Cached table schema"):
        ArrowRecordContainer(
            schema=schema,
            table=pa.Table.from_pydict(
                {"name": ["alpha"]}, schema=other_schema),
        )


@pytest.mark.unit
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
def test_unknown_fields_are_dropped_by_default() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )

    container.append({"id": 1, "extra": "ignored"})

    assert container.captured_extras == []
    assert container.to_table().column("id").to_pylist() == [1]


@pytest.mark.unit
def test_unknown_fields_can_be_captured() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        unknown_field_policy="capture",
    )

    container.append({"id": 1, "extra": "kept"})

    assert container.captured_extras == [{"extra": "kept"}]


@pytest.mark.unit
def test_missing_fields_raise_when_policy_is_error() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([
            pa.field("id", pa.int64()),
            pa.field("name", pa.string()),
        ]),
        missing_field_policy="error",
    )

    with pytest.raises(ValueError, match="Missing required schema field 'name'"):
        container.append({"id": 1})


@pytest.mark.unit
def test_append_matches_case_insensitive_keys_on_slow_path() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([
            pa.field("id", pa.int64()),
            pa.field("name", pa.string()),
        ]),
    )

    container.append({"ID": 1, "Name": "alpha"})

    table = container.to_table()

    assert table.to_pydict() == {"id": [1], "name": ["alpha"]}


@pytest.mark.unit
def test_append_respects_case_sensitive_mode() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        case_insensitive_keys=False,
        missing_field_policy="error",
    )

    with pytest.raises(ValueError, match="Missing required schema field 'id'"):
        container.append({"ID": 1})


class PassthroughMapping(dict[str, object]):
    """Simple mapping subclass to exercise normalize hooks."""


class UpperKeyContainer(ArrowRecordContainer):
    def normalize_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {key.lower(): value for key, value in record.items()}


@pytest.mark.unit
def test_default_normalize_record_copies_non_dict_mapping() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )

    record = PassthroughMapping({"id": 9})
    normalized = container.normalize_record(record)

    assert normalized == {"id": 9}
    assert normalized is not record


@pytest.mark.unit
def test_normalize_record_hook_is_used_for_non_default_container() -> None:
    container = UpperKeyContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )

    container.append(PassthroughMapping({"ID": 7}))

    assert container.to_table().column("id").to_pylist() == [7]


@pytest.mark.unit
def test_helper_coercion_methods_cover_non_string_naive_and_passthrough_paths() -> None:
    naive_timestamp = ArrowRecordContainer._coerce_timestamp_value(
        "2024-01-02T03:04:05"
    )
    dt_value = datetime(2024, 1, 2, 3, 4, 5)

    assert naive_timestamp == dt_value
    assert ArrowRecordContainer._coerce_timestamp_value(dt_value) is dt_value
    assert ArrowRecordContainer._coerce_value(None, pa.int64()) is None
    assert (
        ArrowRecordContainer._coerce_value(
            "scalar", pa.struct([pa.field("id", pa.int64())]))
        == "scalar"
    )
    assert (
        ArrowRecordContainer._coerce_value("scalar", pa.list_(pa.int64()))
        == "scalar"
    )


@pytest.mark.unit
def test_extend_and_incremental_flush_manage_pending_batches_and_table() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        batch_size=2,
    )

    container.extend([{"id": 1}, {"id": 2}, {"id": 3}])

    assert container.batch_total_rows == 3
    assert container.total_rows == 3
    assert container.incremental_flush(threshold=10) is False
    assert container.batch_total_rows == 3
    assert container.incremental_flush(threshold=2) is True
    assert container.batch_total_rows == 0
    assert container.total_rows == 3
    assert container.table is not None
    assert container.table.column("id").to_pylist() == [1, 2, 3]


@pytest.mark.unit
def test_exact_key_append_allows_missing_fields_as_nulls_by_default() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([
            pa.field("id", pa.int64()),
            pa.field("name", pa.string()),
        ]),
    )

    container.append({"id": 1})

    assert container.to_table().to_pydict() == {"id": [1], "name": [None]}


@pytest.mark.unit
def test_slow_path_append_allows_missing_fields_as_nulls_by_default() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([
            pa.field("id", pa.int64()),
            pa.field("name", pa.string()),
        ]),
    )

    container.append({"id": 1, "extra": "ignored"})

    assert container.to_table().to_pydict() == {"id": [1], "name": [None]}


@pytest.mark.unit
def test_slow_path_append_flushes_when_batch_size_is_reached() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        batch_size=1,
    )

    container.append({"ID": 1})

    assert container.batch_total_rows == 1
    assert container.to_table().column("id").to_pylist() == [1]


@pytest.mark.unit
def test_to_table_concatenates_with_existing_cached_table() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])
    cached = pa.Table.from_pydict({"id": [10]}, schema=schema)
    container = ArrowRecordContainer(schema=schema, table=cached)

    container.append({"id": 11})

    assert container.to_table().column("id").to_pylist() == [10, 11]


@pytest.mark.unit
def test_to_table_returns_empty_table_for_empty_container() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])
    container = ArrowRecordContainer(schema=schema)

    table = container.to_table()

    assert table.schema.equals(schema)
    assert table.num_rows == 0


@pytest.mark.unit
def test_to_table_returns_cached_table_when_no_batches_are_pending() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])
    cached = pa.Table.from_pydict({"id": [42]}, schema=schema)
    container = ArrowRecordContainer(schema=schema, table=cached)

    table = container.to_table()

    assert table is cached
    assert table.column("id").to_pylist() == [42]


@pytest.mark.unit
def test_reset_and_clear_alias_remove_all_accumulated_state() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
        unknown_field_policy="capture",
        batch_size=2,
    )

    container.append({"id": 1, "extra": "kept"})
    container.append({"id": 2})
    container.incremental_flush()

    assert container.total_rows == 2
    assert container.captured_extras == [{"extra": "kept"}]

    assert container.clear is None

    assert container.table is None
    assert container.batches == []
    assert container.captured_extras == []
    assert container.batch_total_rows == 0
    assert container.total_rows == 0


@pytest.mark.unit
def test_alias_properties_materialize_arrow_and_polars_views() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )
    container.append({"id": 5})

    assert container.to_arrow.column("id").to_pylist() == [5]
    assert container.to_polars["id"].to_list() == [5]


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
def test_to_polars_frame_uses_cached_table_fast_path() -> None:
    schema = pa.schema([pa.field("id", pa.int64())])
    table = pa.Table.from_pydict({"id": [99]}, schema=schema)
    container = ArrowRecordContainer(schema=schema, table=table)

    frame = container.to_polars_frame()

    assert frame["id"].to_list() == [99]


@pytest.mark.unit
def test_timestamp_struct_and_list_values_are_coerced_to_arrow_shapes() -> None:
    schema = pa.schema([
        pa.field("event_at", pa.timestamp("us")),
        pa.field(
            "payload",
            pa.struct([
                pa.field("count", pa.int64()),
                pa.field("nested_at", pa.timestamp("us")),
            ]),
        ),
        pa.field(
            "tags",
            pa.list_(
                pa.struct([
                    pa.field("key", pa.string()),
                    pa.field("value", pa.int64()),
                ])
            ),
        ),
    ])
    container = ArrowRecordContainer(schema=schema)

    container.append(
        {
            "event_at": "2024-01-02T03:04:05Z",
            "payload": {
                "count": 3,
                "nested_at": "2024-01-02T05:04:05+02:00",
            },
            "tags": {"alpha": 1, "beta": 2},
        }
    )

    row = container.to_table().to_pylist()[0]

    expected_timestamp = datetime(2024, 1, 2, 3, 4, 5)
    assert row["event_at"] == expected_timestamp
    assert row["payload"] == {
        "count": 3,
        "nested_at": expected_timestamp,
    }
    assert row["tags"] == [
        {"key": "alpha", "value": 1},
        {"key": "beta", "value": 2},
    ]


@pytest.mark.unit
def test_invalid_timestamp_strings_are_coerced_to_null() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("event_at", pa.timestamp("us"))]),
    )

    container.append({"event_at": "definitely-not-a-timestamp"})

    assert container.to_table().column("event_at").to_pylist() == [None]


@pytest.mark.unit
def test_strict_coercion_policy_preserves_raw_values_until_arrow_validation() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("event_at", pa.timestamp("us"))]),
        coercion_policy="strict",
    )

    container.append({"event_at": "2024-01-02T03:04:05Z"})

    with pytest.raises(ValueError, match="column 'event_at'"):
        container.flush()


@pytest.mark.unit
def test_flush_wraps_arrow_invalid_errors_with_field_context(monkeypatch: pytest.MonkeyPatch) -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )
    container.append({"id": 1})
    original_array = pa.array

    def raising_array(*args: object, **kwargs: object) -> pa.Array:
        raise pa.lib.ArrowInvalid("bad news")

    monkeypatch.setattr(pa, "array", raising_array)

    with pytest.raises(ValueError, match="Invalid data for column 'id': bad news"):
        container.flush()

    monkeypatch.setattr(pa, "array", original_array)
    assert container.to_table().column("id").to_pylist() == [1]


@pytest.mark.unit
def test_flush_wraps_unexpected_errors_with_field_context(monkeypatch: pytest.MonkeyPatch) -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )
    container.append({"id": 1})

    def raising_array(*args: object, **kwargs: object) -> pa.Array:
        raise RuntimeError("oops")

    monkeypatch.setattr(pa, "array", raising_array)

    with pytest.raises(ValueError, match="Error processing column 'id': oops"):
        container.flush()


@pytest.mark.unit
def test_flush_batch_alias_flushes_current_accumulator() -> None:
    container = ArrowRecordContainer(
        schema=pa.schema([pa.field("id", pa.int64())]),
    )
    container.append({"id": 1})

    container._flush_batch()

    assert container.batch_total_rows == 1
    assert container.to_table().column("id").to_pylist() == [1]


@pytest.mark.unit
def test_public_module_re_exports_policy_types() -> None:
    assert get_args(CoercionPolicy) == ("coerce", "strict")
    assert get_args(MissingFieldPolicy) == ("null", "error")
    assert get_args(UnknownFieldPolicy) == ("drop", "error", "capture")
