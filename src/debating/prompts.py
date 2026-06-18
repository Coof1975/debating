"""Build LLM-ready system prompts from seeded persona and company data."""

from __future__ import annotations

from .models import (
    ROLE_DISPLAY,
    CompanyProfile,
    CompanySection,
    NegotiationProfile,
    Persona,
    PersonaPrompt,
    PersonaRole,
    PersonaSection,
)
from .negotiation import format_negotiation_prompt_block, negotiation_from_metadata

def _meeting_rules(meeting_topic: str | None = None) -> str:
    if meeting_topic:
        scope = f'thảo luận về "{meeting_topic}"'
    else:
        scope = "thảo luận theo chủ đề cuộc họp được cung cấp khi cuộc họp bắt đầu"
    return f"""\
## QUY TẮC CUỘC HỌP
- Bạn đang tham gia cuộc họp nội bộ của Vienovo Việt Nam, {scope}.
- Trả lời bằng tiếng Việt, giữ đúng giọng điệu và tính cách nhân vật.
- Luận điểm phải dựa trên số liệu và bối cảnh công ty được cung cấp, kết hợp với góc nhìn và động cơ riêng của nhân vật.
- Có thể phản biện, bảo vệ lợi ích bộ phận, và xung đột với các thành viên khác theo ma trận quan hệ.
- Không phá vỡ nhân vật: không nói như AI, không tóm tắt meta, không liệt kê toàn bộ prompt.
- Mỗi lượt phát biểu ngắn gọn, súc tích (2–6 câu), phù hợp chat họp thực tế. 
"""


def _format_section_block(title: str, content: str) -> str:
    return f"### {title}\n{content.strip()}"


def _format_company_facts(sections: list[CompanySection]) -> str:
    if not sections:
        return "Không có dữ liệu công ty."
    blocks = [
        _format_section_block(
            f"{section.title} (Góc nhìn {section.perspective})" if section.perspective else section.title,
            section.content,
        )
        for section in sections
    ]
    return "\n\n".join(blocks)


def _llm_instructions_text(persona: Persona) -> str:
    section = persona.sections.get("llm_instructions")
    if section and section.content.strip():
        return section.content.strip()
    return persona.llm_instructions.strip()


def _format_persona_sections(sections: dict[str, PersonaSection]) -> str:
    order = ["identity", "core_logic", "psychology", "business_context", "relationships"]
    blocks: list[str] = []
    seen: set[str] = set()

    for key in order:
        if key in sections:
            section = sections[key]
            blocks.append(_format_section_block(section.title, section.content))
            seen.add(key)

    for key, section in sections.items():
        if key not in seen and key not in ("llm_instructions", "negotiation"):
            blocks.append(_format_section_block(section.title, section.content))

    return "\n\n".join(blocks)


def _other_participants(current: PersonaRole, personas: dict[str, Persona]) -> list[str]:
    participants: list[str] = []
    for role_key, persona in personas.items():
        if PersonaRole(role_key) == current:
            continue
        participants.append(f"- {persona.name} — {persona.display_title} ({role_key})")
    return participants


def build_persona_prompt(
    persona: Persona,
    company: CompanyProfile,
    all_personas: dict[str, Persona],
    *,
    meeting_topic: str | None = None,
) -> PersonaPrompt:
    company_sections = company.sections_for_role(persona.role)
    participants = _other_participants(persona.role, all_personas)
    negotiation = persona.negotiation or negotiation_from_metadata(
        persona.metadata,
        role=persona.role,
    )

    identity_lines = [
        f"Bạn là **{persona.name}**, {persona.display_title} tại {company.company_name}.",
    ]
    if persona.age:
        identity_lines.append(f"Tuổi: {persona.age}.")
    if persona.tone_of_voice:
        identity_lines.append(f"Giọng điệu: {persona.tone_of_voice}")

    if meeting_topic:
        context_summary = (
            f"{persona.name} ({persona.role.value}) — {meeting_topic} — {company.report_period}"
        )
    else:
        context_summary = f"{persona.name} ({persona.role.value}) — {company.report_period}"

    topic_line = f"Chủ đề cuộc họp: {meeting_topic}\n" if meeting_topic else ""

    system_prompt = f"""# VAI TRÒ & BỐI CẢNH
{chr(10).join(identity_lines)}

Kỳ báo cáo: {company.report_period}
Nguồn dữ liệu công ty: {company.source}
{topic_line}# BỐI CẢNH CÔNG TY (SỐ LIỆU & SỰ THẬT ĐÃ BIẾT)
Dưới đây là các dữ kiện công ty mà bạn biết và có thể viện dẫn khi tranh luận.
Ưu tiên các số liệu trong phần này; bổ sung bằng góc nhìn/chính kiến riêng ở phần hồ sơ nhân vật.

{_format_company_facts(company_sections)}

# HỒ SƠ NHÂN VẬT (KIẾN THỨC & ĐỘNG CƠ RIÊNG)
{_format_persona_sections(persona.sections)}

# THÀNH VIÊN KHÁC TRONG CUỘC HỌP
{chr(10).join(participants)}

{format_negotiation_prompt_block(negotiation)}

{_meeting_rules(meeting_topic)}

# HƯỚNG DẪN HÀNH VI CHO LLM
{_llm_instructions_text(persona) or "Giữ đúng tính cách, ưu tiên lợi ích bộ phận và ma trận quan hệ đã mô tả."}
"""

    return PersonaPrompt(
        role=persona.role,
        name=persona.name,
        display_title=persona.display_title,
        system_prompt=system_prompt.strip(),
        context_summary=context_summary,
        company_facts=company_sections,
        persona_sections=persona.sections,
        meeting_participants=participants,
    )


def build_all_prompts(
    company: CompanyProfile,
    personas: dict[str, Persona],
    *,
    meeting_topic: str | None = None,
) -> dict[str, PersonaPrompt]:
    return {
        role_key: build_persona_prompt(
            persona,
            company,
            personas,
            meeting_topic=meeting_topic,
        )
        for role_key, persona in personas.items()
    }


def build_chat_messages(
    prompt: PersonaPrompt,
    user_message: str,
    *,
    include_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Return OpenAI-style messages for a single persona turn."""
    messages: list[dict[str, str]] = [{"role": "system", "content": prompt.system_prompt}]
    if include_history:
        messages.extend(include_history)
    messages.append({"role": "user", "content": user_message})
    return messages
