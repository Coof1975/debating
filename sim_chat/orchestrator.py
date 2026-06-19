"""Orchestrator: honor direct requests, otherwise pick by conflict-weighted selection."""

from __future__ import annotations

import json
import re
from collections import Counter

from .domain import get_domain
from .llm import LLMProvider
from .models import DialogueTurn, MeetingState, RelationshipMatrix, SpeakerSelection, SpeakerSelectionMethod
from .transcript import format_transcript_for_context

# Re-export enterprise defaults for backward compatibility in tests/imports.
from .domains.enterprise import DISPLAY_ALIASES, ORCHESTRATOR_SYSTEM_PROMPT, ROLE_ALIASES, TOPIC_ROLE_KEYWORDS

# Tunable weights for conflict-first speaker selection.
CONFLICT_WEIGHT = 2.5
AFFINITY_TENSION_WEIGHT = 1.8
FACTION_OPPOSITION_BONUS = 0.55
TOPIC_RELEVANCE_BONUS = 0.45
SPEAK_BALANCE_PENALTY = 0.10
CONFLICT_SHORTCUT_MIN_SCORE = 1.20
CONFLICT_SHORTCUT_MIN_GAP = 0.35
LLM_OVERRIDE_MIN_GAP = 0.40

REQUEST_MARKERS = (
    "trả lời",
    "phản hồi",
    "cho ý kiến",
    "nói rõ",
    "nói thẳng",
    "giải thích",
    "làm rõ",
    "xin ý kiến",
    "muốn nghe",
    "nhờ",
    "mời",
    "hỏi",
    "em ơi",
    "anh ơi",
    "chị ơi",
    "ông ơi",
    "bà ơi",
)

def _speak_counts(messages: list[DialogueTurn], participant_ids: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter({pid: 0 for pid in participant_ids})
    for turn in messages:
        counts[turn.speaker_id] += 1
    return counts


def _faction_for(matrix: RelationshipMatrix, role_id: str) -> set[str]:
    return {name for name, members in matrix.factions.items() if role_id in members}


def _topic_bonus(role_id: str, last_content: str, *, domain_id: str) -> float:
    lowered = last_content.lower()
    keywords = get_domain(domain_id).topic_role_keywords.get(role_id, ())
    hits = sum(1 for keyword in keywords if keyword in lowered)
    if hits == 0:
        return 0.0
    return TOPIC_RELEVANCE_BONUS * min(hits, 3)


def _relationship_notes_bonus(matrix: RelationshipMatrix, last_speaker: str, candidate: str, last_content: str) -> float:
    edge = matrix.edge(candidate, last_speaker)
    if not edge or not edge.notes:
        return 0.0
    lowered_content = last_content.lower()
    tokens = [token for token in re.findall(r"[\wÀ-ỹ]{4,}", lowered_content) if len(token) >= 4]
    if not tokens:
        return 0.0
    notes = edge.notes.lower()
    overlap = sum(1 for token in tokens[:12] if token in notes)
    return 0.08 * min(overlap, 4)


def score_conflict_candidate(
    state: MeetingState,
    candidate: str,
    *,
    last_speaker: str,
    speak_counts: Counter[str],
    last_content: str,
) -> float:
    """Higher score = stronger reason to let this persona respond next."""
    if candidate == last_speaker:
        return -999.0

    matrix = state["relationship_matrix"]
    forward = matrix.edge(last_speaker, candidate)
    backward = matrix.edge(candidate, last_speaker)

    score = 0.0
    if forward:
        score += forward.conflict_weight * CONFLICT_WEIGHT
        score += max(0.0, -forward.affinity) * AFFINITY_TENSION_WEIGHT
    if backward:
        score += backward.conflict_weight * (CONFLICT_WEIGHT * 0.6)
        score += max(0.0, -backward.affinity) * (AFFINITY_TENSION_WEIGHT * 0.6)

    last_factions = _faction_for(matrix, last_speaker)
    cand_factions = _faction_for(matrix, candidate)
    if last_factions and cand_factions and not (last_factions & cand_factions):
        score += FACTION_OPPOSITION_BONUS

    score += _topic_bonus(candidate, last_content, domain_id=state["config"].domain_id)
    score += _relationship_notes_bonus(matrix, last_speaker, candidate, last_content)

    participant_ids = state["participant_ids"]
    avg_speaks = sum(speak_counts.values()) / max(1, len(participant_ids))
    score -= SPEAK_BALANCE_PENALTY * max(0.0, speak_counts[candidate] - avg_speaks)

    return score


def rank_candidates_by_conflict(state: MeetingState) -> list[tuple[str, float]]:
    participant_ids = state["participant_ids"]
    last_speaker = state.get("last_speaker") or ""
    messages = state["messages"]
    speak_counts = _speak_counts(messages, participant_ids)
    last_content = messages[-1].content if messages else ""

    ranked = [
        (
            candidate,
            score_conflict_candidate(
                state,
                candidate,
                last_speaker=last_speaker,
                speak_counts=speak_counts,
                last_content=last_content,
            ),
        )
        for candidate in participant_ids
        if candidate != last_speaker
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def _format_conflict_ranking(state: MeetingState) -> str:
    ranked = rank_candidates_by_conflict(state)
    if not ranked:
        return "Không có ứng viên hợp lệ."

    lines: list[str] = []
    for index, (role_id, score) in enumerate(ranked, start=1):
        name = state["persona_names"].get(role_id, role_id)
        matrix = state["relationship_matrix"]
        last_speaker = state.get("last_speaker") or ""
        edge = matrix.edge(last_speaker, role_id)
        detail = ""
        if edge:
            detail = (
                f"affinity={edge.affinity:.2f}, xung đột={edge.conflict_weight:.2f}"
            )
        lines.append(f"{index}. {role_id} ({name}) — điểm xung đột={score:.2f}. {detail}")
    return "\n".join(lines)


def _build_alias_map(state: MeetingState) -> list[tuple[str, str]]:
    """Return (alias, role_id) pairs sorted longest-first for matching."""
    domain = get_domain(state["config"].domain_id)
    pairs: list[tuple[str, str]] = []
    for role_id in state["participant_ids"]:
        pairs.append((role_id.lower(), role_id))
        name = state["persona_names"].get(role_id, "")
        if name:
            pairs.append((name.lower(), role_id))
            for part in name.split():
                if len(part) > 2:
                    pairs.append((part.lower(), role_id))
        for alias, mapped in domain.role_aliases.items():
            if mapped == role_id:
                pairs.append((alias, role_id))
        for alias, mapped in domain.display_aliases.items():
            if mapped == role_id:
                pairs.append((alias, role_id))

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for alias, role_id in sorted(pairs, key=lambda item: len(item[0]), reverse=True):
        if alias in seen:
            continue
        seen.add(alias)
        unique.append((alias, role_id))
    return unique


def _looks_like_request(content: str) -> bool:
    lowered = content.lower()
    if any(marker in lowered for marker in REQUEST_MARKERS):
        return True
    if re.search(r"\b(?:anh|chị|em|ông|bà)\s+[\wÀ-ỹ]+\s*[,:?]", lowered):
        return True
    return "?" in content


def detect_requested_speaker(state: MeetingState) -> str | None:
    """If the previous turn explicitly asks someone to answer, return their role id."""
    messages = state["messages"]
    if not messages:
        return None

    last_turn = messages[-1]
    content = last_turn.content
    if not _looks_like_request(content):
        return None

    lowered = content.lower()
    for alias, role_id in _build_alias_map(state):
        if role_id == last_turn.speaker_id:
            continue
        if alias in lowered:
            return role_id
    return None


def _format_transcript_from_state(state: MeetingState) -> str:
    config = state["config"]
    return format_transcript_for_context(
        state,
        style="orchestrator",
        fallback_limit=config.transcript_window_orchestrator,
    )


def _next_turn_index(state: MeetingState) -> int:
    return state["turn_index"] + 1


def _build_selection(
    state: MeetingState,
    *,
    next_speaker: str,
    reason: str,
    method: SpeakerSelectionMethod,
) -> SpeakerSelection:
    return SpeakerSelection(
        next_speaker=next_speaker,
        reason=reason,
        method=method,
        turn_index=_next_turn_index(state),
    )


def _format_conflict_reason(
    state: MeetingState,
    role: str,
    score: float,
    *,
    runner_up_score: float | None = None,
) -> str:
    last_speaker = state.get("last_speaker") or ""
    name = state["persona_names"].get(role, role)
    last_name = state["persona_names"].get(last_speaker, last_speaker)
    matrix = state["relationship_matrix"]
    edge = matrix.edge(last_speaker, role)

    parts = [f"Phản biện {last_name} — điểm xung đột {score:.2f}"]
    if edge:
        parts.append(
            f"(affinity={edge.affinity:.2f}, xung đột={edge.conflict_weight:.2f})"
        )
    if runner_up_score is not None:
        gap = score - runner_up_score
        if gap >= CONFLICT_SHORTCUT_MIN_GAP:
            parts.append(f"; khoảng cách với ứng viên thứ hai {gap:.2f}")
    return f"{name} ({role}): {' '.join(parts)}"


def _parse_orchestrator_response(
    raw: str,
    participant_ids: list[str],
) -> tuple[str | None, str | None]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
        role = str(payload.get("next_speaker", "")).strip().upper()
        reason = str(payload.get("reason", "")).strip()
        if role in participant_ids:
            return role, reason or None
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    for role_id in participant_ids:
        if re.search(rf"\b{re.escape(role_id)}\b", cleaned, re.IGNORECASE):
            return role_id, None
    return None, None


def _selection_by_conflict(
    state: MeetingState,
    *,
    method: SpeakerSelectionMethod,
    reason_prefix: str = "",
) -> SpeakerSelection:
    ranked = rank_candidates_by_conflict(state)
    if ranked:
        role, score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else None
        reason = _format_conflict_reason(state, role, score, runner_up_score=runner_up)
        if reason_prefix:
            reason = f"{reason_prefix}{reason}"
        return _build_selection(state, next_speaker=role, reason=reason, method=method)

    participant_ids = state["participant_ids"]
    last_speaker = state.get("last_speaker") or ""
    candidates = [pid for pid in participant_ids if pid != last_speaker]
    fallback = candidates[0] if candidates else participant_ids[0]
    return _build_selection(
        state,
        next_speaker=fallback,
        reason=f"{reason_prefix}Không có ứng viên xung đột hợp lệ; chọn {fallback}.",
        method=method,
    )


def _maybe_conflict_shortcut(state: MeetingState) -> SpeakerSelection | None:
    """Skip LLM when one antagonist clearly should respond."""
    ranked = rank_candidates_by_conflict(state)
    if len(ranked) < 1:
        return None
    top_role, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score >= CONFLICT_SHORTCUT_MIN_SCORE and (top_score - second_score) >= CONFLICT_SHORTCUT_MIN_GAP:
        reason = _format_conflict_reason(
            state,
            top_role,
            top_score,
            runner_up_score=second_score,
        )
        return _build_selection(
            state,
            next_speaker=top_role,
            reason=f"Xung đột rõ ràng — {reason}",
            method=SpeakerSelectionMethod.CONFLICT_SHORTCUT,
        )
    return None


def _apply_conflict_override(
    state: MeetingState,
    chosen: str,
    llm_reason: str | None,
) -> SpeakerSelection:
    """Prefer top conflict scorer if LLM picked a much weaker antagonist."""
    ranked = rank_candidates_by_conflict(state)
    if not ranked:
        return _build_selection(
            state,
            next_speaker=chosen,
            reason=llm_reason or f"LLM chọn {chosen}.",
            method=SpeakerSelectionMethod.LLM,
        )

    scores = dict(ranked)
    top_role, top_score = ranked[0]
    chosen_score = scores.get(chosen, 0.0)
    if top_role != chosen and (top_score - chosen_score) >= LLM_OVERRIDE_MIN_GAP:
        runner_up = ranked[1][1] if len(ranked) > 1 else None
        reason = _format_conflict_reason(state, top_role, top_score, runner_up_score=runner_up)
        reason = (
            f"Heuristic override: LLM chọn {chosen} (điểm {chosen_score:.2f}); "
            f"ưu tiên {top_role} — {reason}"
        )
        return _build_selection(
            state,
            next_speaker=top_role,
            reason=reason,
            method=SpeakerSelectionMethod.CONFLICT_OVERRIDE,
        )

    reason = llm_reason or _format_conflict_reason(state, chosen, chosen_score)
    return _build_selection(
        state,
        next_speaker=chosen,
        reason=reason,
        method=SpeakerSelectionMethod.LLM,
    )


def select_next_speaker_llm(state: MeetingState, llm: LLMProvider) -> SpeakerSelection:
    """Ask the LLM who should speak next, with conflict-weighted guardrails."""
    participant_ids = state["participant_ids"]
    last_speaker = state.get("last_speaker") or "—"
    matrix = state["relationship_matrix"]
    speak_counts = _speak_counts(state["messages"], participant_ids)

    shortcut = _maybe_conflict_shortcut(state)
    if shortcut:
        return shortcut

    roster = "\n".join(
        f"- {role_id}: {state['persona_names'].get(role_id, role_id)} "
        f"(đã nói {speak_counts[role_id]} lần)"
        for role_id in participant_ids
    )
    rel_overview = "\n".join(
        f"{role_id}: {matrix.summary_for(role_id)}"
        for role_id in participant_ids
    )
    conflict_ranking = _format_conflict_ranking(state)

    user_message = f"""\
Chủ đề: {state["meeting_topic"]}
Last speaker: {last_speaker}

Danh sách participant_ids hợp lệ: {", ".join(participant_ids)}

Thành viên:
{roster}

Ma trận quan hệ (chi tiết):
{rel_overview}

Bảng xếp hạng xung đột với last_speaker (điểm cao = nên phản biện):
{conflict_ranking}

Biên bản gần nhất:
{_format_transcript_from_state(state)}

Chọn next_speaker có xung đột/lợi ích mạnh nhất với last_speaker về luận điểm vừa nêu.
"""
    raw = llm.generate(get_domain(state["config"].domain_id).prompts.orchestrator_system, user_message)
    chosen, llm_reason = _parse_orchestrator_response(raw, participant_ids)
    if chosen and chosen != last_speaker:
        return _apply_conflict_override(state, chosen, llm_reason)
    if chosen == last_speaker:
        return _selection_by_conflict(
            state,
            method=SpeakerSelectionMethod.HEURISTIC_FALLBACK,
            reason_prefix="LLM chọn lại last_speaker; fallback heuristic — ",
        )
    return _selection_by_conflict(
        state,
        method=SpeakerSelectionMethod.HEURISTIC_FALLBACK,
        reason_prefix="LLM không trả về speaker hợp lệ; fallback heuristic — ",
    )


def select_next_speaker(state: MeetingState, llm: LLMProvider) -> SpeakerSelection:
    """Pick the next persona: direct request first, else conflict-weighted orchestration."""
    participant_ids = state["participant_ids"]

    if not state["messages"]:
        opener = state["config"].opening_speaker
        next_speaker = opener if opener in participant_ids else participant_ids[0]
        return _build_selection(
            state,
            next_speaker=next_speaker,
            reason="Mở đầu cuộc họp theo cấu hình (opening_speaker).",
            method=SpeakerSelectionMethod.OPENING,
        )

    requested = detect_requested_speaker(state)
    if requested and requested in participant_ids:
        name = state["persona_names"].get(requested, requested)
        return _build_selection(
            state,
            next_speaker=requested,
            reason=f"{name} ({requested}) được chỉ định trực tiếp trong lượt trước.",
            method=SpeakerSelectionMethod.DIRECT_REQUEST,
        )

    return select_next_speaker_llm(state, llm)
