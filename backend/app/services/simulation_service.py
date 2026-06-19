"""Run meeting simulations in background threads with SSE event queues."""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sim_chat.config import MeetingConfig
from sim_chat.extension import ExtensionSignificance, evaluate_extension_significance
from sim_chat.graph import iter_meeting_events
from sim_chat.insight import generate_insight_report
from sim_chat.llm import create_llm_provider
from sim_chat.models import MeetingRecord, NegotiationProfile
from sim_chat.resume import attach_extension_audit, extension_count_from_record, prepare_extension_state

from app.bootstrap import setup_paths

setup_paths()

from app.config import get_settings
from app.db.models import Meeting, MeetingStatus
from app.db.session import SessionLocal
from app.services import meeting_service, persona_service
from app.services.prompt_service import build_meeting_system_prompts, persona_from_row

logger = logging.getLogger(__name__)

SENTINEL = {"type": "_end"}


class ExtensionRejected(Exception):
    """Facilitator message did not pass significance gate."""

    def __init__(self, *, reason: str, suggestion: str = "none") -> None:
        self.reason = reason
        self.suggestion = suggestion
        super().__init__(reason)


@dataclass
class MeetingRun:
    meeting_id: str
    event_queue: queue.Queue = field(default_factory=queue.Queue)
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    error: str | None = None


@dataclass
class _ExtensionContext:
    facilitator_content: str
    forced: bool
    significance_reason: str
    started_at: datetime
    prior_message_count: int


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


def _build_extension_runtime(
    db,
    row: Meeting,
) -> tuple[dict[str, str], dict[str, str], dict[str, NegotiationProfile]]:
    system_prompts = build_meeting_system_prompts(db, row.participant_ids, row.topic)
    persona_names: dict[str, str] = {}
    negotiation_profiles: dict[str, NegotiationProfile] = {}

    for role_id in row.participant_ids:
        persona_row = persona_service.get_persona_or_404(db, role_id)
        persona = persona_from_row(persona_row)
        persona_names[role_id] = persona_row.name
        negotiation_profiles[role_id] = NegotiationProfile.model_validate(
            persona.negotiation.model_dump()
        )

    return system_prompts, persona_names, negotiation_profiles


def _require_completed_with_record(row: Meeting) -> MeetingRecord:
    if row.status != MeetingStatus.COMPLETED:
        raise ValueError("Extension is only available for completed meetings")
    if not row.record:
        raise ValueError("Meeting has no simulation record")
    return MeetingRecord.model_validate(row.record)


def _ensure_extension_allowed(row: Meeting, record: MeetingRecord) -> None:
    config = _build_meeting_config(row)
    if not config.enable_meeting_extension:
        raise ValueError("Meeting extension is disabled for this meeting")
    if has_active_run(row.id):
        raise ValueError("Meeting simulation is already running")
    if extension_count_from_record(record) >= config.max_extensions_per_meeting:
        raise ValueError(
            f"Maximum extensions reached ({config.max_extensions_per_meeting})"
        )


def _evaluate_extension_significance(
    row: Meeting,
    record: MeetingRecord,
    content: str,
    *,
    llm,
) -> ExtensionSignificance:
    insight_excerpt = (row.insight_report or "")[:600]
    return evaluate_extension_significance(
        record,
        content,
        insight_excerpt=insight_excerpt,
        llm=llm,
    )


def evaluate_extension(db, meeting_id: str, content: str) -> ExtensionSignificance:
    """Classify facilitator message significance without starting simulation."""
    row = meeting_service.get_meeting_or_404(db, meeting_id)
    record = _require_completed_with_record(row)
    _ensure_extension_allowed(row, record)

    text = content.strip()
    if not text:
        raise ValueError("Message content is required")

    config = _build_meeting_config(row)
    settings = get_settings()
    _, persona_names, _ = _build_extension_runtime(db, row)
    llm = create_llm_provider(
        config,
        use_mock=bool(config.use_mock) or settings.use_mock_llm,
        persona_names=persona_names,
    )
    return _evaluate_extension_significance(row, record, text, llm=llm)


def _attach_extension_metadata(
    record: MeetingRecord,
    *,
    context: _ExtensionContext,
) -> dict[str, Any]:
    return attach_extension_audit(
        record,
        facilitator_content=context.facilitator_content,
        significance_reason=context.significance_reason,
        forced=context.forced,
        started_at=context.started_at,
        prior_message_count=context.prior_message_count,
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


def _run_extension_thread(
    meeting_id: str,
    run: MeetingRun,
    context: _ExtensionContext,
) -> None:
    db = SessionLocal()
    try:
        row = meeting_service.get_meeting_or_404(db, meeting_id)
        if row.status != MeetingStatus.RUNNING:
            raise RuntimeError(
                f"Extension cannot run (status={row.status.value})"
            )

        prior_record = MeetingRecord.model_validate(row.record)
        prompts, persona_names, negotiation_profiles = _build_extension_runtime(db, row)
        initial_state = prepare_extension_state(
            prior_record,
            context.facilitator_content,
            prompts=prompts,
            persona_names=persona_names,
            negotiation_profiles=negotiation_profiles,
        )
        config = initial_state["config"]

        settings = get_settings()
        provider = create_llm_provider(
            config,
            use_mock=bool(config.use_mock) or settings.use_mock_llm,
            persona_names=persona_names,
        )

        facilitator_turn = initial_state["messages"][-1]
        facilitator_event = {
            "type": "turn",
            "data": facilitator_turn.model_dump(),
        }
        run.events.append(facilitator_event)
        run.event_queue.put(facilitator_event)

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

                record_payload = _attach_extension_metadata(record, context=context)

                insight_event = {
                    "type": "insight",
                    "data": {"insight_report": insight},
                }
                run.events.append(insight_event)
                run.event_queue.put(insight_event)

                meeting_service.mark_meeting_completed(
                    db,
                    meeting_id,
                    record=record_payload,
                    insight_report=insight,
                    termination_reason=(
                        record.termination_reason.value if record.termination_reason else None
                    ),
                )

        if record is None:
            raise RuntimeError("Extension ended without a meeting record")

    except Exception as exc:
        logger.exception("Meeting extension failed for %s", meeting_id)
        run.error = str(exc)
        error_event = {"type": "error", "data": {"message": str(exc)}}
        run.events.append(error_event)
        run.event_queue.put(error_event)
        try:
            meeting_service.mark_meeting_failed(db, meeting_id, str(exc))
        except Exception:
            logger.exception("Failed to mark meeting %s as failed after extension", meeting_id)
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


def extend_meeting_simulation(
    db,
    meeting_id: str,
    content: str,
    *,
    force: bool = False,
) -> MeetingRun:
    """Validate significance and resume group simulation from completed record."""
    row = meeting_service.get_meeting_or_404(db, meeting_id)
    record = _require_completed_with_record(row)
    _ensure_extension_allowed(row, record)

    text = content.strip()
    if not text:
        raise ValueError("Message content is required")

    config = _build_meeting_config(row)
    settings = get_settings()
    prompts, persona_names, negotiation_profiles = _build_extension_runtime(db, row)
    llm = create_llm_provider(
        config,
        use_mock=bool(config.use_mock) or settings.use_mock_llm,
        persona_names=persona_names,
    )

    significance = _evaluate_extension_significance(row, record, text, llm=llm)
    if not significance.is_significant and not force:
        raise ExtensionRejected(
            reason=significance.reason or "Tin nhắn chưa đủ ý nghĩa để mở lại cuộc họp.",
            suggestion=significance.suggestion,
        )

    prior_message_count = len(record.messages)
    context = _ExtensionContext(
        facilitator_content=text,
        forced=force,
        significance_reason=significance.reason,
        started_at=datetime.now(timezone.utc),
        prior_message_count=prior_message_count,
    )

    meeting_service.mark_meeting_running_for_extension(db, meeting_id)

    with _lock:
        existing = _active_runs.get(meeting_id)
        if existing and not existing.done:
            return existing

        run = MeetingRun(meeting_id=meeting_id)
        _active_runs[meeting_id] = run
        thread = threading.Thread(
            target=_run_extension_thread,
            args=(meeting_id, run, context),
            name=f"meeting-ext-{meeting_id}",
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
