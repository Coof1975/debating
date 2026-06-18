"""Tests for cross-agent shared fact caching."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.embeddings import is_duplicate_fact
from sim_chat.facts import (
    apply_fact_acceptances,
    extract_facts_from_speech,
    format_shared_facts_for_context,
    infer_facts_from_speech,
    merge_shared_facts,
    parse_fact_extraction,
    update_shared_facts_after_turn,
)
from sim_chat.llm import MockLLMProvider
from sim_chat.models import FactAcceptance, ReasoningResult, SharedFact
from sim_chat.reasoning import parse_reasoning_result


def _fact(**kwargs) -> SharedFact:
    defaults = {
        "id": "f1_cfo_abc123",
        "source_speaker_id": "CFO",
        "turn_index": 1,
        "fact": "Chi phí vận hành Q1 tăng 20%",
        "category": "financial",
        "confidence": 0.85,
    }
    defaults.update(kwargs)
    return SharedFact(**defaults)


def test_parse_fact_extraction_valid_json() -> None:
    raw = """
    {
      "facts": [
        {
          "fact": "Chi phí vận hành Q1 tăng 20%",
          "category": "financial",
          "confidence": 0.85
        }
      ]
    }
    """
    drafts = parse_fact_extraction(raw)
    assert len(drafts) == 1
    assert drafts[0].category == "financial"
    assert drafts[0].confidence == 0.85


def test_infer_facts_from_speech_percent() -> None:
    drafts = infer_facts_from_speech(
        "Theo số liệu nội bộ, chi phí vận hành Q1 đã tăng +20% so với kế hoạch."
    )
    assert drafts
    assert "20" in drafts[0].fact


def test_is_duplicate_fact_detects_similar_text() -> None:
    assert is_duplicate_fact(
        "Chi phí vận hành Q1 tăng 20%",
        ["Chi phí vận hành quý 1 tăng 20 phần trăm"],
        threshold=0.5,
    )


def test_merge_shared_facts_dedupes_and_caps() -> None:
    config = MeetingConfig(
        enable_shared_facts=True,
        max_shared_facts=2,
        fact_dedup_similarity_threshold=0.85,
    )
    existing = [_fact(id="f1_cfo_a", turn_index=1)]
    incoming = [
        _fact(id="f2_cfo_b", turn_index=2, fact="Chi phí vận hành Q1 tăng 20%"),
        _fact(id="f3_ceo_c", turn_index=3, fact="Công suất nhà máy đạt 200 tấn/tháng"),
        _fact(id="f4_mkt_d", turn_index=4, fact="KPI TikTok tháng đầu 1.2 triệu view"),
    ]
    merged = merge_shared_facts(existing, incoming, config=config)
    assert len(merged) == 2
    merged_ids = {fact.id for fact in merged}
    assert "f4_mkt_d" in merged_ids
    assert "f3_ceo_c" in merged_ids
    assert "f2_cfo_b" not in merged_ids  # duplicate of f1
    assert "f1_cfo_a" not in merged_ids  # dropped by cap (oldest)


def test_apply_fact_acceptances_records_speaker() -> None:
    facts = apply_fact_acceptances(
        [_fact()],
        speaker_id="MARKETING",
        acceptances=[FactAcceptance(fact_id="f1_cfo_abc123", accepted=True)],
    )
    assert facts[0].accepted_by["MARKETING"] is True


def test_format_shared_facts_excludes_own_claims() -> None:
    text = format_shared_facts_for_context(
        [_fact(), _fact(id="f2_mkt_x", source_speaker_id="MARKETING", fact="Budget cap 500M")],
        speaker_id="MARKETING",
    )
    assert "CFO" in text
    assert "Budget cap 500M" not in text


def test_parse_reasoning_result_fact_acceptances() -> None:
    raw = """
    {
      "absorb": "Ghi nhận số liệu CFO.",
      "compromise_space": "Điều chỉnh plan.",
      "stance_shift": 0.3,
      "fact_acceptances": [{"fact_id": "f1_cfo_abc", "accepted": true}]
    }
    """
    result = parse_reasoning_result(raw)
    assert result is not None
    assert len(result.fact_acceptances) == 1
    assert result.fact_acceptances[0].fact_id == "f1_cfo_abc"


def test_extract_facts_from_speech_mock_llm() -> None:
    llm = MockLLMProvider()
    config = MeetingConfig(enable_shared_facts=True, fact_extraction_min_confidence=0.6)
    facts = extract_facts_from_speech(
        llm,
        speech="Chi phí vận hành Q1 đã tăng +20% so với forecast.",
        speaker_id="CFO",
        turn_index=3,
        config=config,
    )
    assert len(facts) == 1
    assert facts[0].source_speaker_id == "CFO"
    assert "20" in facts[0].fact


def test_update_shared_facts_disabled_returns_unchanged() -> None:
    llm = MockLLMProvider()
    existing = [_fact()]
    config = MeetingConfig(enable_shared_facts=False)
    updated = update_shared_facts_after_turn(
        existing,
        llm=llm,
        speaker_id="CFO",
        turn_index=2,
        speech="Chi phí vận hành Q1 +20%.",
        reasoning=None,
        config=config,
    )
    assert updated == existing


def test_cfo_fact_visible_to_marketing_context() -> None:
    """Integration-style: CFO fact appears in Marketing's user context block."""
    cfo_fact = _fact(turn_index=5)
    text = format_shared_facts_for_context([cfo_fact], speaker_id="MARKETING")
    assert "Chi phí vận hành Q1 tăng 20%" in text
    assert "CFO @ lượt 5" in text


def test_marketing_reasoning_accepts_cfo_fact() -> None:
    llm = MockLLMProvider(persona_names={"MARKETING": "Lan Marketing"})
    config = MeetingConfig(enable_shared_facts=True, enable_internal_monologue=True)
    context = format_shared_facts_for_context([_fact()], speaker_id="MARKETING")
    reasoning_user = f"[Cuộc họp: Keos]\n\n{context}\n\n[INTERNAL REASONING]"
    raw = llm.generate("INTERNAL REASONING", reasoning_user)
    result = parse_reasoning_result(raw)
    assert result is not None
    assert result.fact_acceptances
    assert result.fact_acceptances[0].fact_id == "f1_cfo_abc123"
