#!/usr/bin/env python3
"""Debate designed to deadlock — verify stagnation-based early stop."""

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


STAGNATION_DEBATE_CONFIG = MeetingConfig(
    meeting_topic=(
        "Keos đại chiến kênh bán: đại lý truyền thống vs sàn TMĐT — chiết khấu, tồn kho và quyền exclusivity"
    ),
    opening_message=(
        "Cuộc họp khẩn về kênh phân phối Keos — phải chốt trước khi tan họp:\n"
        "(1) Chiết khấu đại lý cấp 1: Sales đòi 22%, CFO giữ trần 15%, Marketing muốn dồn ngân sách digital.\n"
        "(2) Đại lý cấp 2 qua sàn TMĐT: Sales bảo phải 18% chiết khấu + hỗ trợ ads, "
        "Product cảnh báo lệch giá và hàng giả.\n"
        "(3) Tồn kho trả hàng: CFO yêu cầu đại lý gánh 100% hàng cận date, "
        "Sales phản đối vì mất đối tác chiến lược.\n"
        "(4) Exclusivity vùng: Marketing muốn mở bán online toàn quốc, "
        "Sales bảo phá cam kết độc quyền 120 đại lý.\n"
        "Mỗi người bảo vệ quyền lợi bộ phận — không nhượng bộ dễ dàng."
    ),
    opening_speaker="CEO",
    max_turns=25,
    min_turns_before_consensus=20,
    consensus_check_interval=5,
    consensus_threshold=0.9,
    stop_on_stakeholder_approval=False,
    stagnation_limit=5,
    min_turns_before_stagnation=8,
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    llm_temperature=0.9,
)


def main() -> None:
    config = STAGNATION_DEBATE_CONFIG
    print(f"Starting stagnation test debate: {config.meeting_topic}")
    print(
        f"Max turns: {config.max_turns} | Stagnation limit: {config.stagnation_limit} | "
        f"Min before stagnation stop: {config.min_turns_before_stagnation}\n"
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
    print(f"Saved JSON: {json_path}")
    print(f"Saved TXT : {txt_path}\n")

    print("=== Transcript (last 5 turns) ===")
    for turn in record.messages[-5:]:
        print(f"[L{turn.turn_index}|{turn.speaker_id}] {turn.speaker_name}")
        print(f"{turn.content}\n")

    print("=== Insight Report ===")
    print(record.insight_report)


if __name__ == "__main__":
    main()
