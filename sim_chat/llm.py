"""LLM provider abstraction for persona and secretary nodes."""

from __future__ import annotations

import json
import os
import re
from typing import Protocol

from .config import MeetingConfig
from .text_quality import text_looks_incomplete


class LLMProvider(Protocol):
    def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str: ...


class MockLLMProvider:
    """Deterministic responses for dry-run and tests."""

    def __init__(self, *, persona_names: dict[str, str] | None = None) -> None:
        self.persona_names = persona_names or {}
        self._turn = 0

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        self._turn += 1
        role_match = re.search(r"Bạn là \*\*([^*]+)\*\*", system_prompt)
        name = role_match.group(1) if role_match else "Thành viên"
        if (
            "NGƯỜI TỔ CHỨC" in system_prompt.upper()
            or "MỞ LẠI TRANH LUẬN NHÓM" in system_prompt.upper()
        ):
            content_match = re.search(r'Tin nhắn mới: "([^"]*)"', user_message)
            content = content_match.group(1) if content_match else user_message
            lowered = content.lower()
            if any(marker in lowered for marker in ("cảm ơn", "thank you", "ok", "đã rõ", "tốt rồi")):
                return json.dumps(
                    {
                        "is_significant": False,
                        "reason": "Dry-run: tin nhắn xác nhận/filler.",
                        "suggestion": "none",
                    },
                    ensure_ascii=False,
                )
            if "giải thích thêm quan điểm cá nhân" in lowered:
                return json.dumps(
                    {
                        "is_significant": False,
                        "reason": "Dry-run: phù hợp chat riêng.",
                        "suggestion": "chat_with_persona",
                    },
                    ensure_ascii=False,
                )
            if any(
                marker in lowered
                for marker in ("ngân sách", "triệu", "tỷ", "deadline", "duyệt thêm", "bổ sung")
            ):
                return json.dumps(
                    {
                        "is_significant": True,
                        "reason": "Dry-run: directive mới với ràng buộc/số liệu.",
                        "suggestion": "extend",
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "is_significant": False,
                    "reason": "Dry-run: không đủ ý nghĩa.",
                    "suggestion": "none",
                },
                ensure_ascii=False,
            )
        if "MEETING ORCHESTRATOR" in system_prompt.upper() or "ĐIỀU PHỐI VIÊN" in system_prompt.upper():
            roles = re.findall(r"\b(CEO|CFO|MARKETING|PRODUCT|SALE)\b", user_message)
            last_match = re.search(r"Last speaker:\s*(\w+)", user_message)
            last_speaker = last_match.group(1) if last_match else ""
            if last_speaker == "FACILITATOR":
                for role in ("CFO", "MARKETING", "PRODUCT", "SALE", "CEO"):
                    if role in user_message:
                        return json.dumps(
                            {
                                "next_speaker": role,
                                "reason": "Dry-run: facilitator directive — ưu tiên được gọi tên.",
                            },
                            ensure_ascii=False,
                        )
            for marker in ("trả lời", "phản hồi", "cho ý kiến", "giải thích", "xin ý kiến"):
                if marker in user_message.lower():
                    for role in ("CFO", "MARKETING", "PRODUCT", "SALE", "CEO"):
                        if role in user_message and role != last_speaker:
                            return json.dumps(
                                {"next_speaker": role, "reason": f"Dry-run: được yêu cầu ({marker})."},
                                ensure_ascii=False,
                            )
            pick = next((r for r in reversed(roles) if r != last_speaker), "CFO")
            return json.dumps(
                {"next_speaker": pick, "reason": "Dry-run: LLM orchestrator fallback."},
                ensure_ascii=False,
            )
        if "trích xuất sự kiện" in system_prompt.lower():
            facts: list[dict] = []
            percent_match = re.search(r"(\+?\d+[\.,]?\d*)\s*%", user_message)
            if percent_match and (
                "chi phí" in user_message.lower() or "vận hành" in user_message.lower()
            ):
                facts.append(
                    {
                        "fact": f"Chi phí vận hành Q1 tăng {percent_match.group(1)}%",
                        "category": "financial",
                        "confidence": 0.85,
                    }
                )
            return json.dumps({"facts": facts}, ensure_ascii=False)
        if "SECRETARY" in system_prompt.upper() or "THƯ KÝ" in system_prompt.upper():
            if "working_proposals" in user_message and '"aggregate_score": 0.9' in user_message:
                return json.dumps(
                    {
                        "consensus_score": 0.9,
                        "has_consensus": True,
                        "key_stakeholder_approval": True,
                        "summary": "Dry-run: đạt đồng thuận qua working_proposals.",
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "consensus_score": 0.35,
                    "has_consensus": False,
                    "key_stakeholder_approval": False,
                    "summary": "Dry-run: chưa đạt đồng thuận.",
                },
                ensure_ascii=False,
            )
        if "tóm tắt biên bản" in system_prompt.lower():
            turn_count = user_message.count("[Lượt ")
            return (
                f"(dry-run) Tóm tắt {turn_count} lượt: các bên tranh chiết khấu/ngân sách/sản xuất; "
                "chưa chốt phương án."
            )
        if "cố vấn chiến lược" in system_prompt.lower():
            has_internal = "[Nội bộ]" in user_message
            motivation_line = (
                "6. Động cơ & ý định: CFO giữ dòng tiền nhưng nội bộ chấp nhận chia pha; "
                "Marketing công khai cứng nhưng nội bộ linh hoạt hơn.\n"
                if has_internal
                else "6. Động cơ & ý định: chưa có suy nghĩ nội bộ — suy luận từ lời nói công khai.\n"
            )
            return (
                "1. Lý do kết thúc: (dry-run) cuộc họp dừng theo tiêu chí hệ thống "
                "trong metadata biên bản.\n"
                "2. Xung đột chính: ngân sách Marketing vs dòng tiền CFO.\n"
                "3. Phe: growth (CEO/Marketing/Sales) vs caution (CFO/Product).\n"
                "4. Chưa đồng thuận về KPI Keos tháng đầu.\n"
                "5. Rủi ro: bao bì kẹt cảng, công suất 200 tấn.\n"
                f"{motivation_line}"
                "7. Đề xuất: chốt phương án ngân sách phân kỳ trong 48h."
            )
        if "PRIVATE" in user_message.upper() or "PHỎNG VẤN RIÊNG" in user_message.upper():
            return f"{name}: (dry-run) Tôi sẽ trả lời chi tiết hơn trong phiên chat riêng."
        if "[INTERNAL REASONING]" in user_message or "INTERNAL REASONING" in system_prompt.upper():
            payload: dict = {
                "absorb": (
                    f"(dry-run) {name} thừa nhận một phần luận điểm trước, "
                    "nhưng vẫn có rủi ro với ngân sách/dòng tiền."
                ),
                "compromise_space": (
                    "(dry-run) Có thể chia pha triển khai hoặc giảm scope giai đoạn 1 "
                    "để giữ lợi ích bộ phận."
                ),
                "stance_shift": 0.35,
                "relationship_lens": (
                    f"(dry-run) {name} vừa nghe đồng nghiệp nói — "
                    "vừa nghi ngờ một phần nhưng cũng muốn ủng hộ phe mình nếu họ đúng hướng."
                ),
                "proposal_scores": [],
                "new_proposal": None,
                "fact_acceptances": [],
            }
            proposal_ids = re.findall(r"\[(p\d+_[^\]]+)\]", user_message)
            fact_ids = re.findall(r"\| (f\d+_[^\]|]+)\]:", user_message)
            for proposal_id in proposal_ids:
                payload["proposal_scores"].append(
                    {
                        "id": proposal_id,
                        "score": 0.55 + (self._turn % 3) * 0.1,
                        "concerns": "(dry-run) Cần làm rõ timeline và ngân sách.",
                    }
                )
            for fact_id in fact_ids:
                payload["fact_acceptances"].append({"fact_id": fact_id, "accepted": True})
                payload["absorb"] = (
                    f"(dry-run) {name} ghi nhận số liệu từ đồng nghiệp ({fact_id}) "
                    "và sẽ xử lý trong phát biểu."
                )
            if not proposal_ids and self._turn % 4 == 0:
                payload["new_proposal"] = {
                    "title": f"(dry-run) Phương án dung hòa từ {name}",
                    "description": (
                        "Chia pha triển khai: giai đoạn 1 thu hẹp scope marketing, "
                        "giữ công suất sản xuất ổn định."
                    ),
                    "parent_id": None,
                }
            return json.dumps(payload, ensure_ascii=False)
        if "[ABSORB]" in user_message and "[COMPROMISE SPACE]" in user_message:
            if "CHỈ ĐẠO TỪ NGƯỜI TỔ CHỨC" in user_message:
                return (
                    f"{name}: Theo directive facilitator vừa phát, "
                    f"tôi sẽ điều chỉnh phương án bộ phận cho phù hợp ràng buộc mới."
                )
            if "mở đầu cuộc họp" in user_message.lower():
                return (
                    f"{name}: (dry-run) Mở đầu cuộc họp — nêu mandate, "
                    f"2–4 decision points và kỳ vọng tranh luận thẳng thắn."
                )
            angles = [
                "ngân sách và dòng tiền",
                "công suất nhà máy Keos",
                "chiết khấu kênh GT",
                "chiến dịch brand TikTok",
                "KPI doanh số tháng đầu",
            ]
            angle = angles[self._turn % len(angles)]
            if "Sự kiện đồng nghiệp" in user_message or "Chi phí vận hành Q1" in user_message:
                return (
                    f"{name}: Tôi đồng ý một phần với hướng vừa trao đổi. "
                    "Với con số chi phí vận hành Q1 +20% mà CFO vừa nêu, "
                    "Marketing cần điều chỉnh kế hoạch chi tiêu cho phù hợp."
                )
            return (
                f"{name}: Tôi đồng ý một phần với hướng vừa trao đổi, "
                f"nhưng cần điều chỉnh theo {angle}. "
                f"Đề xuất chia pha để giảm áp lực giai đoạn đầu — lượt {self._turn}."
            )
        angles = [
            "ngân sách và dòng tiền",
            "công suất nhà máy Keos",
            "chiết khấu kênh GT",
            "chiến dịch brand TikTok",
            "KPI doanh số tháng đầu",
        ]
        angle = angles[self._turn % len(angles)]
        return (
            f"{name}: (dry-run) Theo góc nhìn bộ phận, ưu tiên {angle}. "
            f"Cần thống nhất trước khi cam kết — lượt {self._turn}."
        )


class OpenAILLMProvider:
    """OpenAI Chat Completions backend."""

    def __init__(self, config: MeetingConfig, *, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("Missing OPENAI_API_KEY for OpenAILLMProvider")

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        kwargs: dict = {
            "model": self.config.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.config.llm_temperature,
            "max_tokens": max_tokens or self.config.max_output_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return (response.choices[0].message.content or "").strip()


def _is_gemini_thinking_model(model: str) -> bool:
    """Gemini 2.5+ allocates thinking tokens inside max_output_tokens."""
    normalized = model.lower()
    if "flash-lite" in normalized or "flash_lite" in normalized:
        return False
    return "2.5" in normalized or normalized.startswith("gemini-3")


def _effective_gemini_output_tokens(requested: int, model: str) -> int:
    """Raise floor for 2.5+ so visible output is not starved by thinking tokens."""
    if not _is_gemini_thinking_model(model):
        return requested
    return max(requested, 4096)


GEMINI_FALLBACK_MODEL = "gemini-2.5-flash-lite"


def _gemini_finish_reason(response: object) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    reason = getattr(candidates[0], "finish_reason", None)
    return str(reason) if reason is not None else None


def _gemini_thoughts_token_count(response: object) -> int:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0
    try:
        return int(getattr(usage, "thoughts_token_count", None) or 0)
    except (TypeError, ValueError):
        return 0


def _gemini_output_truncated(response: object, text: str, *, requested_tokens: int) -> bool:
    if text_looks_incomplete(text):
        return True

    reason = _gemini_finish_reason(response)
    if reason and "MAX" in reason.upper():
        return True

    thoughts = _gemini_thoughts_token_count(response)
    if thoughts and thoughts >= max(1, requested_tokens - 64) and len(text) < 120:
        return True

    return False


def _extract_gemini_text(response: object) -> str:
    chunks: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if not part_text:
                continue
            if getattr(part, "thought", False):
                continue
            chunks.append(str(part_text))

    joined = "".join(chunks).strip()
    if joined:
        return joined

    text = getattr(response, "text", None)
    return str(text).strip() if text else ""


class GeminiLLMProvider:
    """Google Gemini backend."""

    def __init__(self, config: MeetingConfig, *, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Missing GOOGLE_API_KEY or GEMINI_API_KEY for GeminiLLMProvider")

    def _build_generate_config(
        self,
        *,
        system_prompt: str,
        max_output_tokens: int,
        thinking_budget: int | None,
        json_mode: bool,
    ) -> object:
        from google.genai import types

        kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": self.config.llm_temperature,
            "max_output_tokens": max_output_tokens,
        }
        if thinking_budget is not None:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs)

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        from google import genai

        client = genai.Client(api_key=self.api_key)
        requested = max_tokens or self.config.max_output_tokens
        uses_thinking = _is_gemini_thinking_model(self.config.llm_model)
        thinking_budget = 0 if uses_thinking else None

        limits: list[int] = []
        first = _effective_gemini_output_tokens(requested, self.config.llm_model)
        limits.extend([first, 8192, 16384])
        limits = sorted(set(limits))

        models = [self.config.llm_model]
        if uses_thinking and self.config.llm_model != GEMINI_FALLBACK_MODEL:
            models.append(GEMINI_FALLBACK_MODEL)

        text = ""

        def _call(model: str, output_tokens: int, budget: int | None, message: str) -> object | None:
            budget_for_call = None if model == GEMINI_FALLBACK_MODEL else budget
            try:
                return client.models.generate_content(
                    model=model,
                    contents=message,
                    config=self._build_generate_config(
                        system_prompt=system_prompt,
                        max_output_tokens=output_tokens,
                        thinking_budget=budget_for_call,
                        json_mode=json_mode,
                    ),
                )
            except Exception:
                return None

        completion_user = (
            f"{user_message.rstrip()}\n\n"
            "[HOÀN THIỆN] Trả lời đầy đủ, kết thúc bằng dấu chấm. Không dừng giữa câu."
        )

        for model in models:
            for limit in limits:
                response = _call(model, limit, thinking_budget, user_message)
                if response is None:
                    continue
                text = _extract_gemini_text(response)
                if not _gemini_output_truncated(response, text, requested_tokens=limit):
                    return text

            response = _call(model, 8192, thinking_budget, completion_user)
            if response is None:
                continue
            text = _extract_gemini_text(response)
            if not _gemini_output_truncated(response, text, requested_tokens=8192):
                return text

        return text


def create_llm_provider(
    config: MeetingConfig,
    *,
    use_mock: bool = False,
    persona_names: dict[str, str] | None = None,
) -> LLMProvider:
    if use_mock:
        return MockLLMProvider(persona_names=persona_names)
    provider = os.getenv("LLM_PROVIDER", config.llm_provider).lower()
    if provider == "gemini":
        return GeminiLLMProvider(config)
    return OpenAILLMProvider(config)
