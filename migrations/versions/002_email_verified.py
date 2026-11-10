"""users.email_verified (account-linking safety).

Revision ID: 002
"""
import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("users")]
    if "email_verified" not in cols:  # fresh installs get it from the baseline metadata
        op.add_column("users", sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"))


def downgrade():
    op.drop_column("users", "email_verified")
