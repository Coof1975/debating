"""Post-simulation insight report generation."""

from __future__ import annotations

from .llm import LLMProvider, MockLLMProvider
from .models import MeetingRecord, TerminationReason

INSIGHT_SYSTEM_PROMPT = """\
Bạn là cố vấn chiến lược phân tích biên bản cuộc họp nội bộ doanh nghiệp.

Viết báo cáo insight ngắn gọn bằng tiếng Việt, BÁM SÁT nội dung biên bản thực tế.
Không lặp lại mẫu chung chung; mọi nhận định phải dựa trên lượt phát biểu cụ thể.

Cấu trúc bắt buộc:
1. Lý do kết thúc cuộc họp — giải thích vì sao cuộc trao đổi dừng lại, dựa trên
   "Thông tin kết thúc" trong biên bản (đồng thuận / lặp lại / hết vòng / dừng thủ công)
   và chỉ ra bằng chứng cụ thể từ các lượt phát biểu cuối
2. Xung đột chính — nêu rõ các bên và luận điểm đối lập
3. Các phe/phái — ai liên minh với ai trong cuộc họp này
4. Điểm đồng thuận (nếu có) — hoặc ghi rõ "Chưa đạt đồng thuận"
5. Rủi ro còn tồn đọng — từ tranh luận thực tế
6. Đề xuất bước tiếp theo — hành động cụ thể cho ban lãnh đạo
"""

_TERMINATION_LABELS: dict[TerminationReason, str] = {
    TerminationReason.MAX_ROUNDS: "Đạt giới hạn số vòng/lượt phát biểu",
    TerminationReason.CONSENSUS: "Đạt đồng thuận theo đánh giá Thư ký",
    TerminationReason.STAGNATION: "Tranh luận lặp lại, không có luận điểm mới",
    TerminationReason.MANUAL: "Dừng thủ công",
}


def _describe_termination_context(record: MeetingRecord) -> str:
    """Human-readable termination metadata for the insight prompt."""
    reason = record.termination_reason
    if reason is None:
        return "Không xác định — cuộc họp chưa ghi nhận lý do kết thúc."

    lines = [
        f"Loại kết thúc: {_TERMINATION_LABELS.get(reason, reason.value)} ({reason.value})",
    ]
    cfg = record.config

    if reason == TerminationReason.MAX_ROUNDS:
        if cfg.max_turns is not None:
            lines.append(
                f"Đã dùng hết {len(record.messages)}/{cfg.max_turns} lượt phát biểu cho phép."
            )
        else:
            lines.append(
                f"Đã hoàn thành {record.loop_count}/{cfg.max_rounds} vòng họp "
                f"({len(record.messages)} lượt phát biểu)."
            )

    if reason == TerminationReason.STAGNATION:
        lines.append(
            f"Điểm stagnation: {record.stagnation_score} "
            f"(ngưỡng dừng: {cfg.stagnation_limit})."
        )
        lines.append(
            "Các lượt phát biểu gần cuối lặp lại luận điểm cũ, không tiến triển."
        )

    if reason == TerminationReason.CONSENSUS:
        verdict = record.metadata.get("secretary_verdict") or {}
        score = verdict.get("consensus_score")
        if score is not None:
            lines.append(
                f"Điểm đồng thuận Thư ký: {score} (ngưỡng: {cfg.consensus_threshold})."
            )
        if verdict.get("has_consensus"):
            lines.append("Thư ký xác nhận đã đạt đồng thuận.")
        if verdict.get("key_stakeholder_approval"):
            stakeholders = ", ".join(cfg.key_stakeholders) or "—"
            lines.append(f"Key stakeholder ({stakeholders}) đã chấp thuận.")
        summary = verdict.get("summary", "")
        if summary:
            lines.append(f"Tóm tắt Thư ký: {summary}")

    if reason == TerminationReason.MANUAL:
        lines.append("Cuộc họp được dừng theo yêu cầu thủ công, không qua tiêu chí tự động.")

    return "\n".join(lines)


def _format_record_for_insight(record: MeetingRecord) -> str:
    lines = [
        f"Chủ đề: {record.topic}",
        f"Số lượt phát biểu: {len(record.messages)}",
        "",
        "Thông tin kết thúc:",
        _describe_termination_context(record),
        "",
    ]

    verdict = record.metadata.get("secretary_verdict")
    if verdict:
        lines.extend(
            [
                "Đánh giá Thư ký:",
                f"  - consensus_score: {verdict.get('consensus_score')}",
                f"  - has_consensus: {verdict.get('has_consensus')}",
                f"  - key_stakeholder_approval: {verdict.get('key_stakeholder_approval')}",
                f"  - summary: {verdict.get('summary', '')}",
                "",
            ]
        )

    lines.append("Biên bản:")
    for turn in record.messages:
        lines.append(
            f"[Vòng {turn.round_number} | {turn.speaker_name} ({turn.speaker_id})] "
            f"{turn.content}"
        )

    factions = record.relationship_matrix.factions
    if factions:
        lines.append("\nPhe/phái (tham khảo ma trận quan hệ):")
        for name, members in factions.items():
            lines.append(f"  - {name}: {', '.join(members)}")
    return "\n".join(lines)


def generate_insight_report(
    record: MeetingRecord,
    llm: LLMProvider | None = None,
) -> str:
    """Produce an executive insight summary from a completed meeting."""
    llm = llm or MockLLMProvider()
    body = _format_record_for_insight(record)
    report = llm.generate(
        INSIGHT_SYSTEM_PROMPT,
        f"Biên bản cuộc họp:\n\n{body}",
    )
    return report.strip()
