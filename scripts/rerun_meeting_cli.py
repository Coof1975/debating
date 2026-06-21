#!/usr/bin/env python3
"""Rerun a meeting simulation synchronously and print quality metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Meeting, MeetingStatus
from app.services import meeting_service
from app.services.simulation_service import _build_initial_state, _build_meeting_config
from sim_chat import generate_insight_report, iter_meeting_events
from sim_chat.llm import create_llm_provider
from sim_chat.models import MeetingRecord
from sim_chat.text_quality import text_looks_incomplete


def analyze_record(record: MeetingRecord, insight: str) -> dict:
    msgs = record.messages
    incomplete = [
        {
            "turn": m.turn_index,
            "speaker": m.speaker_name,
            "tail": m.content[-80:],
        }
        for m in msgs
        if text_looks_incomplete(m.content)
    ]
    return {
        "turn_count": len(msgs),
        "termination": record.termination_reason.value if record.termination_reason else None,
        "insight_len": len(insight),
        "insight_tail": insight[-200:] if insight else "",
        "incomplete_turns": incomplete,
        "incomplete_count": len(incomplete),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("meeting_id")
    parser.add_argument("--save", action="store_true", help="Persist results to DB")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        row = meeting_service.get_meeting_or_404(db, args.meeting_id)
        print(f"Meeting: {row.topic[:70]}...")
        print(f"Provider: {row.config.get('llm_provider')} / {row.config.get('llm_model')}")

        config = _build_meeting_config(row)
        print(
            f"Config tokens: speech={config.speech_max_tokens}, "
            f"reasoning={config.reasoning_max_tokens}, "
            f"insight={config.insight_max_tokens}"
        )

        initial_state = _build_initial_state(db, row)
        provider = create_llm_provider(
            config,
            use_mock=bool(config.use_mock) or settings.use_mock_llm,
            persona_names=initial_state["persona_names"],
        )

        record: MeetingRecord | None = None
        for event in iter_meeting_events(
            config,
            llm=provider,
            meeting_id=args.meeting_id,
            initial_state=initial_state,
        ):
            if event["type"] == "turn":
                turn = event["data"]
                print(f"  [turn {turn['turn_index']}] {turn['speaker_name']}: {turn['content'][:100]}...")
            elif event["type"] == "completed":
                record = MeetingRecord.model_validate(event["data"]["record"])

        if record is None:
            print("ERROR: simulation produced no record")
            return 1

        insight = generate_insight_report(record, llm=provider)
        metrics = analyze_record(record, insight)

        print("\n=== RESULTS ===")
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        print("\n=== INSIGHT (first 800 chars) ===")
        print(insight[:800])

        if args.save:
            meeting_service.mark_meeting_completed(
                db,
                args.meeting_id,
                record=record.model_dump(mode="json"),
                insight_report=insight,
                termination_reason=(
                    record.termination_reason.value if record.termination_reason else None
                ),
            )
            row = meeting_service.get_meeting_or_404(db, args.meeting_id)
            row.status = MeetingStatus.COMPLETED
            db.commit()
            print("\nSaved to database.")

    return 0 if metrics["incomplete_count"] == 0 and metrics["insight_len"] > 500 else 2


if __name__ == "__main__":
    raise SystemExit(main())
