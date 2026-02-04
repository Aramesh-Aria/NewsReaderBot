"""add enabled lookup indexes

Revision ID: c4c2b6a2d1f3
Revises: b9807055096a
Create Date: 2026-02-04

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "c4c2b6a2d1f3"
down_revision = "b9807055096a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_sources_user_id_is_enabled",
        "user_sources",
        ["user_id", "is_enabled"],
    )
    op.create_index(
        "ix_user_topics_user_id_is_enabled",
        "user_topics",
        ["user_id", "is_enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_topics_user_id_is_enabled", table_name="user_topics")
    op.drop_index("ix_user_sources_user_id_is_enabled", table_name="user_sources")

