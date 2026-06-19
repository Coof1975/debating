"""Run meeting simulations in background threads with SSE event queues."""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Any

from sim_chat.config import MeetingConfig
from sim_chat.graph import iter_meeting_events
from sim_chat.insight import generate_insight_report
from sim_chat.llm import create_llm_provider
from sim_chat.models import MeetingRecord

from app.bootstrap import setup_paths

setup_paths()

from app.config import get_settings
from app.db.models import Meeting, MeetingStatus
from app.db.session import SessionLocal
from app.services import meeting_service, persona_service
from app.services.prompt_service import build_meeting_system_prompts, persona_from_row

logger = logging.getLogger(__name__)

SENTINEL = {"type": "_end"}


@dataclass
class MeetingRun:
    meeting_id: str
    event_queue: queue.Queue = field(default_factory=queue.Queue)
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    error: str | None = None


_active_runs: dict[str, MeetingRun] = {}
_lock = threading.Lock()


def get_active_run(meeting_id: str) -> MeetingRun | None:
    return _get_run(meeting_id)


def has_active_run(meeting_id: str) -> bool:
    with _lock:
        run = _active_runs.get(meeting_id)
        return run is not None and not run.done


def _get_run(meeting_id: str) -> MeetingRun | None:
    with _lock:
        return _active_runs.get(meeting_id)


def _build_meeting_config(row: Meeting) -> MeetingConfig:
    cfg_data = dict(row.config or {})
    cfg_data["meeting_topic"] = row.topic
    cfg_data["participant_ids"] = list(row.participant_ids)
    # opening_message is not required: the opening speaker generates the mandate
    # from the meeting topic in the first turn.
    if row.opening_message:
        cfg_data["opening_message"] = row.opening_message

    allowed = set(MeetingConfig.model_fields.keys())
    filtered = {key: value for key, value in cfg_data.items() if key in allowed}
    config = MeetingConfig(**filtered)
    config = config.model_copy(update={"monologue_in_sse": True})

    stakeholders = [pid for pid in config.key_stakeholders if pid in row.participant_ids]
    if stakeholders:
        config.key_stakeholders = stakeholders

    return config


def _build_initial_state(db, row: Meeting):
    from sim_chat.bootstrap import create_initial_state

    personas: dict[str, Any] = {}
    system_prompts: dict[str, str] = {}
    persona_names: dict[str, str] = {}

    system_prompts = build_meeting_system_prompts(db, row.participant_ids, row.topic)

    for role_id in row.participant_ids:
        persona_row = persona_service.get_persona_or_404(db, role_id)
        personas[role_id] = persona_from_row(persona_row)
        persona_names[role_id] = persona_row.name

    config = _build_meeting_config(row)
    return create_initial_state(
        config,
        system_prompts=system_prompts,
        persona_names=persona_names,
        personas=personas,
    )


def _run_simulation_thread(meeting_id: str, run: MeetingRun) -> None:
    db = SessionLocal()
    try:
        row = meeting_service.get_meeting_or_404(db, meeting_id)
        if row.status not in (MeetingStatus.PENDING, MeetingStatus.RUNNING):
            raise RuntimeError(f"Meeting cannot be started (status={row.status.value})")

        meeting_service.mark_meeting_running(db, meeting_id)
        config = _build_meeting_config(row)
        initial_state = _build_initial_state(db, row)
        settings = get_settings()
        provider = create_llm_provider(
            config,
            use_mock=bool(config.use_mock) or settings.use_mock_llm,
            persona_names=initial_state["persona_names"],
        )

        record: MeetingRecord | None = None

        for event in iter_meeting_events(
            config,
            llm=provider,
            meeting_id=meeting_id,
            initial_state=initial_state,
        ):
            run.events.append(event)
            run.event_queue.put(event)

            if event["type"] == "completed":
                record = MeetingRecord.model_validate(event["data"]["record"])
                insight = generate_insight_report(record, llm=provider)
                record.insight_report = insight

                insight_event = {
                    "type": "insight",
                    "data": {"insight_report": insight},
                }
                run.events.append(insight_event)
                run.event_queue.put(insight_event)

                meeting_service.mark_meeting_completed(
                    db,
                    meeting_id,
                    record=record.model_dump(mode="json"),
                    insight_report=insight,
                    termination_reason=(
                        record.termination_reason.value if record.termination_reason else None
                    ),
                )

        if record is None:
            raise RuntimeError("Simulation ended without a meeting record")

    except Exception as exc:
        logger.exception("Meeting simulation failed for %s", meeting_id)
        run.error = str(exc)
        error_event = {"type": "error", "data": {"message": str(exc)}}
        run.events.append(error_event)
        run.event_queue.put(error_event)
        try:
            meeting_service.mark_meeting_failed(db, meeting_id, str(exc))
        except Exception:
            logger.exception("Failed to mark meeting %s as failed", meeting_id)
    finally:
        run.done = True
        run.event_queue.put(SENTINEL)
        db.close()
        with _lock:
            _active_runs.pop(meeting_id, None)


def start_meeting_simulation(meeting_id: str) -> MeetingRun:
    with _lock:
        existing = _active_runs.get(meeting_id)
        if existing and not existing.done:
            return existing

        run = MeetingRun(meeting_id=meeting_id)
        _active_runs[meeting_id] = run
        thread = threading.Thread(
            target=_run_simulation_thread,
            args=(meeting_id, run),
            name=f"meeting-sim-{meeting_id}",
            daemon=True,
        )
        thread.start()
        return run


def replay_events_from_record(row: Meeting) -> list[dict[str, Any]]:
    if not row.record:
        return []

    record = MeetingRecord.model_validate(row.record)
    events: list[dict[str, Any]] = [
        {
            "type": "started",
            "data": {
                "meeting_id": row.id,
                "participant_ids": row.participant_ids,
                "topic": row.topic,
            },
        },
    ]

    hidden_by_turn: dict[int, dict[str, Any]] = {}
    for hidden in record.metadata.get("hidden_turns") or []:
        if not isinstance(hidden, dict):
            continue
        turn_index = hidden.get("turn_index")
        if isinstance(turn_index, int):
            hidden_by_turn[turn_index] = hidden

    selection_by_turn: dict[int, dict[str, Any]] = {}
    for selection in record.metadata.get("speaker_selections") or []:
        if not isinstance(selection, dict):
            continue
        turn_index = selection.get("turn_index")
        if isinstance(turn_index, int):
            selection_by_turn[turn_index] = selection

    for turn in record.messages:
        selection = selection_by_turn.get(turn.turn_index)
        if selection:
            events.append({"type": "orchestrator", "data": selection})
        hidden = hidden_by_turn.get(turn.turn_index)
        if hidden:
            events.append({"type": "monologue", "data": hidden})
        events.append({"type": "turn", "data": turn.model_dump()})

    verdict = record.metadata.get("secretary_verdict")
    if verdict:
        events.append({"type": "secretary", "data": verdict})

    events.append(
        {
            "type": "completed",
            "data": {
                "meeting_id": row.id,
                "termination_reason": (
                    record.termination_reason.value if record.termination_reason else None
                ),
                "turn_count": len(record.messages),
                "record": row.record,
            },
        }
    )

    if row.insight_report:
        events.append({"type": "insight", "data": {"insight_report": row.insight_report}})

    return events
