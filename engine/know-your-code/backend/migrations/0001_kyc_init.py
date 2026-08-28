"""Legend — initial tables (kyc_*).

Alembic revision. NOTE FOR THE MAINTAINER: set `down_revision` below to your current head
(run `alembic heads` to find it) so this chains onto the host's migration history, then
`alembic upgrade head`.
"""
from alembic import op
import sqlalchemy as sa

revision = "kyc_0001_init"
down_revision = None          # <-- set to your current Alembic head before upgrading
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "kyc_repos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("orgs.id", ondelete="CASCADE"), index=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="indexing"),
        sa.Column("stats", sa.JSON(), nullable=True),
        sa.Column("progress", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "kyc_files",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("repo_id", sa.String(), sa.ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("language", sa.String(), server_default="other"),
        sa.Column("size_bytes", sa.Integer(), server_default="0"),
        sa.Column("sha256", sa.String(), server_default=""),
    )
    op.create_table(
        "kyc_symbols",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("repo_id", sa.String(), sa.ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True),
        sa.Column("file_id", sa.String(), sa.ForeignKey("kyc_files.id", ondelete="CASCADE"), index=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("signature", sa.Text(), server_default=""),
        sa.Column("line_start", sa.Integer(), server_default="0"),
        sa.Column("line_end", sa.Integer(), server_default="0"),
        sa.Column("docstring", sa.Text(), server_default=""),
    )
    op.create_table(
        "kyc_qa_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("repo_id", sa.String(), sa.ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "kyc_qa_turns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("kyc_qa_sessions.id", ondelete="CASCADE"), index=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), server_default=""),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "kyc_tours",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("repo_id", sa.String(), sa.ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("steps", sa.JSON(), nullable=True),
    )


def downgrade():
    for t in ("kyc_tours", "kyc_qa_turns", "kyc_qa_sessions", "kyc_symbols", "kyc_files", "kyc_repos"):
        op.drop_table(t)
