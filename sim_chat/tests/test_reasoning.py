"""Tests for internal monologue parsing and persona speech generation."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.llm import MockLLMProvider
from sim_chat.models import InternalMonologue
from sim_chat.reasoning import (
    build_reasoning_user_message,
    build_speech_user_message,
    generate_persona_speech,
    parse_monologue,
    strip_json_fence,
)


def test_strip_json_fence() -> None:
    raw = '```json\n{"absorb": "a", "compromise_space": "b", "stance_shift": 0.1}\n```'
    assert strip_json_fence(raw).startswith("{")


def test_parse_monologue_valid_json() -> None:
    raw = """
    {
      "absorb": "Luận điểm về tiềm năng hợp lý.",
      "compromise_space": "Chia pha triển khai giai đoạn 1.",
      "stance_shift": 0.4
    }
    """
    monologue = parse_monologue(raw)
    assert monologue is not None
    assert "tiềm năng" in monologue.absorb
    assert monologue.stance_shift == 0.4


def test_parse_monologue_clamps_stance_shift() -> None:
    raw = '{"absorb": "a", "compromise_space": "b", "stance_shift": 9.9}'
    monologue = parse_monologue(raw)
    assert monologue is not None
    assert monologue.stance_shift == 1.0


def test_parse_monologue_invalid_returns_none() -> None:
    assert parse_monologue("not json") is None
    assert parse_monologue('{"absorb": "only one field"}') is None


def test_build_reasoning_user_message_includes_marker() -> None:
    message = build_reasoning_user_message("[Cuộc họp: test]")
    assert "[INTERNAL REASONING]" in message


def test_build_speech_user_message_includes_monologue() -> None:
    monologue = InternalMonologue(
        absorb="Đồng ý một phần.",
        compromise_space="Chia pha.",
        stance_shift=0.2,
        relationship_lens="Hơi bực với CFO nhưng phải giữ mặt.",
    )
    message = build_speech_user_message("[Cuộc họp: test]", monologue)
    assert "[ABSORB]" in message
    assert "[RELATIONSHIP LENS]" in message
    assert "Đồng ý một phần." in message
    assert "Hơi bực" in message


def test_generate_persona_speech_disabled_uses_single_call() -> None:
    llm = MockLLMProvider(persona_names={"CFO": "Trần Minh Trí"})
    config = MeetingConfig(enable_internal_monologue=False, use_mock=True)
    system_prompt = "Bạn là **Trần Minh Trí**, CFO."
    content, reasoning = generate_persona_speech(
        llm,
        config=config,
        system_prompt=system_prompt,
        meeting_context="[Cuộc họp: Keos]",
    )
    assert reasoning is None
    assert "Trần Minh Trí" in content


def test_generate_persona_speech_enabled_returns_monologue() -> None:
    llm = MockLLMProvider(persona_names={"CFO": "Trần Minh Trí"})
    config = MeetingConfig(enable_internal_monologue=True, use_mock=True)
    system_prompt = "Bạn là **Trần Minh Trí**, CFO."
    content, reasoning = generate_persona_speech(
        llm,
        config=config,
        system_prompt=system_prompt,
        meeting_context="[Cuộc họp: Keos]\n\nBiên bản gần nhất:\nCEO: cần tăng ngân sách.",
    )
    assert reasoning is not None
    assert reasoning.monologue.stance_shift > 0
    assert "đồng ý một phần" in content.lower()


def test_generate_persona_speech_fallback_on_bad_json() -> None:
    class BadReasoningLLM(MockLLMProvider):
        def generate(self, system_prompt, user_message, *, max_tokens=None):
            if "[INTERNAL REASONING]" in user_message:
                return "invalid json response"
            return super().generate(system_prompt, user_message, max_tokens=max_tokens)

    llm = BadReasoningLLM(persona_names={"CFO": "Trần Minh Trí"})
    config = MeetingConfig(enable_internal_monologue=True, use_mock=True)
    system_prompt = "Bạn là **Trần Minh Trí**, CFO."
    content, reasoning = generate_persona_speech(
        llm,
        config=config,
        system_prompt=system_prompt,
        meeting_context="[Cuộc họp: Keos]",
    )
    assert reasoning is None
    assert content
