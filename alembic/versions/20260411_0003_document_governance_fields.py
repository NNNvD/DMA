"""document governance fields

Revision ID: 20260411_0003
Revises: 20260324_0002
Create Date: 2026-04-11 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260411_0003"
down_revision = "20260324_0002"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    columns = _column_names("documents")
    indexes = _index_names("documents")

    if "source_class" not in columns:
        op.add_column(
            "documents",
            sa.Column(
                "source_class",
                sa.String(length=32),
                nullable=False,
                server_default="private_local",
            ),
        )
    if "privacy_scope" not in columns:
        op.add_column(
            "documents",
            sa.Column(
                "privacy_scope",
                sa.String(length=32),
                nullable=False,
                server_default="private_local",
            ),
        )
    if "review_status" not in columns:
        op.add_column(
            "documents",
            sa.Column(
                "review_status",
                sa.String(length=32),
                nullable=False,
                server_default="approved",
            ),
        )
    if "visibility_scope" not in columns:
        op.add_column(
            "documents",
            sa.Column(
                "visibility_scope",
                sa.String(length=32),
                nullable=False,
                server_default="gm_only",
            ),
        )
    if "rag_eligible" not in columns:
        op.add_column(
            "documents",
            sa.Column(
                "rag_eligible", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
        )
    if "train_eligible" not in columns:
        op.add_column(
            "documents",
            sa.Column(
                "train_eligible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    if "ix_documents_source_class" not in indexes:
        op.create_index(
            "ix_documents_source_class", "documents", ["source_class"], unique=False
        )
    if "ix_documents_review_status" not in indexes:
        op.create_index(
            "ix_documents_review_status", "documents", ["review_status"], unique=False
        )
    if "ix_documents_visibility_scope" not in indexes:
        op.create_index(
            "ix_documents_visibility_scope",
            "documents",
            ["visibility_scope"],
            unique=False,
        )
    if "idx_documents_kind_rag_visibility" not in indexes:
        op.create_index(
            "idx_documents_kind_rag_visibility",
            "documents",
            ["kind", "rag_eligible", "visibility_scope"],
            unique=False,
        )


def downgrade() -> None:
    columns = _column_names("documents")
    indexes = _index_names("documents")

    if "idx_documents_kind_rag_visibility" in indexes:
        op.drop_index("idx_documents_kind_rag_visibility", table_name="documents")
    if "ix_documents_visibility_scope" in indexes:
        op.drop_index("ix_documents_visibility_scope", table_name="documents")
    if "ix_documents_review_status" in indexes:
        op.drop_index("ix_documents_review_status", table_name="documents")
    if "ix_documents_source_class" in indexes:
        op.drop_index("ix_documents_source_class", table_name="documents")

    if "train_eligible" in columns:
        op.drop_column("documents", "train_eligible")
    if "rag_eligible" in columns:
        op.drop_column("documents", "rag_eligible")
    if "visibility_scope" in columns:
        op.drop_column("documents", "visibility_scope")
    if "review_status" in columns:
        op.drop_column("documents", "review_status")
    if "privacy_scope" in columns:
        op.drop_column("documents", "privacy_scope")
    if "source_class" in columns:
        op.drop_column("documents", "source_class")
