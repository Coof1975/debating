"""Persona CRUD service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Persona as PersonaModel
from app.schemas.persona import PersonaCreate, PersonaResponse, PersonaUpdate
from app.services.prompt_service import build_system_prompt_for_role, rebuild_all_prompts_in_db


def _sections_to_dict(sections: dict) -> dict:
    return {key: section.model_dump() for key, section in sections.items()}


def _llm_instructions_from_sections(sections: dict) -> str:
    """Derive top-level llm_instructions from the llm_instructions section."""
    section = sections.get("llm_instructions")
    if section is None:
        return ""
    if isinstance(section, dict):
        return (section.get("content") or "").strip()
    return (section.content or "").strip()


def _relationships_to_list(relationships: list) -> list:
    return [rel.model_dump() for rel in relationships]


def to_response(row: PersonaModel) -> PersonaResponse:
    return PersonaResponse(
        role=row.role,
        display_title=row.display_title,
        name=row.name,
        age=row.age,
        tone_of_voice=row.tone_of_voice,
        sections=row.sections or {},
        relationships=row.relationships or [],
        llm_instructions=row.llm_instructions,
        is_active=row.is_active,
        source_file=row.source_file,
        system_prompt=row.system_prompt,
        metadata=row.extra_metadata or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_personas(db: Session, *, active_only: bool = False) -> list[PersonaModel]:
    stmt = select(PersonaModel).order_by(PersonaModel.role)
    if active_only:
        stmt = stmt.where(PersonaModel.is_active.is_(True))
    return list(db.scalars(stmt).all())


def get_persona(db: Session, role: str) -> PersonaModel | None:
    return db.get(PersonaModel, role.upper())


def get_persona_or_404(db: Session, role: str) -> PersonaModel:
    persona = get_persona(db, role)
    if persona is None:
        raise LookupError(f"Persona not found: {role}")
    return persona


def create_persona(db: Session, payload: PersonaCreate) -> PersonaResponse:
    role = payload.role.upper()
    if get_persona(db, role):
        raise ValueError(f"Persona already exists: {role}")

    sections_dict = _sections_to_dict(payload.sections)
    row = PersonaModel(
        role=role,
        display_title=payload.display_title,
        name=payload.name,
        age=payload.age,
        tone_of_voice=payload.tone_of_voice,
        sections=sections_dict,
        relationships=_relationships_to_list(payload.relationships),
        llm_instructions=_llm_instructions_from_sections(sections_dict),
        is_active=payload.is_active,
        extra_metadata={"section_keys": list(payload.sections.keys())},
    )
    db.add(row)
    db.flush()
    row.system_prompt = build_system_prompt_for_role(db, row.role)
    db.commit()
    db.refresh(row)
    return to_response(row)


def update_persona(db: Session, role: str, payload: PersonaUpdate) -> PersonaResponse:
    row = get_persona_or_404(db, role)
    updates = payload.model_dump(exclude_unset=True)

    if "sections" in updates and updates["sections"] is not None:
        updates["sections"] = _sections_to_dict(updates["sections"])
        updates["llm_instructions"] = _llm_instructions_from_sections(updates["sections"])
        row.extra_metadata = {
            **(row.extra_metadata or {}),
            "section_keys": list(updates["sections"].keys()),
        }
    if "relationships" in updates and updates["relationships"] is not None:
        updates["relationships"] = _relationships_to_list(updates["relationships"])

    for field, value in updates.items():
        setattr(row, field, value)

    row.system_prompt = build_system_prompt_for_role(db, row.role)
    db.commit()
    db.refresh(row)
    return to_response(row)


def delete_persona(db: Session, role: str) -> None:
    row = get_persona_or_404(db, role)
    row.is_active = False
    db.commit()


def preview_prompt(
    db: Session,
    role: str,
    *,
    meeting_topic: str | None = None,
) -> tuple[str | None, str]:
    row = get_persona_or_404(db, role)
    topic = meeting_topic.strip() if meeting_topic and meeting_topic.strip() else None
    prompt = build_system_prompt_for_role(db, row.role, meeting_topic=topic)
    return topic, prompt or row.system_prompt


def rebuild_all_prompts(db: Session) -> list[str]:
    return rebuild_all_prompts_in_db(db)
