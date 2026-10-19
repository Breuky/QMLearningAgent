from sqlalchemy.orm import Session

from app.retrieval.retriever import RetrievedChunk, search_chunks


def search_materials(
    db: Session,
    course_id: int,
    query: str,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    return search_chunks(db, course_id, query, top_k=top_k)
