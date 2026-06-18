"""Post-simulation insight report generation."""

from __future__ import annotations

from .facts import format_shared_facts_for_insight
from .llm import LLMProvider, MockLLMProvider
from .models import (
    HiddenTurn,
    InternalMonologue,
    MeetingRecord,
    SharedFact,
    TerminationReason,
    WorkingProposal,
)
from .proposals import (
    best_active_proposal,
    format_proposals_for_insight,
    stakeholder_approved_proposal,
)

INSIGHT_SYSTEM_PROMPT = """\
Bạn là cố vấn chiến lược phân tích biên bản cuộc họp nội bộ doanh nghiệp.

Viết báo cáo insight ngắn gọn bằng tiếng Việt, BÁM SÁT nội dung biên bản thực tế.
Không lặp lại mẫu chung chung; mọi nhận định phải dựa trên lượt phát biểu cụ thể.

Biên bản có thể gồm hai lớp cho mỗi lượt:
- **[Nội bộ]**: suy nghĩ ẩn trước khi phát biểu (absorb, compromise_space, stance_shift)
- **[Công khai]**: lời nói trong cuộc họp

Ngoài biên bản, có thể có dữ liệu bảng đen đã cấu trúc:
- **working_proposals**: đề xuất dung hòa với điểm chung (aggregate_score) và approvals từng persona
- **shared_facts**: số liệu/sự kiện factual kèm phản hồi chấp nhận/bác bỏ của từng persona

Dùng suy nghĩ nội bộ để suy luận động cơ, lợi ích bộ phận, và ý định thật của từng persona.
So sánh nội bộ vs công khai khi chúng lệch nhau (ví dụ: nội bộ sẵn sàng nhún nhường nhưng nói cứng).
Khi có working_proposals hoặc shared_facts, ưu tiên chúng cho phần đồng thuận/rủi ro/bước tiếp
thay vì suy đoán lại từ lời nói — trừ khi blackboard mâu thuẫn rõ với biên bản.

Cấu trúc bắt buộc:
1. Lý do kết thúc cuộc họp — giải thích vì sao cuộc trao đổi dừng lại, dựa trên
   "Thông tin kết thúc" trong biên bản (đồng thuận / lặp lại / hết vòng / dừng thủ công)
   và chỉ ra bằng chứng cụ thể từ các lượt phát biểu cuối; nếu có working_proposals
   đạt ngưỡng đồng thuận thì nêu rõ đề xuất đó
2. Xung đột chính — nêu rõ các bên và luận điểm đối lập
3. Các phe/phái — ai liên minh với ai trong cuộc họp này
4. Điểm đồng thuận (nếu có) — dựa trên working_proposals (aggregate_score, approvals)
   và shared_facts được chấp nhận rộng rãi; hoặc ghi rõ "Chưa đạt đồng thuận"
5. Rủi ro còn tồn đọng — từ tranh luận thực tế; nêu facts bị bác bỏ/tranh cãi
   và proposals có approvals thấp hoặc concerns chưa giải quyết
6. Động cơ & ý định từng persona — phân tích theo suy nghĩ nội bộ (nếu có);
   nêu ai bảo vệ lợi ích gì, ai sẵn sàng compromise ở đâu, và có khoảng cách nào
   giữa suy nghĩ ẩn vs lời nói công khai
7. Đề xuất bước tiếp theo — hành động cụ thể cho ban lãnh đạo; nếu có proposal
   active điểm cao nhất thì xem xét đưa vào khuyến nghị
"""

_TERMINATION_LABELS: dict[TerminationReason, str] = {
    TerminationReason.MAX_ROUNDS: "Đạt giới hạn số vòng/lượt phát biểu",
    TerminationReason.CONSENSUS: "Đạt đồng thuận (Thư ký và/hoặc working_proposals)",
    TerminationReason.STAGNATION: "Tranh luận lặp lại, không có luận điểm mới",
    TerminationReason.MANUAL: "Dừng thủ công",
}


def _parse_working_proposals(record: MeetingRecord) -> list[WorkingProposal]:
    raw = record.metadata.get("working_proposals") or []
    if not isinstance(raw, list):
        return []
    proposals: list[WorkingProposal] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            proposals.append(WorkingProposal.model_validate(item))
        except Exception:
            continue
    return proposals


def _parse_shared_facts(record: MeetingRecord) -> list[SharedFact]:
    raw = record.metadata.get("shared_facts") or []
    if not isinstance(raw, list):
        return []
    facts: list[SharedFact] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            facts.append(SharedFact.model_validate(item))
        except Exception:
            continue
    return facts


def _describe_termination_context(record: MeetingRecord) -> str:
    """Human-readable termination metadata for the insight prompt."""
    reason = record.termination_reason
    if reason is None:
        return "Không xác định — cuộc họp chưa ghi nhận lý do kết thúc."

    lines = [
        f"Loại kết thúc: {_TERMINATION_LABELS.get(reason, reason.value)} ({reason.value})",
    ]
    cfg = record.config
    proposals = _parse_working_proposals(record)

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
            lines.append(f"Key stakeholder ({stakeholders}) đã chấp thuận (Thư ký).")
        summary = verdict.get("summary", "")
        if summary:
            lines.append(f"Tóm tắt Thư ký: {summary}")

        if cfg.enable_working_proposals:
            best = best_active_proposal(proposals)
            if best is not None:
                lines.append(
                    f"Đề xuất hàng đầu trên bàn: [{best.id}] {best.title} "
                    f"(aggregate_score={best.aggregate_score:.0%})."
                )
                if best.aggregate_score >= cfg.consensus_threshold and stakeholder_approved_proposal(
                    best,
                    key_stakeholders=cfg.key_stakeholders,
                    threshold=cfg.consensus_threshold,
                ):
                    stakeholders = ", ".join(cfg.key_stakeholders) or "—"
                    lines.append(
                        f"Proposal aggregate đạt ngưỡng và key stakeholder ({stakeholders}) "
                        "đã chấp thuận."
                    )

    if reason == TerminationReason.MANUAL:
        lines.append("Cuộc họp được dừng theo yêu cầu thủ công, không qua tiêu chí tự động.")

    return "\n".join(lines)


def _parse_hidden_turns(record: MeetingRecord) -> list[HiddenTurn]:
    raw = record.metadata.get("hidden_turns") or []
    if not isinstance(raw, list):
        return []
    hidden_turns: list[HiddenTurn] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            hidden_turns.append(HiddenTurn.model_validate(item))
        except Exception:
            continue
    return hidden_turns


def _hidden_turn_key(*, turn_index: int, speaker_id: str) -> tuple[int, str]:
    return turn_index, speaker_id


def _index_hidden_turns(hidden_turns: list[HiddenTurn]) -> dict[tuple[int, str], HiddenTurn]:
    indexed: dict[tuple[int, str], HiddenTurn] = {}
    for hidden in hidden_turns:
        indexed[_hidden_turn_key(turn_index=hidden.turn_index, speaker_id=hidden.speaker_id)] = hidden
    return indexed


def _format_monologue(monologue: InternalMonologue) -> str:
    parts = [
        f"absorb: {monologue.absorb.strip()}",
        f"compromise_space: {monologue.compromise_space.strip()}",
    ]
    if monologue.stance_shift != 0:
        parts.append(f"stance_shift: {monologue.stance_shift:+.1f}")
    return " | ".join(parts)


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

    proposals = _parse_working_proposals(record)
    facts = _parse_shared_facts(record)

    if record.config.enable_working_proposals:
        lines.extend(
            [
                format_proposals_for_insight(proposals),
                "",
            ]
        )

    if record.config.enable_shared_facts:
        lines.extend(
            [
                format_shared_facts_for_insight(facts),
                "",
            ]
        )

    hidden_turns = _parse_hidden_turns(record)
    hidden_by_key = _index_hidden_turns(hidden_turns)
    if hidden_turns:
        lines.append(
            f"Suy nghĩ nội bộ: có {len(hidden_turns)} lượt ghi nhận "
            "(dùng để phân tích động cơ & ý định)."
        )
        lines.append("")
    else:
        lines.append("Suy nghĩ nội bộ: không có dữ liệu cho cuộc họp này.")
        lines.append("")

    lines.append("Biên bản:")
    for turn in record.messages:
        hidden = hidden_by_key.get(
            _hidden_turn_key(turn_index=turn.turn_index, speaker_id=turn.speaker_id)
        )
        lines.append(
            f"[Vòng {turn.round_number} | {turn.speaker_name} ({turn.speaker_id}) | "
            f"Lượt {turn.turn_index}]"
        )
        if hidden is not None:
            lines.append(f"  [Nội bộ] {_format_monologue(hidden.monologue)}")
        lines.append(f"  [Công khai] {turn.content}")

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
