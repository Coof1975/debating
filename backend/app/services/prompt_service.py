"""Prompt building helpers using debating package."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap import setup_paths

setup_paths()

from debating.models import CompanyProfile, Persona, PersonaRole, PersonaSection
from debating.negotiation import negotiation_from_metadata
from debating.prompts import build_all_prompts, build_persona_prompt

from app.db.models import CompanyProfile as CompanyProfileModel
from app.db.models import Persona as PersonaModel


def persona_from_row(row: PersonaModel) -> Persona:
    try:
        role = PersonaRole(row.role)
    except ValueError:
        matched = next((r for r in PersonaRole if r.value == row.role), None)
        if matched is None:
            raise ValueError(f"Unknown persona role: {row.role}")
        role = matched

    sections = {
        key: PersonaSection(**section)
        for key, section in (row.sections or {}).items()
    }
    metadata = row.extra_metadata or {}
    negotiation = negotiation_from_metadata(metadata, role=row.role)
    return Persona(
        role=role,
        display_title=row.display_title,
        name=row.name,
        age=row.age,
        tone_of_voice=row.tone_of_voice,
        source_file=row.source_file,
        raw_content=row.raw_content,
        sections=sections,
        relationships=[],
        llm_instructions=row.llm_instructions,
        metadata=metadata,
        negotiation=negotiation,
    )


def company_from_row(row: CompanyProfileModel) -> CompanyProfile:
    from debating.models import CompanySection

    sections = {
        key: CompanySection(**section)
        for key, section in (row.sections or {}).items()
    }
    return CompanyProfile(
        company_name=row.company_name,
        report_period=row.report_period,
        source=row.source,
        raw_content=row.raw_content,
        sections=sections,
    )


def load_domain_personas(db: Session, *, active_only: bool = True) -> dict[str, Persona]:
    stmt = select(PersonaModel).order_by(PersonaModel.role)
    if active_only:
        stmt = stmt.where(PersonaModel.is_active.is_(True))
    rows = db.scalars(stmt).all()
    return {row.role: persona_from_row(row) for row in rows}


def rebuild_all_system_prompts(
    company: CompanyProfile,
    personas: dict[str, Persona],
) -> dict[str, str]:
    prompts = build_all_prompts(company, personas)
    return {role: prompt.system_prompt for role, prompt in prompts.items()}


def rebuild_all_prompts_in_db(db: Session) -> list[str]:
    company_row = db.get(CompanyProfileModel, 1)
    if company_row is None:
        raise LookupError("Company profile not found")

    company = company_from_row(company_row)
    personas = load_domain_personas(db, active_only=True)
    prompts = rebuild_all_system_prompts(company, personas)

    updated: list[str] = []
    for role, prompt_text in prompts.items():
        row = db.get(PersonaModel, role)
        if row:
            row.system_prompt = prompt_text
            updated.append(role)
    db.commit()
    return updated


def build_system_prompt_for_role(
    db: Session,
    role: str,
    *,
    meeting_topic: str | None = None,
) -> str:
    company_row = db.get(CompanyProfileModel, 1)
    if company_row is None:
        raise LookupError("Company profile not found")

    persona_row = db.get(PersonaModel, role)
    if persona_row is None:
        raise LookupError(f"Persona not found: {role}")

    company = company_from_row(company_row)
    personas = load_domain_personas(db, active_only=True)
    persona = persona_from_row(persona_row)
    prompt = build_persona_prompt(persona, company, personas, meeting_topic=meeting_topic)
    return prompt.system_prompt


def build_meeting_system_prompts(
    db: Session,
    participant_ids: list[str],
    meeting_topic: str,
) -> dict[str, str]:
    company_row = db.get(CompanyProfileModel, 1)
    if company_row is None:
        raise LookupError("Company profile not found")

    company = company_from_row(company_row)
    all_personas = load_domain_personas(db, active_only=True)
    meeting_personas = {
        role_id: all_personas[role_id]
        for role_id in participant_ids
        if role_id in all_personas
    }
    missing = [role_id for role_id in participant_ids if role_id not in meeting_personas]
    if missing:
        raise LookupError(f"Persona not found: {', '.join(missing)}")

    prompts: dict[str, str] = {}
    for role_id in participant_ids:
        prompt = build_persona_prompt(
            meeting_personas[role_id],
            company,
            meeting_personas,
            meeting_topic=meeting_topic,
        )
        prompts[role_id] = prompt.system_prompt
    return prompts
