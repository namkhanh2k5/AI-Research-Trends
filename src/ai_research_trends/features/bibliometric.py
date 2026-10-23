"""Pure work-level features derived from normalized category memberships."""

from __future__ import annotations

from typing import Any


def add_category_features(work: dict[str, Any], memberships: list[dict[str, Any]]) -> None:
    native = {row["category"] for row in memberships if row["analytical_layer"] == "openalex_native"}
    custom = {row["category"] for row in memberships if row["analytical_layer"] == "custom_emerging"}
    work.update(
        {
            "native_category_count": len(native),
            "custom_category_count": len(custom),
            "has_native_category": bool(native),
            "has_custom_category": bool(custom),
            "llm_text_match": "large_language_models" in custom,
            "multimodal_text_match": "multimodal_ai" in custom,
            "rag_text_match": "retrieval_augmented_generation" in custom,
        }
    )
