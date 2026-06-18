"""LangGraph node implementations."""

from __future__ import annotations

import json
import re

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

SECRETARY_SYSTEM_PROMPT = """\
Bạn là Thư ký cuộc họp (Meeting Secretary). Nhiệm vụ: đánh giá mức đồng thuận trong cuộc họp nội bộ.

Tiêu chí nghiêm ngặt:
- has_consensus = true CHỈ KHI các phe đối lập đã chấp nhận cùng một phương án cụ thể (con số, timeline).
- Nếu vẫn còn bất đồng về ngân sách, chiết khấu, năng lực sản xuất → has_consensus = false.
- key_stakeholder_approval = true chỉ khi CEO hoặc CFO nói rõ "chấp nhận/thống nhất" phương án cuối.
- Nếu có working_proposals: has_consensus = true CHỈ KHI có ≥1 proposal active với aggregate_score
  ≥ ngưỡng đồng thuận VÀ key stakeholder đã approve proposal đó (trong approvals hoặc speech).

Trả lời CHỈ bằng JSON hợp lệ với các trường:
- consensus_score: float từ 0.0 đến 1.0
- has_consensus: boolean (true nếu >= 80% đồng thuận về hướng hành động)
- key_stakeholder_approval: boolean (CEO hoặc CFO đã chấp nhận phương án chung)
- summary: string ngắn gọn bằng tiếng Việt

Không thêm markdown hay giải thích ngoài JSON.
"""


def _build_user_context(state: MeetingState, *, speaker_id: str) -> str:
    topic = state["meeting_topic"]
    config = state["config"]
    transcript = format_transcript_for_context(
        state,
        style="default",
        fallback_limit=config.transcript_window_persona,
    )
    last_speaker = state.get("last_speaker") or ""
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

    if not state["messages"]:
        # First turn: the meeting opener (mandater) should create the mandate
        # based on the meeting topic, not rely on a pre-baked opening_message.
        opener = state.get("config").opening_speaker or "CEO"
        is_opener = speaker_id == opener
        if is_opener:
            return f"""\
[Cuộc họp: {topic}]

Bạn được chỉ định mở đầu cuộc họp. Hãy phát biểu 1 lượt mở đầu (2–6 câu) để:
- Nêu "mandate"/mục tiêu cuộc họp và phạm vi thảo luận bám sát chủ đề.
- Đưa ra 2–4 điểm cần chốt (decision points) và tiêu chí ra quyết định (VD: ROI, dòng tiền, rủi ro vận hành).
- Chỉ định kỳ vọng tranh luận: thẳng, có số liệu, phản biện trực tiếp.
"""
        return f"""\
[Cuộc họp: {topic}]

Cuộc họp vừa bắt đầu. Hãy phát biểu lượt đầu tiên với tư cách của bạn (2–6 câu), bám sát chủ đề và ưu tiên lợi ích bộ phận.
"""

    return f"""\
[Cuộc họp: {topic}]

Biên bản gần nhất:
{transcript}

Người vừa phát biểu: {last_speaker or "—"}
Ma trận quan hệ của bạn:
{rel_summary}

Hãy phát biểu tiếp theo với tư cách của bạn trong cuộc họp. Phản biện trực tiếp nếu cần.{proposals_block}{facts_block}
"""


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
        next_speaker = select_next_speaker(state, llm)
        return {"current_speaker": next_speaker}

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
        user_message = (
            f"Chủ đề: {state['meeting_topic']}\n\n"
            f"Biên bản:\n{transcript}\n\n"
            f"Stakeholder then chốt: {', '.join(state['config'].key_stakeholders)}"
            f"{proposals_section}"
        )
        raw = llm.generate(SECRETARY_SYSTEM_PROMPT, user_message)
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
