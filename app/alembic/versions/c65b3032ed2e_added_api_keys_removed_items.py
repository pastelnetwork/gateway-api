"""added api_keys; removed items

Revision ID: c65b3032ed2e
Revises: 8b5ee0ca9754
Create Date: 2022-10-05 22:14:34.068599

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c65b3032ed2e'
down_revision = '8b5ee0ca9754'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('apikey',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('api_key', sa.String(), nullable=True),
    sa.Column('can_nft', sa.Boolean(), nullable=True),
    sa.Column('can_sense', sa.Boolean(), nullable=True),
    sa.Column('can_cascade', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_apikey_api_key'), 'apikey', ['api_key'], unique=False)
    op.create_index(op.f('ix_apikey_id'), 'apikey', ['id'], unique=False)
    op.drop_index('ix_item_description', table_name='item')
    op.drop_index('ix_item_id', table_name='item')
    op.drop_index('ix_item_title', table_name='item')
    op.drop_table('item')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('item',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('title', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('description', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('owner_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='item_owner_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='item_pkey')
    )
    op.create_index('ix_item_title', 'item', ['title'], unique=False)
    op.create_index('ix_item_id', 'item', ['id'], unique=False)
    op.create_index('ix_item_description', 'item', ['description'], unique=False)
    op.drop_index(op.f('ix_apikey_id'), table_name='apikey')
    op.drop_index(op.f('ix_apikey_api_key'), table_name='apikey')
    op.drop_table('apikey')
    # ### end Alembic commands ###
