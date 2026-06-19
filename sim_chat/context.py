"""Domain-aware turn context assembly for persona nodes."""

from __future__ import annotations

from .domain import SimulationDomain, get_domain
from .models import FACILITATOR_SPEAKER_ID, MeetingState


def build_persona_user_context(
    state: MeetingState,
    *,
    speaker_id: str,
    domain: SimulationDomain | None = None,
    transcript: str,
    rel_summary: str,
    proposals_block: str = "",
    facts_block: str = "",
    anti_repetition_block: str = "",
) -> str:
    domain = domain or get_domain(state["config"].domain_id)
    labels = domain.labels
    topic = state["meeting_topic"]
    extra = f"{proposals_block}{facts_block}"
    opener = state["config"].opening_speaker or domain.default_opening_speaker or speaker_id
    is_opener = speaker_id == opener

    if not state["messages"]:
        if is_opener:
            return f"""\
[{labels.session_noun}: {topic}]

Bạn được chỉ định mở đầu. Hãy phát biểu 1 lượt mở đầu (2–6 câu) để:
- Nêu mục tiêu phiên và phạm vi thảo luận bám sát chủ đề.
- Đưa ra 2–4 điểm cần chốt và tiêu chí ra quyết định.
- Đặt kỳ vọng tranh luận: thẳng, có bằng chứng/số liệu, phản biện trực tiếp.
"""
        return f"""\
[{labels.session_noun}: {topic}]

Phiên vừa bắt đầu. Hãy phát biểu lượt đầu tiên (2–6 câu), bám sát chủ đề. Đi thẳng vào quan điểm — không mở đầu bằng câu lịch sự.
"""

    last_speaker = state.get("last_speaker") or "—"
    anti_block = f"\n\n{anti_repetition_block.strip()}" if anti_repetition_block.strip() else ""

    facilitator_block = ""
    messages = state.get("messages") or []
    if last_speaker == FACILITATOR_SPEAKER_ID and messages:
        facilitator_block = f"""

## CHỈ ĐẠO TỪ NGƯỜI TỔ CHỨC (vừa phát)
{messages[-1].content}

Phản hồi trực tiếp directive này. Không lặp lại toàn bộ biên bản cũ.
"""

    return f"""\
[{labels.session_noun}: {topic}]

{labels.transcript_label}:
{transcript}

{labels.last_speaker_label}: {last_speaker}
{labels.relationship_label}:
{rel_summary}
{anti_block}{facilitator_block}

Hãy phát biểu tiếp theo. Phản biện trực tiếp nếu cần — đi thẳng vào luận điểm, tránh câu mở đầu lịch sự/khách sáo.{extra}
"""
