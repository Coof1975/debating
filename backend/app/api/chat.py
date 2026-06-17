"""Post-meeting chat API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import (
    ChatMessageResponse,
    ChatSessionResponse,
    CreateChatSessionRequest,
    SendChatMessageRequest,
    SendChatMessageResponse,
)
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_chat_sessions(meeting_id: str, db: Session = Depends(get_db)) -> list[ChatSessionResponse]:
    try:
        return chat_service.list_sessions(db, meeting_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_chat_session(
    meeting_id: str,
    payload: CreateChatSessionRequest,
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    try:
        return chat_service.get_or_create_session(db, meeting_id, payload.persona_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_chat_messages(
    meeting_id: str,
    session_id: str,
    db: Session = Depends(get_db),
) -> list[ChatMessageResponse]:
    try:
        return chat_service.list_messages(db, meeting_id, session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages", response_model=SendChatMessageResponse)
def send_chat_message(
    meeting_id: str,
    session_id: str,
    payload: SendChatMessageRequest,
    db: Session = Depends(get_db),
) -> SendChatMessageResponse:
    try:
        return chat_service.send_message(db, meeting_id, session_id, payload.content)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
