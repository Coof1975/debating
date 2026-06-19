"""Hydrate MeetingState from a completed record and prepare extension runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import MeetingConfig
from .models import (
    DialogueTurn,
    FACILITATOR_SPEAKER_ID,
    FACILITATOR_SPEAKER_NAME,
    HiddenTurn,
    MeetingRecord,
    MeetingState,
    NegotiationProfile,
    SecretaryVerdict,
    SharedFact,
    SpeakerSelection,
    WorkingProposal,
)


def _max_turn_index(messages: list[DialogueTurn]) -> int:
    if not messages:
        return 0
    return max(turn.turn_index for turn in messages)


def _load_working_proposals(metadata: dict[str, Any]) -> list[WorkingProposal]:
    raw = metadata.get("working_proposals") or []
    return [WorkingProposal.model_validate(item) for item in raw]


def _load_shared_facts(metadata: dict[str, Any]) -> list[SharedFact]:
    raw = metadata.get("shared_facts") or []
    return [SharedFact.model_validate(item) for item in raw]


def _load_hidden_turns(metadata: dict[str, Any]) -> list[HiddenTurn]:
    raw = metadata.get("hidden_turns") or []
    return [HiddenTurn.model_validate(item) for item in raw]


def _load_speaker_selections(metadata: dict[str, Any]) -> list[SpeakerSelection]:
    raw = metadata.get("speaker_selections") or []
    return [SpeakerSelection.model_validate(item) for item in raw]


def _load_secretary_verdict(metadata: dict[str, Any]) -> SecretaryVerdict | None:
    raw = metadata.get("secretary_verdict")
    if not raw:
        return None
    return SecretaryVerdict.model_validate(raw)


def state_from_record(
    record: MeetingRecord,
    *,
    prompts: dict[str, str],
    persona_names: dict[str, str],
    negotiation_profiles: dict[str, NegotiationProfile] | None = None,
) -> MeetingState:
    """Rebuild LangGraph state from a persisted meeting record."""
    metadata = record.metadata or {}
    messages = list(record.messages)
    participant_ids = list(metadata.get("participant_ids") or record.config.participant_ids or [])
    if not participant_ids:
        participant_ids = list(
            dict.fromkeys(
                turn.speaker_id
                for turn in messages
                if turn.speaker_id not in (FACILITATOR_SPEAKER_ID,)
            )
        )

    config = record.config
    if participant_ids and not config.participant_ids:
        config = config.model_copy(update={"participant_ids": participant_ids})

    turn_index = _max_turn_index(messages)
    last_speaker = messages[-1].speaker_id if messages else ""

    return MeetingState(
        messages=messages,
        relationship_matrix=record.relationship_matrix,
        current_speaker=config.opening_speaker or (participant_ids[0] if participant_ids else ""),
        last_speaker=last_speaker,
        loop_count=record.loop_count,
        stagnation_score=record.stagnation_score,
        turn_index=turn_index,
        participant_ids=participant_ids,
        meeting_topic=record.topic,
        config=config,
        prompts=prompts,
        persona_names=persona_names,
        terminated=False,
        termination_reason="",
        secretary_verdict=_load_secretary_verdict(metadata),
        turns_since_secretary=0,
        transcript_summary=str(metadata.get("transcript_summary") or ""),
        summary_through_turn=int(metadata.get("summary_through_turn") or 0),
        hidden_turns=_load_hidden_turns(metadata),
        speaker_selections=_load_speaker_selections(metadata),
        last_monologue={},
        negotiation_profiles=negotiation_profiles or {},
        working_proposals=_load_working_proposals(metadata),
        shared_facts=_load_shared_facts(metadata),
    )


def append_facilitator_turn(state: MeetingState, content: str) -> MeetingState:
    """Append a human facilitator directive to the transcript."""
    text = content.strip()
    if not text:
        raise ValueError("Facilitator content is required")

    messages = list(state["messages"])
    turn_index = state["turn_index"] + 1
    last_round = messages[-1].round_number if messages else 1
    turn = DialogueTurn(
        speaker_id=FACILITATOR_SPEAKER_ID,
        speaker_name=FACILITATOR_SPEAKER_NAME,
        content=text,
        round_number=last_round,
        turn_index=turn_index,
    )
    messages.append(turn)

    return {
        **state,
        "messages": messages,
        "last_speaker": FACILITATOR_SPEAKER_ID,
        "turn_index": turn_index,
    }


def prepare_extension_state(
    record: MeetingRecord,
    facilitator_content: str,
    *,
    prompts: dict[str, str],
    persona_names: dict[str, str],
    negotiation_profiles: dict[str, NegotiationProfile] | None = None,
) -> MeetingState:
    """Hydrate record, append facilitator turn, and apply extension run limits."""
    state = state_from_record(
        record,
        prompts=prompts,
        persona_names=persona_names,
        negotiation_profiles=negotiation_profiles,
    )
    state = append_facilitator_turn(state, facilitator_content)

    config = state["config"]
    if not config.enable_meeting_extension:
        raise ValueError("Meeting extension is disabled in config")

    turn_index = state["turn_index"]
    new_max_turns = turn_index + config.extension_turn_budget
    config = config.model_copy(
        update={
            "max_turns": new_max_turns,
            # Stale secretary verdict / proposal scores from the prior segment must not
            # end the extension after a single persona turn.
            "min_turns_before_consensus": new_max_turns + 1,
        }
    )

    patch: dict[str, Any] = {
        "config": config,
        "terminated": False,
        "termination_reason": "",
        "turns_since_secretary": 0,
        "secretary_verdict": None,
    }
    if config.extension_stagnation_reset:
        patch["stagnation_score"] = 0

    return {**state, **patch}


def extension_count_from_record(record: MeetingRecord | dict[str, Any]) -> int:
    if isinstance(record, MeetingRecord):
        metadata = record.metadata or {}
    else:
        metadata = record.get("metadata") or {}
    extensions = metadata.get("extensions") or []
    return len(extensions) if isinstance(extensions, list) else 0


def attach_extension_audit(
    record: MeetingRecord,
    *,
    facilitator_content: str,
    significance_reason: str,
    forced: bool,
    started_at: datetime,
    prior_message_count: int,
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    """Append extension audit entry to record metadata and return JSON payload."""
    from datetime import timezone

    record_dict = record.model_dump(mode="json")
    metadata = dict(record_dict.get("metadata") or {})
    extensions = list(metadata.get("extensions") or [])
    done_at = completed_at or datetime.now(timezone.utc)
    turns_added = max(0, len(record.messages) - prior_message_count)
    extensions.append(
        {
            "index": len(extensions) + 1,
            "facilitator_content": facilitator_content,
            "significance_reason": significance_reason,
            "forced": forced,
            "turns_added": turns_added,
            "started_at": started_at.isoformat(),
            "completed_at": done_at.isoformat(),
        }
    )
    metadata["extensions"] = extensions
    record_dict["metadata"] = metadata
    return record_dict
