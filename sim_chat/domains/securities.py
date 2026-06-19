"""Securities advisory domain — analyst + risk + client advisor debate."""

from __future__ import annotations

from ..domain import DomainPrompts, ParticipantBundle, SessionLabels, SimulationDomain
from ..models import NegotiationProfile, RelationshipEdge, RelationshipMatrix

ORCHESTRATOR_SYSTEM = """\
Bạn điều phối phiên tư vấn đầu tư chứng khoán.
Chọn người nói tiếp theo để tranh luận rủi ro/lợi nhuận cân bằng, không one-sided pitch.

Quy tắc:
1. Ưu tiên người bị hỏi trực tiếp.
2. Sau bullish thesis → ưu tiên RISK hoặc COMPLIANCE phản biện.
3. Sau số liệu P/E, margin → ưu tiên ANALYST hoặc ADVISOR làm rõ.
4. Không chọn lại last_speaker trừ khi bị yêu cầu.

JSON: {"next_speaker": "<ID>", "reason": "..."}
"""

SECRETARY_SYSTEM = """\
Thư ký phiên tư vấn — đánh giá đã có khuyến nghị đầu tư rõ ràng chưa.

has_consensus = true khi nhóm thống nhất khuyến nghị (MUA/GIỮ/BÁN) + khung rủi ro + điều kiện invalidation.
key_stakeholder_approval = true khi ADVISOR (người chịu trách nhiệm với khách) xác nhận.

JSON: consensus_score, has_consensus, key_stakeholder_approval, summary
"""

INSIGHT_SYSTEM = """\
Phân tích biên bản phiên tư vấn chứng khoán. Báo cáo ngắn:
1. Lý do kết thúc
2. Luận điểm bull vs bear
3. Rủi ro chưa giải quyết
4. Khuyến nghị cuối (nếu có)
5. Điều kiện theo dõi tiếp
"""

FACT_EXTRACTOR = """\
Trích xuất số liệu/sự kiện thị trường từ phát biểu: P/E, EPS, biên, nợ, catalyst, ngày công bố.
JSON: {"facts": [{"fact": "...", "category": "financial|market|risk|other", "confidence": 0.0-1.0}]}
"""

REASONING_SUFFIX = """

## SUY NGHĨ NỘI BỘ
JSON: relationship_lens, absorb, compromise_space, stance_shift
Mục tiêu: phiên phải ra khuyến nghị có thể hành động, không pitch một chiều.
"""

REASONING_USER = "[INTERNAL REASONING]\nJSON như trên + proposal_scores, new_proposal, fact_acceptances"

SPEECH = """
2–5 câu phát biển trong phiên tư vấn:

[RELATIONSHIP LENS]
{relationship_lens}
[ABSORB]
{absorb}
[COMPROMISE SPACE]
{compromise_space}

Quy tắc: nêu số liệu/ticker/catalyst cụ thể; phản biện thẳng; không cam kết lợi nhuận mơ hồ.
"""

TOPIC_KEYWORDS = {
    "ANALYST": ("p/e", "eps", "doanh thu", "biên", "dcf", "target price", "catalyst"),
    "RISK": ("drawdown", "nợ", "liquidity", "beta", "stress", "downside", "rủi ro"),
    "ADVISOR": ("khách hàng", "khuyến nghị", "mua", "bán", "giữ", "phân bổ", "horizon"),
    "COMPLIANCE": ("disclosure", "tuân thủ", "conflict", "pháp lý", "cảnh báo"),
}

SECURITIES_DOMAIN = SimulationDomain(
    id="securities",
    label="Tư vấn đầu tư chứng khoán",
    labels=SessionLabels(
        session_noun="Phiên tư vấn",
        topic_label="Mã / chủ đề",
        transcript_label="Diễn biến gần nhất",
        relationship_label="Quan hệ trong phòng tư vấn",
        last_speaker_label="Người vừa phát biểu",
        orchestrator_noun="Điều phối viên phiên",
        secretary_noun="Thư ký phiên",
        moderator_role_hint="ADVISOR",
    ),
    prompts=DomainPrompts(
        orchestrator_system=ORCHESTRATOR_SYSTEM,
        secretary_system=SECRETARY_SYSTEM,
        insight_system=INSIGHT_SYSTEM,
        fact_extractor_system=FACT_EXTRACTOR,
        reasoning_system_suffix=REASONING_SUFFIX,
        reasoning_user_suffix=REASONING_USER,
        speech_instructions=SPEECH,
        negotiation_pressure_block="- Áp lực: khách hàng cần khuyến nghị rõ trước cuối phiên",
    ),
    topic_role_keywords=TOPIC_KEYWORDS,
    role_aliases={"phân tích": "ANALYST", "rủi ro": "RISK", "môi giới": "ADVISOR", "tuân thủ": "COMPLIANCE"},
    default_factions={"bull": ["ANALYST"], "guard": ["RISK", "COMPLIANCE"], "client": ["ADVISOR"]},
    default_opening_speaker="ADVISOR",
    default_key_stakeholders=["ADVISOR"],
)

DEMO_PROMPTS = {
    "ADVISOR": "# VAI TRÒ\nBạn là **Chị Mai**, cố vấn đầu tư. Cân bằng lợi nhuận khách hàng và tuân thủ.",
    "ANALYST": "# VAI TRÒ\nBạn là **Analyst Tuấn**, bullish có số liệu, hay dùng DCF và catalyst.",
    "RISK": "# VAI TRÒ\nBạn là **Risk Officer Linh**, pessimistic, stress-test và nợ.",
    "COMPLIANCE": "# VAI TRÒ\nBạn là **Compliance Hùng**, nhắc disclosure và conflict of interest.",
}


def load_securities_demo_participants(**_) -> ParticipantBundle:
    ids = list(DEMO_PROMPTS.keys())
    edges = {
        "ADVISOR": {
            "ANALYST": RelationshipEdge(source_id="ADVISOR", target_id="ANALYST", affinity=0.2, conflict_weight=0.35),
            "RISK": RelationshipEdge(source_id="ADVISOR", target_id="RISK", affinity=0.3, conflict_weight=0.5),
        },
        "ANALYST": {
            "RISK": RelationshipEdge(source_id="ANALYST", target_id="RISK", affinity=-0.3, conflict_weight=0.7,
                                     notes="RISK hay bóp target price"),
        },
        "RISK": {
            "ANALYST": RelationshipEdge(source_id="RISK", target_id="ANALYST", affinity=-0.2, conflict_weight=0.65),
        },
    }
    matrix = RelationshipMatrix(participants=ids, edges=edges, factions=SECURITIES_DOMAIN.default_factions)
    return ParticipantBundle(
        participant_ids=ids,
        persona_names={"ADVISOR": "Chị Mai", "ANALYST": "Tuấn", "RISK": "Linh", "COMPLIANCE": "Hùng"},
        system_prompts={k: v + "\n\nTrả lời tiếng Việt, ngắn gọn." for k, v in DEMO_PROMPTS.items()},
        relationship_matrix=matrix,
        negotiation_profiles={
            pid: NegotiationProfile(compromise_threshold=0.4 if pid == "RISK" else 0.55)
            for pid in ids
        },
    )
