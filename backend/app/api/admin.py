"""Admin / seed API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import seed_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed")
def seed_database(
    force: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        counts = seed_service.seed_from_files(db, force=force)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "seeded", "counts": counts}
