from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.models import Feedback, Message
from app.schemas.feedback import FeedbackCreate, FeedbackRead

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(payload: FeedbackCreate, db: SessionDep):
    message = db.get(Message, payload.message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")

    feedback = Feedback(
        message_id=payload.message_id,
        rating=payload.rating,
        reason=payload.reason,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
