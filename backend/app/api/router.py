"""API router aggregation."""

from fastapi import APIRouter

from app.api import admin, company, health, llm, meetings, personas

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(llm.router)
api_router.include_router(personas.router)
api_router.include_router(company.router)
api_router.include_router(meetings.router)
api_router.include_router(admin.router)
