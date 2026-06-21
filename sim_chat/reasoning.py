"""Internal monologue (multi-stage reasoning) before public speech."""

from __future__ import annotations

import json
import re

from .config import MeetingConfig
from .text_quality import text_looks_incomplete
from .llm import LLMProvider
from .models import (
    HiddenTurn,
    InternalMonologue,
    MeetingState,
    NegotiationProfile,
    NewProposalDraft,
    ProposalScore,
    ReasoningResult,
    SharedFact,
    WorkingProposal,
    FactAcceptance,
    DialogueTurn,
    RelationshipMatrix,
)
from .domain import get_domain
from .facts import format_shared_facts_for_reasoning
from .proposals import format_proposals_for_context
from .relationship import format_relationships_for_reasoning


def _domain(config: MeetingConfig):
    return get_domain(config.domain_id)

def strip_json_fence(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_monologue(raw: str) -> InternalMonologue | None:
    result = parse_reasoning_result(raw)
    return result.monologue if result else None


def parse_reasoning_result(raw: str) -> ReasoningResult | None:
    """Parse LLM JSON into full reasoning result including proposal updates."""
    cleaned = strip_json_fence(raw)
    if not cleaned:
        return None
    try:
        payload = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None

    absorb = payload.get("absorb")
    compromise_space = payload.get("compromise_space")
    if not absorb or not compromise_space:
        return None

    try:
        stance_shift = float(payload.get("stance_shift", 0.0))
    except (TypeError, ValueError):
        stance_shift = 0.0
    stance_shift = max(-1.0, min(1.0, stance_shift))

    proposal_scores: list[ProposalScore] = []
    for item in payload.get("proposal_scores") or []:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("id", "")).strip()
        if not proposal_id:
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(1.0, score))
        proposal_scores.append(
            ProposalScore(
                id=proposal_id,
                score=score,
                concerns=str(item.get("concerns", "")).strip(),
            )
        )

    new_proposal: NewProposalDraft | None = None
    raw_new = payload.get("new_proposal")
    if isinstance(raw_new, dict):
        title = str(raw_new.get("title", "")).strip()
        description = str(raw_new.get("description", "")).strip()
        if title and description:
            parent_raw = raw_new.get("parent_id")
            parent_id = str(parent_raw).strip() if parent_raw not in (None, "", "null") else None
            new_proposal = NewProposalDraft(
                title=title,
                description=description,
                parent_id=parent_id,
            )

    fact_acceptances: list[FactAcceptance] = []
    for item in payload.get("fact_acceptances") or []:
        if not isinstance(item, dict):
            continue
        fact_id = str(item.get("fact_id", "")).strip()
        if not fact_id:
            continue
        fact_acceptances.append(
            FactAcceptance(
                fact_id=fact_id,
                accepted=bool(item.get("accepted", True)),
            )
        )

    return ReasoningResult(
        monologue=InternalMonologue(
            absorb=str(absorb).strip(),
            compromise_space=str(compromise_space).strip(),
            stance_shift=stance_shift,
            relationship_lens=str(payload.get("relationship_lens", "")).strip(),
        ),
        proposal_scores=proposal_scores,
        new_proposal=new_proposal,
        fact_acceptances=fact_acceptances,
    )


def build_reasoning_user_message(
    meeting_context: str,
    *,
    config: MeetingConfig,
    negotiation: NegotiationProfile | None = None,
    effective_threshold: float | None = None,
    working_proposals: list[WorkingProposal] | None = None,
    participant_ids: list[str] | None = None,
    shared_facts: list[SharedFact] | None = None,
    speaker_id: str | None = None,
    relationship_matrix: RelationshipMatrix | None = None,
    last_speaker: str = "",
    recent_messages: list[DialogueTurn] | None = None,
    enable_relationship_reasoning: bool = True,
) -> str:
    domain = _domain(config)
    suffix = domain.prompts.reasoning_user_suffix
    blocks: list[str] = [meeting_context.rstrip()]

    if (
        enable_relationship_reasoning
        and relationship_matrix is not None
        and speaker_id is not None
    ):
        rel_block = format_relationships_for_reasoning(
            relationship_matrix,
            speaker_id=speaker_id,
            last_speaker=last_speaker,
            recent_messages=recent_messages,
        )
        blocks.append(rel_block)

    if shared_facts is not None and speaker_id is not None:
        facts_block = format_shared_facts_for_reasoning(shared_facts, speaker_id=speaker_id)
        if facts_block:
            blocks.append(facts_block)

    if working_proposals is not None:
        blocks.append(format_proposals_for_context(working_proposals, participant_ids=participant_ids))

    if negotiation is not None:
        threshold = effective_threshold if effective_threshold is not None else negotiation.compromise_threshold
        retention_pct = int(round(negotiation.min_interest_retention * 100))
        blocks.append(
            f"""[HỒ SƠ ĐÀM PHÁN — lượt này]
- Chỉ số thỏa hiệp hiệu dụng: {threshold:.2f}/1.0
- Tối thiểu giữ lợi ích bộ phận: {retention_pct}%
{domain.prompts.negotiation_pressure_block}"""
        )

    blocks.append(suffix.strip())
    return "\n\n".join(blocks)


def build_speech_user_message(
    meeting_context: str,
    monologue: InternalMonologue,
    *,
    config: MeetingConfig,
    stagnation_score: int = 0,
) -> str:
    relationship_lens = monologue.relationship_lens.strip() or "(không ghi nhận bias quan hệ đặc biệt)"
    speech_block = _domain(config).prompts.speech_instructions.format(
        relationship_lens=relationship_lens,
        absorb=monologue.absorb,
        compromise_space=monologue.compromise_space,
    )
    parts = [meeting_context.rstrip(), speech_block.strip()]
    if stagnation_score >= 1:
        parts.append(
            "[NHẮC LẠI] Phiên đang lặp ý — lượt công khai phải mang thông tin MỚI "
            "(số khác, điều kiện chấp nhận, counter-proposal). Không paraphrase lại absorb/compromise."
        )
    return "\n\n".join(parts)


def effective_compromise_threshold(
    profile: NegotiationProfile,
    *,
    stagnation_score: int = 0,
    enable_dynamic: bool = False,
) -> float:
    base = profile.compromise_threshold
    if not enable_dynamic or stagnation_score <= 0:
        return base
    factor = min(1.0, stagnation_score * 0.12)
    boosted = base * (1.0 + profile.director_sensitivity * factor)
    return min(1.0, boosted)


_SPEECH_LEAK_MARKERS = (
    "[proposal_scores]",
    '"absorb"',
    '"compromise_space"',
    "proposal_id",
    "[internal reasoning]",
    "```json",
)


def _looks_like_leaked_reasoning(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith(("{", "[", "```")):
        return True
    lowered = stripped.lower()
    return any(marker in lowered for marker in _SPEECH_LEAK_MARKERS)


def _looks_like_bad_speech(text: str) -> bool:
    if text_looks_incomplete(text):
        return True
    return _looks_like_leaked_reasoning(text)


def _generate_public_speech(
    llm: LLMProvider,
    *,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
) -> str:
    attempts = [
        user_message,
        (
            f"{user_message.rstrip()}\n\n"
            "[QUAN TRỌNG] Viết 2–6 câu tiếng Việt công khai trong cuộc họp. "
            "Không JSON, không markdown, không proposal_scores. Kết thúc bằng dấu chấm."
        ),
    ]
    last = ""
    for index, prompt in enumerate(attempts):
        tokens = max(max_tokens, 1024) if index else max_tokens
        last = llm.generate(system_prompt, prompt, max_tokens=tokens).strip()
        if not _looks_like_bad_speech(last):
            return last
    return last


def generate_persona_speech(
    llm: LLMProvider,
    *,
    config: MeetingConfig,
    system_prompt: str,
    meeting_context: str,
    negotiation: NegotiationProfile | None = None,
    stagnation_score: int = 0,
    working_proposals: list[WorkingProposal] | None = None,
    participant_ids: list[str] | None = None,
    shared_facts: list[SharedFact] | None = None,
    speaker_id: str | None = None,
    relationship_matrix: RelationshipMatrix | None = None,
    last_speaker: str = "",
    recent_messages: list[DialogueTurn] | None = None,
) -> tuple[str, ReasoningResult | None]:
    """Generate public speech, optionally via hidden internal monologue."""
    if not config.enable_internal_monologue:
        return _generate_public_speech(
            llm,
            system_prompt=system_prompt,
            user_message=meeting_context,
            max_tokens=config.speech_max_tokens,
        ), None

    effective_threshold = None
    if negotiation is not None:
        effective_threshold = effective_compromise_threshold(
            negotiation,
            stagnation_score=stagnation_score,
            enable_dynamic=config.enable_dynamic_compromise,
        )

    domain = _domain(config)
    reasoning_system = f"{system_prompt.rstrip()}{domain.prompts.reasoning_system_suffix}"
    reasoning_user = build_reasoning_user_message(
        meeting_context,
        config=config,
        negotiation=negotiation,
        effective_threshold=effective_threshold,
        working_proposals=working_proposals if config.enable_working_proposals else None,
        participant_ids=participant_ids,
        shared_facts=shared_facts if config.enable_shared_facts else None,
        speaker_id=speaker_id,
        relationship_matrix=relationship_matrix,
        last_speaker=last_speaker,
        recent_messages=recent_messages,
        enable_relationship_reasoning=config.enable_relationship_reasoning,
    )
    raw_reasoning = llm.generate(
        reasoning_system,
        reasoning_user,
        max_tokens=config.reasoning_max_tokens,
        json_mode=True,
    )
    reasoning = parse_reasoning_result(raw_reasoning)
    if reasoning is None:
        content = _generate_public_speech(
            llm,
            system_prompt=system_prompt,
            user_message=meeting_context,
            max_tokens=config.speech_max_tokens,
        )
        return content, None

    speech_user = build_speech_user_message(
        meeting_context,
        reasoning.monologue,
        config=config,
        stagnation_score=stagnation_score,
    )
    content = _generate_public_speech(
        llm,
        system_prompt=system_prompt,
        user_message=speech_user,
        max_tokens=config.speech_max_tokens,
    )
    return content, reasoning


def monologue_state_patch(
    state: MeetingState,
    *,
    speaker_id: str,
    turn_index: int,
    reasoning: ReasoningResult | None,
) -> dict:
    """Build state patch fields for hidden monologue tracking."""
    if reasoning is None:
        return {}

    hidden_turn = HiddenTurn(
        speaker_id=speaker_id,
        turn_index=turn_index,
        monologue=reasoning.monologue,
    )
    last_monologue = dict(state.get("last_monologue") or {})
    last_monologue[speaker_id] = reasoning.monologue
    return {
        "hidden_turns": [hidden_turn],
        "last_monologue": last_monologue,
    }
