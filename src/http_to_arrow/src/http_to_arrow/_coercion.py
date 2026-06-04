"""Value coercion helpers used by ``ArrowRecordContainer``.

These functions are intentionally pure: they take a value and an Arrow type
and return a Python value shaped for Arrow construction. They do not touch
container state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, cast

import pyarrow as pa


def coerce_timestamp_value(value: Any) -> datetime | Any | None:
    """Parse ISO-8601 strings while preserving the represented instant."""
    if not isinstance(value, str):
        return value

    iso_value = value.strip()
    if iso_value.endswith("Z"):
        iso_value = f"{iso_value[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(iso_value)
    except TypeError, ValueError:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def coerce_value(value: Any, arrow_type: pa.DataType) -> Any:
    """Recursively coerce a value to match the given explicit-schema PyArrow type."""
    if value is None:
        return None

    if pa.types.is_timestamp(arrow_type):
        return coerce_timestamp_value(value)

    if pa.types.is_struct(arrow_type):
        if not isinstance(value, Mapping):
            return value

        return {
            arrow_field.name: coerce_value(
                value.get(arrow_field.name), arrow_field.type
            )
            for arrow_field in arrow_type
        }

    if pa.types.is_list(arrow_type) or pa.types.is_large_list(arrow_type):
        item_type = cast(pa.DataType, arrow_type.value_type)
        if (
            isinstance(value, Mapping)
            and pa.types.is_struct(item_type)
            and item_type.num_fields == 2
        ):
            first_field = item_type.field(0).name
            second_field = item_type.field(1).name
            value = [
                {first_field: key, second_field: item_value}
                for key, item_value in value.items()
            ]

        if not isinstance(value, list):
            return value

        return [coerce_value(item, item_type) for item in value]

    return value


def coerce_inferred_value(value: Any, arrow_type: pa.DataType) -> Any:
    """Coerce inferred-mode values into the current Arrow field shape."""
    if value is None:
        return None

    if pa.types.is_string(arrow_type):
        return value if isinstance(value, str) else str(value)

    if pa.types.is_struct(arrow_type):
        if not isinstance(value, Mapping):
            return value

        return {
            arrow_field.name: coerce_inferred_value(
                value.get(arrow_field.name), arrow_field.type
            )
            for arrow_field in arrow_type
        }

    if pa.types.is_list(arrow_type) or pa.types.is_large_list(arrow_type):
        if not isinstance(value, list):
            return value

        item_type = cast(pa.DataType, arrow_type.value_type)
        return [coerce_inferred_value(item, item_type) for item in value]

    return coerce_value(value, arrow_type)


__all__ = [
    "coerce_timestamp_value",
    "coerce_value",
    "coerce_inferred_value",
]
