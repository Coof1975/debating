"""Tests for post-meeting insight report generation."""

from __future__ import annotations

from pathlib import Path

from sim_chat.config import MeetingConfig
from sim_chat.insight import (
    _describe_termination_context,
    _format_record_for_insight,
    generate_insight_report,
)
from sim_chat.models import (
    DialogueTurn,
    MeetingRecord,
    RelationshipMatrix,
    TerminationReason,
)
from sim_chat.persistence import load_meeting_record

MEETINGS_DIR = Path(__file__).resolve().parents[1] / "data" / "meetings"


def test_describe_stagnation_termination() -> None:
    record = load_meeting_record("1e0aa0b7-3bf7-4a2f-ac54-ecb06dab3ca2", storage_dir=MEETINGS_DIR)
    context = _describe_termination_context(record)

    assert record.termination_reason == TerminationReason.STAGNATION
    assert "stagnation" in context
    assert "5" in context
    assert "Tranh luận lặp lại" in context


def test_insight_report_includes_termination_section() -> None:
    record = load_meeting_record("1e0aa0b7-3bf7-4a2f-ac54-ecb06dab3ca2", storage_dir=MEETINGS_DIR)
    report = generate_insight_report(record)

    assert "Lý do kết thúc" in report


def test_describe_consensus_termination() -> None:
    record = MeetingRecord(
        meeting_id="test",
        topic="Test topic",
        config=MeetingConfig(consensus_threshold=0.8),
        relationship_matrix=RelationshipMatrix(),
        messages=[],
        loop_count=2,
        stagnation_score=0,
        termination_reason=TerminationReason.CONSENSUS,
        metadata={
            "secretary_verdict": {
                "consensus_score": 0.9,
                "has_consensus": True,
                "key_stakeholder_approval": True,
                "summary": "Các bên thống nhất triển khai.",
            }
        },
    )
    context = _describe_termination_context(record)

    assert "consensus" in context
    assert "0.9" in context
    assert "đồng thuận" in context.lower()


def _sample_record_with_hidden_turns() -> MeetingRecord:
    return MeetingRecord(
        meeting_id="hidden-test",
        topic="Budget alignment",
        config=MeetingConfig(),
        relationship_matrix=RelationshipMatrix(),
        messages=[
            DialogueTurn(
                speaker_id="CFO",
                speaker_name="CFO Name",
                content="Chúng ta không thể tăng ngân sách quá 15%.",
                round_number=1,
                turn_index=1,
            ),
            DialogueTurn(
                speaker_id="MARKETING",
                speaker_name="Marketing Name",
                content="Cần ít nhất 22% để đạt KPI digital.",
                round_number=1,
                turn_index=2,
            ),
        ],
        loop_count=1,
        stagnation_score=0,
        termination_reason=TerminationReason.MAX_ROUNDS,
        metadata={
            "hidden_turns": [
                {
                    "speaker_id": "CFO",
                    "turn_index": 1,
                    "monologue": {
                        "absorb": "Marketing có điểm hợp lý về KPI.",
                        "compromise_space": "Có thể chia pha ngân sách Q2.",
                        "stance_shift": 0.3,
                    },
                },
                {
                    "speaker_id": "MARKETING",
                    "turn_index": 2,
                    "monologue": {
                        "absorb": "CFO lo dòng tiền là đúng.",
                        "compromise_space": "Giảm scope campaign tháng đầu.",
                        "stance_shift": 0.4,
                    },
                },
            ]
        },
    )


def test_format_record_includes_hidden_turns() -> None:
    body = _format_record_for_insight(_sample_record_with_hidden_turns())

    assert "Suy nghĩ nội bộ: có 2 lượt" in body
    assert "[Nội bộ]" in body
    assert "absorb: Marketing có điểm hợp lý về KPI." in body
    assert "compromise_space: Có thể chia pha ngân sách Q2." in body
    assert "[Công khai] Chúng ta không thể tăng ngân sách quá 15%." in body


def test_insight_report_includes_motivation_section() -> None:
    report = generate_insight_report(_sample_record_with_hidden_turns())

    assert "Động cơ" in report


def _sample_record_with_blackboard() -> MeetingRecord:
    return MeetingRecord(
        meeting_id="blackboard-test",
        topic="Chiết khấu Keos",
        config=MeetingConfig(
            consensus_threshold=0.8,
            key_stakeholders=["CEO"],
        ),
        relationship_matrix=RelationshipMatrix(),
        messages=[
            DialogueTurn(
                speaker_id="CFO",
                speaker_name="CFO",
                content="Chi phí vận hành tăng 12%.",
                round_number=1,
                turn_index=1,
            ),
        ],
        loop_count=1,
        stagnation_score=0,
        termination_reason=TerminationReason.CONSENSUS,
        metadata={
            "working_proposals": [
                {
                    "id": "p1_cfo_abc123",
                    "author_id": "CFO",
                    "turn_index": 1,
                    "title": "Chiết khấu 18% chia pha",
                    "description": "18% cho đại lý cấp 1, review sau Q2.",
                    "approvals": {
                        "CEO": {"persona_id": "CEO", "score": 0.85, "concerns": ""},
                        "CFO": {"persona_id": "CFO", "score": 0.9, "concerns": ""},
                    },
                    "aggregate_score": 0.875,
                    "status": "active",
                    "parent_id": None,
                }
            ],
            "shared_facts": [
                {
                    "id": "f1_cfo_def456",
                    "source_speaker_id": "CFO",
                    "turn_index": 1,
                    "fact": "Chi phí vận hành tăng 12%",
                    "category": "financial",
                    "confidence": 0.9,
                    "accepted_by": {"CEO": True, "MARKETING": False},
                }
            ],
            "secretary_verdict": {
                "consensus_score": 0.85,
                "has_consensus": True,
                "key_stakeholder_approval": True,
                "summary": "Thống nhất chiết khấu chia pha.",
            },
        },
    )


def test_format_record_includes_working_proposals_and_shared_facts() -> None:
    body = _format_record_for_insight(_sample_record_with_blackboard())

    assert "WORKING PROPOSALS" in body
    assert "Chiết khấu 18% chia pha" in body
    assert "aggregate_score=88%" in body or "điểm chung 88%" in body
    assert "SHARED FACTS" in body
    assert "Chi phí vận hành tăng 12%" in body
    assert "MARKETING=bác bỏ" in body


def test_describe_consensus_includes_best_proposal() -> None:
    context = _describe_termination_context(_sample_record_with_blackboard())

    assert "Đề xuất hàng đầu" in context
    assert "Chiết khấu 18% chia pha" in context
    assert "Proposal aggregate đạt ngưỡng" in context
