"""
Migration script template.
"""
from alembic import op
import sqlalchemy as sa

{{ imports if imports else '' }}


def upgrade():
    {{ upgrade_ops }}


def downgrade():
    {{ downgrade_ops }}
