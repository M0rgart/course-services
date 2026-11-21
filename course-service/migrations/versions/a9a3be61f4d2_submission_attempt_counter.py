from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9a3be61f4d2"
down_revision: str | None = "c5c8ccad4829"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submission_attempt_counters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "student_id"),
    )
    op.create_index(
        "ix_submission_attempt_counters_student_id",
        "submission_attempt_counters",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_submission_attempt_counters_student_id",
        table_name="submission_attempt_counters",
    )
    op.drop_table("submission_attempt_counters")
