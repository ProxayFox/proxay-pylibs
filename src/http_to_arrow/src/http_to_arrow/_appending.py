"""Append-path helpers for ``ArrowRecordContainer``.

These helpers own explicit-schema and inferred-schema record ingestion while
leaving the public class and subclass hook surface in ``http_to_arrow.main``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Mapping

from http_to_arrow._coercion import coerce_inferred_value, coerce_value

if TYPE_CHECKING:
    from http_to_arrow.main import ArrowRecordContainer


def resolve_field_key(
    container: ArrowRecordContainer,
    field_name: str,
    record: Mapping[str, Any],
    lower_key_map: dict[str, str],
) -> str | None:
    """Resolve an incoming key for a schema field."""
    if field_name in record:
        return field_name

    if not container.case_insensitive_keys:
        return None

    return lower_key_map.get(field_name.lower())


def handle_unknown_fields(
    container: ArrowRecordContainer, extras: dict[str, Any]
) -> None:
    """Apply the configured explicit-schema policy for extra keys."""
    if not extras:
        return

    if container.unknown_field_policy == "error":
        extra_keys = ", ".join(sorted(extras))
        raise ValueError(f"Unexpected fields not present in schema: {extra_keys}")

    if container.unknown_field_policy == "capture":
        container.captured_extras.append(extras)


def append_exact_key_record(
    container: ArrowRecordContainer, record: Mapping[str, Any]
) -> bool:
    """Fast path for records that contain no keys outside the schema."""
    if any(key not in container._schema_field_names for key in record):
        return False

    for arrow_field in container._schema_fields:
        if arrow_field.name in record:
            raw_value = record.get(arrow_field.name)
        else:
            if container.missing_field_policy == "error":
                raise ValueError(f"Missing required schema field '{arrow_field.name}'.")
            raw_value = None

        value = (
            coerce_value(raw_value, arrow_field.type)
            if container.coercion_policy == "coerce"
            else raw_value
        )
        container._accumulator[arrow_field.name].append(value)

    container._current_count += 1
    if container._current_count >= container.batch_size:
        container.flush()

    return True


def append_inferred_record(
    container: ArrowRecordContainer, record: Mapping[str, Any]
) -> None:
    """Append a record while inferring and widening schema over time."""
    resolved_record = {
        container._canonicalize_inferred_key(key): value
        for key, value in record.items()
    }

    if not resolved_record and container.schema is None:
        raise ValueError("Cannot infer schema from an empty record.")

    container._ensure_inferred_schema_for_record(resolved_record)

    for arrow_field in container._schema_fields:
        if arrow_field.name in resolved_record:
            raw_value = resolved_record.get(arrow_field.name)
        else:
            if container.missing_field_policy == "error":
                raise ValueError(f"Missing required schema field '{arrow_field.name}'.")
            raw_value = None

        value = (
            coerce_inferred_value(raw_value, arrow_field.type)
            if container.coercion_policy == "coerce"
            else raw_value
        )
        container._accumulator[arrow_field.name].append(value)

    container._current_count += 1
    if container._current_count >= container.batch_size:
        container.flush()


def append(container: ArrowRecordContainer, record: Mapping[str, Any]) -> None:
    """Append a single record to the container."""
    normalized_record = container._prepare_record(record)
    if not container._schema_explicit:
        container._append_inferred_record(normalized_record)
        return

    if container._append_exact_key_record(normalized_record):
        return

    lower_key_map = {key.lower(): key for key in normalized_record}
    matched_keys: set[str] = set()

    for arrow_field in container._schema_fields:
        resolved_key = container._resolve_field_key(
            arrow_field.name,
            normalized_record,
            lower_key_map,
        )

        if resolved_key is None:
            if container.missing_field_policy == "error":
                raise ValueError(f"Missing required schema field '{arrow_field.name}'.")

            raw_value = None
        else:
            matched_keys.add(resolved_key)
            raw_value = normalized_record.get(resolved_key)

        value = (
            coerce_value(raw_value, arrow_field.type)
            if container.coercion_policy == "coerce"
            else raw_value
        )
        container._accumulator[arrow_field.name].append(value)

    extras = {
        key: value
        for key, value in normalized_record.items()
        if key not in matched_keys
    }
    container._handle_unknown_fields(extras)

    container._current_count += 1
    if container._current_count >= container.batch_size:
        container.flush()


def extend(
    container: ArrowRecordContainer, records: Iterable[Mapping[str, Any]]
) -> None:
    """Append multiple records to the container."""
    for record in records:
        container.append(record)


__all__ = [
    "append",
    "append_exact_key_record",
    "append_inferred_record",
    "extend",
    "handle_unknown_fields",
    "resolve_field_key",
]
