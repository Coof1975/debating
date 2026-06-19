"""Tests for relationship-aware internal reasoning context."""

from __future__ import annotations

from sim_chat.models import AstrologyProfile, DialogueTurn, RelationshipEdge, RelationshipMatrix
from sim_chat.reasoning import build_reasoning_user_message, parse_monologue
from sim_chat.relationship import format_relationships_for_reasoning, infer_session_mood


def _sample_matrix() -> RelationshipMatrix:
    return RelationshipMatrix(
        participants=["CEO", "CFO", "SALE"],
        edges={
            "CEO": {
                "CFO": RelationshipEdge(
                    source_id="CEO",
                    target_id="CFO",
                    affinity=0.2,
                    conflict_weight=0.5,
                    notes="Tin CFO nhưng sẵn sàng bật lại khi than vãn margin.",
                ),
                "SALE": RelationshipEdge(
                    source_id="CEO",
                    target_id="SALE",
                    affinity=-0.5,
                    conflict_weight=0.85,
                    notes="Dị ứng quản lý thủ công, nghi ngờ kéo bè với Marketing.",
                ),
            },
            "CFO": {},
            "SALE": {},
        },
        astrology={
            "CEO": AstrologyProfile(
                persona_id="CEO",
                summary="Hạn Thiên Không — nóng vội, áp lực",
                mood_modifier=0.1,
            ),
        },
    )


def test_format_relationships_for_reasoning_includes_last_speaker() -> None:
    matrix = _sample_matrix()
    block = format_relationships_for_reasoning(
        matrix,
        speaker_id="CEO",
        last_speaker="SALE",
    )
    assert "[QUAN HỆ & TÂM TRẠNG" in block
    assert "SALE" in block
    assert "relationship_lens" in block
    assert "Dị ứng" in block or "căm ghét" in block


def test_infer_session_mood_from_recent_friction() -> None:
    matrix = _sample_matrix()
    messages = [
        DialogueTurn(
            speaker_id="SALE",
            speaker_name="Sales",
            content="Anh CEO sai hoàn toàn, không chấp nhận cách này.",
            turn_index=1,
        ),
    ]
    cues = infer_session_mood(
        matrix,
        "CEO",
        recent_messages=messages,
        last_speaker="SALE",
    )
    assert any("SALE" in c or "căng" in c.lower() for c in cues)


def test_build_reasoning_user_message_includes_relationship_block() -> None:
    matrix = _sample_matrix()
    message = build_reasoning_user_message(
        "[Cuộc họp: Keos]",
        speaker_id="CEO",
        relationship_matrix=matrix,
        last_speaker="SALE",
        enable_relationship_reasoning=True,
    )
    assert "[QUAN HỆ & TÂM TRẠNG" in message
    assert "[INTERNAL REASONING]" in message


def test_format_relationships_for_reasoning_includes_allies() -> None:
    matrix = RelationshipMatrix(
        participants=["MARKETING", "SALE", "CFO"],
        edges={
            "MARKETING": {
                "SALE": RelationshipEdge(
                    source_id="MARKETING",
                    target_id="SALE",
                    affinity=0.45,
                    conflict_weight=0.3,
                    faction="growth",
                    notes="Hợp tính cánh, hỗ trợ bọc lót lẫn nhau với Sales.",
                ),
                "CFO": RelationshipEdge(
                    source_id="MARKETING",
                    target_id="CFO",
                    affinity=-0.2,
                    conflict_weight=0.7,
                    notes="Xung đột ngân sách.",
                ),
            },
            "SALE": {},
            "CFO": {},
        },
        factions={"growth": ["MARKETING", "SALE"]},
    )
    block = format_relationships_for_reasoning(
        matrix,
        speaker_id="MARKETING",
        last_speaker="SALE",
    )
    assert "Đồng minh" in block or "tích cực" in block
    assert "ủng hộ" in block or "bảo vệ" in block
    assert "growth" in block
    assert "tích cực" in block or "tin tưởng" in block


def test_parse_monologue_reads_relationship_lens() -> None:
    raw = """
    {
      "relationship_lens": "Ghét Sale vì hay tuồn chiết khấu.",
      "absorb": "Luận điểm có phần đúng.",
      "compromise_space": "Chia pha.",
      "stance_shift": 0.2
    }
    """
    monologue = parse_monologue(raw)
    assert monologue is not None
    assert "Ghét Sale" in monologue.relationship_lens
