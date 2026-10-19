import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.ingestion.pipeline import process_document
from app.models import Course, Document, Job
from app.schemas.document import DocumentRead, UploadResponse

router = APIRouter(tags=["documents"])
settings = get_settings()
ALLOWED_SUFFIXES = {".pptx", ".pdf", ".txt", ".md"}


@router.post(
    "/courses/{course_id}/documents",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    course_id: int,
    background_tasks: BackgroundTasks,
    db: SessionDep,
    file: UploadFile = File(...),
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix or 'unknown'}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_mb} MB",
        )

    checksum = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(Document).where(
            Document.course_id == course_id,
            Document.checksum == checksum,
        )
    )
    if existing is not None and existing.status != "failed":
        job = db.scalar(
            select(Job)
            .where(Job.document_id == existing.id)
            .order_by(Job.id.desc())
        )
        return UploadResponse(
            document=DocumentRead.model_validate(existing),
            job_id=job.id if job is not None else 0,
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    file_path = settings.upload_dir / stored_name
    file_path.write_bytes(content)

    document = Document(
        course_id=course_id,
        filename=filename,
        stored_name=stored_name,
        file_type=suffix.lstrip("."),
        file_path=str(file_path),
        checksum=checksum,
        status="pending",
    )
    db.add(document)
    db.flush()

    job = Job(document_id=document.id, status="pending", stage="upload")
    db.add(job)
    db.commit()
    db.refresh(document)
    db.refresh(job)

    background_tasks.add_task(process_document, document.id, job.id)
    return UploadResponse(
        document=DocumentRead.model_validate(document),
        job_id=job.id,
    )


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, db: SessionDep):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
