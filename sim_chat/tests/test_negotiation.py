"""Tests for negotiation profile defaults and prompt injection."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from debating.negotiation import (
    DEFAULT_NEGOTIATION_BY_ROLE,
    NegotiationProfile,
    default_negotiation_for_role,
    effective_compromise_threshold,
    format_negotiation_prompt_block,
    negotiation_from_metadata,
)
from debating.prompts import build_persona_prompt
from sim_chat.bootstrap import create_initial_state
from sim_chat.config import MeetingConfig
from sim_chat.reasoning import build_reasoning_user_message, effective_compromise_threshold as sim_effective


def test_cfo_more_conservative_than_ceo() -> None:
    cfo = default_negotiation_for_role("CFO")
    ceo = default_negotiation_for_role("CEO")
    assert cfo.compromise_threshold < ceo.compromise_threshold
    assert cfo.min_interest_retention > ceo.min_interest_retention


def test_negotiation_from_metadata_fallback() -> None:
    profile = negotiation_from_metadata({}, role="CFO")
    assert profile.compromise_threshold == DEFAULT_NEGOTIATION_BY_ROLE["CFO"].compromise_threshold


def test_format_negotiation_prompt_block_contains_threshold() -> None:
    profile = NegotiationProfile(compromise_threshold=0.25, min_interest_retention=0.85)
    block = format_negotiation_prompt_block(profile)
    assert "HỒ SƠ ĐÀM PHÁN" in block
    assert "0.25" in block
    assert "85%" in block


def test_build_persona_prompt_includes_negotiation_block() -> None:
    from debating.loaders import load_seed_sources

    company, personas = load_seed_sources(ROOT / "test_data")
    prompt = build_persona_prompt(personas["CFO"], company, personas)
    assert "HỒ SƠ ĐÀM PHÁN" in prompt.system_prompt
    assert "0.25" in prompt.system_prompt


def test_bootstrap_populates_negotiation_profiles() -> None:
    config = MeetingConfig(participant_ids=["CEO", "CFO"], use_mock=True)
    state = create_initial_state(config)
    profiles = state["negotiation_profiles"]
    assert profiles["CFO"].compromise_threshold < profiles["CEO"].compromise_threshold


def test_dynamic_compromise_increases_with_stagnation() -> None:
    profile = default_negotiation_for_role("CFO")
    base = effective_compromise_threshold(profile, stagnation_score=0, enable_dynamic=False)
    boosted = sim_effective(profile, stagnation_score=3, enable_dynamic=True)
    assert boosted >= base


def test_reasoning_user_message_includes_negotiation() -> None:
    profile = default_negotiation_for_role("CFO")
    message = build_reasoning_user_message(
        "[Cuộc họp: test]",
        config=MeetingConfig(),
        negotiation=profile,
        effective_threshold=0.3,
    )
    assert "HỒ SƠ ĐÀM PHÁN" in message
    assert "0.30" in message
