"""Tests for meeting resume and facilitator turn injection."""

from __future__ import annotations

from sim_chat.bootstrap import create_initial_state_from_bundle
from sim_chat.config import MeetingConfig
from sim_chat.domain import load_domain_participants
from sim_chat.graph import iter_meeting_events, run_meeting
from sim_chat.llm import create_llm_provider
from sim_chat.models import (
    FACILITATOR_SPEAKER_ID,
    DialogueTurn,
    SpeakerSelectionMethod,
    TerminationReason,
)
from sim_chat.orchestrator import select_next_speaker
from sim_chat.resume import append_facilitator_turn, prepare_extension_state, state_from_record


def _compact_config(**overrides) -> MeetingConfig:
    base = {
        "domain_id": "tutoring",
        "meeting_topic": "Giải phương trình bậc hai",
        "max_turns": 2,
        "participant_ids": ["TUTOR", "STUDENT_A", "STUDENT_B"],
        "use_mock": True,
        "enable_working_proposals": False,
        "enable_shared_facts": False,
        "enable_stagnation_check": False,
        "extension_turn_budget": 2,
    }
    base.update(overrides)
    return MeetingConfig(**base)


def _initial_state(config: MeetingConfig):
    bundle = load_domain_participants("tutoring")
    return create_initial_state_from_bundle(config, bundle)


def test_state_from_record_restores_metadata() -> None:
    config = _compact_config()
    initial = _initial_state(config)
    record = run_meeting(config, use_mock=True, initial_state=initial)

    hydrated = state_from_record(
        record,
        prompts=initial["prompts"],
        persona_names=initial["persona_names"],
    )

    assert hydrated["turn_index"] == len(record.messages)
    assert hydrated["terminated"] is False
    assert hydrated["termination_reason"] == ""
    assert len(hydrated["messages"]) == len(record.messages)
    assert hydrated["relationship_matrix"] == record.relationship_matrix


def test_append_facilitator_turn() -> None:
    config = _compact_config()
    initial = _initial_state(config)
    record = run_meeting(config, use_mock=True, initial_state=initial)
    state = state_from_record(
        record,
        prompts=initial["prompts"],
        persona_names=initial["persona_names"],
    )
    prior_turn_index = state["turn_index"]
    prior_loop = state["loop_count"]

    updated = append_facilitator_turn(state, "  Bổ sung ngân sách 500 triệu.  ")

    assert updated["turn_index"] == prior_turn_index + 1
    assert updated["loop_count"] == prior_loop
    assert updated["last_speaker"] == FACILITATOR_SPEAKER_ID
    assert updated["messages"][-1].speaker_id == FACILITATOR_SPEAKER_ID
    assert updated["messages"][-1].content == "Bổ sung ngân sách 500 triệu."


def test_prepare_extension_state_resets_stagnation_and_extends_max_turns() -> None:
    config = _compact_config(extension_stagnation_reset=True, extension_turn_budget=3)
    initial = _initial_state(config)
    record = run_meeting(config, use_mock=True, initial_state=initial)
    record = record.model_copy(update={"stagnation_score": 4})

    state = prepare_extension_state(
        record,
        "CFO phản hồi về ngân sách mới.",
        prompts=initial["prompts"],
        persona_names=initial["persona_names"],
    )

    assert state["stagnation_score"] == 0
    assert state["secretary_verdict"] is None
    assert state["config"].max_turns == state["turn_index"] + 3
    assert state["config"].min_turns_before_consensus == state["config"].max_turns + 1
    assert state["messages"][-1].speaker_id == FACILITATOR_SPEAKER_ID


def test_orchestrator_selects_named_persona_after_facilitator() -> None:
    config = _compact_config()
    initial = _initial_state(config)
    state = append_facilitator_turn(
        {
            **initial,
            "messages": [
                DialogueTurn(
                    speaker_id="TUTOR",
                    speaker_name="TUTOR",
                    content="Chốt phương án.",
                    turn_index=1,
                    round_number=1,
                )
            ],
            "turn_index": 1,
            "last_speaker": "TUTOR",
        },
        "STUDENT_A phản hồi ngay về tác động ngân sách 500 triệu.",
    )
    llm = create_llm_provider(config, use_mock=True, persona_names=initial["persona_names"])
    selection = select_next_speaker(state, llm)

    assert selection.next_speaker == "STUDENT_A"
    assert selection.method == SpeakerSelectionMethod.FACILITATOR_DIRECTIVE


def test_resume_meeting_adds_persona_turns_after_facilitator() -> None:
    config = _compact_config(max_turns=2, extension_turn_budget=2)
    initial = _initial_state(config)
    record = run_meeting(config, use_mock=True, initial_state=initial)
    assert len(record.messages) == 2
    assert record.termination_reason == TerminationReason.MAX_ROUNDS

    state = prepare_extension_state(
        record,
        "Sếp duyệt thêm 500 triệu ngân sách. STUDENT_A phản hồi.",
        prompts=initial["prompts"],
        persona_names=initial["persona_names"],
    )

    events = list(
        iter_meeting_events(
            state["config"],
            use_mock=True,
            initial_state=state,
            meeting_id=record.meeting_id,
        )
    )
    completed = events[-1]["data"]
    extended_record = completed["record"]

    assert completed["turn_count"] > len(record.messages)
    facilitator_turns = [
        turn for turn in extended_record["messages"] if turn["speaker_id"] == FACILITATOR_SPEAKER_ID
    ]
    assert len(facilitator_turns) == 1
    persona_turns_after = [
        turn
        for turn in extended_record["messages"]
        if turn["turn_index"] > record.messages[-1].turn_index
        and turn["speaker_id"] != FACILITATOR_SPEAKER_ID
    ]
    assert len(persona_turns_after) >= 1


def test_extension_ignores_stale_consensus_and_runs_budget() -> None:
    config = _compact_config(max_turns=2, extension_turn_budget=3)
    initial = _initial_state(config)
    record = run_meeting(config, use_mock=True, initial_state=initial)
    record = record.model_copy(
        update={
            "termination_reason": TerminationReason.CONSENSUS,
            "metadata": {
                **(record.metadata or {}),
                "secretary_verdict": {
                    "consensus_score": 0.95,
                    "has_consensus": True,
                    "key_stakeholder_approval": True,
                    "summary": "Prior segment reached consensus.",
                },
            },
        }
    )

    state = prepare_extension_state(
        record,
        "Sếp duyệt thêm 500 triệu ngân sách. STUDENT_A và STUDENT_B phản hồi.",
        prompts=initial["prompts"],
        persona_names=initial["persona_names"],
    )

    events = list(
        iter_meeting_events(
            state["config"],
            use_mock=True,
            initial_state=state,
            meeting_id=record.meeting_id,
        )
    )
    completed = events[-1]["data"]
    extended_record = completed["record"]
    persona_turns_after = [
        turn
        for turn in extended_record["messages"]
        if turn["turn_index"] > record.messages[-1].turn_index
        and turn["speaker_id"] != FACILITATOR_SPEAKER_ID
    ]

    assert len(persona_turns_after) >= 2
    assert completed["termination_reason"] != TerminationReason.CONSENSUS.value
