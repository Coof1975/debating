"""Build and update the dynamic relationship matrix from seeded personas."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .config import MeetingConfig
from .models import AstrologyProfile, DialogueTurn, RelationshipEdge, RelationshipMatrix

if TYPE_CHECKING:
    from debating.models import Persona


ROLE_ALIASES: dict[str, str] = {
    "ceo": "CEO",
    "cfo": "CFO",
    "marketing": "MARKETING",
    "sale": "SALE",
    "sales": "SALE",
    "kinh doanh": "SALE",
    "product": "PRODUCT",
    "sản xuất": "PRODUCT",
    "nhà máy": "PRODUCT",
    "r&d": "PRODUCT",
}

DEFAULT_FACTIONS: dict[str, list[str]] = {
    "growth": ["CEO", "MARKETING", "SALE"],
    "caution": ["CFO", "PRODUCT"],
}


def _normalize_role(label: str, role_aliases: dict[str, str] | None = None) -> str | None:
    aliases = role_aliases if role_aliases is not None else ROLE_ALIASES
    cleaned = re.sub(r"[^\w\s&/-]", "", label.lower()).strip()
    for alias, role in aliases.items():
        if alias in cleaned:
            return role
    upper = label.strip().upper()
    if upper in set(aliases.values()):
        return upper
    return None


def _parse_relationship_lines(content: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^Với\s+(.+?)\s*[\(:]", line, re.IGNORECASE)
        if match:
            pairs.append((match.group(1).strip(), line))
    return pairs


def _infer_affinity(notes: str) -> tuple[float, float]:
    lowered = notes.lower()
    negative_markers = [
        "dị ứng",
        "bật lại",
        "đập bàn",
        "cãi",
        "xung đột",
        "ép",
        "không chấp nhận",
        "nghi ngờ",
    ]
    positive_markers = [
        "tin tưởng",
        "kỳ vọng",
        "đồng minh",
        "hợp tác",
        "ủng hộ",
    ]
    neg = sum(1 for marker in negative_markers if marker in lowered)
    pos = sum(1 for marker in positive_markers if marker in lowered)
    if neg > pos:
        affinity = max(-1.0, -0.2 - 0.15 * neg)
        conflict = min(1.0, 0.55 + 0.1 * neg)
    elif pos > neg:
        affinity = min(1.0, 0.2 + 0.15 * pos)
        conflict = max(0.2, 0.45 - 0.05 * pos)
    else:
        affinity = 0.0
        conflict = 0.5
    return affinity, conflict


def _extract_astrology(persona_id: str, content: str, *, enabled: bool) -> AstrologyProfile | None:
    if not enabled or not content:
        return None
    birth_match = re.search(
        r"(?:Sinh năm|Năm sinh|Birth Year):\s*(\d{4}[^.\n]*)",
        content,
        re.IGNORECASE,
    )
    element_match = re.search(
        r"(?:Bản mệnh|Mệnh):\s*([^.\n]+)",
        content,
        re.IGNORECASE,
    )
    astro_match = re.search(
        r"Đặc tính lý số(?:\s*\(Tử vi\s*/?\s*Bát tự\))?:\s*(.+)",
        content,
        re.IGNORECASE,
    ) or re.search(r"Tử vi/Bát tự:\s*(.+)", content, re.IGNORECASE)
    if not any([birth_match, element_match, astro_match]):
        return None
    summary = astro_match.group(1).strip() if astro_match else content[:200]
    mood = 0.1 if "hạn" in summary.lower() or "áp lực" in summary.lower() else 0.0
    return AstrologyProfile(
        persona_id=persona_id,
        birth_year=birth_match.group(1).strip() if birth_match else "",
        element=element_match.group(1).strip() if element_match else "",
        summary=summary,
        mood_modifier=mood,
    )


def build_relationship_matrix(
    personas: dict[str, "Persona"],
    *,
    config: MeetingConfig | None = None,
    role_aliases: dict[str, str] | None = None,
    default_factions: dict[str, list[str]] | None = None,
) -> RelationshipMatrix:
    """Construct the initial relationship matrix from persona relationship sections."""
    config = config or MeetingConfig()
    aliases = role_aliases if role_aliases is not None else ROLE_ALIASES
    factions_source = default_factions if default_factions is not None else DEFAULT_FACTIONS
    participant_ids = list(personas.keys())
    edges: dict[str, dict[str, RelationshipEdge]] = {
        pid: {} for pid in participant_ids
    }
    astrology: dict[str, AstrologyProfile] = {}

    for persona_id, persona in personas.items():
        rel_section = persona.sections.get("relationships")
        rel_content = rel_section.content if rel_section else ""
        for target_label, note in _parse_relationship_lines(rel_content):
            target_id = _normalize_role(target_label, aliases)
            if not target_id or target_id == persona_id or target_id not in participant_ids:
                continue
            affinity, conflict = _infer_affinity(note)
            faction = None
            for name, members in factions_source.items():
                if persona_id in members and target_id in members:
                    faction = name
                    break
            edges[persona_id][target_id] = RelationshipEdge(
                source_id=persona_id,
                target_id=target_id,
                affinity=affinity,
                conflict_weight=conflict,
                faction=faction,
                notes=note,
            )

        psychology = persona.sections.get("psychology")
        identity = persona.sections.get("identity")
        astro_source = psychology.content if psychology else (identity.content if identity else "")
        profile = _extract_astrology(
            persona_id,
            astro_source,
            enabled=config.enable_astrology,
        )
        if profile:
            astrology[persona_id] = profile

    for source_id in participant_ids:
        for target_id in participant_ids:
            if source_id == target_id:
                continue
            if target_id not in edges[source_id]:
                edges[source_id][target_id] = RelationshipEdge(
                    source_id=source_id,
                    target_id=target_id,
                    affinity=0.0,
                    conflict_weight=0.45,
                    notes="Mặc định — chưa có dữ liệu quan hệ chi tiết.",
                )

    factions = {
        name: [pid for pid in members if pid in participant_ids]
        for name, members in factions_source.items()
        if any(pid in participant_ids for pid in members)
    }

    return RelationshipMatrix(
        participants=participant_ids,
        edges=edges,
        factions=factions,
        astrology=astrology,
    )


def filter_relationship_matrix(
    matrix: RelationshipMatrix,
    participant_ids: list[str],
) -> RelationshipMatrix:
    """Restrict matrix to a subset of meeting participants."""
    selected = [pid for pid in participant_ids if pid in matrix.participants]
    if not selected:
        return RelationshipMatrix(participants=[], edges={}, factions={}, astrology={})

    edges: dict[str, dict[str, RelationshipEdge]] = {}
    for source_id in selected:
        edges[source_id] = {
            target_id: edge
            for target_id, edge in matrix.edges.get(source_id, {}).items()
            if target_id in selected
        }

    factions = {
        name: [pid for pid in members if pid in selected]
        for name, members in matrix.factions.items()
        if any(pid in selected for pid in members)
    }

    astrology = {
        pid: profile for pid, profile in matrix.astrology.items() if pid in selected
    }

    return RelationshipMatrix(
        participants=selected,
        edges=edges,
        factions=factions,
        astrology=astrology,
    )


_FRICTION_MARKERS = (
    "sai",
    "không chấp nhận",
    "phản đối",
    "nghi ngờ",
    "đập bàn",
    "vô lý",
    "không đúng",
    "cãi",
    "ép",
    "thủ công",
    "đốt tiền",
    "than vãn",
)

_MOTIVE_SUSPICION_MARKERS = (
    "động cơ",
    "cá nhân",
    "lợi ích riêng",
    "che giấu",
    "qua mặt",
    "bè phái",
    "lá chắn",
    "tuồn",
    "xào nấu",
    "mưu mẹo",
)

_ALLIANCE_MARKERS = (
    "tin tưởng",
    "kỳ vọng",
    "đồng minh",
    "hợp tác",
    "ủng hộ",
    "đồng ý",
    "ủng hộ",
    "cùng phe",
    "hỗ trợ",
    "tôn trọng",
    "đúng rồi",
    "hợp lý",
)

_SUPPORTIVE_TRANSCRIPT_MARKERS = (
    "đồng ý",
    "ủng hộ",
    "hợp lý",
    "đúng",
    "tin",
    "cảm ơn",
    "hỗ trợ",
)


def _speaker_faction(matrix: RelationshipMatrix, persona_id: str) -> str | None:
    for name, members in matrix.factions.items():
        if persona_id in members:
            return name
    return None


def _same_faction(matrix: RelationshipMatrix, source_id: str, target_id: str) -> bool:
    faction = _speaker_faction(matrix, source_id)
    return bool(faction and faction == _speaker_faction(matrix, target_id))


def _stance_label(affinity: float) -> str:
    if affinity > 0.35:
        return "thân thiện / đồng minh"
    if affinity > 0.15:
        return "tương đối thuận"
    if affinity < -0.35:
        return "căm ghét / rất căng"
    if affinity < -0.15:
        return "khó chịu / nghi ngờ"
    return "trung lập"


def infer_session_mood(
    matrix: RelationshipMatrix,
    speaker_id: str,
    *,
    recent_messages: list[DialogueTurn] | None = None,
    last_speaker: str = "",
) -> list[str]:
    """Heuristic session mood cues from astrology and recent transcript friction."""
    cues: list[str] = []
    astro = matrix.astrology.get(speaker_id)
    if astro and astro.summary.strip():
        cues.append(f"Tử vi/hạn năm: {astro.summary.strip()}")
        if astro.mood_modifier > 0:
            cues.append("Tâm trạng nền: dễ nóng, áp lực, có xu hướng liều hoặc cứng rắn hơn bình thường.")

    if not recent_messages:
        return cues

    friction_hits = 0
    targeted_at_speaker = 0
    for turn in recent_messages[-6:]:
        lowered = turn.content.lower()
        if turn.speaker_id == last_speaker and last_speaker and last_speaker != speaker_id:
            edge = matrix.edge(speaker_id, last_speaker)
            if edge and edge.affinity < -0.1 and any(m in lowered for m in _FRICTION_MARKERS):
                targeted_at_speaker += 1
        if turn.speaker_id != speaker_id and any(m in lowered for m in _FRICTION_MARKERS):
            friction_hits += 1

    if targeted_at_speaker >= 1:
        cues.append(
            f"Vừa bị {last_speaker or 'đồng nghiệp'} chọc/gài — dễ phản ứng cứng hoặc khiêu khích lại."
        )
    elif friction_hits >= 2:
        cues.append("Không khí họp đang căng — có thể muốn đẩy mạnh hoặc chọc thêm để lấy lại thế.")

    if last_speaker and last_speaker != speaker_id and recent_messages:
        edge = matrix.edge(speaker_id, last_speaker)
        last_turn = recent_messages[-1]
        if last_turn.speaker_id == last_speaker:
            lowered = last_turn.content.lower()
            if edge and edge.affinity > 0.15 and any(m in lowered for m in _SUPPORTIVE_TRANSCRIPT_MARKERS):
                cues.append(
                    f"{last_speaker} vừa nói đúng hướng phe bạn — có thể muốn ủng hộ hoặc bọc lót thêm."
                )
            elif _same_faction(matrix, speaker_id, last_speaker) and edge and edge.affinity >= 0:
                cues.append(
                    f"Cùng phe với {last_speaker} — cân nhắc bảo vệ đồng minh trước áp lực từ phe đối lập."
                )
    return cues


def format_relationships_for_reasoning(
    matrix: RelationshipMatrix,
    *,
    speaker_id: str,
    last_speaker: str = "",
    recent_messages: list[DialogueTurn] | None = None,
) -> str:
    """Rich relationship + mood block injected only in the internal reasoning step."""
    lines: list[str] = [
        "[QUAN HỆ & TÂM TRẠNG — dùng cho suy nghĩ nội bộ]",
        "Trước absorb/compromise, hãy đọc kỹ quan hệ cá nhân — không chỉ luận điểm nghiệp vụ.",
    ]

    mood_cues = infer_session_mood(
        matrix,
        speaker_id,
        recent_messages=recent_messages,
        last_speaker=last_speaker,
    )
    if mood_cues:
        lines.append("Tâm trạng phiên họp hôm nay:")
        for cue in mood_cues:
            lines.append(f"- {cue}")

    if last_speaker and last_speaker != speaker_id:
        edge = matrix.edge(speaker_id, last_speaker)
        if edge:
            lines.append(f"\nNgười vừa nói ({last_speaker}) — góc nhìn quan hệ của bạn:")
            lines.append(f"- Cảm xúc: {_stance_label(edge.affinity)} (affinity={edge.affinity:.2f})")
            lines.append(f"- Mức xung đột tiềm năng: {edge.conflict_weight:.2f}")
            if edge.faction:
                lines.append(f"- Phe: {edge.faction}")
            if edge.notes.strip():
                lines.append(f"- Bias cố định: {edge.notes.strip()}")
            note_lower = edge.notes.lower()
            if any(m in note_lower for m in _MOTIVE_SUSPICION_MARKERS):
                lines.append("- Gợi ý: nghi ngờ động cơ cá nhân / lợi ích riêng của họ trong lượt này.")
            elif edge.affinity > 0.15 or any(m in note_lower for m in _ALLIANCE_MARKERS):
                lines.append(
                    "- Gợi ý: tin tưởng / tôn trọng — có thể ủng hộ, bọc lót, hoặc nhún nhường hơn với họ."
                )
            elif _same_faction(matrix, speaker_id, last_speaker):
                lines.append("- Gợi ý: cùng phe — ưu tiên bảo vệ đồng minh khi bị phe đối lập tấn công.")
            elif edge.affinity < -0.15:
                lines.append("- Gợi ý: dễ đọc lời họ nói theo hướng thiên vị / muốn bắt bẻ.")

    allies: list[str] = []
    tense: list[str] = []
    for target_id, edge in sorted(matrix.edges.get(speaker_id, {}).items()):
        if target_id == last_speaker:
            continue
        snippet = edge.notes[:120].strip() or _stance_label(edge.affinity)
        if edge.affinity >= 0.2 or any(m in edge.notes.lower() for m in _ALLIANCE_MARKERS):
            allies.append(f"- {target_id}: {_stance_label(edge.affinity)} — {snippet}")
        elif edge.affinity <= -0.15 or edge.conflict_weight >= 0.65:
            tense.append(f"- {target_id}: {_stance_label(edge.affinity)} — {snippet}")
    if allies:
        lines.append("\nĐồng minh / quan hệ tích cực (có thể muốn bảo vệ):")
        lines.extend(allies[:4])
    if tense:
        lines.append("\nQuan hệ căng với các thành viên khác:")
        lines.extend(tense[:4])

    speaker_faction = _speaker_faction(matrix, speaker_id)
    if speaker_faction and matrix.factions.get(speaker_faction):
        mates = [pid for pid in matrix.factions[speaker_faction] if pid != speaker_id]
        if mates:
            lines.append(f"\nPhe của bạn ({speaker_faction}): {', '.join(mates)}")

    lines.append(
        "\nTrong JSON reasoning, trường relationship_lens (string) gồm CẢ hai chiều:"
        " (1) tiêu cực — ghét, nghi ngờ, bực, khiêu khích; "
        "(2) tích cực — tin, tôn trọng, thích, bảo vệ phe/đồng minh, muốn ủng hộ người vừa nói nếu họ thuộc phe bạn. "
        "KHÔNG lộ ra ngoài monologue công khai."
    )
    return "\n".join(lines)
