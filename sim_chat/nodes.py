"""LangGraph node implementations."""

from __future__ import annotations

import json
import re

from .anti_repetition import build_anti_repetition_block
from .context import build_persona_user_context
from .domain import get_domain
from .llm import LLMProvider
from .models import DialogueTurn, MeetingState, SecretaryVerdict
from .orchestrator import select_next_speaker
from .facts import (
    facts_state_patch,
    format_shared_facts_for_context,
    update_shared_facts_after_turn,
)
from .proposals import (
    apply_reasoning_to_proposals,
    format_proposals_for_context,
    format_proposals_for_secretary,
    proposals_state_patch,
)
from .reasoning import generate_persona_speech, monologue_state_patch
from .stopping import heuristic_consensus, update_stagnation
from .transcript import format_transcript_for_context, maybe_refresh_transcript_summary

def _build_user_context(state: MeetingState, *, speaker_id: str) -> str:
    config = state["config"]
    transcript = format_transcript_for_context(
        state,
        style="default",
        fallback_limit=config.transcript_window_persona,
    )
    matrix = state["relationship_matrix"]
    rel_summary = matrix.summary_for(speaker_id)
    proposals_block = ""
    if config.enable_working_proposals:
        proposals = state.get("working_proposals") or []
        if proposals:
            proposals_block = (
                f"\n\n{format_proposals_for_context(proposals, participant_ids=state['participant_ids'])}"
            )
    facts_block = ""
    if config.enable_shared_facts:
        facts = state.get("shared_facts") or []
        formatted = format_shared_facts_for_context(facts, speaker_id=speaker_id)
        if formatted:
            facts_block = f"\n\n{formatted}"

    anti_repetition_block = build_anti_repetition_block(
        speaker_id=speaker_id,
        messages=state.get("messages") or [],
        stagnation_score=state.get("stagnation_score", 0),
        last_speaker=state.get("last_speaker") or "",
    )

    return build_persona_user_context(
        state,
        speaker_id=speaker_id,
        transcript=transcript,
        rel_summary=rel_summary,
        proposals_block=proposals_block,
        facts_block=facts_block,
        anti_repetition_block=anti_repetition_block,
    )


def _parse_secretary_response(raw: str, state: MeetingState) -> SecretaryVerdict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
        return SecretaryVerdict(
            consensus_score=float(payload.get("consensus_score", 0.0)),
            has_consensus=bool(payload.get("has_consensus", False)),
            key_stakeholder_approval=bool(payload.get("key_stakeholder_approval", False)),
            summary=str(payload.get("summary", "")),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return heuristic_consensus(state["messages"], state["config"])


def make_orchestrator_node(llm: LLMProvider):
    def orchestrator_node(state: MeetingState) -> dict:
        selection = select_next_speaker(state, llm)
        return {
            "current_speaker": selection.next_speaker,
            "speaker_selections": [selection],
        }

    return orchestrator_node


def make_persona_node(llm: LLMProvider):
    def persona_node(state: MeetingState) -> dict:
        speaker_id = state["current_speaker"]
        config = state["config"]
        system_prompt = state["prompts"][speaker_id]
        user_message = _build_user_context(state, speaker_id=speaker_id)
        content, reasoning = generate_persona_speech(
            llm,
            config=config,
            system_prompt=system_prompt,
            meeting_context=user_message,
            negotiation=state.get("negotiation_profiles", {}).get(speaker_id),
            stagnation_score=state.get("stagnation_score", 0),
            working_proposals=state.get("working_proposals") or [],
            participant_ids=state["participant_ids"],
            shared_facts=state.get("shared_facts") or [],
            speaker_id=speaker_id,
            relationship_matrix=state.get("relationship_matrix"),
            last_speaker=state.get("last_speaker") or "",
            recent_messages=state.get("messages") or [],
        )

        turn_index = state["turn_index"] + 1
        round_number = state["loop_count"] + 1
        turn = DialogueTurn(
            speaker_id=speaker_id,
            speaker_name=state["persona_names"].get(speaker_id, speaker_id),
            content=content,
            round_number=round_number,
            turn_index=turn_index,
        )

        participant_count = max(1, len(state["participant_ids"]))
        completed_turns = turn_index
        new_loop = completed_turns // participant_count

        stagnation = update_stagnation({**state, "messages": state["messages"] + [turn]})

        post_turn_state = {**state, "messages": state["messages"] + [turn], "turn_index": turn_index}
        summary_updates = maybe_refresh_transcript_summary(post_turn_state, llm)
        updated_proposals = apply_reasoning_to_proposals(
            state.get("working_proposals") or [],
            speaker_id=speaker_id,
            turn_index=turn_index,
            reasoning=reasoning,
            speech=content,
            config=config,
        )
        updated_facts = update_shared_facts_after_turn(
            state.get("shared_facts") or [],
            llm=llm,
            speaker_id=speaker_id,
            turn_index=turn_index,
            speech=content,
            reasoning=reasoning,
            config=config,
        )

        return {
            "messages": [turn],
            "last_speaker": speaker_id,
            "turn_index": turn_index,
            "loop_count": new_loop,
            "stagnation_score": stagnation,
            "turns_since_secretary": state.get("turns_since_secretary", 0) + 1,
            **summary_updates,
            **monologue_state_patch(
                state,
                speaker_id=speaker_id,
                turn_index=turn_index,
                reasoning=reasoning,
            ),
            **proposals_state_patch(updated_proposals),
            **facts_state_patch(updated_facts),
        }

    return persona_node


def make_secretary_node(llm: LLMProvider):
    def secretary_node(state: MeetingState) -> dict:
        config = state["config"]
        transcript = format_transcript_for_context(
            state,
            style="default",
            fallback_limit=config.transcript_window_secretary,
        )
        proposals_section = ""
        if config.enable_working_proposals:
            proposals = state.get("working_proposals") or []
            if proposals:
                proposals_section = (
                    f"\n\nĐề xuất đang trên bàn (working_proposals):\n"
                    f"{format_proposals_for_secretary(proposals)}\n\n"
                    f"Ngưỡng đồng thuận: {config.consensus_threshold:.0%}"
                )
        domain = get_domain(config.domain_id)
        user_message = (
            f"{domain.labels.topic_label}: {state['meeting_topic']}\n\n"
            f"Biên bản:\n{transcript}\n\n"
            f"Stakeholder then chốt: {', '.join(state['config'].key_stakeholders)}"
            f"{proposals_section}"
        )
        raw = llm.generate(domain.prompts.secretary_system, user_message)
        verdict = _parse_secretary_response(raw, state)
        return {
            "secretary_verdict": verdict,
            "turns_since_secretary": 0,
        }

    return secretary_node


def make_finalize_node():
    def finalize_node(state: MeetingState) -> dict:
        from .stopping import evaluate_termination

        reason = evaluate_termination(state)
        return {
            "terminated": True,
            "termination_reason": reason.value if reason else "manual",
        }

    return finalize_node
