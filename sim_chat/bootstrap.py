"""Bootstrap meeting state — domain-agnostic entry points."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config import MeetingConfig
from .domain import ParticipantBundle, get_domain, load_domain_participants
from .models import MeetingState

# Ensure built-in domain packs are registered.
from . import domains as _domains  # noqa: F401

if TYPE_CHECKING:
    from debating.models import Persona


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_src_on_path() -> None:
    src = _repo_root() / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def apply_domain_defaults(config: MeetingConfig) -> MeetingConfig:
    """Fill opening_speaker / key_stakeholders from domain pack when unset."""
    domain = get_domain(config.domain_id)
    updates: dict = {}
    if not config.opening_speaker and domain.default_opening_speaker:
        updates["opening_speaker"] = domain.default_opening_speaker
    if not config.key_stakeholders and domain.default_key_stakeholders:
        updates["key_stakeholders"] = list(domain.default_key_stakeholders)
    if updates:
        return config.model_copy(update=updates)
    return config


def ensure_seeded(test_data_dir: Path | None = None, output_dir: Path | None = None) -> Path:
    _ensure_src_on_path()
    from debating import seed

    root = _repo_root()
    test_data = test_data_dir or root / "test_data"
    output = output_dir or root / "data" / "seeded"
    if not (output / "seed_bundle.json").exists():
        seed(test_data, output)
    return output


from .participant_utils import (
    build_negotiation_profiles,
    ensure_src_on_path as _ensure_src_on_path,
    resolve_opening_speaker as _resolve_opening_speaker,
    resolve_participant_ids as _resolve_participant_ids,
)


def create_initial_state_from_bundle(
    config: MeetingConfig | None = None,
    bundle: ParticipantBundle | None = None,
    *,
    participant_bundle: ParticipantBundle | None = None,
) -> MeetingState:
    """Start a simulation from a pre-built ParticipantBundle (any domain/app)."""
    config = apply_domain_defaults(config or MeetingConfig())
    resolved_bundle = bundle or participant_bundle
    if resolved_bundle is None:
        resolved_bundle = load_domain_participants(config.domain_id, config=config)

    participant_ids = _resolve_participant_ids(resolved_bundle.participant_ids, config)
    system_prompts = {pid: resolved_bundle.system_prompts[pid] for pid in participant_ids}
    persona_names = {pid: resolved_bundle.persona_names[pid] for pid in participant_ids}
    negotiation_profiles = {
        pid: resolved_bundle.negotiation_profiles[pid]
        for pid in participant_ids
        if pid in resolved_bundle.negotiation_profiles
    }
    matrix = resolved_bundle.relationship_matrix
    if set(matrix.participants) != set(participant_ids):
        from .relationship import filter_relationship_matrix

        matrix = filter_relationship_matrix(matrix, participant_ids)

    opening_speaker = _resolve_opening_speaker(participant_ids, config)

    return MeetingState(
        messages=[],
        relationship_matrix=matrix,
        current_speaker=opening_speaker,
        last_speaker="",
        loop_count=0,
        stagnation_score=0,
        turn_index=0,
        participant_ids=participant_ids,
        meeting_topic=config.meeting_topic,
        config=config,
        prompts=system_prompts,
        persona_names=persona_names,
        terminated=False,
        termination_reason="",
        secretary_verdict=None,
        turns_since_secretary=0,
        transcript_summary="",
        summary_through_turn=0,
        hidden_turns=[],
        speaker_selections=[],
        last_monologue={},
        negotiation_profiles=negotiation_profiles,
        working_proposals=[],
        shared_facts=[],
    )


def load_prompts(
    config: MeetingConfig,
    *,
    test_data_dir: Path | None = None,
    personas: dict[str, Persona] | None = None,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Legacy helper — loads enterprise bundle prompts."""
    config = apply_domain_defaults(config)
    bundle = load_domain_participants(
        config.domain_id,
        config=config,
        test_data_dir=test_data_dir,
        personas=personas,
    )
    return bundle.system_prompts, bundle.persona_names, bundle.participant_ids


def create_initial_state(
    config: MeetingConfig | None = None,
    *,
    test_data_dir: Path | None = None,
    system_prompts: dict[str, str] | None = None,
    persona_names: dict[str, str] | None = None,
    personas: dict[str, Persona] | None = None,
    participant_bundle: ParticipantBundle | None = None,
) -> MeetingState:
    """Create initial graph state. Uses domain loader or an explicit ParticipantBundle."""
    config = apply_domain_defaults(config or MeetingConfig())

    if participant_bundle is not None:
        return create_initial_state_from_bundle(config, participant_bundle)

    if system_prompts is not None and persona_names is not None and personas:
        from .relationship import build_relationship_matrix

        participant_ids = _resolve_participant_ids(list(personas.keys()), config)
        filtered = {pid: personas[pid] for pid in participant_ids}
        domain = get_domain(config.domain_id)
        matrix = build_relationship_matrix(
            filtered,
            config=config,
            role_aliases=domain.role_aliases,
            default_factions=domain.default_factions,
        )
        return create_initial_state_from_bundle(
            config,
            ParticipantBundle(
                participant_ids=participant_ids,
                persona_names={pid: persona_names[pid] for pid in participant_ids},
                system_prompts={pid: system_prompts[pid] for pid in participant_ids},
                relationship_matrix=matrix,
                negotiation_profiles=build_negotiation_profiles(participant_ids, filtered),
            ),
        )

    bundle = load_domain_participants(
        config.domain_id,
        config=config,
        test_data_dir=test_data_dir,
        personas=personas,
    )
    return create_initial_state_from_bundle(config, bundle)


def load_seed_bundle(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
