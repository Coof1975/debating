#!/usr/bin/env python3
"""Run a conflict-heavy Keos launch meeting: Marketing+Sales vs Product+CFO."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sim_chat import MeetingConfig, generate_insight_report, run_meeting, save_meeting_record  # noqa: E402
from sim_chat.bootstrap import create_initial_state  # noqa: E402
from sim_chat.export import write_meeting_text  # noqa: E402
from sim_chat.llm import create_llm_provider  # noqa: E402


CONFLICT_MEETING_CONFIG = MeetingConfig(
    meeting_topic=(
        "Phương án tung hàng Keos tháng đầu: đổi bao bì theo trend, "
        "tăng chiết khấu 25% và gói KM tặng quà"
    ),
    opening_message=(
        "Cuộc họp khẩn về kế hoạch ra mắt Keos tháng đầu. Marketing và Sales "
        "trình phương án chung: (1) đổi bao bì premium theo trend trong 3 tuần, "
        "(2) tăng chiết khấu thương mại lên 25% để NPP nhận hàng, "
        "(3) gói khuyến mãi tặng quà kèm hộp — cần ngân sách trade marketing 1.2 tỷ. "
        "Product và CFO được mời phản biện thẳng. Phải chốt phương án hôm nay."
    ),
    opening_speaker="MARKETING",
    max_turns=20,
    max_rounds=4,
    min_turns_before_consensus=12,
    consensus_check_interval=4,
    consensus_threshold=0.85,
    stop_on_stakeholder_approval=False,
    enable_rolling_summary=True,
    rolling_summary_min_turns=12,
    stagnation_limit=4,
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    llm_temperature=0.9,
)


def main() -> None:
    config = CONFLICT_MEETING_CONFIG
    print(f"Starting conflict meeting: {config.meeting_topic}")
    print(f"Max turns: {config.max_turns} | Stakeholder early-stop: {config.stop_on_stakeholder_approval}\n")

    initial = create_initial_state(config)
    llm = create_llm_provider(config, persona_names=initial["persona_names"])

    record = run_meeting(config, llm=llm)
    record.insight_report = generate_insight_report(record, llm=llm)

    json_path = save_meeting_record(record)
    txt_path = write_meeting_text(record)

    print(f"Meeting ID: {record.meeting_id}")
    print(f"Termination: {record.termination_reason}")
    print(f"Turns: {len(record.messages)} | Stagnation score: {record.stagnation_score}")
    print(f"Saved JSON: {json_path}")
    print(f"Saved TXT : {txt_path}\n")

    print("=== Transcript ===")
    for turn in record.messages:
        print(f"[{turn.speaker_name}] {turn.content}\n")

    print("=== Insight Report ===")
    print(record.insight_report)


if __name__ == "__main__":
    main()
