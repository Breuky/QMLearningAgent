import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.ingestion.chunker import chunk_pages
from app.ingestion.parser import parse_document
from app.models import Chunk, Document, Job

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def process_document(document_id: int, job_id: int | None = None) -> None:
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if document is None:
            return

        job = db.get(Job, job_id) if job_id else None
        document.status = "processing"
        if job is not None:
            job.status = "processing"
            job.stage = "parse"
            job.started_at = _now()
        db.commit()

        try:
            pages = parse_document(Path(document.file_path))
            if job is not None:
                job.stage = "chunk"
                db.commit()

            chunks = chunk_pages(pages)
            if not chunks:
                raise ValueError("No chunks generated from the document")

            db.execute(delete(Chunk).where(Chunk.document_id == document_id))
            for item in chunks:
                db.add(
                    Chunk(
                        document_id=document_id,
                        course_id=document.course_id,
                        page=item.page,
                        slide_title=item.slide_title,
                        content_type=item.content_type,
                        text=item.text,
                        token_count=item.token_count,
                    )
                )

            document.status = "ready"
            document.error = None
            if job is not None:
                job.status = "ready"
                job.stage = "done"
                job.finished_at = _now()
            db.commit()
            logger.info("Processed document %s into %s chunks", document_id, len(chunks))
        except Exception as exc:
            db.rollback()
            document = db.get(Document, document_id)
            job = db.get(Job, job_id) if job_id else None
            if document is not None:
                document.status = "failed"
                document.error = str(exc)[:1000]
            if job is not None:
                job.status = "failed"
                job.stage = "failed"
                job.error = str(exc)[:1000]
                job.finished_at = _now()
            db.commit()
            logger.exception("Failed to process document %s", document_id)
