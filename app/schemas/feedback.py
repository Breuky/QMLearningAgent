from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FeedbackCreate(BaseModel):
    message_id: int
    rating: Literal["up", "down"]
    reason: str | None = None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    rating: str
    reason: str | None
    created_at: datetime
