"""Tests for post-meeting insight report generation."""

from __future__ import annotations

from pathlib import Path

from sim_chat.config import MeetingConfig
from sim_chat.insight import _describe_termination_context, generate_insight_report
from sim_chat.models import MeetingRecord, RelationshipMatrix, TerminationReason
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
