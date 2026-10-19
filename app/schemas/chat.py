from pydantic import BaseModel, Field


class Citation(BaseModel):
    document: str
    page: int
    text: str
    score: float = 0.0


class ChatRequest(BaseModel):
    course_id: int
    message: str = Field(min_length=1, max_length=2000)
    session_id: int | None = None


class ChatResponse(BaseModel):
    session_id: int
    answer: str
    citations: list[Citation]
    intent: str
    latency_ms: int
