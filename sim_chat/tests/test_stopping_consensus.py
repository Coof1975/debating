"""Heuristic consensus guards against truncated turns."""

from sim_chat.config import MeetingConfig
from sim_chat.models import DialogueTurn
from sim_chat.stopping import heuristic_consensus


def test_heuristic_rejects_early_or_truncated_meeting() -> None:
    config = MeetingConfig()
    short = [
        DialogueTurn(speaker_id="CEO", speaker_name="CEO", content="Mở đầu.", round_number=1, turn_index=1),
        DialogueTurn(
            speaker_id="PRODUCT",
            speaker_name="PRODUCT",
            content="Về sản lượng Keos, chúng tôi chỉ cam kết được tối đa",
            round_number=1,
            turn_index=2,
        ),
    ]
    verdict = heuristic_consensus(short, config)
    assert verdict.has_consensus is False
