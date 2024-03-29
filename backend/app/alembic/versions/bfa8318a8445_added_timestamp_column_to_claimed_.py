"""Added timestamp column to Claimed PastelIDs table

Revision ID: bfa8318a8445
Revises: 79f1b3288fdd
Create Date: 2023-06-26 22:23:51.177829

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bfa8318a8445'
down_revision = '79f1b3288fdd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('claimedpastelid', sa.Column('added_at', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('claimedpastelid', 'added_at')
    # ### end Alembic commands ###
