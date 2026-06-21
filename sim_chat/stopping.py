"""Stopping criteria: max rounds, consensus, and stagnation."""

from __future__ import annotations

from .text_quality import text_looks_incomplete
from .embeddings import compute_stagnation_signals
from .models import DialogueTurn, MeetingState, SecretaryVerdict, TerminationReason
from .proposals import check_proposal_consensus


def check_max_turns(state: MeetingState) -> bool:
    config = state["config"]
    if config.max_turns is None:
        return False
    return state["turn_index"] >= config.max_turns


def check_max_rounds(state: MeetingState) -> bool:
    config = state["config"]
    if config.max_turns is not None:
        return False
    participant_count = max(1, len(state["participant_ids"]))
    full_rounds = state["turn_index"] // participant_count
    return full_rounds >= config.max_rounds


def update_stagnation(state: MeetingState) -> int:
    """Increment stagnation_score when the latest turn repeats prior arguments."""
    config = state["config"]
    if not config.enable_stagnation_check:
        return state["stagnation_score"]

    messages = state["messages"]
    if len(messages) < 2:
        return state["stagnation_score"]
    if state["turn_index"] < config.min_turns_before_stagnation:
        return state["stagnation_score"]

    signals = compute_stagnation_signals(messages, config)
    if signals.is_stagnant:
        return state["stagnation_score"] + 1
    return state["stagnation_score"]


def check_stagnation(state: MeetingState) -> bool:
    """Stop only when debate is stagnant and consensus has not been reached."""
    config = state["config"]
    if not config.enable_stagnation_check:
        return False
    if state["turn_index"] < config.min_turns_before_stagnation:
        return False
    if state["stagnation_score"] < config.stagnation_limit:
        return False
    if check_consensus(state):
        return False
    return True


def check_consensus(state: MeetingState) -> bool:
    config = state["config"]
    if not config.enable_consensus_check:
        return False
    if state["turn_index"] < config.min_turns_before_consensus:
        return False

    messages = state.get("messages") or []
    if messages and any(text_looks_incomplete(turn.content) for turn in messages[-3:]):
        return False

    mode = config.proposal_consensus_mode
    if mode in ("aggregate", "both") and check_proposal_consensus(state):
        return True
    if mode == "aggregate":
        return False

    verdict = state.get("secretary_verdict")
    if not verdict:
        return False
    if verdict.has_consensus and verdict.consensus_score >= config.consensus_threshold:
        return True
    if config.stop_on_stakeholder_approval:
        return verdict.key_stakeholder_approval
    return False


def evaluate_termination(state: MeetingState) -> TerminationReason | None:
    if check_max_turns(state) or check_max_rounds(state):
        return TerminationReason.MAX_ROUNDS
    if check_consensus(state):
        return TerminationReason.CONSENSUS
    if check_stagnation(state):
        return TerminationReason.STAGNATION
    return None


def route_after_turn(state: MeetingState) -> str:
    """Conditional edge target: 'secretary', 'orchestrator', or 'end'."""
    reason = evaluate_termination(state)
    if reason is not None:
        return "end"

    config = state["config"]
    if state["turn_index"] < config.min_turns_before_consensus:
        return "orchestrator"

    turns_since = state.get("turns_since_secretary", 0) + 1
    if config.enable_consensus_check and turns_since >= config.consensus_check_interval:
        return "secretary"
    return "orchestrator"


def heuristic_consensus(messages: list[DialogueTurn], config: MeetingConfig) -> SecretaryVerdict:
    """Lightweight consensus estimate without LLM (fallback / dry-run)."""
    if len(messages) < 8:
        return SecretaryVerdict(
            consensus_score=0.2,
            has_consensus=False,
            key_stakeholder_approval=False,
            summary="Chưa đủ lượt phát biểu để đánh giá đồng thuận.",
        )

    if any(text_looks_incomplete(turn.content) for turn in messages[-4:]):
        return SecretaryVerdict(
            consensus_score=0.3,
            has_consensus=False,
            key_stakeholder_approval=False,
            summary="Phát hiện phản hồi bị cắt giữa câu — chưa thể kết luận đồng thuận.",
        )

    recent = messages[-6:]
    agreement_markers = [
        "đồng ý",
        "thống nhất",
        "chấp nhận",
        "ok",
        "triển khai",
        "được",
        "nhất trí",
    ]
    conflict_markers = [
        "không chấp nhận",
        "phản đối",
        "không thể",
        "bất khả",
        "đập bàn",
        "cãi",
    ]

    agreement_hits = 0
    conflict_hits = 0
    for turn in recent:
        lowered = turn.content.lower()
        agreement_hits += sum(1 for marker in agreement_markers if marker in lowered)
        conflict_hits += sum(1 for marker in conflict_markers if marker in lowered)

    total = max(1, agreement_hits + conflict_hits)
    score = agreement_hits / total
    stakeholder_ids = set(config.key_stakeholders)
    stakeholder_agree = any(
        turn.speaker_id in stakeholder_ids
        and any(marker in turn.content.lower() for marker in agreement_markers)
        for turn in recent
    )

    return SecretaryVerdict(
        consensus_score=score,
        has_consensus=score >= config.consensus_threshold and conflict_hits == 0,
        key_stakeholder_approval=stakeholder_agree,
        summary=(
            f"Điểm đồng thuận heuristic: {score:.0%}. "
            f"Đồng ý={agreement_hits}, xung đột={conflict_hits}."
        ),
    )
