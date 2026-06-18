"""Data models and LangGraph state schema."""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from .config import MeetingConfig


class TerminationReason(str, Enum):
    MAX_ROUNDS = "max_rounds"
    CONSENSUS = "consensus"
    STAGNATION = "stagnation"
    MANUAL = "manual"


class DialogueTurn(BaseModel):
    """One utterance in the meeting transcript."""

    speaker_id: str
    speaker_name: str
    content: str
    round_number: int = 0
    turn_index: int = 0


class AstrologyProfile(BaseModel):
    """Optional horoscope / metaphysics modifiers for a persona."""

    persona_id: str
    birth_year: str = ""
    element: str = ""
    summary: str = ""
    mood_modifier: float = 0.0


class RelationshipEdge(BaseModel):
    """Directed attitude from one participant toward another."""

    source_id: str
    target_id: str
    affinity: float = Field(default=0.0, ge=-1.0, le=1.0)
    conflict_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    faction: str | None = None
    notes: str = ""


class RelationshipMatrix(BaseModel):
    """Dynamic matrix of conflicts, alliances, and optional astrology."""

    participants: list[str] = Field(default_factory=list)
    edges: dict[str, dict[str, RelationshipEdge]] = Field(default_factory=dict)
    factions: dict[str, list[str]] = Field(default_factory=dict)
    astrology: dict[str, AstrologyProfile] = Field(default_factory=dict)

    def edge(self, source_id: str, target_id: str) -> RelationshipEdge | None:
        return self.edges.get(source_id, {}).get(target_id)

    def affinity(self, source_id: str, target_id: str) -> float:
        edge = self.edge(source_id, target_id)
        return edge.affinity if edge else 0.0

    def conflict(self, source_id: str, target_id: str) -> float:
        edge = self.edge(source_id, target_id)
        return edge.conflict_weight if edge else 0.5

    def summary_for(self, persona_id: str) -> str:
        lines: list[str] = []
        for target_id, edge in self.edges.get(persona_id, {}).items():
            stance = "thân thiện" if edge.affinity > 0.2 else "căng thẳng" if edge.affinity < -0.2 else "trung lập"
            lines.append(
                f"- Với {target_id}: {stance} (affinity={edge.affinity:.2f}, "
                f"xung đột={edge.conflict_weight:.2f}). {edge.notes}".strip()
            )
        if persona_id in self.astrology:
            astro = self.astrology[persona_id]
            lines.append(f"- Tử vi/Bát tự: {astro.summary}")
        return "\n".join(lines) if lines else "Không có dữ liệu ma trận quan hệ."


class InternalMonologue(BaseModel):
    """Hidden reasoning before a persona speaks publicly."""

    absorb: str
    compromise_space: str
    stance_shift: float = Field(default=0.0, ge=-1.0, le=1.0)


class HiddenTurn(BaseModel):
    """Persisted internal monologue for one turn (not shown in public transcript)."""

    speaker_id: str
    turn_index: int
    monologue: InternalMonologue


class NegotiationProfile(BaseModel):
    """Per-persona compromise and director-pressure parameters."""

    compromise_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    min_interest_retention: float = Field(default=0.7, ge=0.0, le=1.0)
    director_sensitivity: float = Field(default=0.6, ge=0.0, le=1.0)
    deadlock_tolerance: float = Field(default=0.3, ge=0.0, le=1.0)


class ProposalApproval(BaseModel):
    """One participant's approval score for a working proposal."""

    persona_id: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    concerns: str = ""


class WorkingProposal(BaseModel):
    """Shared compromise proposal on the meeting blackboard."""

    id: str
    author_id: str
    turn_index: int
    title: str
    description: str
    approvals: dict[str, ProposalApproval] = Field(default_factory=dict)
    aggregate_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = Field(default="active")  # draft | active | superseded | accepted
    parent_id: str | None = None


class ProposalScore(BaseModel):
    """Score assigned to an existing proposal during internal reasoning."""

    id: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    concerns: str = ""


class NewProposalDraft(BaseModel):
    """New compromise proposal extracted from reasoning."""

    title: str
    description: str
    parent_id: str | None = None


class ReasoningResult(BaseModel):
    """Full internal reasoning output including proposal blackboard updates."""

    monologue: InternalMonologue
    proposal_scores: list[ProposalScore] = Field(default_factory=list)
    new_proposal: NewProposalDraft | None = None
    fact_acceptances: list["FactAcceptance"] = Field(default_factory=list)


class FactAcceptance(BaseModel):
    """Accept or reject a colleague's shared fact during internal reasoning."""

    fact_id: str
    accepted: bool = True


class SharedFact(BaseModel):
    """Episodic factual claim surfaced by a participant during the meeting."""

    id: str
    source_speaker_id: str
    turn_index: int
    fact: str
    category: str = "other"  # financial | operational | market | other
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    accepted_by: dict[str, bool] = Field(default_factory=dict)


class FactDraft(BaseModel):
    """Candidate fact extracted from public speech."""

    fact: str
    category: str = "other"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class SecretaryVerdict(BaseModel):
    """Output from the meeting secretary consensus check."""

    consensus_score: float = 0.0
    has_consensus: bool = False
    key_stakeholder_approval: bool = False
    summary: str = ""


class MeetingRecord(BaseModel):
    """Persisted artifact after a simulation completes."""

    meeting_id: str
    topic: str
    config: MeetingConfig
    relationship_matrix: RelationshipMatrix
    messages: list[DialogueTurn]
    loop_count: int
    stagnation_score: int
    termination_reason: TerminationReason | None = None
    insight_report: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MeetingState(TypedDict):
    """LangGraph shared state — centralized meeting context."""

    messages: Annotated[list[DialogueTurn], operator.add]
    relationship_matrix: RelationshipMatrix
    current_speaker: str
    last_speaker: str
    loop_count: int
    stagnation_score: int
    turn_index: int
    participant_ids: list[str]
    meeting_topic: str
    config: MeetingConfig
    prompts: dict[str, str]
    persona_names: dict[str, str]
    terminated: bool
    termination_reason: str
    secretary_verdict: SecretaryVerdict | None
    turns_since_secretary: int
    transcript_summary: str
    summary_through_turn: int
    hidden_turns: Annotated[list[HiddenTurn], operator.add]
    last_monologue: dict[str, InternalMonologue]
    negotiation_profiles: dict[str, NegotiationProfile]
    working_proposals: list[WorkingProposal]
    shared_facts: list[SharedFact]
