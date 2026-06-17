"""LangGraph StateGraph assembly and meeting runner."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from .bootstrap import create_initial_state
from .config import MeetingConfig
from .llm import LLMProvider, create_llm_provider
from .models import MeetingRecord, MeetingState, TerminationReason
from .nodes import (
    make_finalize_node,
    make_orchestrator_node,
    make_persona_node,
    make_secretary_node,
)
from .stopping import route_after_turn


def build_meeting_graph(llm: LLMProvider) -> Any:
    """Compile the Virtual Meeting Room LangGraph."""
    graph = StateGraph(MeetingState)

    graph.add_node("orchestrator", make_orchestrator_node(llm))
    graph.add_node("persona", make_persona_node(llm))
    graph.add_node("secretary", make_secretary_node(llm))
    graph.add_node("finalize", make_finalize_node())

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "persona")

    graph.add_conditional_edges(
        "persona",
        route_after_turn,
        {
            "secretary": "secretary",
            "orchestrator": "orchestrator",
            "end": "finalize",
        },
    )

    graph.add_conditional_edges(
        "secretary",
        route_after_turn,
        {
            "secretary": "secretary",
            "orchestrator": "orchestrator",
            "end": "finalize",
        },
    )

    graph.add_edge("finalize", END)
    return graph.compile()


def record_from_state(
    final_state: MeetingState,
    *,
    meeting_id: str,
    config: MeetingConfig,
) -> MeetingRecord:
    reason_value = final_state.get("termination_reason", "")
    try:
        termination = TerminationReason(reason_value) if reason_value else None
    except ValueError:
        termination = None

    return MeetingRecord(
        meeting_id=meeting_id,
        topic=config.meeting_topic,
        config=config,
        relationship_matrix=final_state["relationship_matrix"],
        messages=final_state["messages"],
        loop_count=final_state["loop_count"],
        stagnation_score=final_state["stagnation_score"],
        termination_reason=termination,
        metadata={
            "participant_ids": final_state["participant_ids"],
            "secretary_verdict": (
                final_state["secretary_verdict"].model_dump()
                if final_state.get("secretary_verdict")
                else None
            ),
            "transcript_summary": final_state.get("transcript_summary", ""),
            "summary_through_turn": final_state.get("summary_through_turn", 0),
        },
    )


def run_meeting(
    config: MeetingConfig | None = None,
    *,
    use_mock: bool = False,
    llm: LLMProvider | None = None,
    meeting_id: str | None = None,
    initial_state: MeetingState | None = None,
) -> MeetingRecord:
    """Execute a full meeting simulation and return a persisted-ready record."""
    config = config or MeetingConfig()
    initial = initial_state or create_initial_state(config)
    provider = llm or create_llm_provider(
        config,
        use_mock=use_mock,
        persona_names=initial["persona_names"],
    )
    app = build_meeting_graph(provider)
    final_state = app.invoke(initial)
    return record_from_state(
        final_state,
        meeting_id=meeting_id or str(uuid.uuid4()),
        config=config,
    )


def iter_meeting_events(
    config: MeetingConfig | None = None,
    *,
    use_mock: bool = False,
    llm: LLMProvider | None = None,
    meeting_id: str | None = None,
    initial_state: MeetingState | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield SSE-friendly events while the meeting graph runs."""
    config = config or MeetingConfig()
    resolved_id = meeting_id or str(uuid.uuid4())
    initial = initial_state or create_initial_state(config)
    provider = llm or create_llm_provider(
        config,
        use_mock=use_mock,
        persona_names=initial["persona_names"],
    )
    app = build_meeting_graph(provider)

    prev_message_count = 0
    prev_verdict_key: tuple | None = None
    final_state: MeetingState | None = None

    yield {
        "type": "started",
        "data": {
            "meeting_id": resolved_id,
            "participant_ids": initial["participant_ids"],
            "topic": config.meeting_topic,
        },
    }

    for state in app.stream(initial, stream_mode="values"):
        final_state = state
        messages = state.get("messages", [])
        if len(messages) > prev_message_count:
            turn = messages[-1]
            prev_message_count = len(messages)
            yield {
                "type": "turn",
                "data": turn.model_dump(),
            }

        verdict = state.get("secretary_verdict")
        if verdict is not None:
            verdict_key = (
                verdict.consensus_score,
                verdict.has_consensus,
                verdict.key_stakeholder_approval,
                verdict.summary,
            )
            if verdict_key != prev_verdict_key:
                prev_verdict_key = verdict_key
                yield {
                    "type": "secretary",
                    "data": verdict.model_dump(),
                }

        yield {
            "type": "status",
            "data": {
                "stagnation_score": state.get("stagnation_score", 0),
                "loop_count": state.get("loop_count", 0),
                "turn_index": state.get("turn_index", 0),
            },
        }

    if final_state is None:
        raise RuntimeError("Meeting simulation produced no state")

    record = record_from_state(final_state, meeting_id=resolved_id, config=config)
    yield {
        "type": "completed",
        "data": {
            "meeting_id": resolved_id,
            "termination_reason": (
                record.termination_reason.value if record.termination_reason else None
            ),
            "turn_count": len(record.messages),
            "record": record.model_dump(mode="json"),
        },
    }
