"""Persona API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.persona import (
    PersonaCreate,
    PersonaListItem,
    PersonaResponse,
    PersonaUpdate,
    PromptPreviewResponse,
)
from app.services import persona_service

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("", response_model=list[PersonaListItem])
def list_personas(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[PersonaListItem]:
    rows = persona_service.list_personas(db, active_only=active_only)
    return [
        PersonaListItem(
            role=row.role,
            display_title=row.display_title,
            name=row.name,
            is_active=row.is_active,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get("/{role}", response_model=PersonaResponse)
def get_persona(role: str, db: Session = Depends(get_db)) -> PersonaResponse:
    try:
        row = persona_service.get_persona_or_404(db, role)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return persona_service.to_response(row)


@router.post("", response_model=PersonaResponse, status_code=201)
def create_persona(payload: PersonaCreate, db: Session = Depends(get_db)) -> PersonaResponse:
    try:
        return persona_service.create_persona(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{role}", response_model=PersonaResponse)
def update_persona(
    role: str,
    payload: PersonaUpdate,
    db: Session = Depends(get_db),
) -> PersonaResponse:
    try:
        return persona_service.update_persona(db, role, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{role}", status_code=204)
def delete_persona(role: str, db: Session = Depends(get_db)) -> None:
    try:
        persona_service.delete_persona(db, role)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{role}/preview-prompt", response_model=PromptPreviewResponse)
def preview_prompt(
    role: str,
    meeting_topic: str | None = None,
    db: Session = Depends(get_db),
) -> PromptPreviewResponse:
    try:
        topic, prompt = persona_service.preview_prompt(db, role, meeting_topic=meeting_topic)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PromptPreviewResponse(role=role.upper(), system_prompt=prompt, meeting_topic=topic)
