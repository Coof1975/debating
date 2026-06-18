"""Data models for company profile and meeting personas."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .negotiation import NegotiationProfile


class PersonaRole(str, Enum):
    CEO = "CEO"
    CFO = "CFO"
    MARKETING = "MARKETING"
    PRODUCT = "PRODUCT"
    SALE = "SALE"


ROLE_DISPLAY: dict[PersonaRole, str] = {
    PersonaRole.CEO: "Tổng Giám đốc (CEO)",
    PersonaRole.CFO: "Giám đốc Tài chính (CFO)",
    PersonaRole.MARKETING: "Trưởng phòng Marketing",
    PersonaRole.PRODUCT: "Giám đốc Sản xuất",
    PersonaRole.SALE: "Giám đốc Kinh doanh",
}

PERSONA_FILES: dict[PersonaRole, str] = {
    PersonaRole.CEO: "CEO_persona.md",
    PersonaRole.CFO: "CFO_persona.md",
    PersonaRole.MARKETING: "MARKETING_persona.md",
    PersonaRole.PRODUCT: "PRODUCT_persona.md",
    PersonaRole.SALE: "SALE_persona.md",
}

# Which company-profile sections each role prioritizes in prompts.
ROLE_COMPANY_SECTIONS: dict[PersonaRole, list[str]] = {
    PersonaRole.CEO: ["financial", "production", "distribution", "marketing"],
    PersonaRole.CFO: ["financial", "production", "distribution"],
    PersonaRole.MARKETING: ["marketing", "financial", "distribution"],
    PersonaRole.PRODUCT: ["production", "financial", "distribution"],
    PersonaRole.SALE: ["distribution", "financial", "marketing"],
}


class CompanySection(BaseModel):
    """One topical block from the company profile."""

    key: str
    title: str
    content: str
    perspective: str = ""


class CompanyProfile(BaseModel):
    """Structured company facts shared across the simulation."""

    company_name: str = "Vienovo Việt Nam"
    report_period: str = "Q2/2026"
    source: str = "Hệ thống ERP & Báo cáo Quản trị Nội bộ"
    raw_content: str = ""
    sections: dict[str, CompanySection] = Field(default_factory=dict)

    def sections_for_role(self, role: PersonaRole) -> list[CompanySection]:
        keys = ROLE_COMPANY_SECTIONS[role]
        return [self.sections[key] for key in keys if key in self.sections]


class PersonaSection(BaseModel):
    """A labeled block extracted from a persona markdown file."""

    key: str
    title: str
    content: str


class PersonaRelationship(BaseModel):
    """How this persona interacts with another participant."""

    target_role: PersonaRole
    target_name: str = ""
    stance: str
    behavior: str = ""


class Persona(BaseModel):
    """Structured persona ready for seeding and prompt assembly."""

    role: PersonaRole
    display_title: str
    name: str = ""
    age: int | None = None
    tone_of_voice: str = ""
    source_file: str = ""
    raw_content: str = ""
    sections: dict[str, PersonaSection] = Field(default_factory=dict)
    relationships: list[PersonaRelationship] = Field(default_factory=list)
    llm_instructions: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    negotiation: NegotiationProfile | None = None


class PersonaPrompt(BaseModel):
    """Final LLM-ready prompt bundle for one meeting participant."""

    role: PersonaRole
    name: str
    display_title: str
    system_prompt: str
    context_summary: str
    company_facts: list[CompanySection]
    persona_sections: dict[str, PersonaSection]
    meeting_participants: list[str]


class SeedBundle(BaseModel):
    """Complete seeded dataset for the simulation."""

    company: CompanyProfile
    personas: dict[str, Persona]
    prompts: dict[str, PersonaPrompt]
