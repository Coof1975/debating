"""Tests for turn-level anti-repetition guidance."""

from __future__ import annotations

from sim_chat.anti_repetition import build_anti_repetition_block, format_own_prior_turns
from sim_chat.models import DialogueTurn


def _turn(speaker_id: str, content: str, turn_index: int) -> DialogueTurn:
    return DialogueTurn(
        speaker_id=speaker_id,
        speaker_name=speaker_id,
        content=content,
        round_number=1,
        turn_index=turn_index,
    )


def test_format_own_prior_turns_empty_for_new_speaker() -> None:
    messages = [_turn("CEO", "Mở đầu.", 1)]
    assert format_own_prior_turns("CFO", messages) == ""


def test_format_own_prior_turns_lists_recent() -> None:
    messages = [
        _turn("CFO", "Chiết khấu tối đa 18%.", 1),
        _turn("CEO", "Cần tăng volume.", 2),
        _turn("CFO", "Dòng tiền âm 8,4 tỷ.", 3),
    ]
    block = format_own_prior_turns("CFO", messages, limit=2)
    assert "Lượt 1" in block
    assert "Lượt 3" in block
    assert "18%" in block
    assert "8,4 tỷ" in block


def test_build_anti_repetition_block_includes_prior_and_banned() -> None:
    messages = [
        _turn("SALE", "Đề xuất chiết khấu 25%.", 1),
        _turn("CFO", "Không quá 18%.", 2),
    ]
    block = build_anti_repetition_block(
        speaker_id="SALE",
        messages=messages,
        stagnation_score=0,
        last_speaker="CFO",
    )
    assert "[CHỐNG LẶP" in block
    assert "25%" in block
    assert "CFO" in block
    assert "Cấm mở đầu" in block


def test_build_anti_repetition_block_stagnation_pressure() -> None:
    block = build_anti_repetition_block(
        speaker_id="CFO",
        messages=[],
        stagnation_score=2,
        last_speaker="SALE",
    )
    assert "stagnation=2" in block
    assert "bế tắc cao" in block.lower() or "Mức bế tắc cao" in block
