# Schema Inference

Pass `schema=None` when the container should infer fields from the records it
receives.

!!! warning
    Inferred schemas are convenient for flexible payloads, but explicit schemas
    are better when downstream systems require a stable contract.

## First record

The first non-empty record establishes the initial schema.

```python
from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=None)
container.append({"id": 1, "name": "alpha"})

assert container.schema is not None
assert container.schema.names == ["id", "name"]
```

An empty first record cannot produce a schema and raises `ValueError`.

## Field growth

When a later record includes a new field, inferred mode widens the schema and
backfills earlier rows with nulls.

```python
from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=None, batch_size=1)
container.append({"id": 1})
container.append({"id": 2, "name": "beta"})

assert container.to_table().to_pydict() == {
    "id": [1, 2],
    "name": [None, "beta"],
}
```

## Type widening

Compatible numeric types widen to a common Arrow type. Conflicting shapes that
cannot be merged fall back to `string`.

```python
from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=None)
container.append({"value": 1})
container.append({"value": {"nested": True}})

assert container.to_table().to_pydict() == {
    "value": ["1", "{'nested': True}"],
}
```

## Case-insensitive names

With the default `case_insensitive_keys=True`, inferred mode preserves the
first-seen spelling of a field name and maps later case variants to it.

```python
from http_to_arrow import ArrowRecordContainer

container = ArrowRecordContainer(schema=None)
container.append({"ID": 1})
container.append({"id": 2})

assert container.schema is not None
assert container.schema.names == ["ID"]
assert container.to_table().column("ID").to_pylist() == [1, 2]
```

## Empty materialization

Calling `to_table()` before an inferred container has a schema or records raises
`ValueError`. Supply an explicit schema if you need an empty table before any
records arrive.

!!! tip
    If an empty result is valid in your workflow, initialize the container with
    an explicit `pyarrow.Schema` so `to_table()` can return an empty table with
    known columns.
