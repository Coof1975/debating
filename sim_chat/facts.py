"""Cross-agent fact extraction, dedup, and context formatting."""

from __future__ import annotations

import json
import re
import uuid
from typing import Literal

from .config import MeetingConfig
from .embeddings import is_duplicate_fact
from .llm import LLMProvider
from .models import FactAcceptance, FactDraft, ReasoningResult, SharedFact

FactCategory = Literal["financial", "operational", "market", "other"]

FACT_EXTRACTOR_SYSTEM_PROMPT = """\
Bạn là trích xuất sự kiện/số liệu từ phát biểu họp nội bộ.

Nhiệm vụ: tách các tuyên bố factual cụ thể (số liệu, timeline, ràng buộc vận hành)
từ lời nói công khai — KHÔNG trích quan điểm chủ quan hay cảm xúc.

Trả lời CHỈ bằng JSON hợp lệ:
{
  "facts": [
    {"fact": "...", "category": "financial|operational|market|other", "confidence": 0.0-1.0}
  ]
}

Nếu không có số liệu/sự kiện cụ thể → {"facts": []}
Không thêm markdown hay giải thích ngoài JSON.
"""

_PERCENT_PATTERN = re.compile(r"(\+?\d+[\.,]?\d*)\s*%")
_NUMBER_CLAIM_PATTERN = re.compile(
    r"(\d+[\.,]?\d*\s*(?:%|tỷ|triệu|tấn|tháng|quý|Q\d|ngày))"
    r"|chi\s*phí|ngân\s*sách|doanh\s*thu|lợi\s*nhuận|margin|công\s*suất",
    re.IGNORECASE,
)


def make_fact_id(*, turn_index: int, speaker_id: str) -> str:
    suffix = uuid.uuid4().hex[:6]
    return f"f{turn_index}_{speaker_id.lower()}_{suffix}"


def strip_json_fence(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_fact_extraction(raw: str) -> list[FactDraft]:
    cleaned = strip_json_fence(raw)
    if not cleaned:
        return []
    try:
        payload = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(payload, dict):
        return []

    drafts: list[FactDraft] = []
    for item in payload.get("facts") or []:
        if not isinstance(item, dict):
            continue
        fact = str(item.get("fact", "")).strip()
        if not fact:
            continue
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        confidence = max(0.0, min(1.0, confidence))
        category = str(item.get("category", "other")).strip().lower()
        if category not in ("financial", "operational", "market", "other"):
            category = "other"
        drafts.append(FactDraft(fact=fact, category=category, confidence=confidence))
    return drafts


def infer_facts_from_speech(speech: str) -> list[FactDraft]:
    """Heuristic fallback when LLM extraction is unavailable."""
    drafts: list[FactDraft] = []
    lowered = speech.lower()

    percent_matches = _PERCENT_PATTERN.findall(speech)
    if percent_matches:
        pct = percent_matches[0]
        if "chi phí" in lowered or "vận hành" in lowered or "ngân sách" in lowered:
            category = "financial"
            subject = "Chi phí vận hành" if "vận hành" in lowered else "Chi phí"
        elif "doanh thu" in lowered or "sales" in lowered:
            category = "market"
            subject = "Doanh thu"
        else:
            category = "other"
            subject = "Chỉ số"
        drafts.append(
            FactDraft(
                fact=f"{subject} thay đổi {pct}%",
                category=category,
                confidence=0.75,
            )
        )

    if not drafts and _NUMBER_CLAIM_PATTERN.search(speech):
        first_sentence = speech.split(".")[0].strip() or speech[:120].strip()
        category = "financial" if any(
            token in lowered for token in ("ngân sách", "chi phí", "dòng tiền", "margin")
        ) else "operational" if "công suất" in lowered or "sản xuất" in lowered else "other"
        drafts.append(FactDraft(fact=first_sentence, category=category, confidence=0.65))

    return drafts


def extract_facts_from_speech(
    llm: LLMProvider,
    *,
    speech: str,
    speaker_id: str,
    turn_index: int,
    config: MeetingConfig,
) -> list[SharedFact]:
    if not config.enable_shared_facts or not speech.strip():
        return []

    user_message = (
        f"Người nói: {speaker_id}\n"
        f"Lượt: {turn_index}\n\n"
        f"Phát biểu:\n{speech.strip()}"
    )
    raw = llm.generate(
        FACT_EXTRACTOR_SYSTEM_PROMPT,
        user_message,
        max_tokens=256,
    )
    drafts = parse_fact_extraction(raw)
    if not drafts:
        drafts = infer_facts_from_speech(speech)

    facts: list[SharedFact] = []
    for draft in drafts:
        if draft.confidence < config.fact_extraction_min_confidence:
            continue
        facts.append(
            SharedFact(
                id=make_fact_id(turn_index=turn_index, speaker_id=speaker_id),
                source_speaker_id=speaker_id,
                turn_index=turn_index,
                fact=draft.fact.strip(),
                category=draft.category,
                confidence=draft.confidence,
            )
        )
    return facts


def merge_shared_facts(
    existing: list[SharedFact],
    incoming: list[SharedFact],
    *,
    config: MeetingConfig,
) -> list[SharedFact]:
    if not config.enable_shared_facts:
        return list(existing)

    merged = [fact.model_copy(deep=True) for fact in existing]
    known_texts = [fact.fact for fact in merged]

    for fact in incoming:
        if is_duplicate_fact(
            fact.fact,
            known_texts,
            threshold=config.fact_dedup_similarity_threshold,
        ):
            continue
        merged.append(fact)
        known_texts.append(fact.fact)

    if len(merged) > config.max_shared_facts:
        merged = sorted(merged, key=lambda fact: (fact.turn_index, fact.id), reverse=True)
        merged = merged[: config.max_shared_facts]
        merged = sorted(merged, key=lambda fact: fact.turn_index)
    return merged


def apply_fact_acceptances(
    facts: list[SharedFact],
    *,
    speaker_id: str,
    acceptances: list[FactAcceptance],
) -> list[SharedFact]:
    if not acceptances:
        return facts

    acceptance_map = {item.fact_id: item.accepted for item in acceptances}
    updated: list[SharedFact] = []
    for fact in facts:
        if fact.id not in acceptance_map:
            updated.append(fact)
            continue
        copy = fact.model_copy(deep=True)
        copy.accepted_by[speaker_id] = acceptance_map[fact.id]
        updated.append(copy)
    return updated


def update_shared_facts_after_turn(
    existing: list[SharedFact],
    *,
    llm: LLMProvider,
    speaker_id: str,
    turn_index: int,
    speech: str,
    reasoning: ReasoningResult | None,
    config: MeetingConfig,
) -> list[SharedFact]:
    if not config.enable_shared_facts:
        return list(existing)

    with_acceptances = apply_fact_acceptances(
        existing,
        speaker_id=speaker_id,
        acceptances=reasoning.fact_acceptances if reasoning else [],
    )
    extracted = extract_facts_from_speech(
        llm,
        speech=speech,
        speaker_id=speaker_id,
        turn_index=turn_index,
        config=config,
    )
    return merge_shared_facts(with_acceptances, extracted, config=config)


def facts_for_speaker(
    facts: list[SharedFact],
    *,
    speaker_id: str,
) -> list[SharedFact]:
    """Facts from colleagues (exclude speaker's own claims for context injection)."""
    return [fact for fact in facts if fact.source_speaker_id != speaker_id]


def format_shared_facts_for_context(
    facts: list[SharedFact],
    *,
    speaker_id: str,
    limit: int = 8,
) -> str:
    relevant = facts_for_speaker(facts, speaker_id=speaker_id)
    if not relevant:
        return ""

    sorted_facts = sorted(relevant, key=lambda fact: fact.turn_index, reverse=True)[:limit]
    lines = [
        "## Sự kiện đồng nghiệp vừa đưa (chưa có trong hồ sơ tĩnh của bạn)",
    ]
    for fact in sorted_facts:
        acceptance = fact.accepted_by.get(speaker_id)
        acceptance_note = ""
        if acceptance is True:
            acceptance_note = " [bạn đã chấp nhận]"
        elif acceptance is False:
            acceptance_note = " [bạn đã bác bỏ]"
        lines.append(
            f"- [{fact.source_speaker_id} @ lượt {fact.turn_index} | {fact.id}]: "
            f"{fact.fact}{acceptance_note}"
        )
    lines.append(
        "→ Không bắt buộc đồng ý quan điểm, nhưng phải xử lý số liệu nếu hợp lý."
    )
    return "\n".join(lines)


def format_shared_facts_for_reasoning(
    facts: list[SharedFact],
    *,
    speaker_id: str,
) -> str:
    block = format_shared_facts_for_context(facts, speaker_id=speaker_id)
    if not block:
        return ""
    return (
        f"{block}\n\n"
        "Trong reasoning JSON, dùng fact_acceptances: "
        '[{"fact_id": "<id>", "accepted": true|false}] để ghi nhận bạn chấp nhận hay bác bỏ từng số liệu.'
    )


def format_shared_facts_for_insight(
    facts: list[SharedFact],
    *,
    limit: int = 20,
) -> str:
    """Compact fact summary for post-meeting insight generation."""
    if not facts:
        return "Không có shared_facts được ghi nhận."

    sorted_facts = sorted(facts, key=lambda fact: fact.turn_index, reverse=True)[:limit]
    lines = ["SHARED FACTS (số liệu/sự kiện từ phát biểu công khai):"]
    for fact in sorted_facts:
        acceptance_bits = [
            f"{persona_id}={'chấp nhận' if accepted else 'bác bỏ'}"
            for persona_id, accepted in fact.accepted_by.items()
        ]
        acceptance_text = ", ".join(acceptance_bits) if acceptance_bits else "chưa có phản hồi"
        lines.append(
            f"- [{fact.id}] {fact.fact}\n"
            f"  Nguồn: {fact.source_speaker_id} @ lượt {fact.turn_index} | "
            f"loại: {fact.category} | confidence: {fact.confidence:.0%}\n"
            f"  Phản hồi: {acceptance_text}"
        )
    lines.append(
        "→ Facts được chấp nhận rộng rãi = nền chung; facts bị bác bỏ hoặc tranh cãi = "
        "giả định/rủi ro chưa thống nhất."
    )
    return "\n".join(lines)


def facts_state_patch(facts: list[SharedFact]) -> dict:
    return {"shared_facts": facts}
