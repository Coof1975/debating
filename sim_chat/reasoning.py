"""Internal monologue (multi-stage reasoning) before public speech."""

from __future__ import annotations

import json
import re

from .config import MeetingConfig
from .llm import LLMProvider
from .models import (
    HiddenTurn,
    InternalMonologue,
    MeetingState,
    NegotiationProfile,
    NewProposalDraft,
    ProposalScore,
    ReasoningResult,
    SharedFact,
    WorkingProposal,
    FactAcceptance,
    DialogueTurn,
    RelationshipMatrix,
)
from .facts import format_shared_facts_for_reasoning
from .proposals import format_proposals_for_context
from .relationship import format_relationships_for_reasoning

REASONING_SYSTEM_SUFFIX = """

## CHẾ ĐỘ SUY NGHĨ NỘI BỘ (INTERNAL REASONING)
Bạn đang ở bước suy nghĩ ẩn — output KHÔNG hiển thị trực tiếp cho người dùng.

Trước khi phát biểu công khai, thực hiện các bước và trả về JSON hợp lệ (không markdown):
0. **relationship_lens** (string): Góc nhìn quan hệ cá nhân — cả hai chiều:
   - Tiêu cực: ghét, nghi ngờ động cơ, muốn bắt bẻ, khiêu khích, bực vì bị chọc...
   - Tích cực: tin tưởng, tôn trọng, thích, đồng cảm, muốn bảo vệ phe/đồng minh, nương theo ý người mình quý...
   Ghi rõ với ai (đặc biệt người vừa nói) và tâm trạng hôm nay. Dựa ma trận quan hệ + phe + biên bản gần nhất.
1. **absorb** (string): Phân tích ý vừa nghe — điểm hợp lý, điểm xung đột, có xâm phạm lợi ích bộ phận? Lọc qua relationship_lens (VD: nếu ghét B thì vẫn tìm điểm hợp lý nhưng không nuốt trọn).
2. **compromise_space** (string): Nếu phủ quyết hoàn toàn → cuộc họp bế tắc. Có phương án dung hòa giữ đủ lợi ích bộ phận?
3. **stance_shift** (float): -1.0 đến 1.0 — mức nhún nhường so với lập trường cứng (0=giữ nguyên, dương=linh hoạt hơn).

Mục tiêu tối thượng: cuộc họp phải ra kết quả cho Sếp (CEO). Bế tắc vô nghĩa sẽ bị đánh giá thấp.
Tuyệt đối không phủ nhận sạch — hãy tìm vùng giao thoa ngay cả khi bảo vệ lợi ích bộ phận.
Quan hệ cá nhân được phép ảnh hưởng giọng điệu và mức cứng nhưng không được phá vỡ vai trò chuyên môn.
Áp dụng HỒ SƠ ĐÀM PHÁN trong system prompt (chỉ số thỏa hiệp, % lợi ích tối thiểu).
"""

REASONING_USER_SUFFIX = """
[INTERNAL REASONING]
Trả lời CHỈ bằng JSON hợp lệ với các trường:
- relationship_lens, absorb, compromise_space, stance_shift
- proposal_scores: [{"id": "<proposal_id>", "score": 0.0-1.0, "concerns": "..."}] — chấm từng đề xuất active
- new_proposal: null HOẶC {"title": "...", "description": "...", "parent_id": "<id>|null"} nếu có phương án dung hòa mới
- fact_acceptances: [{"fact_id": "<id>", "accepted": true|false}] — đánh giá số liệu đồng nghiệp (nếu có)

Không thêm markdown hay giải thích ngoài JSON.
"""

SPEECH_INSTRUCTIONS = """
Dựa trên suy nghĩ nội bộ sau, viết 2–6 câu phát biểu công khai trong cuộc họp:

[RELATIONSHIP LENS]
{relationship_lens}

[ABSORB]
{absorb}

[COMPROMISE SPACE]
{compromise_space}

Quy tắc phát biểu:
- Giọng điệu phản ánh quan hệ cá nhân (thân/tôn trọng/bảo vệ phe hoặc khinh/nghi ngờ) nhưng vẫn lịch sự trong họp nội bộ
- "Yes, and..." — thừa nhận phần hợp lý trước khi bổ sung hoặc phản biện
- Không lặp lại monologue, không meta ("tôi đã suy nghĩ...", "theo phân tích nội bộ...")
- Giữ giọng điệu và tính cách nhân vật
- Bám sát bối cảnh cuộc họp ở trên
"""


def strip_json_fence(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_monologue(raw: str) -> InternalMonologue | None:
    result = parse_reasoning_result(raw)
    return result.monologue if result else None


def parse_reasoning_result(raw: str) -> ReasoningResult | None:
    """Parse LLM JSON into full reasoning result including proposal updates."""
    cleaned = strip_json_fence(raw)
    if not cleaned:
        return None
    try:
        payload = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None

    absorb = payload.get("absorb")
    compromise_space = payload.get("compromise_space")
    if not absorb or not compromise_space:
        return None

    try:
        stance_shift = float(payload.get("stance_shift", 0.0))
    except (TypeError, ValueError):
        stance_shift = 0.0
    stance_shift = max(-1.0, min(1.0, stance_shift))

    proposal_scores: list[ProposalScore] = []
    for item in payload.get("proposal_scores") or []:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("id", "")).strip()
        if not proposal_id:
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(1.0, score))
        proposal_scores.append(
            ProposalScore(
                id=proposal_id,
                score=score,
                concerns=str(item.get("concerns", "")).strip(),
            )
        )

    new_proposal: NewProposalDraft | None = None
    raw_new = payload.get("new_proposal")
    if isinstance(raw_new, dict):
        title = str(raw_new.get("title", "")).strip()
        description = str(raw_new.get("description", "")).strip()
        if title and description:
            parent_raw = raw_new.get("parent_id")
            parent_id = str(parent_raw).strip() if parent_raw not in (None, "", "null") else None
            new_proposal = NewProposalDraft(
                title=title,
                description=description,
                parent_id=parent_id,
            )

    fact_acceptances: list[FactAcceptance] = []
    for item in payload.get("fact_acceptances") or []:
        if not isinstance(item, dict):
            continue
        fact_id = str(item.get("fact_id", "")).strip()
        if not fact_id:
            continue
        fact_acceptances.append(
            FactAcceptance(
                fact_id=fact_id,
                accepted=bool(item.get("accepted", True)),
            )
        )

    return ReasoningResult(
        monologue=InternalMonologue(
            absorb=str(absorb).strip(),
            compromise_space=str(compromise_space).strip(),
            stance_shift=stance_shift,
            relationship_lens=str(payload.get("relationship_lens", "")).strip(),
        ),
        proposal_scores=proposal_scores,
        new_proposal=new_proposal,
        fact_acceptances=fact_acceptances,
    )


def build_reasoning_user_message(
    meeting_context: str,
    *,
    negotiation: NegotiationProfile | None = None,
    effective_threshold: float | None = None,
    working_proposals: list[WorkingProposal] | None = None,
    participant_ids: list[str] | None = None,
    shared_facts: list[SharedFact] | None = None,
    speaker_id: str | None = None,
    relationship_matrix: RelationshipMatrix | None = None,
    last_speaker: str = "",
    recent_messages: list[DialogueTurn] | None = None,
    enable_relationship_reasoning: bool = True,
) -> str:
    suffix = REASONING_USER_SUFFIX
    blocks: list[str] = [meeting_context.rstrip()]

    if (
        enable_relationship_reasoning
        and relationship_matrix is not None
        and speaker_id is not None
    ):
        rel_block = format_relationships_for_reasoning(
            relationship_matrix,
            speaker_id=speaker_id,
            last_speaker=last_speaker,
            recent_messages=recent_messages,
        )
        blocks.append(rel_block)

    if shared_facts is not None and speaker_id is not None:
        facts_block = format_shared_facts_for_reasoning(shared_facts, speaker_id=speaker_id)
        if facts_block:
            blocks.append(facts_block)

    if working_proposals is not None:
        blocks.append(format_proposals_for_context(working_proposals, participant_ids=participant_ids))

    if negotiation is not None:
        threshold = effective_threshold if effective_threshold is not None else negotiation.compromise_threshold
        retention_pct = int(round(negotiation.min_interest_retention * 100))
        blocks.append(
            f"""[HỒ SƠ ĐÀM PHÁN — lượt này]
- Chỉ số thỏa hiệp hiệu dụng: {threshold:.2f}/1.0
- Tối thiểu giữ lợi ích bộ phận: {retention_pct}%
- Áp lực Sếp: nếu bế tắc, Sếp (CEO) đánh giá kém năng lực điều phối"""
        )

    blocks.append(suffix.strip())
    return "\n\n".join(blocks)


def build_speech_user_message(meeting_context: str, monologue: InternalMonologue) -> str:
    relationship_lens = monologue.relationship_lens.strip() or "(không ghi nhận bias quan hệ đặc biệt)"
    speech_block = SPEECH_INSTRUCTIONS.format(
        relationship_lens=relationship_lens,
        absorb=monologue.absorb,
        compromise_space=monologue.compromise_space,
    )
    return f"{meeting_context.rstrip()}\n\n{speech_block}"


def effective_compromise_threshold(
    profile: NegotiationProfile,
    *,
    stagnation_score: int = 0,
    enable_dynamic: bool = False,
) -> float:
    base = profile.compromise_threshold
    if not enable_dynamic or stagnation_score <= 0:
        return base
    factor = min(1.0, stagnation_score * 0.12)
    boosted = base * (1.0 + profile.director_sensitivity * factor)
    return min(1.0, boosted)


def generate_persona_speech(
    llm: LLMProvider,
    *,
    config: MeetingConfig,
    system_prompt: str,
    meeting_context: str,
    negotiation: NegotiationProfile | None = None,
    stagnation_score: int = 0,
    working_proposals: list[WorkingProposal] | None = None,
    participant_ids: list[str] | None = None,
    shared_facts: list[SharedFact] | None = None,
    speaker_id: str | None = None,
    relationship_matrix: RelationshipMatrix | None = None,
    last_speaker: str = "",
    recent_messages: list[DialogueTurn] | None = None,
) -> tuple[str, ReasoningResult | None]:
    """Generate public speech, optionally via hidden internal monologue."""
    if not config.enable_internal_monologue:
        return llm.generate(system_prompt, meeting_context).strip(), None

    effective_threshold = None
    if negotiation is not None:
        effective_threshold = effective_compromise_threshold(
            negotiation,
            stagnation_score=stagnation_score,
            enable_dynamic=config.enable_dynamic_compromise,
        )

    reasoning_system = f"{system_prompt.rstrip()}{REASONING_SYSTEM_SUFFIX}"
    reasoning_user = build_reasoning_user_message(
        meeting_context,
        negotiation=negotiation,
        effective_threshold=effective_threshold,
        working_proposals=working_proposals if config.enable_working_proposals else None,
        participant_ids=participant_ids,
        shared_facts=shared_facts if config.enable_shared_facts else None,
        speaker_id=speaker_id,
        relationship_matrix=relationship_matrix,
        last_speaker=last_speaker,
        recent_messages=recent_messages,
        enable_relationship_reasoning=config.enable_relationship_reasoning,
    )
    raw_reasoning = llm.generate(
        reasoning_system,
        reasoning_user,
        max_tokens=config.reasoning_max_tokens,
    )
    reasoning = parse_reasoning_result(raw_reasoning)
    if reasoning is None:
        content = llm.generate(system_prompt, meeting_context).strip()
        return content, None

    speech_user = build_speech_user_message(meeting_context, reasoning.monologue)
    content = llm.generate(
        system_prompt,
        speech_user,
        max_tokens=config.speech_max_tokens,
    )
    return content.strip(), reasoning


def monologue_state_patch(
    state: MeetingState,
    *,
    speaker_id: str,
    turn_index: int,
    reasoning: ReasoningResult | None,
) -> dict:
    """Build state patch fields for hidden monologue tracking."""
    if reasoning is None:
        return {}

    hidden_turn = HiddenTurn(
        speaker_id=speaker_id,
        turn_index=turn_index,
        monologue=reasoning.monologue,
    )
    last_monologue = dict(state.get("last_monologue") or {})
    last_monologue[speaker_id] = reasoning.monologue
    return {
        "hidden_turns": [hidden_turn],
        "last_monologue": last_monologue,
    }
