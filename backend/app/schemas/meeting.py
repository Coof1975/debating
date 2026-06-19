"""Pydantic schemas for meeting API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateMeetingRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    opening_message: str | None = None
    notes: str | None = None
    scheduled_at: datetime | None = None
    participant_ids: list[str] = Field(..., min_length=1)
    host_id: str | None = None
    max_turns: int | None = None
    llm_provider: str = "openai"
    llm_model: str | None = None
    use_mock: bool = False
    auto_start: bool = False


class UpdateMeetingRequest(BaseModel):
    topic: str | None = Field(default=None, min_length=1)
    opening_message: str | None = None
    notes: str | None = None
    scheduled_at: datetime | None = None
    participant_ids: list[str] | None = Field(default=None, min_length=1)
    host_id: str | None = None
    max_turns: int | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    use_mock: bool | None = None


class RerunMeetingRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    use_mock: bool | None = None
    max_turns: int | None = None


class ExtendMeetingRequest(BaseModel):
    content: str = Field(..., min_length=1)
    force: bool = False


class ExtensionSignificanceResponse(BaseModel):
    is_significant: bool
    reason: str
    suggestion: str


class ExtensionRejectedResponse(BaseModel):
    accepted: bool = False
    reason: str
    suggestion: str


class MeetingListItem(BaseModel):
    id: str
    topic: str
    status: str
    participant_ids: list[str]
    host_id: str | None = None
    scheduled_at: datetime | None = None
    termination_reason: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class MeetingResponse(BaseModel):
    id: str
    topic: str
    opening_message: str
    notes: str = ""
    host_id: str | None = None
    scheduled_at: datetime | None = None
    status: str
    participant_ids: list[str]
    config: dict[str, Any] = Field(default_factory=dict)
    record: dict[str, Any] | None = None
    insight_report: str = ""
    termination_reason: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
