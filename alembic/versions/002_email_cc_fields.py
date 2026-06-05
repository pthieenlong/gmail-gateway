"""add cc_emails and delivered_via to emails

Revision ID: 002
Revises: 001
"""
import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("emails", sa.Column("cc_emails", sa.Text(), nullable=True))
    op.add_column("emails", sa.Column("delivered_via", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("emails", "delivered_via")
    op.drop_column("emails", "cc_emails")
