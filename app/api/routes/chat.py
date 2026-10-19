import json
import time

from fastapi import APIRouter, HTTPException

from app.agent.graph import run_agent
from app.api.deps import SessionDep
from app.models import ChatSession, Course, Message
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: SessionDep):
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    session = (
        db.get(ChatSession, payload.session_id)
        if payload.session_id is not None
        else None
    )
    if payload.session_id is not None and session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session is not None and session.course_id != payload.course_id:
        raise HTTPException(status_code=400, detail="Session belongs to another course")

    if session is None:
        session = ChatSession(course_id=payload.course_id)
        db.add(session)
        db.flush()

    db.add(
        Message(
            session_id=session.id,
            role="user",
            content=payload.message,
        )
    )
    db.commit()

    started = time.perf_counter()
    result = run_agent(db, payload.course_id, payload.message)
    latency_ms = int((time.perf_counter() - started) * 1000)

    citations_json = json.dumps(
        [citation.model_dump() for citation in result.citations],
        ensure_ascii=False,
    )
    db.add(
        Message(
            session_id=session.id,
            role="assistant",
            content=result.answer,
            citations_json=citations_json,
            latency_ms=latency_ms,
            cost=0.0,
        )
    )
    db.commit()

    return ChatResponse(
        session_id=session.id,
        answer=result.answer,
        citations=result.citations,
        intent=result.intent,
        latency_ms=latency_ms,
    )
