from typing import Any


def recall_at_k(
    expected_sources: list[dict[str, Any]],
    retrieved: list[Any],
    k: int,
) -> float:
    if not expected_sources:
        return 0.0

    top_items = retrieved[:k]
    hits = 0
    for source in expected_sources:
        document = source.get("document")
        page = source.get("page")
        if any(
            getattr(item, "document", None) == document
            and getattr(item, "page", None) == page
            for item in top_items
        ):
            hits += 1
    return hits / len(expected_sources)
