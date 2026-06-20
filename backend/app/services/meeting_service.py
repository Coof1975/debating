"""Meeting persistence service (simulation wired in Phase 2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Meeting, MeetingStatus
from app.schemas.meeting import (
    CreateMeetingRequest,
    MeetingListItem,
    MeetingResponse,
    RerunMeetingRequest,
    UpdateMeetingRequest,
)
from app.services import persona_service


def to_response(row: Meeting) -> MeetingResponse:
    return MeetingResponse(
        id=row.id,
        topic=row.topic,
        opening_message=row.opening_message,
        notes=row.notes or "",
        host_id=row.host_id,
        scheduled_at=row.scheduled_at,
        status=row.status.value,
        participant_ids=row.participant_ids,
        config=row.config,
        record=row.record,
        insight_report=row.insight_report,
        termination_reason=row.termination_reason,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def list_meetings(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    q: str | None = None,
) -> list[MeetingListItem]:
    stmt = select(Meeting).order_by(Meeting.created_at.desc())
    if status:
        try:
            status_enum = MeetingStatus(status)
        except ValueError as exc:
            raise ValueError(f"Invalid status filter: {status}") from exc
        stmt = stmt.where(Meeting.status == status_enum)
    if q and q.strip():
        stmt = stmt.where(Meeting.topic.ilike(f"%{q.strip()}%"))
    stmt = stmt.limit(limit).offset(offset)
    rows = db.scalars(stmt).all()
    return [
        MeetingListItem(
            id=row.id,
            topic=row.topic,
            status=row.status.value,
            participant_ids=row.participant_ids,
            host_id=row.host_id,
            scheduled_at=row.scheduled_at,
            termination_reason=row.termination_reason,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )
        for row in rows
    ]


def get_meeting(db: Session, meeting_id: str) -> Meeting | None:
    return db.get(Meeting, meeting_id)


def get_meeting_or_404(db: Session, meeting_id: str) -> Meeting:
    row = get_meeting(db, meeting_id)
    if row is None:
        raise LookupError(f"Meeting not found: {meeting_id}")
    return row


def _default_model_for_provider(provider: str) -> str:
    defaults = {
        "openai": "gpt-4o-mini",
        "gemini": "gemini-2.5-flash",
        "mock": "mock",
    }
    return defaults.get(provider, "gpt-4o-mini")


def _normalize_participant_ids(participant_ids: list[str]) -> list[str]:
    return [pid.strip().upper() for pid in participant_ids if pid.strip()]


def _resolve_host_id(participant_ids: list[str], host_id: str | None) -> str:
    if not participant_ids:
        raise ValueError("At least one participant is required")
    if host_id:
        host = host_id.strip().upper()
        if host not in participant_ids:
            raise ValueError("host_id must be one of the meeting participants")
        return host
    if "CEO" in participant_ids:
        return "CEO"
    return participant_ids[0]


def _validate_participants(db: Session, participant_ids: list[str]) -> None:
    if not participant_ids:
        raise ValueError("At least one participant is required")
    for role_id in participant_ids:
        row = persona_service.get_persona_or_404(db, role_id)
        if not row.is_active:
            raise ValueError(f"Persona {role_id} is not active")


def _apply_host_to_config(config: dict, host_id: str) -> dict:
    updated = dict(config)
    updated["host_id"] = host_id
    updated["opening_speaker"] = host_id
    return updated


def _build_config_from_payload(payload: CreateMeetingRequest, settings, *, host_id: str) -> dict:
    max_turns = payload.max_turns or settings.default_max_turns
    use_mock = payload.use_mock or payload.llm_provider == "mock"
    provider = "openai" if use_mock else payload.llm_provider
    model = payload.llm_model or _default_model_for_provider(
        "mock" if use_mock else payload.llm_provider
    )

    config = {
        "meeting_topic": payload.topic.strip(),
        "max_turns": max_turns,
        "participant_ids": _normalize_participant_ids(payload.participant_ids),
        "llm_provider": provider,
        "llm_model": model,
        "use_mock": use_mock,
    }
    if payload.opening_message:
        config["opening_message"] = payload.opening_message
    return _apply_host_to_config(config, host_id)


def _merge_llm_config(
    config: dict,
    *,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    use_mock: bool | None = None,
    max_turns: int | None = None,
) -> dict:
    updated = dict(config)
    if max_turns is not None:
        updated["max_turns"] = max_turns

    if llm_provider is not None:
        mock = llm_provider == "mock" or bool(use_mock)
        updated["use_mock"] = mock
        updated["llm_provider"] = "openai" if mock else llm_provider
    elif use_mock is not None:
        updated["use_mock"] = use_mock
        if use_mock:
            updated["llm_provider"] = "openai"

    if llm_model is not None:
        updated["llm_model"] = llm_model
    elif llm_provider is not None:
        updated["llm_model"] = _default_model_for_provider(
            "mock" if updated.get("use_mock") else llm_provider
        )

    return updated


def create_meeting(db: Session, payload: CreateMeetingRequest) -> MeetingResponse:
    settings = get_settings()
    participant_ids = _normalize_participant_ids(payload.participant_ids)
    _validate_participants(db, participant_ids)
    host_id = _resolve_host_id(participant_ids, payload.host_id)

    meeting_id = str(uuid.uuid4())
    config = _build_config_from_payload(payload, settings, host_id=host_id)

    row = Meeting(
        id=meeting_id,
        topic=payload.topic.strip(),
        opening_message=payload.opening_message or "",
        notes=(payload.notes or "").strip(),
        host_id=host_id,
        scheduled_at=payload.scheduled_at,
        status=MeetingStatus.PENDING,
        participant_ids=participant_ids,
        config=config,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return to_response(row)


def update_meeting(db: Session, meeting_id: str, payload: UpdateMeetingRequest) -> MeetingResponse:
    row = get_meeting_or_404(db, meeting_id)
    if row.status != MeetingStatus.PENDING:
        raise ValueError("Only pending meetings can be edited")

    participant_ids = (
        _normalize_participant_ids(payload.participant_ids)
        if payload.participant_ids is not None
        else list(row.participant_ids)
    )
    if payload.participant_ids is not None:
        _validate_participants(db, participant_ids)

    host_id = _resolve_host_id(
        participant_ids,
        payload.host_id if payload.host_id is not None else row.host_id,
    )

    if payload.topic is not None:
        row.topic = payload.topic.strip()
    if payload.opening_message is not None:
        row.opening_message = payload.opening_message
    if payload.notes is not None:
        row.notes = payload.notes.strip()
    if "scheduled_at" in payload.model_fields_set:
        row.scheduled_at = payload.scheduled_at

    row.participant_ids = participant_ids
    row.host_id = host_id

    config = dict(row.config or {})
    config["meeting_topic"] = row.topic
    config["participant_ids"] = participant_ids
    if row.opening_message:
        config["opening_message"] = row.opening_message
    elif "opening_message" in config and not row.opening_message:
        config.pop("opening_message", None)

    config = _apply_host_to_config(config, host_id)
    config = _merge_llm_config(
        config,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
        use_mock=payload.use_mock,
        max_turns=payload.max_turns,
    )
    row.config = config

    db.commit()
    db.refresh(row)
    return to_response(row)


def reset_meeting_for_rerun(
    db: Session,
    meeting_id: str,
    payload: RerunMeetingRequest | None = None,
) -> MeetingResponse:
    row = get_meeting_or_404(db, meeting_id)

    if row.status == MeetingStatus.RUNNING:
        raise ValueError("Meeting is currently running")

    config = dict(row.config or {})
    payload = payload or RerunMeetingRequest()
    config["meeting_topic"] = row.topic
    config["participant_ids"] = list(row.participant_ids)
    if row.host_id:
        config = _apply_host_to_config(config, row.host_id)

    config = _merge_llm_config(
        config,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
        use_mock=payload.use_mock,
        max_turns=payload.max_turns,
    )

    row.config = config
    row.status = MeetingStatus.PENDING
    row.record = None
    row.insight_report = ""
    row.termination_reason = None
    row.error_message = None
    row.completed_at = None
    db.commit()
    db.refresh(row)
    return to_response(row)


def mark_meeting_running(db: Session, meeting_id: str) -> Meeting:
    row = get_meeting_or_404(db, meeting_id)
    row.status = MeetingStatus.RUNNING
    db.commit()
    db.refresh(row)
    return row


def mark_meeting_running_for_extension(db: Session, meeting_id: str) -> Meeting:
    """Transition completed → running for facilitator extension."""
    row = get_meeting_or_404(db, meeting_id)
    if row.status != MeetingStatus.COMPLETED:
        raise ValueError("Extension is only available for completed meetings")
    if not row.record:
        raise ValueError("Meeting has no simulation record")
    row.status = MeetingStatus.RUNNING
    row.error_message = None
    db.commit()
    db.refresh(row)
    return row


def mark_meeting_completed(
    db: Session,
    meeting_id: str,
    *,
    record: dict,
    insight_report: str,
    termination_reason: str | None,
) -> Meeting:
    row = get_meeting_or_404(db, meeting_id)
    row.status = MeetingStatus.COMPLETED
    row.record = record
    row.insight_report = insight_report
    row.termination_reason = termination_reason
    row.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def mark_meeting_failed(db: Session, meeting_id: str, error: str) -> Meeting:
    row = get_meeting_or_404(db, meeting_id)
    row.status = MeetingStatus.FAILED
    row.error_message = error
    row.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def delete_meeting(db: Session, meeting_id: str) -> None:
    row = get_meeting_or_404(db, meeting_id)
    if row.status == MeetingStatus.RUNNING:
        raise ValueError("Cannot delete a running meeting")
    db.delete(row)
    db.commit()
