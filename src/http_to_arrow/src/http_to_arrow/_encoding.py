"""Dictionary encoding helpers for ``ArrowRecordContainer``.

These helpers decide when to dictionary-encode an Arrow array based on the
caller's threshold, and produce an encoded array whose type stays stable
across batches so ``pa.Table.from_batches`` accepts the batches.
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc
from typing import cast


def is_dictionary_eligible_type(arrow_type: pa.DataType) -> bool:
    """Return True when *arrow_type* is a string variant we attempt to encode."""
    return pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type)


def maybe_dictionary_encode_array(
    array: pa.Array,
    logical_type: pa.DataType,
    existing_effective_type: pa.DataType,
    cardinality_threshold: float,
) -> pa.Array:
    """Optionally dictionary-encode *array* for low-cardinality string columns.

    Behaviour rules:

    - When the column has already been encoded in a prior batch
      (``existing_effective_type`` is a dictionary type), the new array is
      always encoded so subsequent batches share the same physical type.
    - When the logical column type is not a string/large-string, the array
      is returned unchanged.
    - When the array is empty, no encoding decision can be made; return as-is.
    - Otherwise the array is encoded and kept only if
      ``len(dictionary) / len(array) <= cardinality_threshold``.
    """
    if pa.types.is_dictionary(existing_effective_type):
        return pc.dictionary_encode(array)

    if not is_dictionary_eligible_type(logical_type):
        return array

    if len(array) == 0:
        return array

    encoded = cast("pa.DictionaryArray", pc.dictionary_encode(array))
    if len(encoded.dictionary) / len(array) <= cardinality_threshold:
        return encoded

    return array


__all__ = [
    "is_dictionary_eligible_type",
    "maybe_dictionary_encode_array",
]
