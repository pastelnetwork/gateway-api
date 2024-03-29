"""Updated table for NFT

Revision ID: b8a7547c15f1
Revises: 1c268ae760ae
Create Date: 2023-05-25 14:40:56.021923

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b8a7547c15f1'
down_revision = '1c268ae760ae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('nft', sa.Column('nft_properties', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('nft', sa.Column('collection_act_txid', sa.String(), nullable=True))
    op.add_column('nft', sa.Column('open_api_group_id', sa.String(), nullable=True))
    op.drop_index('ix_nft_burn_txid', table_name='nft')
    op.drop_column('nft', 'burn_txid')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('nft', sa.Column('burn_txid', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.create_index('ix_nft_burn_txid', 'nft', ['burn_txid'], unique=False)
    op.drop_column('nft', 'open_api_group_id')
    op.drop_column('nft', 'collection_act_txid')
    op.drop_column('nft', 'nft_properties')
    # ### end Alembic commands ###
