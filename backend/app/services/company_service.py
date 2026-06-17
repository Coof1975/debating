"""Company profile service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import CompanyProfile as CompanyProfileModel
from app.schemas.company import CompanyProfileResponse, CompanyProfileUpdate
from app.services.prompt_service import rebuild_all_prompts_in_db


def get_company_profile(db: Session) -> CompanyProfileModel | None:
    return db.get(CompanyProfileModel, 1)


def get_company_or_404(db: Session) -> CompanyProfileModel:
    row = get_company_profile(db)
    if row is None:
        raise LookupError("Company profile not found")
    return row


def to_response(row: CompanyProfileModel) -> CompanyProfileResponse:
    return CompanyProfileResponse(
        company_name=row.company_name,
        report_period=row.report_period,
        source=row.source,
        sections=row.sections or {},
        updated_at=row.updated_at,
    )


def update_company_profile(db: Session, payload: CompanyProfileUpdate) -> CompanyProfileResponse:
    row = get_company_or_404(db)
    updates = payload.model_dump(exclude_unset=True)

    if "sections" in updates and updates["sections"] is not None:
        updates["sections"] = {
            key: section.model_dump() for key, section in updates["sections"].items()
        }

    for field, value in updates.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)
    rebuild_all_prompts_in_db(db)
    return to_response(row)
