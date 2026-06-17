"""Export meeting JSON records to readable plain-text transcripts."""

from __future__ import annotations

from pathlib import Path

from .models import MeetingRecord
from .persistence import default_storage_dir, load_meeting_record


def format_meeting_as_text(record: MeetingRecord) -> str:
    """Render a meeting record as a human-readable transcript."""
    lines: list[str] = []
    separator = "=" * 72
    thin = "-" * 72

    lines.append(separator)
    lines.append(f"CUỘC HỌP: {record.topic}")
    lines.append(f"Meeting ID: {record.meeting_id}")
    lines.append(separator)
    lines.append("")

    cfg = record.config
    lines.append("CẤU HÌNH")
    lines.append(thin)
    lines.append(f"  Chủ đề          : {cfg.meeting_topic}")
    lines.append(f"  Người mở đầu    : {cfg.opening_speaker}")
    lines.append(f"  Max rounds      : {cfg.max_rounds}")
    lines.append(f"  LLM             : {cfg.llm_provider}/{cfg.llm_model}")
    lines.append(f"  Temperature     : {cfg.llm_temperature}")
    lines.append(f"  Stakeholders    : {', '.join(cfg.key_stakeholders)}")
    lines.append("")

    lines.append("BIÊN BẢN TRAO ĐỔI")
    lines.append(thin)
    if not record.messages:
        lines.append("  (Chưa có phát biểu.)")
    else:
        for turn in record.messages:
            lines.append(
                f"[Vòng {turn.round_number} | Lượt {turn.turn_index}] "
                f"{turn.speaker_name} ({turn.speaker_id})"
            )
            for paragraph in turn.content.strip().split("\n"):
                paragraph = paragraph.strip()
                if paragraph:
                    lines.append(f"  {paragraph}")
            lines.append("")

    lines.append("KẾT QUẢ")
    lines.append(thin)
    reason = record.termination_reason.value if record.termination_reason else "—"
    lines.append(f"  Kết thúc        : {reason}")
    lines.append(f"  Số lượt phát biểu: {len(record.messages)}")
    lines.append(f"  Vòng họp        : {record.loop_count}")
    lines.append(f"  Stagnation score: {record.stagnation_score}")

    verdict = record.metadata.get("secretary_verdict")
    if verdict:
        lines.append("")
        lines.append("  Đánh giá Thư ký:")
        lines.append(f"    - consensus_score         : {verdict.get('consensus_score', '—')}")
        lines.append(f"    - has_consensus           : {verdict.get('has_consensus', '—')}")
        lines.append(
            f"    - key_stakeholder_approval: {verdict.get('key_stakeholder_approval', '—')}"
        )
        summary = verdict.get("summary", "")
        if summary:
            lines.append(f"    - summary                 : {summary}")

    if record.insight_report.strip():
        lines.append("")
        lines.append("BÁO CÁO INSIGHT")
        lines.append(thin)
        for line in record.insight_report.strip().split("\n"):
            lines.append(f"  {line.rstrip()}")

    lines.append("")
    return "\n".join(lines)


def export_meeting_record(
    meeting_id: str,
    *,
    storage_dir: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Load one meeting JSON and write a .txt transcript alongside it."""
    storage = storage_dir or default_storage_dir()
    record = load_meeting_record(meeting_id, storage_dir=storage)
    return write_meeting_text(record, output_dir=output_dir or storage)


def write_meeting_text(
    record: MeetingRecord,
    *,
    output_dir: Path | None = None,
) -> Path:
    """Write formatted transcript to a .txt file."""
    directory = output_dir or default_storage_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.meeting_id}.txt"
    path.write_text(format_meeting_as_text(record), encoding="utf-8")
    return path


def export_all_meetings(
    *,
    storage_dir: Path | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    """Export every *.json meeting record in storage_dir to .txt files."""
    storage = storage_dir or default_storage_dir()
    out = output_dir or storage
    paths: list[Path] = []

    for json_path in sorted(storage.glob("*.json")):
        meeting_id = json_path.stem
        paths.append(export_meeting_record(meeting_id, storage_dir=storage, output_dir=out))

    return paths
