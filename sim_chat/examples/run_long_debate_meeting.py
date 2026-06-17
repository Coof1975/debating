#!/usr/bin/env python3
"""Long multi-stakeholder Keos debate: Sales+Marketing vs Product+CFO, CEO arbitrates."""

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


LONG_DEBATE_CONFIG = MeetingConfig(
    meeting_topic=(
        "Chốt roadmap Keos Q3: phân bổ 3 tỷ ngân sách, chiết khấu, đổi bao bì và KPI sản lượng"
    ),
    opening_message=(
        "Cuộc họp chiến lược Keos — phải chốt 4 quyết định trước khi tan họp:\n"
        "(1) Phân bổ 3 tỷ VNĐ ngân sách còn lại: Marketing đòi 2.5 tỷ Brand, "
        "Sales+Marketing đề xuất chuyển 1.2 tỷ sang trade marketing/chiết khấu.\n"
        "(2) Chiết khấu thương mại Keos: Sales yêu cầu 25%, CFO giữ 15%, biên lợi nhuận đã sụt.\n"
        "(3) Đổi bao bì premium trong 3 tuần vs Product báo bao bì kẹt cảng, công suất max 200 tấn/tháng.\n"
        "(4) KPI tháng đầu: CEO đặt 300 tấn, Sales cam kết nếu có chiết khấu, Product phản đối.\n"
        "Mỗi người nêu quan điểm thẳng, bảo vệ quyền lợi bộ phận — không nói chung chung."
    ),
    opening_speaker="CEO",
    max_turns=25,
    max_rounds=5,
    min_turns_before_consensus=18,
    consensus_check_interval=5,
    consensus_threshold=0.85,
    stop_on_stakeholder_approval=False,
    stagnation_limit=5,
    enable_rolling_summary=True,
    rolling_summary_min_turns=12,
    rolling_summary_recent_turns=5,
    rolling_summary_refresh_interval=5,
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    llm_temperature=0.9,
)


def main() -> None:
    config = LONG_DEBATE_CONFIG
    print(f"Starting long debate: {config.meeting_topic}")
    print(
        f"Max turns: {config.max_turns} | Min before consensus: {config.min_turns_before_consensus} | "
        f"Rolling summary from turn {config.rolling_summary_min_turns}\n"
    )

    initial = create_initial_state(config)
    llm = create_llm_provider(config, persona_names=initial["persona_names"])

    record = run_meeting(config, llm=llm)
    record.insight_report = generate_insight_report(record, llm=llm)

    json_path = save_meeting_record(record)
    txt_path = write_meeting_text(record)

    print(f"Meeting ID: {record.meeting_id}")
    print(f"Termination: {record.termination_reason}")
    print(f"Turns: {len(record.messages)} | Stagnation score: {record.stagnation_score}")
    summary = record.metadata.get("transcript_summary", "")
    if summary:
        print(f"Rolling summary covers through turn: {record.metadata.get('summary_through_turn', 0)}")
    print(f"Saved JSON: {json_path}")
    print(f"Saved TXT : {txt_path}\n")

    print("=== Transcript ===")
    for turn in record.messages:
        print(f"[L{turn.turn_index}|{turn.speaker_id}] {turn.speaker_name}")
        print(f"{turn.content}\n")

    print("=== Insight Report ===")
    print(record.insight_report)


if __name__ == "__main__":
    main()
