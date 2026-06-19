"""Shared helpers for resolving participants and negotiation profiles."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config import MeetingConfig
from .models import NegotiationProfile

if TYPE_CHECKING:
    from debating.models import Persona


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_src_on_path() -> None:
    src = _repo_root() / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def resolve_participant_ids(all_ids: list[str], config: MeetingConfig) -> list[str]:
    if config.participant_ids:
        selected = [pid.upper() for pid in config.participant_ids]
        missing = [pid for pid in selected if pid not in all_ids]
        if missing:
            raise ValueError(f"Unknown participant_ids: {', '.join(missing)}")
        return selected
    return list(all_ids)


def resolve_opening_speaker(participant_ids: list[str], config: MeetingConfig) -> str:
    opener = (config.opening_speaker or "").upper()
    if opener in participant_ids:
        return opener
    return participant_ids[0]


def build_negotiation_profiles(
    participant_ids: list[str],
    personas: dict[str, Persona] | None,
) -> dict[str, NegotiationProfile]:
    ensure_src_on_path()
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
