"""Virtual Meeting Room Chat Framework — LangGraph multi-persona simulation."""

from .bootstrap import apply_domain_defaults, create_initial_state, create_initial_state_from_bundle
from .config import MeetingConfig
from .domain import ParticipantBundle, get_domain, list_domains, load_domain_participants, register_domain
from .graph import build_meeting_graph, iter_meeting_events, run_meeting
from .insight import generate_insight_report
from .models import (
    DialogueTurn,
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

__all__ = [
    "DialogueTurn",
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
    "apply_domain_defaults",
    "build_meeting_graph",
    "create_initial_state",
    "create_initial_state_from_bundle",
    "create_session_from_record",
    "generate_insight_report",
    "get_domain",
    "iter_meeting_events",
    "list_domains",
    "load_domain_participants",
    "load_meeting_record",
    "register_domain",
    "run_meeting",
    "save_meeting_record",
]
