"""initial schema

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_contexts_key", "contexts", ["key"], unique=False)
    op.create_index("ix_contexts_id", "contexts", ["id"], unique=False)
    op.create_index("ix_contexts_key", "contexts", ["key"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_documents_kind_title", "documents", ["kind", "title"], unique=False)
    op.create_index("ix_documents_id", "documents", ["id"], unique=False)
    op.create_index("ix_documents_kind", "documents", ["kind"], unique=False)
    op.create_index("ix_documents_url", "documents", ["url"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_document_chunks_doc_idx", "document_chunks", ["document_id", "chunk_index"], unique=False)
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False)
    op.create_index("ix_document_chunks_id", "document_chunks", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_chunks_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("idx_document_chunks_doc_idx", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_documents_url", table_name="documents")
    op.drop_index("ix_documents_kind", table_name="documents")
    op.drop_index("ix_documents_id", table_name="documents")
    op.drop_index("idx_documents_kind_title", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_contexts_key", table_name="contexts")
    op.drop_index("ix_contexts_id", table_name="contexts")
    op.drop_index("idx_contexts_key", table_name="contexts")
    op.drop_table("contexts")
