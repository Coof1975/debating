"""Pydantic schemas for persona API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PersonaSectionSchema(BaseModel):
    key: str
    title: str
    content: str


class PersonaRelationshipSchema(BaseModel):
    target_role: str
    target_name: str = ""
    stance: str
    behavior: str = ""


class NegotiationProfileSchema(BaseModel):
    compromise_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    min_interest_retention: float = Field(default=0.7, ge=0.0, le=1.0)
    director_sensitivity: float = Field(default=0.6, ge=0.0, le=1.0)
    deadlock_tolerance: float = Field(default=0.3, ge=0.0, le=1.0)


class PersonaBase(BaseModel):
    role: str = Field(..., min_length=1, max_length=64)
    display_title: str
    name: str = ""
    age: int | None = None
    tone_of_voice: str = ""
    sections: dict[str, PersonaSectionSchema] = Field(default_factory=dict)
    relationships: list[PersonaRelationshipSchema] = Field(default_factory=list)
    llm_instructions: str = ""
    negotiation: NegotiationProfileSchema | None = None
    is_active: bool = True


class PersonaCreate(PersonaBase):
    pass


class PersonaUpdate(BaseModel):
    display_title: str | None = None
    name: str | None = None
    age: int | None = None
    tone_of_voice: str | None = None
    sections: dict[str, PersonaSectionSchema] | None = None
    relationships: list[PersonaRelationshipSchema] | None = None
    llm_instructions: str | None = None
    negotiation: NegotiationProfileSchema | None = None
    is_active: bool | None = None


class PersonaResponse(PersonaBase):
    source_file: str = ""
    system_prompt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonaListItem(BaseModel):
    role: str
    display_title: str
    name: str
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromptPreviewResponse(BaseModel):
    role: str
    system_prompt: str
    meeting_topic: str | None = None
