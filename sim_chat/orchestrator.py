"""Orchestrator: honor direct requests, otherwise pick by conflict-weighted selection."""

from __future__ import annotations

import json
import re
from collections import Counter

from .llm import LLMProvider
from .models import DialogueTurn, MeetingState, RelationshipMatrix
from .transcript import format_transcript_for_context
from .relationship import ROLE_ALIASES

ORCHESTRATOR_SYSTEM_PROMPT = """\
Bạn là Điều phối viên cuộc họp (Meeting Orchestrator).
Nhiệm vụ: chọn MỘT người phát biểu tiếp theo để cuộc họp có tranh luận sôi nổi, không monotonous.

Quy tắc (theo thứ tự ưu tiên):
1. Người bị chỉ định trực tiếp trong lượt trước (nếu có).
2. QUAN TRỌNG NHẤT — chọn người có xung đột/lợi ích trái ngược với last_speaker về luận điểm vừa nêu.
   - Dùng ma trận quan hệ và bảng xếp hạng xung đột được cung cấp.
   - Ưu tiên phe đối lập, affinity âm, conflict_weight cao.
   - Tránh chọn đồng minh cùng phe trừ khi họ bị gọi tên.
3. Chọn người có chuyên môn liên quan đến chủ đề vừa được nhắc (ngân sách→CFO, sản xuất→PRODUCT, …).
4. Cân bằng thời lượng chỉ là yếu tố phụ — không xoay vòng máy móc chỉ vì ai nói ít hơn.
5. KHÔNG chọn last_speaker trừ khi bị yêu cầu trả lời trực tiếp.
6. CEO không nói liên tiếp trừ khi cần chốt quyết định.

Trả lời CHỈ bằng JSON hợp lệ:
{"next_speaker": "<ROLE_ID>", "reason": "<lý do ngắn tiếng Việt — nêu xung đột/lợi ích>"}

ROLE_ID phải là một trong danh sách participant_ids được cung cấp.
"""

# Tunable weights for conflict-first speaker selection.
CONFLICT_WEIGHT = 2.5
AFFINITY_TENSION_WEIGHT = 1.8
FACTION_OPPOSITION_BONUS = 0.55
TOPIC_RELEVANCE_BONUS = 0.45
SPEAK_BALANCE_PENALTY = 0.10
CONFLICT_SHORTCUT_MIN_SCORE = 1.20
CONFLICT_SHORTCUT_MIN_GAP = 0.35
LLM_OVERRIDE_MIN_GAP = 0.40

TOPIC_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "CFO": (
        "ngân sách",
        "dòng tiền",
        "biên lợi nhuận",
        "margin",
        "chi phí",
        "công nợ",
        "tài chính",
        "lợi nhuận",
        "giải ngân",
    ),
    "MARKETING": (
        "thương hiệu",
        "marketing",
        "quảng cáo",
        "brand",
        "campaign",
        "ads",
        "tiktok",
        "kol",
    ),
    "SALE": (
        "chiết khấu",
        "đại lý",
        "npp",
        "doanh số",
        "kênh",
        "bán hàng",
        "sales",
        "phân phối",
        "gt",
        "mt",
    ),
    "PRODUCT": (
        "sản xuất",
        "công suất",
        "nhà máy",
        "bao bì",
        "tồn kho",
        "keos",
        "dây chuyền",
        "cảng",
    ),
    "CEO": (
        "chiến lược",
        "quyết định",
        "thị phần",
        "tầm nhìn",
    ),
}

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

DISPLAY_ALIASES: dict[str, str] = {
    "tổng giám đốc": "CEO",
    "giám đốc tài chính": "CFO",
    "trưởng phòng marketing": "MARKETING",
    "giám đốc marketing": "MARKETING",
    "giám đốc kinh doanh": "SALE",
    "giám đốc sales": "SALE",
    "giám đốc sản xuất": "PRODUCT",
    "nhà máy": "PRODUCT",
}


def _speak_counts(messages: list[DialogueTurn], participant_ids: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter({pid: 0 for pid in participant_ids})
    for turn in messages:
        counts[turn.speaker_id] += 1
    return counts


def _faction_for(matrix: RelationshipMatrix, role_id: str) -> set[str]:
    return {name for name, members in matrix.factions.items() if role_id in members}


def _topic_bonus(role_id: str, last_content: str) -> float:
    lowered = last_content.lower()
    keywords = TOPIC_ROLE_KEYWORDS.get(role_id, ())
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

    score += _topic_bonus(candidate, last_content)
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
    pairs: list[tuple[str, str]] = []
    for role_id in state["participant_ids"]:
        pairs.append((role_id.lower(), role_id))
        name = state["persona_names"].get(role_id, "")
        if name:
            pairs.append((name.lower(), role_id))
            for part in name.split():
                if len(part) > 2:
                    pairs.append((part.lower(), role_id))
        for alias, mapped in ROLE_ALIASES.items():
            if mapped == role_id:
                pairs.append((alias, role_id))
        for alias, mapped in DISPLAY_ALIASES.items():
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


def _parse_orchestrator_response(raw: str, participant_ids: list[str]) -> str | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
        role = str(payload.get("next_speaker", "")).strip().upper()
        if role in participant_ids:
            return role
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    for role_id in participant_ids:
        if re.search(rf"\b{re.escape(role_id)}\b", cleaned, re.IGNORECASE):
            return role_id
    return None


def _select_next_speaker_by_conflict(state: MeetingState) -> str:
    """Conflict-first fallback when LLM output is invalid or too weak."""
    ranked = rank_candidates_by_conflict(state)
    if ranked:
        return ranked[0][0]
    participant_ids = state["participant_ids"]
    last_speaker = state.get("last_speaker") or ""
    candidates = [pid for pid in participant_ids if pid != last_speaker]
    return candidates[0] if candidates else participant_ids[0]


def _maybe_conflict_shortcut(state: MeetingState) -> str | None:
    """Skip LLM when one antagonist clearly should respond."""
    ranked = rank_candidates_by_conflict(state)
    if len(ranked) < 1:
        return None
    top_role, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score >= CONFLICT_SHORTCUT_MIN_SCORE and (top_score - second_score) >= CONFLICT_SHORTCUT_MIN_GAP:
        return top_role
    return None


def _apply_conflict_override(state: MeetingState, chosen: str) -> str:
    """Prefer top conflict scorer if LLM picked a much weaker antagonist."""
    ranked = rank_candidates_by_conflict(state)
    if not ranked:
        return chosen
    scores = dict(ranked)
    top_role, top_score = ranked[0]
    chosen_score = scores.get(chosen, 0.0)
    if top_role != chosen and (top_score - chosen_score) >= LLM_OVERRIDE_MIN_GAP:
        return top_role
    return chosen


def select_next_speaker_llm(state: MeetingState, llm: LLMProvider) -> str:
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
    raw = llm.generate(ORCHESTRATOR_SYSTEM_PROMPT, user_message)
    chosen = _parse_orchestrator_response(raw, participant_ids)
    if chosen and chosen != last_speaker:
        return _apply_conflict_override(state, chosen)
    if chosen == last_speaker:
        return _select_next_speaker_by_conflict(state)
    return _select_next_speaker_by_conflict(state)


def select_next_speaker(state: MeetingState, llm: LLMProvider) -> str:
    """Pick the next persona: direct request first, else conflict-weighted orchestration."""
    participant_ids = state["participant_ids"]

    if not state["messages"]:
        opener = state["config"].opening_speaker
        return opener if opener in participant_ids else participant_ids[0]

    requested = detect_requested_speaker(state)
    if requested and requested in participant_ids:
        return requested

    return select_next_speaker_llm(state, llm)
