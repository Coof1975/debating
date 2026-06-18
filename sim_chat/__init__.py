"""Virtual Meeting Room Chat Framework — LangGraph multi-persona simulation."""

from .config import MeetingConfig
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
    "PrivateChatSession",
    "RelationshipEdge",
    "RelationshipMatrix",
    "TerminationReason",
    "build_meeting_graph",
    "create_session_from_record",
    "generate_insight_report",
    "iter_meeting_events",
    "load_meeting_record",
    "run_meeting",
    "save_meeting_record",
]
