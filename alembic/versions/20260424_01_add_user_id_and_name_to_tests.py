"""add user_id and name columns to tests

Revision ID: 20260424_01
Revises:
Create Date: 2026-04-24 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260424_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    return column_name in columns


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    return index_name in indexes


def upgrade() -> None:
    if not _has_column("tests", "user_id"):
        op.add_column(
            "tests",
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
        )

    if not _has_column("tests", "name"):
        op.add_column(
            "tests",
            sa.Column("name", sa.String(length=255), nullable=False, server_default="generated_pending"),
        )

    if not _has_index("tests", "ix_tests_user_id"):
        op.create_index("ix_tests_user_id", "tests", ["user_id"], unique=False)

    if not _has_index("tests", "ix_tests_name"):
        op.create_index("ix_tests_name", "tests", ["name"], unique=False)

    if _has_column("tests", "user_id"):
        op.alter_column("tests", "user_id", server_default=None)

    if _has_column("tests", "name"):
        op.alter_column("tests", "name", server_default=None)


def downgrade() -> None:
    if _has_index("tests", "ix_tests_name"):
        op.drop_index("ix_tests_name", table_name="tests")

    if _has_index("tests", "ix_tests_user_id"):
        op.drop_index("ix_tests_user_id", table_name="tests")

    if _has_column("tests", "name"):
        op.drop_column("tests", "name")

    if _has_column("tests", "user_id"):
        op.drop_column("tests", "user_id")
