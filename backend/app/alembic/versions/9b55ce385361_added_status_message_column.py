"""Added status_message column

Revision ID: 9b55ce385361
Revises: e102e4c14bf0
Create Date: 2023-07-19 15:11:27.212261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b55ce385361'
down_revision = 'e102e4c14bf0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('cascade', sa.Column('process_status_message', sa.String(), nullable=True))
    op.add_column('collection', sa.Column('process_status_message', sa.String(), nullable=True))
    op.add_column('nft', sa.Column('process_status_message', sa.String(), nullable=True))
    op.add_column('sense', sa.Column('process_status_message', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('sense', 'process_status_message')
    op.drop_column('nft', 'process_status_message')
    op.drop_column('collection', 'process_status_message')
    op.drop_column('cascade', 'process_status_message')
    # ### end Alembic commands ###
