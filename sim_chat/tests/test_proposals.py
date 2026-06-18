"""Tests for shared blackboard (working_proposals)."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.models import (
    DialogueTurn,
    NewProposalDraft,
    ProposalApproval,
    ProposalScore,
    ReasoningResult,
    WorkingProposal,
)
from sim_chat.proposals import (
    active_proposals,
    apply_reasoning_to_proposals,
    check_proposal_consensus,
    compute_aggregate,
    format_proposals_for_context,
    infer_proposal_from_speech,
    make_proposal_id,
    with_aggregate,
)
from sim_chat.reasoning import parse_reasoning_result


def _sample_proposal(*, proposal_id: str = "p1_cfo_abc123", author_id: str = "CFO") -> WorkingProposal:
    proposal = WorkingProposal(
        id=proposal_id,
        author_id=author_id,
        turn_index=1,
        title="Chia pha triển khai",
        description="Giai đoạn 1 thu hẹp marketing.",
    )
    proposal.approvals[author_id] = ProposalApproval(persona_id=author_id, score=0.7)
    return with_aggregate(proposal)


def test_make_proposal_id_is_unique() -> None:
    first = make_proposal_id(turn_index=2, speaker_id="CEO")
    second = make_proposal_id(turn_index=2, speaker_id="CEO")
    assert first.startswith("p2_ceo_")
    assert first != second


def test_compute_aggregate_mean() -> None:
    proposal = _sample_proposal()
    proposal.approvals["CEO"] = ProposalApproval(persona_id="CEO", score=0.9)
    assert compute_aggregate(proposal) == 0.8


def test_parse_reasoning_result_with_proposals() -> None:
    raw = """
    {
      "absorb": "Đồng ý một phần.",
      "compromise_space": "Chia pha.",
      "stance_shift": 0.2,
      "proposal_scores": [{"id": "p1_cfo_abc", "score": 0.75, "concerns": "OK"}],
      "new_proposal": {
        "title": "Pha 1 thu hẹp",
        "description": "Giảm scope marketing 30%.",
        "parent_id": null
      }
    }
    """
    result = parse_reasoning_result(raw)
    assert result is not None
    assert len(result.proposal_scores) == 1
    assert result.proposal_scores[0].score == 0.75
    assert result.new_proposal is not None
    assert result.new_proposal.title == "Pha 1 thu hẹp"


def test_apply_reasoning_scores_existing_proposal() -> None:
    config = MeetingConfig(enable_working_proposals=True)
    proposal = _sample_proposal()
    reasoning = ReasoningResult(
        monologue=parse_reasoning_result(
            '{"absorb":"a","compromise_space":"b","stance_shift":0.1}'
        ).monologue,
        proposal_scores=[ProposalScore(id=proposal.id, score=0.85, concerns="")],
    )
    updated = apply_reasoning_to_proposals(
        [proposal],
        speaker_id="CEO",
        turn_index=2,
        reasoning=reasoning,
        speech="CEO đồng ý phương án.",
        config=config,
    )
    scored = next(p for p in updated if p.id == proposal.id)
    assert "CEO" in scored.approvals
    assert scored.aggregate_score > 0.7


def test_apply_reasoning_creates_new_proposal() -> None:
    config = MeetingConfig(enable_working_proposals=True)
    reasoning = ReasoningResult(
        monologue=parse_reasoning_result(
            '{"absorb":"a","compromise_space":"b","stance_shift":0.1}'
        ).monologue,
        new_proposal=NewProposalDraft(
            title="Phương án mới",
            description="Mô tả chi tiết phương án dung hòa.",
        ),
    )
    updated = apply_reasoning_to_proposals(
        [],
        speaker_id="MARKETING",
        turn_index=3,
        reasoning=reasoning,
        speech="",
        config=config,
    )
    assert len(active_proposals(updated)) == 1
    assert updated[0].author_id == "MARKETING"


def test_infer_proposal_from_speech_marker() -> None:
    draft = infer_proposal_from_speech(
        "Tôi đề xuất chia pha triển khai để giảm rủi ro.",
        speaker_id="CFO",
    )
    assert draft is not None
    assert "đề xuất" in draft.title.lower() or "CFO" in draft.title


def test_format_proposals_for_context_lists_active() -> None:
    text = format_proposals_for_context([_sample_proposal()], participant_ids=["CEO", "CFO"])
    assert "working_proposals" in text
    assert "Chia pha triển khai" in text


def test_check_proposal_consensus_requires_threshold_and_stakeholder() -> None:
    proposal = _sample_proposal()
    proposal.approvals["CFO"].score = 0.82
    proposal.approvals["CEO"] = ProposalApproval(persona_id="CEO", score=0.85)
    proposal = with_aggregate(proposal)

    state = {
        "config": MeetingConfig(
            enable_working_proposals=True,
            proposal_consensus_mode="aggregate",
            consensus_threshold=0.8,
            key_stakeholders=["CEO", "CFO"],
        ),
        "working_proposals": [proposal],
        "turn_index": 5,
    }
    assert check_proposal_consensus(state) is True

    low = proposal.model_copy(deep=True)
    low.approvals["CEO"] = ProposalApproval(persona_id="CEO", score=0.5)
    low = with_aggregate(low)
    state["working_proposals"] = [low]
    assert check_proposal_consensus(state) is False
