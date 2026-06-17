"""Pydantic schemas for post-meeting chat API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateChatSessionRequest(BaseModel):
    persona_id: str = Field(..., min_length=1)


class ChatSessionResponse(BaseModel):
    id: str
    meeting_id: str
    persona_id: str
    persona_name: str
    message_count: int = 0
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SendChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


class SendChatMessageResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
