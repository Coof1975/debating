"""Add scheduled_at, host_id, notes to meetings."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_meeting_metadata"
down_revision: Union[str, None] = "002_drop_debate_scenarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column("host_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("meetings", "notes")
    op.drop_column("meetings", "host_id")
    op.drop_column("meetings", "scheduled_at")
