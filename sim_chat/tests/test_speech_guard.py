"""Speech output guards against leaked JSON / truncated replies."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.reasoning import _generate_public_speech, _looks_like_bad_speech


class _StubLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, system_prompt: str, user_message: str, *, max_tokens=None) -> str:
        self.calls += 1
        if not self.responses:
            return ""
        return self.responses.pop(0)


def test_looks_like_bad_speech_detects_json_leak() -> None:
    assert _looks_like_bad_speech('[{"proposal_id": "p1_abc", "score": 0.7') is True
    assert _looks_like_bad_speech(
        "Anh Dũng, em đồng ý chốt chiết khấu 20% cho GT với điều kiện thu nợ trước khi xuất hàng."
    ) is False


def test_generate_public_speech_retries_on_json_leak() -> None:
    llm = _StubLLM(
        [
            '[proposal_scores]:\np1_ceo_a17eeb: 0.7',
            "Anh Dũng, em đồng ý giảm brand spend 30% để giữ chiết khấu GT ở 20%.",
        ]
    )
    content = _generate_public_speech(
        llm,
        system_prompt="sys",
        user_message="ctx",
        max_tokens=512,
    )
    assert llm.calls == 2
    assert "proposal_scores" not in content
    assert content.endswith(".")
