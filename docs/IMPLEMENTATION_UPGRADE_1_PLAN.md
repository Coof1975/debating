# Implementation Plan — Upgrade 1: Multi-Stage Reasoning

Tài liệu này mô tả kế hoạch nâng cấp kiến trúc xử lý Agent từ **"phản xạ vô điều kiện"** sang **"Tư duy đa tầng" (Multi-stage Reasoning)** — giúp Persona tư duy mở, biết lắng nghe nhưng vẫn giữ bản sắc và lợi ích riêng.

**Combo mục tiêu:** Internal Monologue + Shared Proposals + Cross-Agent Fact Caching + Negotiation Profile.

---

## 1. Mục tiêu & phạm vi

### 1.1 Mục tiêu sản phẩm

| Vấn đề hiện tại | Mục tiêu sau nâng cấp |
|------------------|------------------------|
| Agent đọc transcript rồi phun luận điểm cứng ngay | Agent suy nghĩ 3 bước (Absorb → Compromise → Output) trước khi phát biểu |
| Debate chỉ là free-text chat history | Có **working_proposals** — gọt giũa đề xuất chung thay vì cãi ai đúng |
| Persona không có tham số thỏa hiệp | **compromise_threshold**, áp lực Sếp, min interest retention per persona |
| Mỗi agent chỉ biết static company facts | **Cross-agent fact cache** — số liệu B nói ra được A dùng ở lượt sau |
| Secretary đánh giá consensus từ transcript mơ hồ | Secretary đọc structured proposals + aggregate approval scores |

### 1.2 Ngoài phạm vi (upgrade này)

- Vector RAG / Pinecone cho persona knowledge base
- Dynamic relationship matrix update sau mỗi turn
- Group chat nhiều persona trong một thread
- Hiển thị internal monologue cho end-user (chỉ admin/debug SSE)
- Thay đổi orchestrator speaker-selection logic (giữ nguyên trừ khi cần ưu tiên proposal author)

### 1.3 Hiện trạng codebase (baseline)

| Thành phần | Trạng thái |
|------------|------------|
| LangGraph StateGraph (orchestrator → persona → secretary) | ✅ `sim_chat/graph.py` |
| Persona turn = 1 LLM call → public speech | ⚠️ `sim_chat/nodes.py` `make_persona_node` |
| MeetingState: messages, relationship_matrix, secretary_verdict | ✅ `sim_chat/models.py` |
| Static context injection (role-filtered company facts) | ✅ `src/debating/prompts.py` |
| Persona profiles (PostgreSQL JSONB sections) | ✅ `backend/app/db/models.py` |
| Internal monologue | ❌ |
| working_proposals blackboard | ❌ |
| compromise_threshold per persona | ❌ |
| Cross-agent shared facts | ❌ |
| Embeddings | ⚠️ Chỉ dùng stagnation detection (`sim_chat/embeddings.py`) |

**File tham chiếu chính:**

```
sim_chat/models.py          # MeetingState schema
sim_chat/nodes.py           # persona_node (single-shot)
sim_chat/graph.py           # StateGraph + SSE events
sim_chat/config.py          # MeetingConfig tunables
sim_chat/stopping.py        # consensus / stagnation routing
sim_chat/orchestrator.py    # speaker selection
sim_chat/transcript.py      # rolling summary + context window
src/debating/prompts.py     # system prompt assembly
src/debating/models.py      # Persona domain model
backend/app/services/prompt_service.py
backend/app/services/simulation_service.py
frontend/src/hooks/useMeetingStream.ts
frontend/src/pages/meeting/MeetingSimulationTab.tsx
```

---

## 2. Kiến trúc mục tiêu

### 2.1 Luồng graph hiện tại

```
START → orchestrator → persona (1 LLM) → route → orchestrator | secretary | finalize
```

### 2.2 Luồng graph mục tiêu

```
START → orchestrator → persona (reason → speak → extract) → route → orchestrator | secretary | finalize
```

**persona node nội bộ (3 phase):**

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE A — REASON (hidden, không stream UI)                 │
│  Absorb → Compromise Space → proposal_scores / new_proposal │
├─────────────────────────────────────────────────────────────┤
│  PHASE B — SPEAK (public DialogueTurn.content)              │
│  Yes-and speech, 2–6 câu, không lặp monologue               │
├─────────────────────────────────────────────────────────────┤
│  PHASE C — EXTRACT (Python + optional LLM)                   │
│  shared_facts dedup + working_proposals update              │
└─────────────────────────────────────────────────────────────┘
```

Khuyến nghị triển khai: **1 graph node `persona`**, **2 LLM calls** (reason JSON → speech), phase C là post-process Python (+ LLM nhẹ nếu cần).

### 2.3 MeetingState mở rộng

```python
# sim_chat/models.py — fields mới

class InternalMonologue(BaseModel):
    absorb: str
    compromise_space: str
    stance_shift: float = Field(ge=-1, le=1)  # mức nhún nhường

class HiddenTurn(BaseModel):
    speaker_id: str
    turn_index: int
    monologue: InternalMonologue

class ProposalApproval(BaseModel):
    persona_id: str
    score: float = Field(ge=0, le=1)
    concerns: str = ""

class WorkingProposal(BaseModel):
    id: str
    author_id: str
    turn_index: int
    title: str
    description: str
    approvals: dict[str, ProposalApproval] = {}
    aggregate_score: float = 0.0
    status: Literal["draft", "active", "superseded", "accepted"] = "draft"
    parent_id: str | None = None

class SharedFact(BaseModel):
    id: str
    source_speaker_id: str
    turn_index: int
    fact: str
    category: Literal["financial", "operational", "market", "other"] = "other"
    confidence: float = 0.8
    accepted_by: dict[str, bool] = {}

# MeetingState additions
hidden_turns: Annotated[list[HiddenTurn], operator.add]
working_proposals: Annotated[list[WorkingProposal], operator.add]  # hoặc replace-in-place
shared_facts: Annotated[list[SharedFact], operator.add]
last_monologue: dict[str, InternalMonologue]  # speaker_id → latest
```

### 2.4 NegotiationProfile (Persona)

Lưu trong PostgreSQL (`personas.metadata` hoặc `sections["negotiation"]`), không phải MongoDB.

```python
# src/debating/models.py
class NegotiationProfile(BaseModel):
    compromise_threshold: float = Field(default=0.5, ge=0, le=1)
    min_interest_retention: float = Field(default=0.7, ge=0, le=1)
    director_sensitivity: float = Field(default=0.6, ge=0, le=1)
    deadlock_tolerance: float = Field(default=0.3, ge=0, le=1)
```

**Seed mặc định theo role:**

| Role | compromise_threshold | Ghi chú |
|------|---------------------|---------|
| CFO | 0.25 | Bảo thủ ngân sách, Thái Tuế |
| PRODUCT | 0.35 | Phòng thủ chất lượng |
| MARKETING | 0.55 | Linh hoạt chiến lược |
| SALE | 0.65 | Cần chốt deal |
| CEO | 0.70 | Chịu nhún để ra quyết định |

---

## 3. Chi tiết 4 pillar

### 3.1 Pillar 1 — Internal Monologue 3 bước

**Mục đích:** Thay single-shot bằng suy nghĩ ẩn trước khi phát biểu công khai.

**Prompt reasoning (JSON only):**

```
Bước 1 ABSORB: [last_speaker] vừa nói "...". Đúng/sai theo tri thức của bạn?
              Xâm phạm lợi ích bộ phận không?
Bước 2 COMPROMISE: Nếu phủ quyết hoàn toàn → bế tắc. Có phương án giữ ≥{min_interest_retention}%
                   lợi ích bộ phận không?
Bước 3 (draft): Ghi nhận hướng phát biểu — chưa viết speech.

Input context:
- compromise_threshold: {threshold}
- Áp lực Sếp: {director_pressure_text}
- working_proposals: {proposals_summary}
- shared_facts: {shared_facts_summary}
- Ma trận quan hệ: {rel_summary}
```

**Prompt speak (public):**

```
Dựa trên monologue đã phân tích, viết 2–6 câu phát biểu họp:
- Tuyệt đối không phủ nhận sạch — "Yes, and..."
- Không lặp lại monologue hay meta ("tôi đã suy nghĩ...")
- Giữ giọng điệu persona
```

**Structured JSON option (1 call thay 2):**

```json
{
  "absorb": "...",
  "compromise_space": "...",
  "stance_shift": 0.3,
  "proposal_scores": [{"id": "p1", "score": 0.5, "concerns": "..."}],
  "new_proposal": null,
  "speech": "..."
}
```

**Files:**

| File | Thay đổi |
|------|----------|
| `sim_chat/reasoning.py` | **Mới** — prompts, parse JSON, fallback |
| `sim_chat/models.py` | `InternalMonologue`, `HiddenTurn` |
| `sim_chat/nodes.py` | Refactor `make_persona_node` |
| `sim_chat/config.py` | `enable_internal_monologue: bool = True` |
| `sim_chat/llm.py` | MockLLM trả structured JSON |
| `sim_chat/tests/test_reasoning.py` | **Mới** — parse + fallback tests |

---

### 3.2 Pillar 2 — Shared Blackboard (`working_proposals`)

**Mục đích:** Dịch chuyển debate từ "cãi ai đúng" sang "gọt giũa proposal chung".

**Luồng cập nhật sau mỗi turn:**

1. Reasoning step chấm điểm mỗi `active` proposal (`proposal_scores`)
2. Nếu agent đưa đề xuất dung hòa mới → tạo `WorkingProposal` (`status=active`)
3. Proposal cũ bị refine → `parent_id` link, proposal cũ → `superseded`
4. `aggregate_score` = mean của approval scores
5. Cap `max_active_proposals` (default 5); summarize proposals cũ nếu overflow

**Secretary nâng cấp** (`sim_chat/nodes.py`):

```
Đề xuất đang trên bàn:
{working_proposals_json}

has_consensus = true CHỈ KHI:
- Có ≥1 proposal active với aggregate_score ≥ {consensus_threshold}
- VÀ key_stakeholder đã approve proposal đó (trong approvals hoặc speech)
```

**Stopping** (`sim_chat/stopping.py`):

```python
def check_proposal_consensus(state: MeetingState) -> bool:
    active = [p for p in state["working_proposals"] if p.status == "active"]
    if not active:
        return False
    best = max(active, key=lambda p: p.aggregate_score)
    return best.aggregate_score >= state["config"].consensus_threshold
```

**Persist:** `MeetingRecord.metadata["working_proposals"]`

**SSE:** event type `proposal_update` (optional Phase 3)

**Files:**

| File | Thay đổi |
|------|----------|
| `sim_chat/proposals.py` | **Mới** — extract, merge, aggregate |
| `sim_chat/models.py` | `WorkingProposal`, `ProposalApproval` |
| `sim_chat/nodes.py` | Secretary prompt + post-turn update |
| `sim_chat/stopping.py` | `check_proposal_consensus` |
| `sim_chat/graph.py` | SSE `proposal_update`, persist metadata |
| `frontend/src/hooks/useMeetingStream.ts` | Handle `proposal_update` |
| `frontend/src/pages/meeting/MeetingSimulationTab.tsx` | Proposals panel (optional) |

---

### 3.3 Pillar 3 — Compromise Threshold & Áp lực Sếp

**Mục đích:** Persona có tham số đàm phán; prompt "biết hậu quả" khi gây bế tắc.

**Prompt block mới** (`src/debating/prompts.py`):

```
# HỒ SƠ ĐÀM PHÁN
- Chỉ số thỏa hiệp: {compromise_threshold}/1.0
- Tối thiểu giữ lợi ích bộ phận: {min_interest_retention * 100}%
- Mục tiêu tối thượng: cuộc họp phải ra kết quả cho Sếp (CEO).
  Nếu anh cố chấp gây bế tắc vô nghĩa, Sếp sẽ đánh giá anh kém năng lực điều phối.
- Khi compromise_threshold thấp: vẫn phải "Yes, and..." — không phủ nhận sạch.
```

**Dynamic compromise** (optional, `enable_dynamic_compromise`):

```python
# Khi stagnation_score cao hoặc loop_count tăng:
effective_threshold = base_threshold * (1 + director_sensitivity * stagnation_factor)
# Agent "mềm" dần để tránh bế tắc
```

**Files:**

| File | Thay đổi |
|------|----------|
| `src/debating/models.py` | `NegotiationProfile` |
| `src/debating/prompts.py` | Block HỒ SƠ ĐÀM PHÁN |
| `src/debating/loaders.py` | Parse negotiation từ markdown (optional) |
| `test_data/*_persona.md` | Seed negotiation defaults |
| `backend/alembic/versions/005_persona_negotiation.py` | **Mới** — migration |
| `backend/app/schemas/persona.py` | API schema |
| `backend/app/services/persona_service.py` | CRUD negotiation fields |
| `frontend/src/pages/PersonaEditPage.tsx` | Sliders compromise_threshold |

---

### 3.4 Pillar 4 — Cross-Agent Fact Caching

**Mục đích:** Agent A dùng số liệu factual agent B vừa nói, dù không có trong static company profile.

**Pipeline:**

```
Public speech → fact_extractor (LLM) → shared_facts state
                                      → dedup via embeddings
Next persona reasoning → inject shared_facts vào user context
                      → accept/reject trong absorb step
```

**Fact extractor output:**

```json
{
  "facts": [
    {
      "fact": "Chi phí vận hành Q1 tăng 20%",
      "category": "financial",
      "confidence": 0.85
    }
  ]
}
```

**User context injection** (`sim_chat/nodes.py` `_build_user_context`):

```
## Sự kiện đồng nghiệp vừa đưa (chưa có trong hồ sơ của bạn)
- [CFO @ lượt 5]: Chi phí vận hành Q1 +20%
→ Không bắt buộc đồng ý quan điểm, nhưng phải xử lý số liệu nếu hợp lý.
```

**Khác vector RAG:** Đây là episodic short-term memory trong meeting state; không cần vector DB. Reuse `sim_chat/embeddings.py` cho dedup only.

**Files:**

| File | Thay đổi |
|------|----------|
| `sim_chat/facts.py` | **Mới** — extract, dedup, format context |
| `sim_chat/models.py` | `SharedFact` |
| `sim_chat/nodes.py` | Inject facts vào user context |
| `sim_chat/embeddings.py` | `is_duplicate_fact()` helper |
| `sim_chat/config.py` | `max_shared_facts`, `fact_extraction_min_confidence` |

---

## 4. MeetingConfig mở rộng

```python
# sim_chat/config.py — bổ sung

# Feature flags
enable_internal_monologue: bool = True
enable_working_proposals: bool = True
enable_shared_facts: bool = True
enable_dynamic_compromise: bool = True

# Debug / SSE
monologue_in_sse: bool = False  # admin only

# Proposals
proposal_consensus_mode: Literal["secretary", "aggregate", "both"] = "both"
max_active_proposals: int = 5

# Facts
fact_extraction_min_confidence: float = 0.6
max_shared_facts: int = 20

# Reasoning
reasoning_max_tokens: int = 512
speech_max_tokens: int = 512
```

---

## 5. Lộ trình triển khai (4 phase)

### Phase 1 — Reasoning Core

**Thời gian ước lượng:** 1–2 tuần

**Mục tiêu:** Agent không còn single-shot; có monologue ẩn + speech công khai.

| # | Task | Files |
|---|------|-------|
| 1.1 | Models `InternalMonologue`, `HiddenTurn` | `sim_chat/models.py` |
| 1.2 | `reasoning.py` — prompts + JSON parse + fallback | mới |
| 1.3 | Refactor `make_persona_node` (reason → speak) | `sim_chat/nodes.py` |
| 1.4 | Config flag `enable_internal_monologue` | `sim_chat/config.py` |
| 1.5 | MockLLM structured JSON | `sim_chat/llm.py` |
| 1.6 | Unit tests | `sim_chat/tests/test_reasoning.py` |
| 1.7 | Cập nhật `bootstrap.py` init state fields | `sim_chat/bootstrap.py` |

**Definition of Done:**

- [ ] `run_conflict_meeting.py` chạy không lỗi với flag ON và OFF
- [ ] Public transcript vẫn 2–6 câu, không leak monologue
- [ ] Debug log / optional SSE có monologue khi `monologue_in_sse=True`
- [ ] JSON parse fail → fallback speech-only (behavior cũ)
- [ ] Không regression orchestrator / secretary / stagnation

---

### Phase 2 — Negotiation Profile

**Thời gian ước lượng:** 3–5 ngày

**Mục tiêu:** Persona có compromise threshold; prompt "biết điều".

| # | Task | Files |
|---|------|-------|
| 2.1 | `NegotiationProfile` model | `src/debating/models.py` |
| 2.2 | Prompt block HỒ SƠ ĐÀM PHÁN | `src/debating/prompts.py` |
| 2.3 | Seed defaults per role | `test_data/*_persona.md`, `scripts/seed.py` |
| 2.4 | DB migration | `backend/alembic/versions/005_*.py` |
| 2.5 | API + service | `backend/app/schemas/persona.py`, `persona_service.py` |
| 2.6 | Admin UI sliders | `frontend/src/pages/PersonaEditPage.tsx` |
| 2.7 | Wire vào reasoning prompt | `sim_chat/reasoning.py` |

**Definition of Done:**

- [ ] CFO (threshold 0.25) vs CEO (0.70) cho monologue khác biệt rõ trong cùng scenario
- [ ] Speech vẫn tuân Yes-and rule
- [ ] Admin có thể chỉnh threshold qua UI
- [ ] Seed script populate negotiation defaults

---

### Phase 3 — Shared Blackboard

**Thời gian ước lượng:** 1 tuần

**Mục tiêu:** Proposal-centric debate; secretary chốt trên structured proposals.

| # | Task | Files |
|---|------|-------|
| 3.1 | `WorkingProposal` models | `sim_chat/models.py` |
| 3.2 | `proposals.py` — extract, merge, aggregate | mới |
| 3.3 | Proposal scores trong reasoning JSON | `sim_chat/reasoning.py` |
| 3.4 | Secretary đọc proposals | `sim_chat/nodes.py` |
| 3.5 | `check_proposal_consensus` | `sim_chat/stopping.py` |
| 3.6 | Persist + SSE | `sim_chat/graph.py` |
| 3.7 | Frontend proposals panel (optional) | `MeetingSimulationTab.tsx` |

**Definition of Done:**

- [ ] Meeting Keos tạo ≥1 active proposal
- [ ] Approvals tích lũy theo turn
- [ ] Secretary `has_consensus=true` khi best proposal aggregate ≥ threshold
- [ ] `MeetingRecord.metadata` chứa final proposals
- [ ] Feature flag OFF → behavior Phase 1/2

---

### Phase 4 — Cross-Agent Facts

**Thời gian ước lượng:** 1 tuần

**Mục tiêu:** Agent B reference số liệu factual agent A nói ra.

| # | Task | Files |
|---|------|-------|
| 4.1 | `SharedFact` model | `sim_chat/models.py` |
| 4.2 | `facts.py` — extract + dedup | mới |
| 4.3 | Inject vào `_build_user_context` | `sim_chat/nodes.py` |
| 4.4 | Accept/reject trong reasoning | `sim_chat/reasoning.py` |
| 4.5 | Dedup helper | `sim_chat/embeddings.py` |
| 4.6 | Integration test scenario | `sim_chat/tests/test_facts.py` |

**Definition of Done:**

- [ ] CFO nói "+20% chi phí" → Marketing turn sau reference số liệu đó
- [ ] Duplicate facts không nhân bản (embedding dedup)
- [ ] `max_shared_facts` cap hoạt động
- [ ] Feature flag OFF → không extract facts

---

## 6. Thứ tự triển khai theo ROI

| Ưu tiên | Phase | Lý do |
|---------|-------|-------|
| 1 | Phase 1 — Internal Monologue | Impact lớn nhất, diff nhỏ nhất, không đụng DB/UI |
| 2 | Phase 2 — Negotiation Profile | Cheap, tăng personality variance |
| 3 | Phase 4 — Cross-Agent Facts | Fix "mù số liệu người khác" |
| 4 | Phase 3 — Shared Blackboard | Structural shift lớn nhất, cần secretary + UI |

---

## 7. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giải pháp |
|--------|-----|-----------|
| Latency 2–3× mỗi turn | Cao | Structured single-call; model nhỏ cho extract; cache prompt prefix |
| JSON parse fail | Trung bình | Retry 1 lần + fallback speech-only |
| Agent "giả compromise" | Trung bình | Proposal scores + secretary verify hành động cụ thể |
| Token overflow | Trung bình | Cap proposals/facts; summarize proposals cũ |
| Over-engineering | Thấp | Feature flags từng pillar; ship Phase 1 trước, đo chất lượng |
| Breaking existing meetings | Trung bình | Flags default ON cho meeting mới; replay meeting cũ không cần new fields |

---

## 8. Tiêu chí đánh giá thành công (A/B)

So sánh `enable_internal_monologue=False` vs `True` trên cùng meeting topic:

| Metric | Cách đo | Mục tiêu |
|--------|---------|----------|
| Stagnation rate | Mean `stagnation_score` at termination | Giảm ≥20% |
| Yes-and ratio | % turns có acknowledge trước phản biện (LLM judge hoặc keyword) | Tăng ≥30% |
| Proposal convergence | `aggregate_score` slope over rounds | Tăng monotonic |
| Consensus turn | Turn index khi `has_consensus=true` | Giảm ≥15% |
| Qualitative | Human review 5 meetings | "Không còn cố thủ luận điểm" |

---

## 9. Ví dụ hành vi mong đợi

**Trước (single-shot):**

> "Tôi phản đối dự án X vì phòng tôi không có tiền."

**Sau (multi-stage reasoning):**

> "Tôi đồng ý với anh B là dự án X rất tiềm năng, nhưng ngân sách hiện tại của phòng tôi đang kẹt. Anh B có thể chia pha triển khai để giảm áp lực chi phí giai đoạn 1 được không?"

**Monologue ẩn (không hiển thị UI):**

```json
{
  "absorb": "B đúng về tiềm năng X. Sai ở timeline giai đoạn 1 — trùng peak season.",
  "compromise_space": "Chia 2 pha: pilot Q3, scale Q4. Giữ 70% ngân sách phòng.",
  "stance_shift": 0.4,
  "new_proposal": {
    "title": "Triển khai Keos 2 pha",
    "description": "Pha 1: pilot 3 tỉnh, ngân sách 40% kế hoạch..."
  }
}
```

---

## 10. Checklist bắt đầu Phase 1

```
[ ] Tạo sim_chat/reasoning.py (prompts + parse)
[ ] Thêm InternalMonologue, HiddenTurn vào models.py
[ ] Refactor make_persona_node trong nodes.py
[ ] Thêm enable_internal_monologue vào config.py
[ ] Cập nhật MockLLM trong llm.py
[ ] Viết sim_chat/tests/test_reasoning.py
[ ] Chạy sim_chat/examples/run_conflict_meeting.py — so sánh output
[ ] Document flag trong sim_chat/docs/architecture.md (optional)
```

---

## 11. Liên kết tài liệu

- Kiến trúc gốc: `sim_chat/docs/architecture.md`
- Implementation plan sản phẩm (admin/meeting/chat): `docs/IMPLEMENTATION_PLAN.md`
- Persona seed: `test_data/*_persona.md`

---

*Cập nhật: 2026-06-18 — Upgrade 1: Multi-Stage Reasoning*
