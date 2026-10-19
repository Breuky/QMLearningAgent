from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    filename: str
    file_type: str
    status: str
    error: str | None
    created_at: datetime


class UploadResponse(BaseModel):
    document: DocumentRead
    job_id: int
