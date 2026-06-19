"""Runtime configuration for meeting simulation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LLMProviderName = Literal["openai", "gemini"]


class MeetingConfig(BaseModel):
    """Tunable parameters for graph execution and stopping criteria."""

    # Domain pack: enterprise | tutoring | securities | custom (pass ParticipantBundle)
    domain_id: str = "enterprise"
    # Defaults should be generic; real runs should set these from Meeting rows.
    meeting_topic: str = "Chủ đề phiên (chưa đặt)"
    opening_message: str = "Phiên thảo luận. Hãy bám sát chủ đề và nêu quan điểm thẳng thắn."
    max_rounds: int = 3
    max_turns: int | None = None
    stagnation_limit: int = 4
    stagnation_similarity_threshold: float = 0.75
    stagnation_window: int = 8
    stagnation_max_similarity_threshold: float = 0.62
    stagnation_min_novel_token_ratio: float = 0.28
    min_turns_before_stagnation: int = 8
    consensus_threshold: float = 0.8
    consensus_check_interval: int = 5
    min_turns_before_consensus: int = 0
    stop_on_stakeholder_approval: bool = True
    enable_astrology: bool = True
    enable_consensus_check: bool = True
    enable_stagnation_check: bool = True
    enable_rolling_summary: bool = True
    rolling_summary_min_turns: int = 12
    rolling_summary_recent_turns: int = 5
    rolling_summary_refresh_interval: int = 5
    transcript_window_orchestrator: int = 10
    transcript_window_persona: int = 12
    transcript_window_secretary: int = 20
    opening_speaker: str = ""
    participant_ids: list[str] | None = None
    key_stakeholders: list[str] = Field(default_factory=list)
    llm_provider: LLMProviderName = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.75
    max_output_tokens: int = 1024
    use_mock: bool = False
    enable_internal_monologue: bool = True
    enable_relationship_reasoning: bool = True
    monologue_in_sse: bool = False
    enable_dynamic_compromise: bool = True
    enable_working_proposals: bool = True
    proposal_consensus_mode: Literal["secretary", "aggregate", "both"] = "both"
    max_active_proposals: int = 5
    enable_shared_facts: bool = True
    fact_extraction_min_confidence: float = 0.6
    max_shared_facts: int = 20
    fact_dedup_similarity_threshold: float = 0.85
    reasoning_max_tokens: int = 512
    speech_max_tokens: int = 512
    # Post-meeting facilitator extension (Upgrade 2)
    enable_meeting_extension: bool = True
    extension_turn_budget: int = 8
    max_extensions_per_meeting: int = 3
    extension_stagnation_reset: bool = True
    extension_significance_model: str | None = None
