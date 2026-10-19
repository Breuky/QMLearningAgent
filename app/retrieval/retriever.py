import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.retrieval.reranker import rerank


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document: str
    page: int
    title: str | None
    content_type: str
    text: str
    score: float


def query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[一-鿿]+|[A-Za-z0-9_]+", query.lower()):
        if re.fullmatch(r"[一-鿿]+", token):
            for size in (4, 3, 2):
                if len(token) >= size:
                    for start in range(len(token) - size + 1):
                        terms.append(token[start : start + size])
        else:
            terms.append(token)
    return list(dict.fromkeys(terms))[:20]


def search_chunks(
    db: Session,
    course_id: int,
    query: str,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    terms = query_terms(query)
    if not terms:
        return []

    statement = (
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Chunk.course_id == course_id,
            Document.status == "ready",
            or_(*[Chunk.text.ilike(f"%{term}%") for term in terms]),
        )
        .limit(200)
    )
    rows = db.execute(statement).all()
    if not rows:
        return []

    results: list[RetrievedChunk] = []
    for chunk, filename in rows:
        haystack = chunk.text.lower()
        score = float(sum(1 for term in terms if term in haystack))
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document=filename,
                page=chunk.page,
                title=chunk.slide_title,
                content_type=chunk.content_type,
                text=chunk.text,
                score=score,
            )
        )

    results.sort(key=lambda item: (-item.score, item.document_id, item.page))
    return rerank(query, results, top_k)
