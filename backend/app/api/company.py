"""Company profile API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.company import CompanyProfileResponse, CompanyProfileUpdate, RebuildPromptsResponse
from app.services import company_service, persona_service

router = APIRouter(prefix="/company-profile", tags=["company"])


@router.get("", response_model=CompanyProfileResponse)
def get_company_profile(db: Session = Depends(get_db)) -> CompanyProfileResponse:
    try:
        row = company_service.get_company_or_404(db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return company_service.to_response(row)


@router.put("", response_model=CompanyProfileResponse)
def update_company_profile(
    payload: CompanyProfileUpdate,
    db: Session = Depends(get_db),
) -> CompanyProfileResponse:
    try:
        return company_service.update_company_profile(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rebuild-prompts", response_model=RebuildPromptsResponse)
def rebuild_prompts(db: Session = Depends(get_db)) -> RebuildPromptsResponse:
    try:
        updated = persona_service.rebuild_all_prompts(db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RebuildPromptsResponse(
        updated_personas=updated,
        message=f"Rebuilt system prompts for {len(updated)} personas.",
    )
