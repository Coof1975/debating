"""Tests for conflict-weighted orchestrator speaker selection."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.llm import create_llm_provider
from sim_chat.models import DialogueTurn, RelationshipEdge, RelationshipMatrix, SpeakerSelectionMethod
from sim_chat.orchestrator import (
    detect_requested_speaker,
    rank_candidates_by_conflict,
    score_conflict_candidate,
    select_next_speaker,
)


def _minimal_state(
    *,
    last_speaker: str,
    content: str,
    matrix: RelationshipMatrix,
) -> dict:
    return {
        "participant_ids": matrix.participants,
        "persona_names": {pid: pid for pid in matrix.participants},
        "relationship_matrix": matrix,
        "last_speaker": last_speaker,
        "messages": [
            DialogueTurn(
                speaker_id=last_speaker,
                speaker_name=last_speaker,
                content=content,
                round_number=1,
                turn_index=1,
            )
        ],
        "config": MeetingConfig(),
    }


def test_ceo_budget_turn_prefers_cfo_over_marketing() -> None:
    matrix = RelationshipMatrix(
        participants=["CEO", "CFO", "MARKETING"],
        edges={
            "CEO": {
                "CFO": RelationshipEdge(
                    source_id="CEO",
                    target_id="CFO",
                    affinity=-0.35,
                    conflict_weight=0.85,
                ),
                "MARKETING": RelationshipEdge(
                    source_id="CEO",
                    target_id="MARKETING",
                    affinity=0.25,
                    conflict_weight=0.35,
                    faction="growth",
                ),
            },
            "CFO": {
                "CEO": RelationshipEdge(
                    source_id="CFO",
                    target_id="CEO",
                    affinity=-0.35,
                    conflict_weight=0.85,
                ),
            },
            "MARKETING": {
                "CEO": RelationshipEdge(
                    source_id="MARKETING",
                    target_id="CEO",
                    affinity=0.25,
                    conflict_weight=0.35,
                    faction="growth",
                ),
            },
        },
        factions={"growth": ["CEO", "MARKETING"], "caution": ["CFO"]},
    )
    state = _minimal_state(
        last_speaker="CEO",
        content="Tôi đề xuất nâng chiết khấu lên 20% và giải ngân thêm ngân sách marketing.",
        matrix=matrix,
    )

    ranked = rank_candidates_by_conflict(state)
    assert ranked[0][0] == "CFO"
    assert ranked[0][1] > ranked[1][1]


def test_same_faction_scores_lower_than_opposing_faction() -> None:
    matrix = RelationshipMatrix(
        participants=["CEO", "CFO", "MARKETING"],
        edges={
            "CEO": {
                "CFO": RelationshipEdge(
                    source_id="CEO",
                    target_id="CFO",
                    affinity=-0.5,
                    conflict_weight=0.9,
                ),
                "MARKETING": RelationshipEdge(
                    source_id="CEO",
                    target_id="MARKETING",
                    affinity=0.3,
                    conflict_weight=0.3,
                ),
            },
        },
        factions={"growth": ["CEO", "MARKETING"], "caution": ["CFO"]},
    )
    state = _minimal_state(
        last_speaker="CEO",
        content="Cần quyết định ngay.",
        matrix=matrix,
    )
    cfo_score = score_conflict_candidate(
        state,
        "CFO",
        last_speaker="CEO",
        speak_counts={"CEO": 1, "CFO": 0, "MARKETING": 0},
        last_content=state["messages"][-1].content,
    )
    marketing_score = score_conflict_candidate(
        state,
        "MARKETING",
        last_speaker="CEO",
        speak_counts={"CEO": 1, "CFO": 0, "MARKETING": 0},
        last_content=state["messages"][-1].content,
    )
    assert cfo_score > marketing_score


def test_select_opening_speaker_returns_reason() -> None:
    matrix = RelationshipMatrix(participants=["CEO", "CFO"])
    state = {
        "participant_ids": ["CEO", "CFO"],
        "persona_names": {"CEO": "CEO", "CFO": "CFO"},
        "relationship_matrix": matrix,
        "last_speaker": "",
        "messages": [],
        "config": MeetingConfig(opening_speaker="CEO"),
        "turn_index": 0,
        "meeting_topic": "Budget review",
    }
    llm = create_llm_provider(MeetingConfig(use_mock=True), use_mock=True)

    selection = select_next_speaker(state, llm)

    assert selection.next_speaker == "CEO"
    assert selection.method == SpeakerSelectionMethod.OPENING
    assert selection.reason
    assert selection.turn_index == 1


def test_select_direct_request_returns_reason() -> None:
    matrix = RelationshipMatrix(participants=["CEO", "CFO"])
    state = {
        "participant_ids": ["CEO", "CFO"],
        "persona_names": {"CEO": "CEO", "CFO": "CFO"},
        "relationship_matrix": matrix,
        "last_speaker": "CEO",
        "messages": [
            DialogueTurn(
                speaker_id="CEO",
                speaker_name="CEO",
                content="CFO, em trả lời giúp anh về ngân sách?",
                round_number=1,
                turn_index=1,
            )
        ],
        "config": MeetingConfig(),
        "turn_index": 1,
        "meeting_topic": "Budget review",
    }
    llm = create_llm_provider(MeetingConfig(use_mock=True), use_mock=True)

    assert detect_requested_speaker(state) == "CFO"
    selection = select_next_speaker(state, llm)

    assert selection.next_speaker == "CFO"
    assert selection.method == SpeakerSelectionMethod.DIRECT_REQUEST
    assert "CFO" in selection.reason
    assert selection.turn_index == 2


def test_conflict_shortcut_includes_score_reason() -> None:
    matrix = RelationshipMatrix(
        participants=["CEO", "CFO", "MARKETING"],
        edges={
            "CEO": {
                "CFO": RelationshipEdge(
                    source_id="CEO",
                    target_id="CFO",
                    affinity=-0.5,
                    conflict_weight=0.95,
                ),
                "MARKETING": RelationshipEdge(
                    source_id="CEO",
                    target_id="MARKETING",
                    affinity=0.3,
                    conflict_weight=0.2,
                ),
            },
        },
        factions={"growth": ["CEO", "MARKETING"], "caution": ["CFO"]},
    )
    state = _minimal_state(
        last_speaker="CEO",
        content="Tôi đề xuất nâng chiết khấu lên 20% và giải ngân thêm ngân sách marketing.",
        matrix=matrix,
    )
    state["turn_index"] = 1
    state["meeting_topic"] = "Discount policy"
    llm = create_llm_provider(MeetingConfig(use_mock=True), use_mock=True)

    selection = select_next_speaker(state, llm)

    assert selection.next_speaker == "CFO"
    assert selection.method == SpeakerSelectionMethod.CONFLICT_SHORTCUT
    assert "xung đột" in selection.reason.lower()
    assert selection.turn_index == 2
