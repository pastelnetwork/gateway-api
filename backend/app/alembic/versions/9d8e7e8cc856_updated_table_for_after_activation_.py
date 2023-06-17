"""Updated table for 'after_activation_transfer_to_pastelid' in cascade and nft; and collection_act_txid and open_api_group_id in sense

Revision ID: 9d8e7e8cc856
Revises: bb047a5187a3
Create Date: 2023-06-17 00:32:11.593707

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d8e7e8cc856'
down_revision = 'bb047a5187a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('nft', sa.Column('offer_ticket_txid', sa.String(), nullable=True))
    op.add_column('nft', sa.Column('offer_ticket_intended_rcpt_pastel_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_nft_offer_ticket_intended_rcpt_pastel_id'), 'nft', ['offer_ticket_intended_rcpt_pastel_id'], unique=False)
    op.create_index(op.f('ix_nft_offer_ticket_txid'), 'nft', ['offer_ticket_txid'], unique=False)
    op.add_column('sense', sa.Column('collection_act_txid', sa.String(), nullable=True))
    op.add_column('sense', sa.Column('open_api_group_id', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('sense', 'open_api_group_id')
    op.drop_column('sense', 'collection_act_txid')
    op.drop_index(op.f('ix_nft_offer_ticket_txid'), table_name='nft')
    op.drop_index(op.f('ix_nft_offer_ticket_intended_rcpt_pastel_id'), table_name='nft')
    op.drop_column('nft', 'offer_ticket_intended_rcpt_pastel_id')
    op.drop_column('nft', 'offer_ticket_txid')
    # ### end Alembic commands ###
