"""Persist and load completed meeting records."""

from __future__ import annotations

import json
from pathlib import Path

from .models import MeetingRecord


def default_storage_dir() -> Path:
    return Path(__file__).resolve().parent / "data" / "meetings"


def save_meeting_record(record: MeetingRecord, *, storage_dir: Path | None = None) -> Path:
    directory = storage_dir or default_storage_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.meeting_id}.json"
    path.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_meeting_record(meeting_id: str, *, storage_dir: Path | None = None) -> MeetingRecord:
    directory = storage_dir or default_storage_dir()
    path = directory / f"{meeting_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Meeting record not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return MeetingRecord.model_validate(payload)
