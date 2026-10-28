"""Store operator approval receipts separately from campaign context.

Revision ID: 20261028_0007
Revises: 20261007_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20261028_0007"
down_revision = "20261007_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campaign_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("intent", sa.JSON(), nullable=False),
        sa.Column("intent_hash", sa.String(64), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=True),
        sa.Column("request_key", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("operator_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("approved_at", sa.Float(), nullable=True),
        sa.Column("completed_at", sa.Float(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("scope_key", "request_key", name="uq_approval_request"),
    )


def downgrade():
    op.drop_table("campaign_approvals")
