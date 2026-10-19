from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.retrieval.retriever import RetrievedChunk


def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    return chunks[:top_k]
