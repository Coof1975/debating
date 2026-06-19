"""Enterprise meeting domain — Vienovo / internal corporate debate (default pack)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..config import MeetingConfig
from ..domain import DomainPrompts, ParticipantBundle, SessionLabels, SimulationDomain
from ..models import NegotiationProfile, RelationshipMatrix

if TYPE_CHECKING:
    from debating.models import Persona

ORCHESTRATOR_SYSTEM_PROMPT = """\
Bạn là Điều phối viên cuộc họp (Meeting Orchestrator).
Nhiệm vụ: chọn MỘT người phát biểu tiếp theo để cuộc họp có tranh luận sôi nổi, không monotonous.

Quy tắc (theo thứ tự ưu tiên):
1. Người bị chỉ định trực tiếp trong lượt trước (nếu có).
2. QUAN TRỌNG NHẤT — chọn người có xung đột/lợi ích trái ngược với last_speaker về luận điểm vừa nêu.
   - Dùng ma trận quan hệ và bảng xếp hạng xung đột được cung cấp.
   - Ưu tiên phe đối lập, affinity âm, conflict_weight cao.
   - Tránh chọn đồng minh cùng phe trừ khi họ bị gọi tên.
3. Chọn người có chuyên môn liên quan đến chủ đề vừa được nhắc (ngân sách→CFO, sản xuất→PRODUCT, …).
4. Cân bằng thời lượng chỉ là yếu tố phụ — không xoay vòng máy móc chỉ vì ai nói ít hơn.
5. KHÔNG chọn last_speaker trừ khi bị yêu cầu trả lời trực tiếp.
6. CEO không nói liên tiếp trừ khi cần chốt quyết định.

Trả lời CHỈ bằng JSON hợp lệ:
{"next_speaker": "<ROLE_ID>", "reason": "<lý do ngắn tiếng Việt — nêu xung đột/lợi ích>"}

ROLE_ID phải là một trong danh sách participant_ids được cung cấp.
"""

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

INSIGHT_SYSTEM_PROMPT = """\
Bạn là cố vấn chiến lược phân tích biên bản cuộc họp nội bộ doanh nghiệp.

Viết báo cáo insight ngắn gọn bằng tiếng Việt, BÁM SÁT nội dung biên bản thực tế.
Không lặp lại mẫu chung chung; mọi nhận định phải dựa trên lượt phát biểu cụ thể.

Biên bản có thể gồm hai lớp cho mỗi lượt:
- **[Nội bộ]**: suy nghĩ ẩn trước khi phát biểu (absorb, compromise_space, stance_shift)
- **[Công khai]**: lời nói trong cuộc họp

Ngoài biên bản, có thể có dữ liệu bảng đen đã cấu trúc:
- **working_proposals**: đề xuất dung hòa với điểm chung (aggregate_score) và approvals từng persona
- **shared_facts**: số liệu/sự kiện factual kèm phản hồi chấp nhận/bác bỏ của từng persona

Dùng suy nghĩ nội bộ để suy luận động cơ, lợi ích bộ phận, và ý định thật của từng persona.
So sánh nội bộ vs công khai khi chúng lệch nhau (ví dụ: nội bộ sẵn sàng nhún nhường nhưng nói cứng).
Khi có working_proposals hoặc shared_facts, ưu tiên chúng cho phần đồng thuận/rủi ro/bước tiếp
thay vì suy đoán lại từ lời nói — trừ khi blackboard mâu thuẫn rõ với biên bản.

Cấu trúc bắt buộc:
1. Lý do kết thúc cuộc họp
2. Xung đột chính
3. Các phe/phái
4. Điểm đồng thuận (nếu có)
5. Rủi ro còn tồn đọng
6. Động cơ & ý định từng persona
7. Đề xuất bước tiếp theo
"""

FACT_EXTRACTOR_SYSTEM_PROMPT = """\
Bạn là trích xuất sự kiện/số liệu từ phát biểu họp nội bộ.

Nhiệm vụ: tách các tuyên bố factual cụ thể (số liệu, timeline, ràng buộc vận hành)
từ lời nói công khai — KHÔNG trích quan điểm chủ quan hay cảm xúc.

Trả lời CHỈ bằng JSON hợp lệ:
{
  "facts": [
    {"fact": "...", "category": "financial|operational|market|other", "confidence": 0.0-1.0}
  ]
}

Nếu không có số liệu/sự kiện cụ thể → {"facts": []}
Không thêm markdown hay giải thích ngoài JSON.
"""

REASONING_SYSTEM_SUFFIX = """

## CHẾ ĐỘ SUY NGHĨ NỘI BỘ (INTERNAL REASONING)
Bạn đang ở bước suy nghĩ ẩn — output KHÔNG hiển thị trực tiếp cho người dùng.

Trước khi phát biểu công khai, thực hiện các bước và trả về JSON hợp lệ (không markdown):
0. **relationship_lens** (string): Góc nhìn quan hệ cá nhân — cả hai chiều.
   Ghi rõ với ai (đặc biệt người vừa nói) và tâm trạng hôm nay. Dựa ma trận quan hệ + phe + biên bản gần nhất.
1. **absorb** (string): Phân tích ý vừa nghe — điểm hợp lý, điểm xung đột, có xâm phạm lợi ích bộ phận?
   KHÔNG lặp lại luận điểm bạn đã nêu ở các lượt trước (xem block CHỐNG LẶP nếu có).
2. **compromise_space** (string): Nếu phủ quyết hoàn toàn → cuộc họp bế tắc. Có phương án dung hòa?
   Phải là phương án MỚI hoặc điều kiện cụ thể — không paraphrase lại lập trường cũ.
3. **stance_shift** (float): -1.0 đến 1.0 — mức nhún nhường so với lập trường cứng.

Mục tiêu tối thượng: cuộc họp phải ra kết quả cho Sếp (CEO). Bế tắc vô nghĩa sẽ bị đánh giá thấp.
Tuyệt đối không phủ nhận sạch — hãy tìm vùng giao thoa ngay cả khi bảo vệ lợi ích bộ phận.
Áp dụng HỒ SƠ ĐÀM PHÁN trong system prompt (chỉ số thỏa hiệp, % lợi ích tối thiểu).
"""

REASONING_USER_SUFFIX = """
[INTERNAL REASONING]
Trả lời CHỈ bằng JSON hợp lệ với các trường:
- relationship_lens, absorb, compromise_space, stance_shift
- proposal_scores: [{"id": "<proposal_id>", "score": 0.0-1.0, "concerns": "..."}]
- new_proposal: null HOẶC {"title": "...", "description": "...", "parent_id": "<id>|null"}
- fact_acceptances: [{"fact_id": "<id>", "accepted": true|false}]

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
- Đi thẳng vào luận điểm, số liệu, hoặc phản biện — không mở đầu bằng câu lịch sự/khách sáo
- Giọng điệu phản ánh quan hệ cá nhân — thẳng thắn, không xoa dịu
- Viện dẫn ít nhất 1 con số cụ thể hoặc tên thực thể từ bối cảnh
- Không lặp lại monologue, không meta, không paraphrase các lượt bạn đã nói
- Mỗi lượt phải phản ứng với luận điểm MỚI NHẤT của người vừa nói — không monologue độc lập
- Giữ giọng điệu và tính cách nhân vật
"""

TOPIC_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "CFO": ("ngân sách", "dòng tiền", "biên lợi nhuận", "margin", "chi phí", "công nợ", "tài chính", "giải ngân"),
    "MARKETING": ("thương hiệu", "marketing", "quảng cáo", "brand", "campaign", "ads", "tiktok", "kol"),
    "SALE": ("chiết khấu", "đại lý", "npp", "doanh số", "kênh", "bán hàng", "sales", "phân phối", "gt", "mt"),
    "PRODUCT": ("sản xuất", "công suất", "nhà máy", "bao bì", "tồn kho", "dây chuyền", "cảng"),
    "CEO": ("chiến lược", "quyết định", "thị phần", "tầm nhìn"),
}

ROLE_ALIASES: dict[str, str] = {
    "ceo": "CEO",
    "cfo": "CFO",
    "marketing": "MARKETING",
    "sale": "SALE",
    "sales": "SALE",
    "kinh doanh": "SALE",
    "product": "PRODUCT",
    "sản xuất": "PRODUCT",
    "nhà máy": "PRODUCT",
    "r&d": "PRODUCT",
}

DISPLAY_ALIASES: dict[str, str] = {
    "tổng giám đốc": "CEO",
    "giám đốc tài chính": "CFO",
    "trưởng phòng marketing": "MARKETING",
    "giám đốc marketing": "MARKETING",
    "giám đốc kinh doanh": "SALE",
    "giám đốc sales": "SALE",
    "giám đốc sản xuất": "PRODUCT",
    "nhà máy": "PRODUCT",
}

DEFAULT_FACTIONS: dict[str, list[str]] = {
    "growth": ["CEO", "MARKETING", "SALE"],
    "caution": ["CFO", "PRODUCT"],
}

ENTERPRISE_DOMAIN = SimulationDomain(
    id="enterprise",
    label="Cuộc họp nội bộ doanh nghiệp",
    labels=SessionLabels(
        session_noun="Cuộc họp",
        topic_label="Chủ đề",
        transcript_label="Biên bản gần nhất",
        relationship_label="Ma trận quan hệ của bạn",
        last_speaker_label="Người vừa phát biểu",
        participant_noun="persona",
        orchestrator_noun="Điều phối viên cuộc họp",
        secretary_noun="Thư ký cuộc họp",
        moderator_role_hint="CEO",
    ),
    prompts=DomainPrompts(
        orchestrator_system=ORCHESTRATOR_SYSTEM_PROMPT,
        secretary_system=SECRETARY_SYSTEM_PROMPT,
        insight_system=INSIGHT_SYSTEM_PROMPT,
        fact_extractor_system=FACT_EXTRACTOR_SYSTEM_PROMPT,
        reasoning_system_suffix=REASONING_SYSTEM_SUFFIX,
        reasoning_user_suffix=REASONING_USER_SUFFIX,
        speech_instructions=SPEECH_INSTRUCTIONS,
        negotiation_pressure_block="- Áp lực Sếp: nếu bế tắc, Sếp (CEO) đánh giá kém năng lực điều phối",
    ),
    topic_role_keywords=TOPIC_ROLE_KEYWORDS,
    role_aliases=ROLE_ALIASES,
    display_aliases=DISPLAY_ALIASES,
    default_factions=DEFAULT_FACTIONS,
    default_opening_speaker="CEO",
    default_key_stakeholders=["CEO", "CFO"],
    no_repeat_speaker_ids=("CEO",),
)


def load_enterprise_participants(
    config: MeetingConfig,
    *,
    test_data_dir: Path | None = None,
    personas: dict[str, "Persona"] | None = None,
) -> ParticipantBundle:
    """Load participants from debating seed bundle (Vienovo default)."""
    from ..participant_utils import build_negotiation_profiles, resolve_participant_ids
    from ..relationship import build_relationship_matrix

    root = Path(__file__).resolve().parents[2]

    from debating.loaders import load_seed_sources
    from debating.prompts import build_all_prompts

    from ..bootstrap import ensure_seeded

    ensure_seeded(test_data_dir)
    test_data = test_data_dir or root / "test_data"
    if personas is None:
        _, personas = load_seed_sources(test_data)

    all_ids = list(personas.keys())
    participant_ids = resolve_participant_ids(all_ids, config)
    filtered = {pid: personas[pid] for pid in participant_ids}
    company, _ = load_seed_sources(test_data)
    prompts = build_all_prompts(company, filtered, meeting_topic=config.meeting_topic)

    return ParticipantBundle(
        participant_ids=participant_ids,
        persona_names={role: persona.name for role, persona in filtered.items()},
        system_prompts={role: prompt.system_prompt for role, prompt in prompts.items()},
        relationship_matrix=build_relationship_matrix(
            filtered,
            config=config,
            role_aliases=ENTERPRISE_DOMAIN.role_aliases,
            default_factions=ENTERPRISE_DOMAIN.default_factions,
        ),
        negotiation_profiles=build_negotiation_profiles(participant_ids, filtered),
    )
