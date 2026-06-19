"""Tests for multi-domain simulation engine."""

from __future__ import annotations

from sim_chat.bootstrap import create_initial_state_from_bundle
from sim_chat.config import MeetingConfig
from sim_chat.domain import get_domain, list_domains, load_domain_participants
from sim_chat.graph import run_meeting


def test_builtin_domains_registered() -> None:
    ids = list_domains()
    assert "enterprise" in ids
    assert "tutoring" in ids
    assert "securities" in ids


def test_tutoring_domain_bundle() -> None:
    bundle = load_domain_participants("tutoring")
    assert bundle.participant_ids == ["TUTOR", "STUDENT_A", "STUDENT_B"]
    assert "TUTOR" in bundle.system_prompts
    assert bundle.relationship_matrix.participants == ["TUTOR", "STUDENT_A", "STUDENT_B"]


def test_tutoring_mock_run_completes() -> None:
    config = MeetingConfig(
        domain_id="tutoring",
        meeting_topic="Giải phương trình bậc hai",
        max_turns=3,
        use_mock=True,
        enable_working_proposals=False,
        enable_shared_facts=False,
        enable_stagnation_check=False,
    )
    bundle = load_domain_participants("tutoring")
    state = create_initial_state_from_bundle(config, bundle)
    assert state["current_speaker"] == "TUTOR"
    record = run_meeting(config, use_mock=True, initial_state=state)
    assert len(record.messages) == 3
    assert record.config.domain_id == "tutoring"


def test_domain_prompts_differ() -> None:
    enterprise = get_domain("enterprise")
    tutoring = get_domain("tutoring")
    assert enterprise.prompts.orchestrator_system != tutoring.prompts.orchestrator_system
    assert enterprise.labels.session_noun != tutoring.labels.session_noun
