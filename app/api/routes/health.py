from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: SessionDep):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
