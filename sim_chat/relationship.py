"""Build and update the dynamic relationship matrix from seeded personas."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .config import MeetingConfig
from .models import AstrologyProfile, RelationshipEdge, RelationshipMatrix

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


def _normalize_role(label: str) -> str | None:
    cleaned = re.sub(r"[^\w\s&/-]", "", label.lower()).strip()
    for alias, role in ROLE_ALIASES.items():
        if alias in cleaned:
            return role
    upper = label.strip().upper()
    if upper in {"CEO", "CFO", "MARKETING", "PRODUCT", "SALE"}:
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
) -> RelationshipMatrix:
    """Construct the initial relationship matrix from persona relationship sections."""
    config = config or MeetingConfig()
    participant_ids = list(personas.keys())
    edges: dict[str, dict[str, RelationshipEdge]] = {
        pid: {} for pid in participant_ids
    }
    astrology: dict[str, AstrologyProfile] = {}

    for persona_id, persona in personas.items():
        rel_section = persona.sections.get("relationships")
        rel_content = rel_section.content if rel_section else ""
        for target_label, note in _parse_relationship_lines(rel_content):
            target_id = _normalize_role(target_label)
            if not target_id or target_id == persona_id or target_id not in participant_ids:
                continue
            affinity, conflict = _infer_affinity(note)
            faction = None
            for name, members in DEFAULT_FACTIONS.items():
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
        for name, members in DEFAULT_FACTIONS.items()
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
