"""Drop debate_scenarios from company_profiles."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_drop_debate_scenarios"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("company_profiles", "debate_scenarios")


def downgrade() -> None:
    op.add_column(
        "company_profiles",
        sa.Column("debate_scenarios", sa.Text(), nullable=False, server_default=""),
    )
