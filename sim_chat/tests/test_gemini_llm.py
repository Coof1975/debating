"""Gemini provider helpers — thinking budget and truncation detection."""

from __future__ import annotations

from types import SimpleNamespace

from sim_chat.llm import (
    GeminiLLMProvider,
    _extract_gemini_text,
    _gemini_output_truncated,
    _is_gemini_thinking_model,
)


def test_is_gemini_thinking_model() -> None:
    assert _is_gemini_thinking_model("gemini-2.5-flash")
    assert _is_gemini_thinking_model("gemini-2.0-flash") is False


def test_extract_gemini_text_skips_thought_parts() -> None:
    response = SimpleNamespace(
        text=None,
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(text="hidden reasoning", thought=True),
                        SimpleNamespace(text="Anh Dũng, em đồng ý một phần.", thought=False),
                    ]
                )
            )
        ],
    )
    assert _extract_gemini_text(response) == "Anh Dũng, em đồng ý một phần."


def test_gemini_output_truncated_on_max_tokens() -> None:
    response = SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")],
    )
    assert _gemini_output_truncated(response, "Royal Canin chiết khấu tới **") is True


def test_gemini_output_not_truncated_when_complete() -> None:
    response = SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason="STOP")],
    )
    assert _gemini_output_truncated(response, "Chúng ta chốt chiết khấu 20%.") is False


def test_build_generate_config_sets_thinking_budget_for_25() -> None:
    from sim_chat.config import MeetingConfig

    provider = GeminiLLMProvider(MeetingConfig(llm_model="gemini-2.5-flash"), api_key="test-key")
    config = provider._build_generate_config(
        system_prompt="sys",
        max_output_tokens=512,
        thinking_budget=0,
    )
    assert config.thinking_config.thinking_budget == 0
