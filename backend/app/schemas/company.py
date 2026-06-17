"""Pydantic schemas for company profile API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CompanySectionSchema(BaseModel):
    key: str
    title: str
    content: str
    perspective: str = ""


class CompanyProfileResponse(BaseModel):
    company_name: str
    report_period: str = ""
    source: str = ""
    sections: dict[str, CompanySectionSchema] = Field(default_factory=dict)
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyProfileUpdate(BaseModel):
    company_name: str | None = None
    report_period: str | None = None
    source: str | None = None
    sections: dict[str, CompanySectionSchema] | None = None


class RebuildPromptsResponse(BaseModel):
    updated_personas: list[str]
    message: str
