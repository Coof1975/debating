"""Load and parse markdown sources into structured models."""

from __future__ import annotations

import re
from pathlib import Path

from .models import (
    PERSONA_FILES,
    ROLE_DISPLAY,
    CompanyProfile,
    CompanySection,
    Persona,
    PersonaRole,
    PersonaSection,
)
from .negotiation import default_negotiation_for_role

COMPANY_SECTION_PATTERNS: list[tuple[str, str, str, re.Pattern[str]]] = [
    (
        "financial",
        "Tổng quan Tài chính & Dòng tiền",
        "CFO",
        re.compile(
            r"1\.\s*Tổng quan Tài chính.*?$(.*?)(?=^2\.\s*Tình hình Sản xuất|\Z)",
            re.MULTILINE | re.DOTALL,
        ),
    ),
    (
        "production",
        "Tình hình Sản xuất & Chuỗi cung ứng",
        "Giám đốc Sản xuất",
        re.compile(
            r"2\.\s*Tình hình Sản xuất.*?$(.*?)(?=^3\.\s*Hệ thống Phân phối|\Z)",
            re.MULTILINE | re.DOTALL,
        ),
    ),
    (
        "distribution",
        "Hệ thống Phân phối & Thị trường",
        "Giám đốc Sales",
        re.compile(
            r"3\.\s*Hệ thống Phân phối.*?$(.*?)(?=^4\.\s*Định vị Sản phẩm|\Z)",
            re.MULTILINE | re.DOTALL,
        ),
    ),
    (
        "marketing",
        "Định vị Sản phẩm & Sức khỏe Thương hiệu",
        "Giám đốc Marketing",
        re.compile(
            r"4\.\s*Định vị Sản phẩm.*?$(.*?)(?=^Cách hệ thống bốc dữ liệu|\Z)",
            re.MULTILINE | re.DOTALL,
        ),
    ),
]

PERSONA_SECTION_ALIASES: dict[str, list[str]] = {
    "identity": [
        "system profile",
        "role & persona",
        "thông tin cơ bản",
        "roleplay specification",
    ],
    "core_logic": [
        "hồ sơ tâm lý",
        "core logic",
        "psychological profile",
    ],
    "psychology": [
        "bức tranh huyền học",
        "metaphysics & psychology",
    ],
    "business_context": [
        "internal context",
        "current business pain",
        "xung đột lợi ích",
        "interest conflict",
    ],
    "relationships": [
        "relationship matrix",
        "ma trận quan hệ",
        "relationship links",
    ],
    "llm_instructions": [
        "prompt instruction",
        "instruction for the llm",
        "instruction for llm",
    ],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "_", slug.strip())
    return slug[:64] or "section"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _extract_name(content: str, role: PersonaRole) -> str:
    patterns = [
        r"Target Character:\s*([^(]+)",
        r"Full Name:\s*(.+)",
        r"Name:\s*([^(]+)",
        r"Họ tên:\s*([^(]+)",
        r"Họ và tên:\s*([^(]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return role.value


def _extract_age(content: str) -> int | None:
    match = re.search(r"(\d{2})\s*tuổi", content, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\((\d{2})\s*years old\)", content, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_tone(content: str) -> str:
    patterns = [
        r"Core Relationship/Tone:\s*(.+?)(?=\n\[|\n\d+\.)",
        r"Tone of Voice:\s*(.+?)(?=\n\[|\n\d+\.)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return " ".join(match.group(1).split())
    return ""


def _extract_llm_instructions(content: str) -> str:
    patterns = [
        r"\[5\. PROMPT INSTRUCTION FOR LLM\]\s*(.+)",
        r"\[INSTRUCTION FOR THE LLM\]\s*(.+)",
        r"(?:^|\n)(?:\d+\.\s*)?(?:PROMPT INSTRUCTION|INSTRUCTION FOR THE LLM)[:\s]*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def _classify_section(title: str) -> str:
    normalized = _normalize(title)
    for canonical, aliases in PERSONA_SECTION_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return canonical
    return _slugify(title)


def _parse_bracket_sections(content: str) -> dict[str, PersonaSection]:
    sections: dict[str, PersonaSection] = {}
    pattern = re.compile(r"\[([^\]]+)\]\s*(.*?)(?=\n\[|\Z)", re.DOTALL)
    for match in pattern.finditer(content):
        title = match.group(1).strip()
        body = match.group(2).strip()
        key = _classify_section(title)
        sections[key] = PersonaSection(key=key, title=title, content=body)
    return sections


def _parse_numbered_sections(content: str) -> dict[str, PersonaSection]:
    sections: dict[str, PersonaSection] = {}
    pattern = re.compile(r"^(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(content))
    for index, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        key = _classify_section(title)
        sections[key] = PersonaSection(key=key, title=title, content=body)
    return sections


def _parse_persona_sections(content: str) -> dict[str, PersonaSection]:
    if re.search(r"^\[", content, re.MULTILINE):
        sections = _parse_bracket_sections(content)
        if sections:
            return sections
    return _parse_numbered_sections(content)


def _extract_company_header(content: str) -> tuple[str, str, str]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    company_name = "Vienovo Việt Nam"
    report_period = "Q2/2026"
    source = "Hệ thống ERP & Báo cáo Quản trị Nội bộ"

    if lines:
        header = lines[0]
        if "Q" in header:
            match = re.search(r"\((Q\d/\d{4})\)", header)
            if match:
                report_period = match.group(1)
            company_name = header.split("-")[0].strip()
        if len(lines) > 1 and "Nguồn dữ liệu" in lines[1]:
            source = re.sub(r"^\(|\)$", "", lines[1].replace("Nguồn dữ liệu:", "").strip())

    return company_name, report_period, source


def load_company_profile(path: Path) -> CompanyProfile:
    content = _read_text(path)
    company_name, report_period, source = _extract_company_header(content)
    sections: dict[str, CompanySection] = {}

    for key, title, perspective, pattern in COMPANY_SECTION_PATTERNS:
        match = pattern.search(content)
        if match:
            sections[key] = CompanySection(
                key=key,
                title=title,
                content=match.group(1).strip(),
                perspective=perspective,
            )

    return CompanyProfile(
        company_name=company_name,
        report_period=report_period,
        source=source,
        raw_content=content,
        sections=sections,
    )


def load_persona(path: Path, role: PersonaRole) -> Persona:
    content = _read_text(path)
    sections = _parse_persona_sections(content)
    llm_section = sections.get("llm_instructions")
    llm_instructions = (
        llm_section.content.strip()
        if llm_section and llm_section.content.strip()
        else _extract_llm_instructions(content)
    )

    return Persona(
        role=role,
        display_title=ROLE_DISPLAY[role],
        name=_extract_name(content, role),
        age=_extract_age(content),
        tone_of_voice=_extract_tone(content),
        source_file=path.name,
        raw_content=content,
        sections=sections,
        llm_instructions=llm_instructions,
        negotiation=default_negotiation_for_role(role),
        metadata={
            "section_keys": list(sections.keys()),
            "has_relationships": "relationships" in sections,
            "negotiation": default_negotiation_for_role(role).model_dump(),
        },
    )


def load_all_personas(test_data_dir: Path) -> dict[str, Persona]:
    personas: dict[str, Persona] = {}
    for role, filename in PERSONA_FILES.items():
        path = test_data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing persona file: {path}")
        personas[role.value] = load_persona(path, role)
    return personas


def load_seed_sources(test_data_dir: Path) -> tuple[CompanyProfile, dict[str, Persona]]:
    company_path = test_data_dir / "COMPANY_profile.md"
    if not company_path.exists():
        raise FileNotFoundError(f"Missing company profile: {company_path}")
    company = load_company_profile(company_path)
    personas = load_all_personas(test_data_dir)
    return company, personas
