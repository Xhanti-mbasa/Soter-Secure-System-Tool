"""Initial Secure schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("scans", sa.Column("id", sa.String(36), primary_key=True), sa.Column("target", sa.Text(), nullable=False), sa.Column("hostname", sa.String(253), nullable=False), sa.Column("profile", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("authorization_record", sa.JSON(), nullable=False), sa.Column("summary", sa.JSON(), nullable=False), sa.Column("celery_task_id", sa.String(64)), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_scans_status", "scans", ["status"])
    op.create_table("assets", sa.Column("id", sa.String(36), primary_key=True), sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False), sa.Column("hostname", sa.String(253), nullable=False), sa.Column("url", sa.Text()), sa.Column("metadata", sa.JSON(), nullable=False))
    op.create_index("ix_assets_scan_id", "assets", ["scan_id"])
    op.create_table("findings", sa.Column("id", sa.String(36), primary_key=True), sa.Column("scan_id", sa.String(36), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False), sa.Column("source", sa.String(40), nullable=False), sa.Column("source_rule_id", sa.String(200)), sa.Column("title", sa.Text(), nullable=False), sa.Column("severity", sa.String(16), nullable=False), sa.Column("confidence", sa.String(16), nullable=False), sa.Column("affected_url", sa.Text(), nullable=False), sa.Column("category", sa.String(100)), sa.Column("cwe", sa.String(32)), sa.Column("owasp", sa.String(100)), sa.Column("summary", sa.Text(), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False), sa.Column("remediation", sa.Text(), nullable=False), sa.Column("references", sa.JSON(), nullable=False), sa.Column("fingerprint", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False))
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])


def downgrade() -> None:
    op.drop_table("findings")
    op.drop_table("assets")
    op.drop_table("scans")
