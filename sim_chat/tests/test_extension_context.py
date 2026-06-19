"""Tests for facilitator directive context injection."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.context import build_persona_user_context
from sim_chat.models import DialogueTurn, FACILITATOR_SPEAKER_ID


def test_facilitator_directive_block_in_persona_context() -> None:
    state = {
        "meeting_topic": "Ngân sách Keos Q3",
        "config": MeetingConfig(domain_id="enterprise"),
        "messages": [
            DialogueTurn(
                speaker_id="CEO",
                speaker_name="CEO",
                content="Chốt phương án tạm.",
                turn_index=1,
                round_number=1,
            ),
            DialogueTurn(
                speaker_id=FACILITATOR_SPEAKER_ID,
                speaker_name="Người tổ chức",
                content="Bổ sung 500 triệu ngân sách, CFO phản hồi.",
                turn_index=2,
                round_number=1,
            ),
        ],
        "last_speaker": FACILITATOR_SPEAKER_ID,
    }

    context = build_persona_user_context(
        state,  # type: ignore[arg-type]
        speaker_id="CFO",
        transcript="[CEO]: Chốt phương án tạm.\n[Người tổ chức]: Bổ sung 500 triệu...",
        rel_summary="Trung lập với CEO.",
    )

    assert "CHỈ ĐẠO TỪ NGƯỜI TỔ CHỨC" in context
    assert "500 triệu ngân sách" in context
    assert "Phản hồi trực tiếp directive này" in context
