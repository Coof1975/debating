#!/usr/bin/env python3
"""Run a Virtual Meeting Room simulation (dry-run or live LLM)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sim_chat import (  # noqa: E402
    MeetingConfig,
    create_session_from_record,
    generate_insight_report,
    run_meeting,
    save_meeting_record,
)
from sim_chat.bootstrap import create_initial_state, load_prompts  # noqa: E402
from sim_chat.llm import create_llm_provider  # noqa: E402
from sim_chat.private_chat import demo_private_reply  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock LLM (no API key required)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=2,
        help="Number of full meeting rounds before max-rounds stop (default: 2)",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        default="openai",
        help="LLM provider (default: openai)",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        help="Override model name (default: gpt-4o-mini for OpenAI)",
    )
    parser.add_argument(
        "--private-with",
        metavar="ROLE",
        help="After meeting, open 1-1 chat with persona (e.g. CFO)",
    )
    args = parser.parse_args()

    config_kwargs: dict = {"max_rounds": args.max_rounds, "llm_provider": args.provider}
    if args.model:
        config_kwargs["llm_model"] = args.model
    config = MeetingConfig(**config_kwargs)
    print(f"Starting meeting: {config.meeting_topic}")
    mode = "dry-run (mock)" if args.dry_run else f"live ({config.llm_provider}/{config.llm_model})"
    print(f"Mode: {mode}\n")

    record = run_meeting(config, use_mock=args.dry_run)
    if args.dry_run:
        record.insight_report = generate_insight_report(record)
    else:
        initial = create_initial_state(config)
        llm = create_llm_provider(
            config,
            persona_names=initial["persona_names"],
        )
        record.insight_report = generate_insight_report(record, llm=llm)
    path = save_meeting_record(record)

    print(f"Meeting ID: {record.meeting_id}")
    print(f"Termination: {record.termination_reason}")
    print(f"Turns: {len(record.messages)} | Stagnation score: {record.stagnation_score}")
    print(f"Saved: {path}\n")

    print("=== Transcript ===")
    for turn in record.messages:
        print(f"[{turn.speaker_name}] {turn.content}\n")

    print("=== Insight Report ===")
    print(record.insight_report)
    print()

    if args.private_with:
        prompts, _, _ = load_prompts(config)
        session = create_session_from_record(record, args.private_with.upper(), prompts)
        answer = demo_private_reply(
            session,
            "Sau cuộc họp, anh/chị thật sự nghĩ gì về ngân sách Marketing 2.5 tỷ?",
            use_mock=args.dry_run,
        )
        print(f"=== 1-1 with {session.persona_name} ===")
        print(answer)


if __name__ == "__main__":
    main()
