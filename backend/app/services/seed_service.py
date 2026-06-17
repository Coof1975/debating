"""Seed database from data/seeded JSON files."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import CompanyProfile, Persona
from app.services.prompt_service import rebuild_all_prompts_in_db


def seed_from_files(db: Session, *, force: bool = False) -> dict[str, int]:
    settings = get_settings()
    seeded_dir = settings.seeded_data_dir

    personas_dir = seeded_dir / "personas"
    company_path = seeded_dir / "company_profile.json"

    if not company_path.exists() or not personas_dir.exists():
        raise FileNotFoundError(
            f"Seeded data not found at {seeded_dir}. Run debating seed from repo root first."
        )

    counts = {"personas": 0, "company": 0}

    existing_company = db.get(CompanyProfile, 1)
    if existing_company is None or force:
        company_data = json.loads(company_path.read_text(encoding="utf-8"))
        if existing_company is None:
            row = CompanyProfile(
                id=1,
                company_name=company_data["company_name"],
                report_period=company_data.get("report_period", ""),
                source=company_data.get("source", ""),
                raw_content=company_data.get("raw_content", ""),
                sections=company_data.get("sections", {}),
            )
            db.add(row)
            counts["company"] = 1
        elif force:
            for key, value in company_data.items():
                if key == "sections":
                    existing_company.sections = value
                elif hasattr(existing_company, key):
                    setattr(existing_company, key, value)
            counts["company"] = 1

    for persona_file in sorted(personas_dir.glob("*.json")):
        data = json.loads(persona_file.read_text(encoding="utf-8"))
        role = data["role"]
        existing = db.get(Persona, role)
        if existing is not None and not force:
            continue

        if existing is None:
            row = Persona(
                role=role,
                display_title=data.get("display_title", role),
                name=data.get("name", ""),
                age=data.get("age"),
                tone_of_voice=data.get("tone_of_voice", ""),
                source_file=data.get("source_file", persona_file.name),
                raw_content=data.get("raw_content", ""),
                sections=data.get("sections", {}),
                relationships=data.get("relationships", []),
                llm_instructions=data.get("llm_instructions", ""),
                extra_metadata=data.get("metadata", {}),
                is_active=True,
            )
            db.add(row)
        elif force:
            existing.display_title = data.get("display_title", role)
            existing.name = data.get("name", "")
            existing.age = data.get("age")
            existing.tone_of_voice = data.get("tone_of_voice", "")
            existing.source_file = data.get("source_file", persona_file.name)
            existing.raw_content = data.get("raw_content", "")
            existing.sections = data.get("sections", {})
            existing.relationships = data.get("relationships", [])
            existing.llm_instructions = data.get("llm_instructions", "")
            existing.extra_metadata = data.get("metadata", {})
            existing.is_active = True

        counts["personas"] += 1

    db.commit()
    rebuild_all_prompts_in_db(db)
    return counts


def seed_if_empty(db: Session) -> dict[str, int] | None:
    persona_count = db.query(Persona).count()
    if persona_count > 0:
        return None
    return seed_from_files(db)
