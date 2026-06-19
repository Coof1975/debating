"""Turn-level guidance to reduce repeated arguments and polite filler."""

from __future__ import annotations

from .models import DialogueTurn

BANNED_OPENERS_VI = (
    "Cảm ơn",
    "Tôi hiểu quan điểm",
    "Để tôi bổ sung",
    "Tôi xin lên tiếng",
    "Tôi sẽ mở đầu",
    "Cho phép tôi",
    "Theo quan điểm của tôi thì",
)


def _truncate(text: str, limit: int = 220) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def format_own_prior_turns(
    speaker_id: str,
    messages: list[DialogueTurn],
    *,
    limit: int = 2,
) -> str:
    """Compact list of this speaker's recent public utterances."""
    own = [turn for turn in messages if turn.speaker_id == speaker_id][-limit:]
    if not own:
        return ""
    lines: list[str] = []
    for turn in own:
        lines.append(f"- Lượt {turn.turn_index}: {_truncate(turn.content)}")
    return "\n".join(lines)


def build_anti_repetition_block(
    *,
    speaker_id: str,
    messages: list[DialogueTurn],
    stagnation_score: int = 0,
    last_speaker: str = "",
) -> str:
    """Inject explicit no-repeat rules into persona turn context."""
    prior = format_own_prior_turns(speaker_id, messages)
    if not prior and stagnation_score <= 0:
        return ""

    parts = ["[CHỐNG LẶP — bắt buộc tuân thủ]"]
    if prior:
        parts.append(
            "Bạn đã phát biểu các lượt sau — KHÔNG nhắc lại cùng con số, luận điểm, hay cấu trúc câu:"
        )
        parts.append(prior)

    react_target = f" từ {last_speaker}" if last_speaker and last_speaker != speaker_id else ""
    parts.append(
        f"Lượt này PHẢI phản ứng trực tiếp với luận điểm mới nhất{react_target}: "
        "chỉ ra điểm sai/thiếu, đưa số liệu khác, điều kiện chấp nhận, hoặc counter-proposal cụ thể. "
        "Không tái diễn lập trường đã nói."
    )
    banned = ", ".join(f'"{phrase}"' for phrase in BANNED_OPENERS_VI[:5])
    parts.append(f"Cấm mở đầu bằng: {banned}, …")

    if stagnation_score >= 1:
        parts.append(
            f"Phiên đang lặp ý (stagnation={stagnation_score}): "
            "bắt buộc đưa góc MỚI hoặc nhượng bộ có điều kiện — không lặp lại stance cũ."
        )
    if stagnation_score >= 2:
        parts.append(
            "Mức bế tắc cao: phải đề xuất phương án chốt được test "
            "(timeline, KPI, ngưỡng số) thay vì tranh luận vòng lặp."
        )

    return "\n".join(parts)
