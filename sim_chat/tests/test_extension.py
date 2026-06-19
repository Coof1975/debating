"""Tests for post-meeting extension significance classifier."""

from __future__ import annotations

from sim_chat.bootstrap import create_initial_state_from_bundle
from sim_chat.config import MeetingConfig
from sim_chat.domain import load_domain_participants
from sim_chat.extension import evaluate_extension_significance
from sim_chat.graph import run_meeting
from sim_chat.llm import MockLLMProvider
from sim_chat.models import DialogueTurn, MeetingRecord, RelationshipMatrix, TerminationReason


def _record_with_transcript() -> MeetingRecord:
    config = MeetingConfig(
        domain_id="tutoring",
        meeting_topic="Giải phương trình bậc hai",
        max_turns=2,
        participant_ids=["TUTOR", "STUDENT_A", "STUDENT_B"],
        use_mock=True,
        enable_working_proposals=False,
        enable_shared_facts=False,
        enable_stagnation_check=False,
    )
    bundle = load_domain_participants("tutoring")
    initial = create_initial_state_from_bundle(config, bundle)
    return run_meeting(config, use_mock=True, initial_state=initial)


def _minimal_record() -> MeetingRecord:
    return MeetingRecord(
        meeting_id="test-meeting",
        topic="Ngân sách Keos",
        config=MeetingConfig(participant_ids=["CEO", "CFO"]),
        relationship_matrix=RelationshipMatrix(participants=["CEO", "CFO"]),
        messages=[
            DialogueTurn(
                speaker_id="CEO",
                speaker_name="CEO",
                content="Chốt phương án tạm.",
                turn_index=1,
                round_number=1,
            )
        ],
        loop_count=1,
        stagnation_score=0,
        termination_reason=TerminationReason.MAX_ROUNDS,
    )


def test_mock_llm_accepts_budget_directive() -> None:
    record = _record_with_transcript()
    llm = MockLLMProvider()
    result = evaluate_extension_significance(
        record,
        "Sếp vừa duyệt thêm 500 triệu ngân sách Q3.",
        llm=llm,
    )
    assert result.is_significant is True
    assert result.suggestion == "extend"


def test_mock_llm_rejects_thanks() -> None:
    record = _record_with_transcript()
    llm = MockLLMProvider()
    result = evaluate_extension_significance(record, "Cảm ơn mọi người, cuộc họp tốt.", llm=llm)
    assert result.is_significant is False
    assert result.suggestion == "none"


def test_mock_llm_suggests_private_chat() -> None:
    record = _record_with_transcript()
    llm = MockLLMProvider()
    result = evaluate_extension_significance(
        record,
        "CFO giải thích thêm quan điểm cá nhân về chiết khấu.",
        llm=llm,
    )
    assert result.is_significant is False
    assert result.suggestion == "chat_with_persona"


def test_heuristic_fallback_when_json_invalid() -> None:
    record = _minimal_record()

    class BrokenLLM:
        def generate(self, system_prompt: str, user_message: str, *, max_tokens=None) -> str:
            return "not json"

    result = evaluate_extension_significance(
        record,
        "Bổ sung ngân sách marketing thêm 200 triệu.",
        llm=BrokenLLM(),
    )
    assert result.is_significant is True


def test_empty_content_rejected() -> None:
    record = _minimal_record()
    result = evaluate_extension_significance(record, "   ", llm=MockLLMProvider())
    assert result.is_significant is False
