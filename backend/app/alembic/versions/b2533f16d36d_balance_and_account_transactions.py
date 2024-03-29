"""Balance and account transactions

Revision ID: b2533f16d36d
Revises: 376d9eba0a8b
Create Date: 2023-11-30 20:20:06.793605

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2533f16d36d'
down_revision = '376d9eba0a8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('accounttransactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.Enum('DEPOSIT', 'WITHDRAWAL', 'MOVED_TO_APIKEY', 'USAGE', name='txtype'), nullable=False),
    sa.Column('balance', sa.Float(), nullable=True),
    sa.Column('added_at', sa.DateTime(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accounttransactions_id'), 'accounttransactions', ['id'], unique=False)
    op.add_column('apikey', sa.Column('balance', sa.Float(), nullable=True))
    op.add_column('user', sa.Column('balance', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'balance')
    op.drop_column('apikey', 'balance')
    op.drop_index(op.f('ix_accounttransactions_id'), table_name='accounttransactions')
    op.drop_table('accounttransactions')
    # ### end Alembic commands ###
