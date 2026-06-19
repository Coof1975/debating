"""Significance gate for post-meeting facilitator extension."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel

from .llm import LLMProvider
from .models import DialogueTurn, MeetingRecord

EXTENSION_SIGNIFICANCE_SYSTEM = """\
Bạn đánh giá tin nhắn của NGƯỜI TỔ CHỨC sau cuộc họp mô phỏng đã kết thúc.

Nhiệm vụ: quyết định có nên MỞ LẠI tranh luận nhóm hay không.

is_significant = true CHỈ KHI tin nhắn:
- Bổ sung ràng buộc / số liệu / quyết định CHƯA có trong biên bản
- Yêu cầu một hoặc nhiều phe phản hồi trước nhóm
- Thay đổi tiêu chí chốt hoặc ưu tiên thảo luận

is_significant = false nếu:
- Cảm ơn, xác nhận, filler
- Lặp nội dung đã thảo luận
- Câu hỏi phù hợp chat riêng 1 persona (suggestion = chat_with_persona)

Trả lời CHỈ bằng JSON hợp lệ:
{"is_significant": boolean, "reason": "...", "suggestion": "extend"|"chat_with_persona"|"none"}
"""


class ExtensionSignificance(BaseModel):
    is_significant: bool
    reason: str = ""
    suggestion: Literal["extend", "chat_with_persona", "none"] = "none"


def _format_recent_transcript(messages: list[DialogueTurn], *, limit: int = 5) -> str:
    recent = messages[-limit:]
    return "\n".join(
        f"[{turn.speaker_name} ({turn.speaker_id})]: {turn.content}"
        for turn in recent
    )


def _parse_significance_response(raw: str) -> ExtensionSignificance | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
        suggestion = str(payload.get("suggestion", "none")).strip().lower()
        if suggestion not in ("extend", "chat_with_persona", "none"):
            suggestion = "none"
        return ExtensionSignificance(
            is_significant=bool(payload.get("is_significant", False)),
            reason=str(payload.get("reason", "")).strip(),
            suggestion=suggestion,  # type: ignore[arg-type]
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _heuristic_significance(content: str) -> ExtensionSignificance:
    """Fallback when LLM JSON parse fails."""
    lowered = content.lower().strip()
    filler_markers = ("cảm ơn", "thank", "ok", "đã rõ", "tốt rồi", "hết")
    if any(marker in lowered for marker in filler_markers) and len(lowered) < 80:
        return ExtensionSignificance(
            is_significant=False,
            reason="Tin nhắn mang tính xác nhận/filler.",
            suggestion="none",
        )
    if "giải thích thêm" in lowered and "?" in content:
        return ExtensionSignificance(
            is_significant=False,
            reason="Phù hợp chat riêng với persona hơn là mở lại nhóm.",
            suggestion="chat_with_persona",
        )
    significant_markers = (
        "ngân sách",
        "triệu",
        "tỷ",
        "deadline",
        "duyệt",
        "bổ sung",
        "ràng buộc",
        "yêu cầu",
        "phải chốt",
    )
    if any(marker in lowered for marker in significant_markers):
        return ExtensionSignificance(
            is_significant=True,
            reason="Có thông tin/ràng buộc mới cần phản hồi nhóm.",
            suggestion="extend",
        )
    return ExtensionSignificance(
        is_significant=False,
        reason="Không phát hiện directive đủ ý nghĩa để mở lại cuộc họp.",
        suggestion="none",
    )


def build_extension_significance_prompt(
    record: MeetingRecord,
    content: str,
    *,
    insight_excerpt: str = "",
) -> str:
    termination = (
        record.termination_reason.value if record.termination_reason else "unknown"
    )
    excerpt = insight_excerpt.strip()
    if len(excerpt) > 600:
        excerpt = excerpt[:600] + "…"

    return f"""\
Chủ đề: {record.topic}
Lý do kết thúc: {termination}
Tóm tắt insight (rút gọn): {excerpt or "(không có)"}

Biên bản gần nhất:
{_format_recent_transcript(record.messages)}

Tin nhắn mới: "{content.strip()}"
"""


def evaluate_extension_significance(
    record: MeetingRecord,
    content: str,
    *,
    insight_excerpt: str = "",
    llm: LLMProvider,
) -> ExtensionSignificance:
    """Classify whether a facilitator message should resume group simulation."""
    text = content.strip()
    if not text:
        return ExtensionSignificance(
            is_significant=False,
            reason="Nội dung trống.",
            suggestion="none",
        )

    user_message = build_extension_significance_prompt(
        record,
        text,
        insight_excerpt=insight_excerpt,
    )
    raw = llm.generate(EXTENSION_SIGNIFICANCE_SYSTEM, user_message)
    parsed = _parse_significance_response(raw)
    if parsed is not None:
        if parsed.is_significant:
            parsed.suggestion = "extend"
        return parsed
    return _heuristic_significance(text)
