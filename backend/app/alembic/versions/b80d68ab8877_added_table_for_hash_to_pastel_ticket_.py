"""added table for hash to pastel ticket mapping

Revision ID: b80d68ab8877
Revises: e661b0515902
Create Date: 2023-02-15 22:08:17.587457

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b80d68ab8877'
down_revision = 'e661b0515902'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('regticket',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('data_hash', sa.String(), nullable=True),
    sa.Column('reg_ticket_txid', sa.String(), nullable=True),
    sa.Column('ticket_type', sa.String(), nullable=True),
    sa.Column('blocknum', sa.Integer(), nullable=True),
    sa.Column('caller_pastel_id', sa.String(), nullable=True),
    sa.Column('file_name', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regticket_blocknum'), 'regticket', ['blocknum'], unique=False)
    op.create_index(op.f('ix_regticket_caller_pastel_id'), 'regticket', ['caller_pastel_id'], unique=False)
    op.create_index(op.f('ix_regticket_data_hash'), 'regticket', ['data_hash'], unique=False)
    op.create_index(op.f('ix_regticket_id'), 'regticket', ['id'], unique=False)
    op.create_index(op.f('ix_regticket_reg_ticket_txid'), 'regticket', ['reg_ticket_txid'], unique=False)
    op.create_index(op.f('ix_regticket_ticket_type'), 'regticket', ['ticket_type'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_regticket_ticket_type'), table_name='regticket')
    op.drop_index(op.f('ix_regticket_reg_ticket_txid'), table_name='regticket')
    op.drop_index(op.f('ix_regticket_id'), table_name='regticket')
    op.drop_index(op.f('ix_regticket_data_hash'), table_name='regticket')
    op.drop_index(op.f('ix_regticket_caller_pastel_id'), table_name='regticket')
    op.drop_index(op.f('ix_regticket_blocknum'), table_name='regticket')
    op.drop_table('regticket')
    # ### end Alembic commands ###