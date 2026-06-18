"""Backfill persona negotiation profiles in metadata JSONB."""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_persona_negotiation"
down_revision: Union[str, None] = "004_chat_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_NEGOTIATION_BY_ROLE: dict[str, dict[str, float]] = {
    "CFO": {
        "compromise_threshold": 0.25,
        "min_interest_retention": 0.85,
        "director_sensitivity": 0.45,
        "deadlock_tolerance": 0.2,
    },
    "PRODUCT": {
        "compromise_threshold": 0.35,
        "min_interest_retention": 0.75,
        "director_sensitivity": 0.5,
        "deadlock_tolerance": 0.25,
    },
    "MARKETING": {
        "compromise_threshold": 0.55,
        "min_interest_retention": 0.65,
        "director_sensitivity": 0.65,
        "deadlock_tolerance": 0.4,
    },
    "SALE": {
        "compromise_threshold": 0.65,
        "min_interest_retention": 0.6,
        "director_sensitivity": 0.7,
        "deadlock_tolerance": 0.45,
    },
    "CEO": {
        "compromise_threshold": 0.70,
        "min_interest_retention": 0.55,
        "director_sensitivity": 0.85,
        "deadlock_tolerance": 0.35,
    },
}

DEFAULT_PROFILE: dict[str, float] = {
    "compromise_threshold": 0.5,
    "min_interest_retention": 0.7,
    "director_sensitivity": 0.6,
    "deadlock_tolerance": 0.3,
}


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT role, metadata FROM personas")).mappings().all()
    for row in rows:
        role = row["role"]
        metadata = row["metadata"] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if metadata.get("negotiation"):
            continue
        negotiation = DEFAULT_NEGOTIATION_BY_ROLE.get(role, DEFAULT_PROFILE)
        metadata = {**metadata, "negotiation": negotiation}
        bind.execute(
            sa.text("UPDATE personas SET metadata = CAST(:metadata AS jsonb) WHERE role = :role"),
            {"metadata": json.dumps(metadata), "role": role},
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT role, metadata FROM personas")).mappings().all()
    for row in rows:
        metadata = row["metadata"] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if "negotiation" not in metadata:
            continue
        metadata = {key: value for key, value in metadata.items() if key != "negotiation"}
        bind.execute(
            sa.text("UPDATE personas SET metadata = CAST(:metadata AS jsonb) WHERE role = :role"),
            {"metadata": json.dumps(metadata), "role": row["role"]},
        )
