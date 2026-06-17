"""Regression tests for stagnation detection."""

from __future__ import annotations

import json
from pathlib import Path

from sim_chat.config import MeetingConfig
from sim_chat.models import DialogueTurn
from sim_chat.stopping import update_stagnation

MEETINGS_DIR = Path(__file__).resolve().parents[1] / "data" / "meetings"


def _replay_stagnation(meeting_id: str) -> tuple[int, int]:
    path = MEETINGS_DIR / f"{meeting_id}.json"
    data = json.loads(path.read_text())
    config = MeetingConfig(**{**MeetingConfig().model_dump(), **data["config"]})
    messages = [DialogueTurn(**m) for m in data["messages"]]

    score = 0
    stop_turn = 0
    for index in range(1, len(messages) + 1):
        subset = messages[:index]
        state = {
            "config": config,
            "messages": subset,
            "turn_index": index,
            "stagnation_score": score,
        }
        score = update_stagnation(state)
        if stop_turn == 0 and score >= config.stagnation_limit:
            stop_turn = index
    return score, stop_turn


def test_deadlock_meeting_triggers_stagnation() -> None:
    score, stop_turn = _replay_stagnation("5ab83ebf-43b7-4f45-bb3f-b5eb5e190a34")
    assert score >= 5
    assert 10 <= stop_turn <= 14


def test_consensus_meeting_does_not_hit_limit() -> None:
    score, stop_turn = _replay_stagnation("306db122-00e6-4f62-b6d4-804d96527c15")
    assert score < 3
    assert stop_turn == 0
