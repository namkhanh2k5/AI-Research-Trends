"""Pure text transformations shared by profiling and later preprocessing."""

from __future__ import annotations

from typing import Any


def reconstruct_abstract(inverted_index: Any) -> str | None:
    """Reconstruct readable text from an OpenAlex abstract inverted index.

    Duplicate positions or malformed tokens are rejected rather than silently
    producing a misleading abstract.
    """
    if inverted_index is None or inverted_index == {}:
        return None
    if not isinstance(inverted_index, dict):
        raise ValueError("Abstract inverted index must be an object or null")
    positioned_tokens: dict[int, str] = {}
    for token, positions in inverted_index.items():
        if not isinstance(token, str) or not token:
            raise ValueError("Abstract tokens must be non-empty strings")
        if not isinstance(positions, list):
            raise ValueError("Abstract token positions must be lists")
        for position in positions:
            if not isinstance(position, int) or isinstance(position, bool) or position < 0:
                raise ValueError("Abstract positions must be non-negative integers")
            if position in positioned_tokens:
                raise ValueError(f"Duplicate abstract position: {position}")
            positioned_tokens[position] = token
    return " ".join(positioned_tokens[index] for index in sorted(positioned_tokens))
