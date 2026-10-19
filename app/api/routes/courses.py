from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models import Course, Document
from app.schemas.course import CourseCreate, CourseRead
from app.schemas.document import DocumentRead

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreate, db: SessionDep):
    course = Course(name=payload.name, term=payload.term)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("", response_model=list[CourseRead])
def list_courses(db: SessionDep):
    return list(db.scalars(select(Course).order_by(Course.id)))


@router.get("/{course_id}/documents", response_model=list[DocumentRead])
def list_documents(course_id: int, db: SessionDep):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return list(
        db.scalars(
            select(Document)
            .where(Document.course_id == course_id)
            .order_by(Document.id.desc())
        )
    )
