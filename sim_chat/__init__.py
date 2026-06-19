"""Virtual Meeting Room Chat Framework — LangGraph multi-persona simulation."""

from .bootstrap import apply_domain_defaults, create_initial_state, create_initial_state_from_bundle
from .config import MeetingConfig
from .domain import ParticipantBundle, get_domain, list_domains, load_domain_participants, register_domain
from .graph import build_meeting_graph, iter_meeting_events, run_meeting
from .extension import ExtensionSignificance, evaluate_extension_significance
from .insight import generate_insight_report
from .models import (
    DialogueTurn,
    FACILITATOR_SPEAKER_ID,
    FACILITATOR_SPEAKER_NAME,
    HiddenTurn,
    InternalMonologue,
    MeetingRecord,
    MeetingState,
    RelationshipEdge,
    RelationshipMatrix,
    TerminationReason,
)
from .persistence import load_meeting_record, save_meeting_record
from .private_chat import PrivateChatSession, create_session_from_record
from .resume import (
    append_facilitator_turn,
    attach_extension_audit,
    extension_count_from_record,
    prepare_extension_state,
    state_from_record,
)

__all__ = [
    "DialogueTurn",
    "ExtensionSignificance",
    "FACILITATOR_SPEAKER_ID",
    "FACILITATOR_SPEAKER_NAME",
    "HiddenTurn",
    "InternalMonologue",
    "MeetingConfig",
    "MeetingRecord",
    "MeetingState",
    "ParticipantBundle",
    "PrivateChatSession",
    "RelationshipEdge",
    "RelationshipMatrix",
    "TerminationReason",
    "append_facilitator_turn",
    "apply_domain_defaults",
    "attach_extension_audit",
    "build_meeting_graph",
    "create_initial_state",
    "create_initial_state_from_bundle",
    "create_session_from_record",
    "evaluate_extension_significance",
    "extension_count_from_record",
    "generate_insight_report",
    "get_domain",
    "iter_meeting_events",
    "list_domains",
    "load_domain_participants",
    "load_meeting_record",
    "prepare_extension_state",
    "register_domain",
    "run_meeting",
    "save_meeting_record",
    "state_from_record",
]
