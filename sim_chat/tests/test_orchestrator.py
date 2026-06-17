"""Tests for conflict-weighted orchestrator speaker selection."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.models import DialogueTurn, RelationshipEdge, RelationshipMatrix
from sim_chat.orchestrator import rank_candidates_by_conflict, score_conflict_candidate


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
