"""Added client table for client ids and secrets

Revision ID: c9b9615c2c52
Revises: d5bebf95cc98
Create Date: 2024-04-24 00:10:11.159479

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9b9615c2c52'
down_revision = 'd5bebf95cc98'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('client',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hashed_secret', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_client_hashed_secret'), 'client', ['hashed_secret'], unique=True)
    op.create_index(op.f('ix_client_id'), 'client', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_client_id'), table_name='client')
    op.drop_index(op.f('ix_client_hashed_secret'), table_name='client')
    op.drop_table('client')
    # ### end Alembic commands ###
