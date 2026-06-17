"""Transcript formatting and rolling summary for meeting context windows."""

from __future__ import annotations

from .config import MeetingConfig
from .llm import LLMProvider
from .models import DialogueTurn, MeetingState

SUMMARY_SYSTEM_PROMPT = """\
Bạn tóm tắt biên bản cuộc họp nội bộ bằng tiếng Việt.
Giữ lại: luận điểm chính, con số cụ thể, ai ủng hộ/phản đối gì, mức bất đồng còn lại.
Tối đa 8 câu, không meta, không markdown.
"""

SUMMARY_USER_TEMPLATE = """\
Chủ đề: {topic}

{prior_block}Các lượt cần gộp vào tóm tắt:
{turns}

Viết tóm tắt cập nhật (hoặc tóm tắt mới nếu chưa có bản trước):
"""


def _turn_line(turn: DialogueTurn, *, style: str) -> str:
    if style == "orchestrator":
        return f"- {turn.speaker_name} ({turn.speaker_id}): {turn.content}"
    return f"[Vòng {turn.round_number}] {turn.speaker_name} ({turn.speaker_id}): {turn.content}"


def _format_turns(messages: list[DialogueTurn], *, style: str) -> str:
    if not messages:
        return "(Chưa có phát biểu.)"
    return "\n".join(_turn_line(turn, style=style) for turn in messages)


def _rolling_active(config: MeetingConfig, turn_count: int) -> bool:
    return config.enable_rolling_summary and turn_count >= config.rolling_summary_min_turns


def _recent_count(config: MeetingConfig) -> int:
    return max(1, config.rolling_summary_recent_turns)


def _summarize_through_index(message_count: int, config: MeetingConfig) -> int:
    """Index (exclusive) into messages that rolling summary should cover."""
    return max(0, message_count - _recent_count(config))


def should_refresh_summary(state: MeetingState) -> bool:
    config = state["config"]
    messages = state["messages"]
    turn_count = len(messages)

    if not _rolling_active(config, turn_count):
        return False

    through = _summarize_through_index(turn_count, config)
    if through <= 0:
        return False

    covered = state.get("summary_through_turn") or 0
    summary = (state.get("transcript_summary") or "").strip()

    if not summary:
        return True

    delta = through - covered
    if delta <= 0:
        return False

    return delta >= config.rolling_summary_refresh_interval


def _format_turns_for_summary(messages: list[DialogueTurn]) -> str:
    return "\n".join(
        f"[Lượt {turn.turn_index}] {turn.speaker_name} ({turn.speaker_id}): {turn.content}"
        for turn in messages
    )


def refresh_transcript_summary(state: MeetingState, llm: LLMProvider) -> dict:
    """Summarize older turns; keep the most recent K turns as full text."""
    config = state["config"]
    messages = state["messages"]
    through = _summarize_through_index(len(messages), config)
    if through <= 0:
        return {}

    to_summarize = messages[:through]
    prior = (state.get("transcript_summary") or "").strip()
    covered = state.get("summary_through_turn") or 0
    new_turns = messages[covered:through]

    if prior and new_turns:
        prior_block = f"Tóm tắt trước:\n{prior}\n\n"
        turns_block = _format_turns_for_summary(new_turns)
    else:
        prior_block = ""
        turns_block = _format_turns_for_summary(to_summarize)

    user_message = SUMMARY_USER_TEMPLATE.format(
        topic=state["meeting_topic"],
        prior_block=prior_block,
        turns=turns_block,
    )
    summary = llm.generate(SUMMARY_SYSTEM_PROMPT, user_message).strip()
    return {
        "transcript_summary": summary,
        "summary_through_turn": through,
    }


def maybe_refresh_transcript_summary(state: MeetingState, llm: LLMProvider) -> dict:
    if should_refresh_summary(state):
        return refresh_transcript_summary(state, llm)
    return {}


def format_transcript_for_context(
    state: MeetingState,
    *,
    style: str = "default",
    fallback_limit: int = 10,
) -> str:
    """Build transcript context: rolling summary + recent full turns, or sliding window."""
    messages = state["messages"]
    if not messages:
        return "(Chưa có phát biểu.)"

    config = state["config"]
    if not _rolling_active(config, len(messages)):
        recent = messages[-fallback_limit:]
        return _format_turns(recent, style=style)

    recent_count = _recent_count(config)
    older_count = len(messages) - recent_count
    summary = (state.get("transcript_summary") or "").strip()
    recent = messages[-recent_count:]

    parts: list[str] = []
    if older_count > 0:
        if summary:
            parts.append(f"Tóm tắt các lượt 1–{older_count}:\n{summary}")
        else:
            parts.append(
                f"(Tóm tắt các lượt 1–{older_count} đang được cập nhật; "
                f"dưới đây là {recent_count} lượt gần nhất.)"
            )
    parts.append(f"Các lượt gần nhất ({len(recent)}):")
    parts.append(_format_turns(recent, style=style))
    return "\n\n".join(parts)
