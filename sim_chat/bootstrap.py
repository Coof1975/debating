"""Bootstrap meeting state from the debating seed bundle."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config import MeetingConfig
from .models import MeetingState, NegotiationProfile, SecretaryVerdict
from .relationship import build_relationship_matrix

if TYPE_CHECKING:
    from debating.models import Persona


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_src_on_path() -> None:
    src = _repo_root() / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def ensure_seeded(test_data_dir: Path | None = None, output_dir: Path | None = None) -> Path:
    _ensure_src_on_path()
    from debating import seed

    root = _repo_root()
    test_data = test_data_dir or root / "test_data"
    output = output_dir or root / "data" / "seeded"
    if not (output / "seed_bundle.json").exists():
        seed(test_data, output)
    return output


def _resolve_participant_ids(all_ids: list[str], config: MeetingConfig) -> list[str]:
    if config.participant_ids:
        selected = [pid.upper() for pid in config.participant_ids]
        missing = [pid for pid in selected if pid not in all_ids]
        if missing:
            raise ValueError(f"Unknown participant_ids: {', '.join(missing)}")
        return selected
    return list(all_ids)


def _resolve_opening_speaker(participant_ids: list[str], config: MeetingConfig) -> str:
    opener = config.opening_speaker.upper()
    if opener in participant_ids:
        return opener
    return participant_ids[0]


def _build_negotiation_profiles(
    participant_ids: list[str],
    personas: dict[str, Persona] | None,
) -> dict[str, NegotiationProfile]:
    _ensure_src_on_path()
    from debating.negotiation import default_negotiation_for_role, negotiation_from_metadata

    profiles: dict[str, NegotiationProfile] = {}
    for pid in participant_ids:
        if personas and pid in personas:
            persona = personas[pid]
            if persona.negotiation is not None:
                resolved = persona.negotiation
            else:
                resolved = negotiation_from_metadata(persona.metadata, role=pid)
        else:
            resolved = default_negotiation_for_role(pid)
        profiles[pid] = NegotiationProfile.model_validate(resolved.model_dump())
    return profiles


def load_prompts(
    config: MeetingConfig,
    *,
    test_data_dir: Path | None = None,
    personas: dict[str, Persona] | None = None,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    _ensure_src_on_path()
    from debating.loaders import load_seed_sources
    from debating.prompts import build_all_prompts

    root = _repo_root()
    if personas is None:
        ensure_seeded(test_data_dir)
        _, personas = load_seed_sources(test_data_dir or root / "test_data")

    all_ids = list(personas.keys())
    participant_ids = _resolve_participant_ids(all_ids, config)
    filtered_personas = {pid: personas[pid] for pid in participant_ids}

    if personas is not None and len(filtered_personas) < len(participant_ids):
        missing = set(participant_ids) - set(filtered_personas)
        raise ValueError(f"Unknown participant_ids: {', '.join(sorted(missing))}")

    company, _ = load_seed_sources(test_data_dir or root / "test_data") if personas is None else (
        load_seed_sources(test_data_dir or root / "test_data")
    )
    prompts = build_all_prompts(company, filtered_personas, meeting_topic=config.meeting_topic)
    system_prompts = {role: prompt.system_prompt for role, prompt in prompts.items()}
    persona_names = {role: persona.name for role, persona in filtered_personas.items()}
    return system_prompts, persona_names, participant_ids


def create_initial_state(
    config: MeetingConfig | None = None,
    *,
    test_data_dir: Path | None = None,
    system_prompts: dict[str, str] | None = None,
    persona_names: dict[str, str] | None = None,
    personas: dict[str, Persona] | None = None,
) -> MeetingState:
    config = config or MeetingConfig()
    _ensure_src_on_path()

    if personas is not None:
        all_ids = list(personas.keys())
        participant_ids = _resolve_participant_ids(all_ids, config)
        filtered_personas = {pid: personas[pid] for pid in participant_ids}
        matrix = build_relationship_matrix(filtered_personas, config=config)

        if system_prompts is None or persona_names is None:
            from debating.loaders import load_seed_sources

            root = _repo_root()
            ensure_seeded(test_data_dir)
            company, _ = load_seed_sources(test_data_dir or root / "test_data")
            from debating.prompts import build_all_prompts

            prompts = build_all_prompts(
                company,
                filtered_personas,
                meeting_topic=config.meeting_topic,
            )
            system_prompts = system_prompts or {
                role: prompt.system_prompt for role, prompt in prompts.items()
            }
            persona_names = persona_names or {
                role: persona.name for role, persona in filtered_personas.items()
            }
        else:
            system_prompts = {pid: system_prompts[pid] for pid in participant_ids}
            persona_names = {pid: persona_names[pid] for pid in participant_ids}
    else:
        root = _repo_root()
        ensure_seeded(test_data_dir)
        from debating.loaders import load_seed_sources

        company, loaded_personas = load_seed_sources(test_data_dir or root / "test_data")
        participant_ids = _resolve_participant_ids(list(loaded_personas.keys()), config)
        filtered_personas = {pid: loaded_personas[pid] for pid in participant_ids}
        matrix = build_relationship_matrix(filtered_personas, config=config)

        if system_prompts is None or persona_names is None:
            loaded_prompts, loaded_names, _ = load_prompts(
                config,
                test_data_dir=test_data_dir,
                personas=loaded_personas,
            )
            system_prompts = system_prompts or loaded_prompts
            persona_names = persona_names or loaded_names
        else:
            system_prompts = {pid: system_prompts[pid] for pid in participant_ids}
            persona_names = {pid: persona_names[pid] for pid in participant_ids}

    opening_speaker = _resolve_opening_speaker(participant_ids, config)
    negotiation_profiles = _build_negotiation_profiles(participant_ids, filtered_personas)

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
        last_monologue={},
        negotiation_profiles=negotiation_profiles,
        working_proposals=[],
        shared_facts=[],
    )


def load_seed_bundle(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
