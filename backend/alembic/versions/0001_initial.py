"""Initial tenant, documents, screening and review schema."""

from alembic import op
from app.db import Base

revision = "0001"
down_revision = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind)


def downgrade():
    Base.metadata.drop_all(op.get_bind())
