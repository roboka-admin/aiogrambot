"""Switch the seeded Gemini provider to the current free-tier model.

Google retired ``gemini-2.5-flash-lite`` for new users; the API now answers
404 and points to ``gemini-3.5-flash-lite`` (500 free requests/day). Only
rows still on the old default are touched so an admin-chosen model is kept.

Revision ID: 0013_update_gemini_model
Revises: 0012_add_ai_monitoring
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_update_gemini_model"
down_revision: Union[str, Sequence[str], None] = "0012_add_ai_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_MODEL = "gemini-2.5-flash-lite"
_NEW_MODEL = "gemini-3.5-flash-lite"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ai_providers SET model = :new_model, status = 'ready', "
            "last_error = NULL WHERE `key` = 'gemini' AND model = :old_model"
        ).bindparams(new_model=_NEW_MODEL, old_model=_OLD_MODEL)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ai_providers SET model = :old_model "
            "WHERE `key` = 'gemini' AND model = :new_model"
        ).bindparams(new_model=_NEW_MODEL, old_model=_OLD_MODEL)
    )
