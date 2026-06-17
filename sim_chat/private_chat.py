"""1-1 private interrogation chat with a single persona after the meeting."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .llm import LLMProvider, MockLLMProvider
from .models import DialogueTurn, MeetingRecord


class PrivateChatMessage(BaseModel):
    role: str
    content: str


class PrivateChatSession(BaseModel):
    """Isolated chat with one persona, seeded from a completed meeting."""

    persona_id: str
    persona_name: str
    system_prompt: str
    messages: list[PrivateChatMessage] = Field(default_factory=list)
    meeting_id: str = ""
    meeting_topic: str = ""

    def chat(self, user_message: str, llm: LLMProvider) -> str:
        history_block = ""
        if self.messages:
            history_block = "\n".join(
                f"{'User' if msg.role == 'user' else self.persona_name}: {msg.content}"
                for msg in self.messages[-10:]
            )
            history_block = f"\n\nLịch sử chat riêng:\n{history_block}"

        prompt = (
            f"[PHỎNG VẤN RIÊNG — sau cuộc họp: {self.meeting_topic}]\n"
            f"Câu hỏi của người dùng: {user_message}"
            f"{history_block}"
        )
        reply = llm.generate(self.system_prompt, prompt)
        self.messages.append(PrivateChatMessage(role="user", content=user_message))
        self.messages.append(PrivateChatMessage(role="assistant", content=reply))
        return reply


def _format_meeting_transcript(messages: list[DialogueTurn]) -> str:
    return "\n".join(
        f"[{turn.speaker_name} ({turn.speaker_id})]: {turn.content}"
        for turn in messages
    )


def build_private_chat_session(
    record: MeetingRecord,
    persona_id: str,
    *,
    persona_system_prompt: str,
    enable_astrology: bool = True,
) -> PrivateChatSession:
    """Transfer completed graph state into an independent 1-1 chat session."""
    matrix = record.relationship_matrix
    rel_summary = matrix.summary_for(persona_id)
    transcript = _format_meeting_transcript(record.messages)

    astro_block = ""
    if enable_astrology and persona_id in matrix.astrology:
        astro = matrix.astrology[persona_id]
        astro_block = f"\n# TỬ VI / BÁT TỰ\n{astro.summary}\n"

    private_system = f"""{persona_system_prompt}

# NGỮ CẢNH SAU CUỘC HỌP MÔ PHỎNG
Bạn đang ở phiên chat riêng 1-1 với người dùng sau cuộc họp nội bộ.
Trả lời thẳng thắn, giữ đúng tính cách nhân vật, có thể bộc lộ động cơ ẩn hơn so với trong họp.

# MA TRẬN QUAN HỆ ĐỘNG
{rel_summary}
{astro_block}
# TOÀN BỘ BIÊN BẢN CUỘC HỌP
{transcript}

# QUY TẮC CHAT RIÊNG
- Trả lời tiếng Việt, giọng điệu đúng nhân vật.
- Có thể giải thích lý do đứng về phe, bộ phận, hoặc cá nhân.
- Không phá vỡ nhân vật; không nói như AI.
"""

    persona_name = next(
        (turn.speaker_name for turn in record.messages if turn.speaker_id == persona_id),
        persona_id,
    )

    return PrivateChatSession(
        persona_id=persona_id,
        persona_name=persona_name,
        system_prompt=private_system.strip(),
        meeting_id=record.meeting_id,
        meeting_topic=record.topic,
    )


def create_session_from_record(
    record: MeetingRecord,
    persona_id: str,
    persona_prompts: dict[str, str],
    *,
    enable_astrology: bool = True,
) -> PrivateChatSession:
    if persona_id not in persona_prompts:
        raise KeyError(f"Unknown persona_id: {persona_id}")
    return build_private_chat_session(
        record,
        persona_id,
        persona_system_prompt=persona_prompts[persona_id],
        enable_astrology=enable_astrology,
    )


def demo_private_reply(
    session: PrivateChatSession,
    question: str,
    *,
    use_mock: bool = True,
) -> str:
    llm = MockLLMProvider(persona_names={session.persona_id: session.persona_name})
    if not use_mock:
        from .config import MeetingConfig
        from .llm import create_llm_provider

        llm = create_llm_provider(MeetingConfig())
    return session.chat(question, llm)
