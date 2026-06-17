"""Meeting API routes."""

from __future__ import annotations

import asyncio
import json
import queue as queue_module
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.models import MeetingStatus
from app.db.session import get_db
from app.schemas.meeting import (
    CreateMeetingRequest,
    MeetingListItem,
    MeetingResponse,
    RerunMeetingRequest,
    UpdateMeetingRequest,
)
from app.services import meeting_service, simulation_service
from app.api import chat

router = APIRouter(prefix="/meetings", tags=["meetings"])
router.include_router(chat.router, prefix="/{meeting_id}/chat")


def _format_sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _stream_run_events(run: simulation_service.MeetingRun) -> AsyncIterator[str]:
    for past in run.events:
        yield _format_sse(past)

    while not run.done:
        try:
            event = await asyncio.to_thread(run.event_queue.get, True, 0.5)
        except queue_module.Empty:
            continue
        if event.get("type") == "_end":
            break
        yield _format_sse(event)


async def _stream_replay(events: list[dict]) -> AsyncIterator[str]:
    for event in events:
        yield _format_sse(event)


@router.get("", response_model=list[MeetingListItem])
def list_meetings(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
) -> list[MeetingListItem]:
    try:
        return meeting_service.list_meetings(db, limit=limit, offset=offset, status=status, q=q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)) -> MeetingResponse:
    try:
        row = meeting_service.get_meeting_or_404(db, meeting_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return meeting_service.to_response(row)


@router.post("", response_model=MeetingResponse, status_code=201)
def create_meeting(
    payload: CreateMeetingRequest,
    db: Session = Depends(get_db),
) -> MeetingResponse:
    try:
        response = meeting_service.create_meeting(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.auto_start:
        meeting_service.mark_meeting_running(db, response.id)
        simulation_service.start_meeting_simulation(response.id)
        row = meeting_service.get_meeting_or_404(db, response.id)
        return meeting_service.to_response(row)
    return response


@router.patch("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: str,
    payload: UpdateMeetingRequest,
    db: Session = Depends(get_db),
) -> MeetingResponse:
    try:
        return meeting_service.update_meeting(db, meeting_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{meeting_id}/start", response_model=MeetingResponse)
def start_meeting(meeting_id: str, db: Session = Depends(get_db)) -> MeetingResponse:
    try:
        row = meeting_service.get_meeting_or_404(db, meeting_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if row.status == MeetingStatus.COMPLETED:
        return meeting_service.to_response(row)
    if row.status == MeetingStatus.RUNNING:
        simulation_service.start_meeting_simulation(meeting_id)
        return meeting_service.to_response(row)
    if row.status != MeetingStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Meeting cannot be started (status={row.status.value})",
        )

    meeting_service.mark_meeting_running(db, meeting_id)
    simulation_service.start_meeting_simulation(meeting_id)
    row = meeting_service.get_meeting_or_404(db, meeting_id)
    return meeting_service.to_response(row)


@router.get("/{meeting_id}/stream")
async def stream_meeting(meeting_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    try:
        row = meeting_service.get_meeting_or_404(db, meeting_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    run = simulation_service.get_active_run(meeting_id)
    if run is not None:
        generator = _stream_run_events(run)
    elif row.status in (MeetingStatus.COMPLETED, MeetingStatus.FAILED):
        events = simulation_service.replay_events_from_record(row)
        if row.status == MeetingStatus.FAILED and row.error_message:
            events.append({"type": "error", "data": {"message": row.error_message}})
        generator = _stream_replay(events)
    elif row.status == MeetingStatus.PENDING:
        raise HTTPException(status_code=400, detail="Meeting has not started yet")
    else:
        raise HTTPException(status_code=404, detail="No active simulation stream for this meeting")

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(meeting_id: str, db: Session = Depends(get_db)) -> None:
    if simulation_service.has_active_run(meeting_id):
        raise HTTPException(status_code=400, detail="Meeting is currently running")
    try:
        meeting_service.delete_meeting(db, meeting_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{meeting_id}/rerun", response_model=MeetingResponse)
def rerun_meeting(
    meeting_id: str,
    payload: RerunMeetingRequest | None = None,
    db: Session = Depends(get_db),
) -> MeetingResponse:
    try:
        response = meeting_service.reset_meeting_for_rerun(db, meeting_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    meeting_service.mark_meeting_running(db, meeting_id)
    simulation_service.start_meeting_simulation(meeting_id)
    row = meeting_service.get_meeting_or_404(db, meeting_id)
    return meeting_service.to_response(row)
