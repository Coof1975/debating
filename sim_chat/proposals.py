"""Shared blackboard: working proposals extract, merge, and aggregate."""

from __future__ import annotations

import uuid

from .config import MeetingConfig
from .models import (
    MeetingState,
    NewProposalDraft,
    ProposalApproval,
    ProposalScore,
    ReasoningResult,
    WorkingProposal,
)


def make_proposal_id(*, turn_index: int, speaker_id: str) -> str:
    suffix = uuid.uuid4().hex[:6]
    return f"p{turn_index}_{speaker_id.lower()}_{suffix}"


def active_proposals(proposals: list[WorkingProposal]) -> list[WorkingProposal]:
    return [proposal for proposal in proposals if proposal.status == "active"]


def compute_aggregate(proposal: WorkingProposal) -> float:
    if not proposal.approvals:
        return 0.0
    scores = [approval.score for approval in proposal.approvals.values()]
    return sum(scores) / len(scores)


def with_aggregate(proposal: WorkingProposal) -> WorkingProposal:
    updated = proposal.model_copy(deep=True)
    updated.aggregate_score = round(compute_aggregate(updated), 3)
    return updated


def format_proposals_for_context(
    proposals: list[WorkingProposal],
    *,
    participant_ids: list[str] | None = None,
) -> str:
    active = active_proposals(proposals)
    if not active:
        return "Chưa có đề xuất dung hòa nào trên bàn."

    lines: list[str] = ["ĐỀ XUẤT ĐANG TRÊN BÀN (working_proposals):"]
    for proposal in sorted(active, key=lambda p: p.aggregate_score, reverse=True):
        approval_bits: list[str] = []
        for persona_id, approval in proposal.approvals.items():
            approval_bits.append(f"{persona_id}={approval.score:.0%}")
        approvals_text = ", ".join(approval_bits) if approval_bits else "chưa ai chấm"
        lines.append(
            f"- [{proposal.id}] {proposal.title} (tác giả {proposal.author_id}, "
            f"điểm chung {proposal.aggregate_score:.0%})\n"
            f"  Mô tả: {proposal.description}\n"
            f"  Approvals: {approvals_text}"
        )
        if participant_ids:
            missing = [pid for pid in participant_ids if pid not in proposal.approvals]
            if missing:
                lines.append(f"  Bạn cần chấm điểm proposal này trong reasoning JSON (proposal_scores).")
    return "\n".join(lines)


def format_proposals_for_insight(proposals: list[WorkingProposal]) -> str:
    """Compact proposal summary for post-meeting insight generation."""
    active = active_proposals(proposals)
    if not active:
        return "Chưa có đề xuất dung hòa active trên bàn."

    lines: list[str] = ["WORKING PROPOSALS (đề xuất dung hòa trên bàn):"]
    for proposal in sorted(active, key=lambda p: p.aggregate_score, reverse=True):
        approval_bits: list[str] = []
        for persona_id, approval in proposal.approvals.items():
            bit = f"{persona_id}={approval.score:.0%}"
            if approval.concerns.strip():
                bit += f" (lo ngại: {approval.concerns.strip()})"
            approval_bits.append(bit)
        approvals_text = ", ".join(approval_bits) if approval_bits else "chưa ai chấm"
        lines.append(
            f"- [{proposal.id}] {proposal.title} (tác giả {proposal.author_id}, "
            f"điểm chung {proposal.aggregate_score:.0%})\n"
            f"  Mô tả: {proposal.description}\n"
            f"  Approvals: {approvals_text}"
        )
    return "\n".join(lines)


def infer_proposal_from_speech(
    speech: str,
    *,
    speaker_id: str,
) -> NewProposalDraft | None:
    lowered = speech.lower()
    markers = ("đề xuất", "chia pha", "phương án", "compromise", "pha 1", "giai đoạn")
    if not any(marker in lowered for marker in markers):
        return None
    first_sentence = speech.split(".")[0].strip() or speech[:120].strip()
    title = first_sentence[:80] or f"Đề xuất dung hòa từ {speaker_id}"
    return NewProposalDraft(title=title, description=speech.strip()[:400])


def apply_reasoning_to_proposals(
    proposals: list[WorkingProposal],
    *,
    speaker_id: str,
    turn_index: int,
    reasoning: ReasoningResult | None,
    speech: str,
    config: MeetingConfig,
) -> list[WorkingProposal]:
    if not config.enable_working_proposals:
        return list(proposals)

    updated = [proposal.model_copy(deep=True) for proposal in proposals]

    if reasoning is not None:
        for score in reasoning.proposal_scores:
            proposal = _find_proposal(updated, score.id)
            if proposal is None or proposal.status != "active":
                continue
            proposal.approvals[speaker_id] = ProposalApproval(
                persona_id=speaker_id,
                score=score.score,
                concerns=score.concerns,
            )
            idx = updated.index(proposal)
            updated[idx] = with_aggregate(proposal)

        if reasoning.new_proposal and reasoning.new_proposal.title.strip():
            updated = _add_proposal(
                updated,
                author_id=speaker_id,
                turn_index=turn_index,
                draft=reasoning.new_proposal,
                config=config,
            )
    elif infer_proposal_from_speech(speech, speaker_id=speaker_id) is not None:
        draft = infer_proposal_from_speech(speech, speaker_id=speaker_id)
        if draft is not None:
            updated = _add_proposal(
                updated,
                author_id=speaker_id,
                turn_index=turn_index,
                draft=draft,
                config=config,
            )

    return _cap_active_proposals(updated, config.max_active_proposals)


def _find_proposal(proposals: list[WorkingProposal], proposal_id: str) -> WorkingProposal | None:
    for proposal in proposals:
        if proposal.id == proposal_id:
            return proposal
    return None


def _add_proposal(
    proposals: list[WorkingProposal],
    *,
    author_id: str,
    turn_index: int,
    draft: NewProposalDraft,
    config: MeetingConfig,
) -> list[WorkingProposal]:
    updated = list(proposals)
    if draft.parent_id:
        parent = _find_proposal(updated, draft.parent_id)
        if parent is not None:
            parent.status = "superseded"

    proposal = WorkingProposal(
        id=make_proposal_id(turn_index=turn_index, speaker_id=author_id),
        author_id=author_id,
        turn_index=turn_index,
        title=draft.title.strip(),
        description=draft.description.strip(),
        parent_id=draft.parent_id,
        status="active",
    )
    proposal.approvals[author_id] = ProposalApproval(
        persona_id=author_id,
        score=min(1.0, max(0.55, config.consensus_threshold - 0.1)),
        concerns="",
    )
    updated.append(with_aggregate(proposal))
    return _cap_active_proposals(updated, config.max_active_proposals)


def _cap_active_proposals(
    proposals: list[WorkingProposal],
    max_active: int,
) -> list[WorkingProposal]:
    active = active_proposals(proposals)
    if len(active) <= max_active:
        return proposals

    overflow = len(active) - max_active
    to_supersede = sorted(active, key=lambda p: (p.aggregate_score, p.turn_index))[:overflow]
    superseded_ids = {proposal.id for proposal in to_supersede}
    result: list[WorkingProposal] = []
    for proposal in proposals:
        if proposal.id in superseded_ids and proposal.status == "active":
            copy = proposal.model_copy(deep=True)
            copy.status = "superseded"
            result.append(copy)
        else:
            result.append(proposal)
    return result


def best_active_proposal(proposals: list[WorkingProposal]) -> WorkingProposal | None:
    active = active_proposals(proposals)
    if not active:
        return None
    return max(active, key=lambda p: p.aggregate_score)


def stakeholder_approved_proposal(
    proposal: WorkingProposal,
    *,
    key_stakeholders: list[str],
    threshold: float,
) -> bool:
    for stakeholder_id in key_stakeholders:
        approval = proposal.approvals.get(stakeholder_id)
        if approval and approval.score >= threshold:
            return True
    return False


def check_proposal_consensus(state: MeetingState) -> bool:
    config = state["config"]
    if not config.enable_working_proposals:
        return False
    if config.proposal_consensus_mode == "secretary":
        return False

    proposals = state.get("working_proposals") or []
    best = best_active_proposal(proposals)
    if best is None:
        return False
    if best.aggregate_score < config.consensus_threshold:
        return False
    return stakeholder_approved_proposal(
        best,
        key_stakeholders=config.key_stakeholders,
        threshold=config.consensus_threshold,
    )


def format_proposals_for_secretary(proposals: list[WorkingProposal]) -> str:
    active = active_proposals(proposals)
    if not active:
        return "[]"
    payload = [
        {
            "id": proposal.id,
            "title": proposal.title,
            "description": proposal.description,
            "aggregate_score": proposal.aggregate_score,
            "approvals": {
                persona_id: {"score": approval.score, "concerns": approval.concerns}
                for persona_id, approval in proposal.approvals.items()
            },
        }
        for proposal in sorted(active, key=lambda p: p.aggregate_score, reverse=True)
    ]
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


def proposals_state_patch(proposals: list[WorkingProposal]) -> dict:
    return {"working_proposals": proposals}
