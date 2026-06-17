"""Post-meeting 1-1 persona chat service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import setup_paths
from app.config import get_settings
from app.db.models import ChatMessage, ChatSession, Meeting, MeetingStatus
from app.schemas.chat import (
    ChatMessageResponse,
    ChatSessionResponse,
    SendChatMessageResponse,
)
from app.services import meeting_service, persona_service
from app.services.prompt_service import build_meeting_system_prompts

setup_paths()

from sim_chat.config import MeetingConfig
from sim_chat.llm import create_llm_provider
from sim_chat.models import MeetingRecord
from sim_chat.private_chat import PrivateChatMessage, PrivateChatSession, create_session_from_record


def _require_completed_meeting(db: Session, meeting_id: str) -> Meeting:
    row = meeting_service.get_meeting_or_404(db, meeting_id)
    if row.status != MeetingStatus.COMPLETED:
        raise ValueError("Chat is only available for completed meetings")
    if not row.record:
        raise ValueError("Meeting has no simulation record")
    return row


def _validate_persona_participant(meeting: Meeting, persona_id: str) -> str:
    pid = persona_id.strip().upper()
    if pid not in meeting.participant_ids:
        raise ValueError(f"Persona {pid} did not participate in this meeting")
    return pid


def _build_llm_for_meeting(meeting: Meeting, *, persona_id: str, persona_name: str):
    settings = get_settings()
    cfg_data = dict(meeting.config or {})
    cfg_data["meeting_topic"] = meeting.topic
    cfg_data["participant_ids"] = list(meeting.participant_ids)

    allowed = set(MeetingConfig.model_fields.keys())
    filtered = {key: value for key, value in cfg_data.items() if key in allowed}
    config = MeetingConfig(**filtered)

    use_mock = bool(config.use_mock) or settings.use_mock_llm
    return create_llm_provider(
        config,
        use_mock=use_mock,
        persona_names={persona_id: persona_name},
    )


def _session_to_response(db: Session, row: ChatSession) -> ChatSessionResponse:
    message_count = db.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == row.id)
    ) or 0
    last_message = db.scalar(
        select(ChatMessage)
        .where(ChatMessage.session_id == row.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    preview = None
    if last_message:
        preview = last_message.content[:120]
        if len(last_message.content) > 120:
            preview += "…"

    return ChatSessionResponse(
        id=row.id,
        meeting_id=row.meeting_id,
        persona_id=row.persona_id,
        persona_name=row.persona_name,
        message_count=int(message_count),
        last_message_preview=preview,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_to_response(row: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=row.id,
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        created_at=row.created_at,
    )


def list_sessions(db: Session, meeting_id: str) -> list[ChatSessionResponse]:
    _require_completed_meeting(db, meeting_id)
    rows = db.scalars(
        select(ChatSession)
        .where(ChatSession.meeting_id == meeting_id)
        .order_by(ChatSession.updated_at.desc())
    ).all()
    return [_session_to_response(db, row) for row in rows]


def get_session_or_404(db: Session, meeting_id: str, session_id: str) -> ChatSession:
    row = db.get(ChatSession, session_id)
    if row is None or row.meeting_id != meeting_id:
        raise LookupError(f"Chat session not found: {session_id}")
    return row


def get_or_create_session(db: Session, meeting_id: str, persona_id: str) -> ChatSessionResponse:
    meeting = _require_completed_meeting(db, meeting_id)
    pid = _validate_persona_participant(meeting, persona_id)
    persona_service.get_persona_or_404(db, pid)

    existing = db.scalar(
        select(ChatSession).where(
            ChatSession.meeting_id == meeting_id,
            ChatSession.persona_id == pid,
        )
    )
    if existing:
        return _session_to_response(db, existing)

    record = MeetingRecord.model_validate(meeting.record)
    persona_prompts = build_meeting_system_prompts(db, meeting.participant_ids, meeting.topic)
    private = create_session_from_record(record, pid, persona_prompts)

    row = ChatSession(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        persona_id=pid,
        persona_name=private.persona_name,
        system_prompt=private.system_prompt,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _session_to_response(db, row)


def list_messages(db: Session, meeting_id: str, session_id: str) -> list[ChatMessageResponse]:
    _require_completed_meeting(db, meeting_id)
    session = get_session_or_404(db, meeting_id, session_id)
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return [_message_to_response(row) for row in rows]


def send_message(
    db: Session,
    meeting_id: str,
    session_id: str,
    content: str,
) -> SendChatMessageResponse:
    meeting = _require_completed_meeting(db, meeting_id)
    session = get_session_or_404(db, meeting_id, session_id)
    text = content.strip()
    if not text:
        raise ValueError("Message content is required")

    history_rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    ).all()

    private = PrivateChatSession(
        persona_id=session.persona_id,
        persona_name=session.persona_name,
        system_prompt=session.system_prompt,
        messages=[
            PrivateChatMessage(role=row.role, content=row.content) for row in history_rows
        ],
        meeting_id=meeting_id,
        meeting_topic=meeting.topic,
    )

    llm = _build_llm_for_meeting(
        meeting,
        persona_id=session.persona_id,
        persona_name=session.persona_name,
    )
    reply = private.chat(text, llm)

    now = datetime.now(timezone.utc)
    user_row = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        role="user",
        content=text,
        created_at=now,
    )
    assistant_row = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        role="assistant",
        content=reply,
        created_at=datetime.now(timezone.utc),
    )
    session.updated_at = assistant_row.created_at

    db.add(user_row)
    db.add(assistant_row)
    db.commit()
    db.refresh(user_row)
    db.refresh(assistant_row)

    return SendChatMessageResponse(
        user_message=_message_to_response(user_row),
        assistant_message=_message_to_response(assistant_row),
    )
