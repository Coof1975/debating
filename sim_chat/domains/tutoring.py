"""Tutoring domain — multi-agent study session (teacher + students)."""

from __future__ import annotations

from ..domain import DomainPrompts, ParticipantBundle, SessionLabels, SimulationDomain
from ..models import NegotiationProfile, RelationshipEdge, RelationshipMatrix

ORCHESTRATOR_SYSTEM = """\
Bạn là Điều phối viên buổi học nhóm.
Chọn MỘT người nói tiếp theo để buổi học có tranh luận học thuật, không monotonous.

Quy tắc:
1. Ưu tiên người bị gọi tên trực tiếp trong lượt trước.
2. Sau khi giáo viên giải thích, ưu tiên học sinh hỏi lại hoặc phản biện chỗ chưa hiểu.
3. Nếu học sinh sai lầm rõ ràng, ưu tiên học sinh khác hoặc giáo viên sửa — không để sai lan truyền.
4. Cân bằng thời lượng: học sinh nói ít hơn nên được ưu tiên nếu chưa hỏi.
5. Không chọn lại last_speaker trừ khi bị yêu cầu.

Trả lời CHỈ JSON: {"next_speaker": "<ID>", "reason": "<lý do ngắn>"}
"""

SECRETARY_SYSTEM = """\
Bạn là Thư ký buổi học. Đánh giá mức độ học sinh đã nắm được kiến thức.

has_consensus = true CHỈ KHI:
- Học sinh thống nhất được phương pháp giải / đáp án / bước tiếp theo cụ thể, HOẶC
- Giáo viên chốt lại và học sinh không còn mâu thuẫn về cách làm.

key_stakeholder_approval = true khi TUTOR xác nhận "đúng", "chốt", "làm theo hướng này".

JSON: consensus_score, has_consensus, key_stakeholder_approval, summary
"""

INSIGHT_SYSTEM = """\
Bạn phân tích biên bản buổi học nhóm (tutor + học sinh).
Viết báo cáo ngắn bằng tiếng Việt:
1. Lý do kết thúc
2. Lỗ hổng kiến thức còn lại
3. Ai hiểu đúng / ai hiểu sai
4. Điểm đã thống nhất
5. Bài tập / bước ôn tập tiếp theo
"""

FACT_EXTRACTOR = """\
Trích xuất phát biểu factual từ buổi học: công thức, định lý, bước giải, điều kiện áp dụng.
JSON: {"facts": [{"fact": "...", "category": "concept|procedure|constraint|other", "confidence": 0.0-1.0}]}
"""

REASONING_SUFFIX = """

## SUY NGHĨ NỘI BỘ (trước khi nói)
Trả JSON: relationship_lens, absorb, compromise_space, stance_shift
- absorb: phân tích ý vừa nghe — đúng/sai chỗ nào, còn thắc mắc gì
- compromise_space: có thể chấp nhận cách giải nào nếu cách mình sai một phần
Mục tiêu: buổi học phải ra kết luận học được, không lặp vô ích.
"""

REASONING_USER = """
[INTERNAL REASONING]
JSON: relationship_lens, absorb, compromise_space, stance_shift, proposal_scores, new_proposal, fact_acceptances
"""

SPEECH = """
Viết 2–5 câu phát biểu trong buổi học dựa trên suy nghĩ nội bộ:

[RELATIONSHIP LENS]
{relationship_lens}
[ABSORB]
{absorb}
[COMPROMISE SPACE]
{compromise_space}

Quy tắc: hỏi thẳng, chỉ ra bước sai, viện dẫn công thức/định nghĩa cụ thể. Không nói chung chung "em hiểu".
"""

TOPIC_KEYWORDS = {
    "TUTOR": ("đề bài", "chứng minh", "công thức", "định lý", "bước", "giải thích", "chốt"),
    "STUDENT_A": ("em không hiểu", "tại sao", "chỗ này", "bước", "đáp án"),
    "STUDENT_B": ("em nghĩ", "cách khác", "phản ví dụ", "sai ở đâu"),
}

TUTORING_DOMAIN = SimulationDomain(
    id="tutoring",
    label="Buổi học nhóm / gia sư",
    labels=SessionLabels(
        session_noun="Buổi học",
        topic_label="Chủ đề",
        transcript_label="Diễn biến gần nhất",
        relationship_label="Quan hệ trong nhóm",
        last_speaker_label="Người vừa nói",
        participant_noun="học viên",
        orchestrator_noun="Điều phối viên buổi học",
        secretary_noun="Thư ký buổi học",
        moderator_role_hint="TUTOR",
    ),
    prompts=DomainPrompts(
        orchestrator_system=ORCHESTRATOR_SYSTEM,
        secretary_system=SECRETARY_SYSTEM,
        insight_system=INSIGHT_SYSTEM,
        fact_extractor_system=FACT_EXTRACTOR,
        reasoning_system_suffix=REASONING_SUFFIX,
        reasoning_user_suffix=REASONING_USER,
        speech_instructions=SPEECH,
        negotiation_pressure_block="- Áp lực: nếu không chốt được hướng giải, buổi học kéo dài vô ích",
    ),
    topic_role_keywords=TOPIC_KEYWORDS,
    role_aliases={"giáo viên": "TUTOR", "thầy": "TUTOR", "cô": "TUTOR", "học sinh a": "STUDENT_A"},
    display_aliases={"gia sư": "TUTOR"},
    default_factions={"learners": ["STUDENT_A", "STUDENT_B"], "guide": ["TUTOR"]},
    default_opening_speaker="TUTOR",
    default_key_stakeholders=["TUTOR"],
    no_repeat_speaker_ids=("TUTOR",),
)


def _demo_prompt(role: str, name: str, body: str) -> str:
    return f"# VAI TRÒ\nBạn là **{name}** ({role}).\n\n{body}\n\nTrả lời tiếng Việt, ngắn gọn, bám chủ đề buổi học."


def load_tutoring_demo_participants(**_) -> ParticipantBundle:
    """Minimal demo bundle — replace with your CMS/DB loader in production."""
    prompts = {
        "TUTOR": _demo_prompt(
            "TUTOR",
            "Cô Lan",
            "Giáo viên Toán lớp 12. Thẳng thắn, hay hỏi ngược, bắt học sinh nêu bước giải.",
        ),
        "STUDENT_A": _demo_prompt(
            "STUDENT_A",
            "Minh",
            "Học sinh khá nhưng hay vội kết luận. Thích tranh luận cách giải ngắn hơn.",
        ),
        "STUDENT_B": _demo_prompt(
            "STUDENT_B",
            "Hà",
            "Học sinh trung bình, hay hỏi lại từng bước. Sợ sai nên hay im lặng.",
        ),
    }
    ids = list(prompts.keys())
    edges: dict[str, dict[str, RelationshipEdge]] = {
        "TUTOR": {
            "STUDENT_A": RelationshipEdge(
                source_id="TUTOR", target_id="STUDENT_A", affinity=0.3, conflict_weight=0.4,
                notes="Minh hay tranh — cần ép chứng minh từng bước",
            ),
            "STUDENT_B": RelationshipEdge(
                source_id="TUTOR", target_id="STUDENT_B", affinity=0.5, conflict_weight=0.3,
                notes="Hà nhút nhát — cần gọi tên hỏi",
            ),
        },
        "STUDENT_A": {
            "STUDENT_B": RelationshipEdge(
                source_id="STUDENT_A", target_id="STUDENT_B", affinity=0.2, conflict_weight=0.35,
                notes="Hay cười khi Hà hỏi chậm",
            ),
            "TUTOR": RelationshipEdge(
                source_id="STUDENT_A", target_id="TUTOR", affinity=0.1, conflict_weight=0.45,
            ),
        },
        "STUDENT_B": {
            "STUDENT_A": RelationshipEdge(
                source_id="STUDENT_B", target_id="STUDENT_A", affinity=-0.1, conflict_weight=0.4,
            ),
            "TUTOR": RelationshipEdge(
                source_id="STUDENT_B", target_id="TUTOR", affinity=0.4, conflict_weight=0.25,
            ),
        },
    }
    matrix = RelationshipMatrix(
        participants=ids,
        edges=edges,
        factions=TUTORING_DOMAIN.default_factions,
    )
    negotiation = {
        pid: NegotiationProfile(
            compromise_threshold=0.5 if pid != "TUTOR" else 0.65,
            min_interest_retention=0.6,
        )
        for pid in ids
    }
    return ParticipantBundle(
        participant_ids=ids,
        persona_names={"TUTOR": "Cô Lan", "STUDENT_A": "Minh", "STUDENT_B": "Hà"},
        system_prompts=prompts,
        relationship_matrix=matrix,
        negotiation_profiles=negotiation,
    )
