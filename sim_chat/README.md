# sim_chat — Multi-Agent Simulation Engine

LangGraph engine for multi-participant dialogue: internal monologue, shared proposals, cross-agent facts, conflict-driven orchestration, and SSE streaming.

**Not limited to corporate meetings.** The same core powers tutoring sessions, investment advisory panels, and other apps via **domain packs**.

Full architecture: [`docs/architecture.md`](docs/architecture.md)

## Capabilities

| Feature | Status |
|---------|--------|
| Multi-domain simulation | Done |
| Internal monologue + proposals + facts | Done |
| SSE streaming | Done |
| Post-session private chat | Done (product API) |
| **Resume after completed (facilitator extension)** | **Phase A done** — engine resume + classifier |

## Quick start

```bash
# Run tests (no API key)
python3 -m pytest sim_chat/tests/ -q

# Enterprise meeting (default domain)
python3 sim_chat/examples/run_meeting.py

# Tutoring domain
python3 -c "
from sim_chat import MeetingConfig, create_initial_state, run_meeting
config = MeetingConfig(domain_id='tutoring', meeting_topic='Phương trình bậc hai', max_turns=5, use_mock=True)
print(run_meeting(config, initial_state=create_initial_state(config)))
"
```

## Domains

| `domain_id` | Use case |
|-------------|----------|
| `enterprise` | Internal corporate meeting (default; uses `test_data/` + `src/debating`) |
| `tutoring` | Group tutoring / Socratic debate |
| `securities` | Investment advisory panel |

## API surface

```python
from sim_chat import (
    MeetingConfig,
    ParticipantBundle,
    create_initial_state,
    create_initial_state_from_bundle,
    run_meeting,
    iter_meeting_events,
    get_domain,
    list_domains,
)
```

Resume from a completed record:

```python
from sim_chat import prepare_extension_state, iter_meeting_events, run_meeting

state = prepare_extension_state(
    record,
    "Sếp duyệt thêm 500 triệu. CFO phản hồi.",
    prompts=prompts,
    persona_names=persona_names,
)
for event in iter_meeting_events(state["config"], initial_state=state, llm=llm):
    ...
```

## Integrating your app

1. Build a `ParticipantBundle` from your DB (system prompts, names, relationship matrix).
2. Call `create_initial_state_from_bundle(config, bundle)` or register a domain loader.
3. Run via `run_meeting()` or `iter_meeting_events()` for SSE.

See **§4 Domain packs** and **§17 Meeting extension** in [`docs/architecture.md`](docs/architecture.md).
