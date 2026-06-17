"""LLM provider options for the UI."""

from __future__ import annotations

from pydantic import BaseModel


class LlmModelOption(BaseModel):
    id: str
    label: str


class LlmProviderOption(BaseModel):
    id: str
    label: str
    models: list[LlmModelOption]
    default_model: str


class LlmOptionsResponse(BaseModel):
    providers: list[LlmProviderOption]
