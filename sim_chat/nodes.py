"""LangGraph node implementations."""

from __future__ import annotations

import json
import re

from .llm import LLMProvider
from .models import DialogueTurn, MeetingState, SecretaryVerdict
from .orchestrator import select_next_speaker
from .stopping import heuristic_consensus, update_stagnation
from .transcript import format_transcript_for_context, maybe_refresh_transcript_summary

SECRETARY_SYSTEM_PROMPT = """\
Bạn là Thư ký cuộc họp (Meeting Secretary). Nhiệm vụ: đánh giá mức đồng thuận trong cuộc họp nội bộ.

Tiêu chí nghiêm ngặt:
- has_consensus = true CHỈ KHI các phe đối lập đã chấp nhận cùng một phương án cụ thể (con số, timeline).
- Nếu vẫn còn bất đồng về ngân sách, chiết khấu, năng lực sản xuất → has_consensus = false.
- key_stakeholder_approval = true chỉ khi CEO hoặc CFO nói rõ "chấp nhận/thống nhất" phương án cuối.

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

Hãy phát biểu tiếp theo với tư cách của bạn trong cuộc họp. Phản biện trực tiếp nếu cần.
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
        system_prompt = state["prompts"][speaker_id]
        user_message = _build_user_context(state, speaker_id=speaker_id)
        content = llm.generate(system_prompt, user_message)

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

        return {
            "messages": [turn],
            "last_speaker": speaker_id,
            "turn_index": turn_index,
            "loop_count": new_loop,
            "stagnation_score": stagnation,
            "turns_since_secretary": state.get("turns_since_secretary", 0) + 1,
            **summary_updates,
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
        user_message = (
            f"Chủ đề: {state['meeting_topic']}\n\n"
            f"Biên bản:\n{transcript}\n\n"
            f"Stakeholder then chốt: {', '.join(state['config'].key_stakeholders)}"
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
