"""Integration tests for graph execution and SSE event streaming."""

from __future__ import annotations

from sim_chat.config import MeetingConfig
from sim_chat.graph import build_meeting_graph, iter_meeting_events, run_meeting
from sim_chat.llm import create_llm_provider
from sim_chat.bootstrap import create_initial_state
from sim_chat.models import TerminationReason


def _compact_config(**overrides) -> MeetingConfig:
    """Small mock run: few turns, no proposal/fact side effects."""
    base = {
        "max_turns": 3,
        "participant_ids": ["CEO", "CFO"],
        "use_mock": True,
        "enable_working_proposals": False,
        "enable_shared_facts": False,
        "enable_stagnation_check": False,
    }
    base.update(overrides)
    return MeetingConfig(**base)


def test_build_meeting_graph_compiles() -> None:
    config = _compact_config()
    state = create_initial_state(config)
    llm = create_llm_provider(config, use_mock=True, persona_names=state["persona_names"])
    app = build_meeting_graph(llm)
    assert app is not None


def test_run_meeting_completes_with_mock() -> None:
    config = _compact_config()
    record = run_meeting(config, use_mock=True)
    assert len(record.messages) == 3
    assert record.termination_reason == TerminationReason.MAX_ROUNDS


def test_graph_sse_events() -> None:
    config = _compact_config()
    events = list(iter_meeting_events(config, use_mock=True))
    types = [event["type"] for event in events]

    assert types[0] == "started"
    assert types[-1] == "completed"
    assert "turn" in types
    assert "status" in types

    started_idx = types.index("started")
    first_turn_idx = types.index("turn")
    completed_idx = types.index("completed")

    assert first_turn_idx > started_idx
    assert completed_idx > first_turn_idx

    if "secretary" in types:
        assert types.index("secretary") > first_turn_idx

    completed = events[-1]["data"]
    assert completed["turn_count"] == 3
    assert completed["termination_reason"] == TerminationReason.MAX_ROUNDS.value


def test_graph_sse_monologue_when_enabled() -> None:
    config = _compact_config(monologue_in_sse=True, enable_internal_monologue=True)
    types = [event["type"] for event in iter_meeting_events(config, use_mock=True)]

    assert "monologue" in types
    assert types.index("monologue") < types.index("turn")
    assert types.index("monologue") < types.index("completed")
