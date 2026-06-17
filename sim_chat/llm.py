"""LLM provider abstraction for persona and secretary nodes."""

from __future__ import annotations

import json
import os
import re
from typing import Protocol

from .config import MeetingConfig


class LLMProvider(Protocol):
    def generate(self, system_prompt: str, user_message: str) -> str: ...


class MockLLMProvider:
    """Deterministic responses for dry-run and tests."""

    def __init__(self, *, persona_names: dict[str, str] | None = None) -> None:
        self.persona_names = persona_names or {}
        self._turn = 0

    def generate(self, system_prompt: str, user_message: str) -> str:
        self._turn += 1
        role_match = re.search(r"Bạn là \*\*([^*]+)\*\*", system_prompt)
        name = role_match.group(1) if role_match else "Thành viên"
        if "MEETING ORCHESTRATOR" in system_prompt.upper() or "ĐIỀU PHỐI VIÊN" in system_prompt.upper():
            roles = re.findall(r"\b(CEO|CFO|MARKETING|PRODUCT|SALE)\b", user_message)
            last_match = re.search(r"Last speaker:\s*(\w+)", user_message)
            last_speaker = last_match.group(1) if last_match else ""
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
        if "SECRETARY" in system_prompt.upper() or "THƯ KÝ" in system_prompt.upper():
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
            return (
                "1. Lý do kết thúc: (dry-run) cuộc họp dừng theo tiêu chí hệ thống "
                "trong metadata biên bản.\n"
                "2. Xung đột chính: ngân sách Marketing vs dòng tiền CFO.\n"
                "3. Phe: growth (CEO/Marketing/Sales) vs caution (CFO/Product).\n"
                "4. Chưa đồng thuận về KPI Keos tháng đầu.\n"
                "5. Rủi ro: bao bì kẹt cảng, công suất 200 tấn.\n"
                "6. Đề xuất: chốt phương án ngân sách phân kỳ trong 48h."
            )
        if "PRIVATE" in user_message.upper() or "PHỎNG VẤN RIÊNG" in user_message.upper():
            return f"{name}: (dry-run) Tôi sẽ trả lời chi tiết hơn trong phiên chat riêng."
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

    def generate(self, system_prompt: str, user_message: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.config.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=self.config.llm_temperature,
            max_tokens=self.config.max_output_tokens,
        )
        return (response.choices[0].message.content or "").strip()


class GeminiLLMProvider:
    """Google Gemini backend."""

    def __init__(self, config: MeetingConfig, *, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Missing GOOGLE_API_KEY or GEMINI_API_KEY for GeminiLLMProvider")

    def generate(self, system_prompt: str, user_message: str) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.config.llm_model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.config.llm_temperature,
                max_output_tokens=self.config.max_output_tokens,
            ),
        )
        return (response.text or "").strip()


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
