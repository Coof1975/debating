"""Tests for extension audit helpers in sim_chat.resume."""

from __future__ import annotations

from datetime import datetime, timezone

from sim_chat.config import MeetingConfig
from sim_chat.models import DialogueTurn, MeetingRecord, RelationshipMatrix, TerminationReason
from sim_chat.resume import attach_extension_audit, extension_count_from_record


def _sample_record(*, extensions: list | None = None) -> MeetingRecord:
    metadata: dict = {"participant_ids": ["CEO", "CFO"]}
    if extensions is not None:
        metadata["extensions"] = extensions
    return MeetingRecord(
        meeting_id="m1",
        topic="Test",
        config=MeetingConfig(participant_ids=["CEO", "CFO"]),
        relationship_matrix=RelationshipMatrix(participants=["CEO", "CFO"]),
        messages=[
            DialogueTurn(
                speaker_id="CEO",
                speaker_name="CEO",
                content="Done.",
                turn_index=1,
                round_number=1,
            )
        ],
        loop_count=1,
        stagnation_score=0,
        termination_reason=TerminationReason.MAX_ROUNDS,
        metadata=metadata,
    )


def test_extension_count_from_record_empty() -> None:
    assert extension_count_from_record(_sample_record()) == 0


def test_extension_count_from_record_with_history() -> None:
    record = _sample_record(extensions=[{"index": 1}, {"index": 2}])
    assert extension_count_from_record(record) == 2


def test_attach_extension_audit_appends_entry() -> None:
    record = _sample_record()
    record.messages.extend(
        [
            DialogueTurn(
                speaker_id="FACILITATOR",
                speaker_name="Người tổ chức",
                content="Thêm ngân sách.",
                turn_index=2,
                round_number=1,
            ),
            DialogueTurn(
                speaker_id="CFO",
                speaker_name="CFO",
                content="Phản hồi.",
                turn_index=3,
                round_number=1,
            ),
        ]
    )
    started = datetime(2026, 6, 19, tzinfo=timezone.utc)
    payload = attach_extension_audit(
        record,
        facilitator_content="Thêm ngân sách.",
        significance_reason="Directive mới.",
        forced=False,
        started_at=started,
        prior_message_count=1,
        completed_at=datetime(2026, 6, 19, 1, 0, tzinfo=timezone.utc),
    )
    extensions = payload["metadata"]["extensions"]
    assert len(extensions) == 1
    assert extensions[0]["turns_added"] == 2
    assert extensions[0]["completed_at"].startswith("2026")
