"""Domain-agnostic simulation contracts — plug in enterprise, tutoring, securities, etc."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from pydantic import BaseModel, Field

from .models import NegotiationProfile, RelationshipMatrix


class SessionLabels(BaseModel):
    """Terminology injected into turn/orchestrator prompts."""

    session_noun: str = "phiên thảo luận"
    topic_label: str = "Chủ đề"
    transcript_label: str = "Biên bản gần nhất"
    relationship_label: str = "Ma trận quan hệ của bạn"
    last_speaker_label: str = "Người vừa phát biểu"
    participant_noun: str = "participant"
    orchestrator_noun: str = "Điều phối viên"
    secretary_noun: str = "Thư ký"
    moderator_role_hint: str = ""


class DomainPrompts(BaseModel):
    """LLM system prompts and suffixes owned by a domain pack."""

    orchestrator_system: str
    secretary_system: str
    insight_system: str
    fact_extractor_system: str
    reasoning_system_suffix: str
    reasoning_user_suffix: str
    speech_instructions: str
    negotiation_pressure_block: str = (
        "- Áp lực điều phối: nếu bế tắc, người chủ trì đánh giá kém năng lực điều phối"
    )


class ParticipantBundle(BaseModel):
    """Everything the engine needs to start a run — domain-agnostic input."""

    participant_ids: list[str]
    persona_names: dict[str, str]
    system_prompts: dict[str, str]
    relationship_matrix: RelationshipMatrix
    negotiation_profiles: dict[str, NegotiationProfile] = Field(default_factory=dict)


class SimulationDomain(BaseModel):
    """Configuration pack for one application vertical."""

    id: str
    label: str
    labels: SessionLabels = Field(default_factory=SessionLabels)
    prompts: DomainPrompts
    topic_role_keywords: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    role_aliases: dict[str, str] = Field(default_factory=dict)
    display_aliases: dict[str, str] = Field(default_factory=dict)
    default_factions: dict[str, list[str]] = Field(default_factory=dict)
    default_opening_speaker: str | None = None
    default_key_stakeholders: list[str] = Field(default_factory=list)
    no_repeat_speaker_ids: tuple[str, ...] = ()


@dataclass
class DomainRegistry:
    _domains: dict[str, SimulationDomain] = field(default_factory=dict)
    _loaders: dict[str, Callable[..., ParticipantBundle]] = field(default_factory=dict)

    def register(
        self,
        domain: SimulationDomain,
        *,
        loader: Callable[..., ParticipantBundle] | None = None,
    ) -> None:
        self._domains[domain.id] = domain
        if loader is not None:
            self._loaders[domain.id] = loader

    def get(self, domain_id: str) -> SimulationDomain:
        if domain_id not in self._domains:
            known = ", ".join(sorted(self._domains)) or "(none)"
            raise KeyError(f"Unknown simulation domain '{domain_id}'. Registered: {known}")
        return self._domains[domain_id]

    def list_ids(self) -> list[str]:
        return sorted(self._domains)

    def load_participants(self, domain_id: str, **kwargs) -> ParticipantBundle:
        if domain_id not in self._loaders:
            raise KeyError(
                f"Domain '{domain_id}' has no participant loader. "
                "Pass a ParticipantBundle to create_initial_state_from_bundle() instead."
            )
        return self._loaders[domain_id](**kwargs)


_registry = DomainRegistry()


def register_domain(
    domain: SimulationDomain,
    *,
    loader: Callable[..., ParticipantBundle] | None = None,
) -> None:
    _registry.register(domain, loader=loader)


def get_domain(domain_id: str) -> SimulationDomain:
    return _registry.get(domain_id)


def list_domains() -> list[str]:
    return _registry.list_ids()


def load_domain_participants(domain_id: str, **kwargs) -> ParticipantBundle:
    return _registry.load_participants(domain_id, **kwargs)


class DomainContextBuilder(Protocol):
    """Optional hook for apps that need custom turn context beyond labels."""

    def build_opener_context(self, *, topic: str, labels: SessionLabels) -> str: ...

    def build_first_turn_context(self, *, topic: str, labels: SessionLabels) -> str: ...

    def build_followup_context(
        self,
        *,
        topic: str,
        transcript: str,
        last_speaker: str,
        rel_summary: str,
        labels: SessionLabels,
        extra_blocks: str = "",
    ) -> str: ...
