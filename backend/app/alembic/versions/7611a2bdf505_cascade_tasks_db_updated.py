"""cascade tasks db updated

Revision ID: 7611a2bdf505
Revises: 669a53466d02
Create Date: 2022-10-25 14:23:58.088170

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7611a2bdf505'
down_revision = '669a53466d02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('cascade', sa.Column('original_file_name', sa.String(), nullable=True))
    op.add_column('cascade', sa.Column('original_file_content_type', sa.String(), nullable=True))
    op.add_column('cascade', sa.Column('original_file_local_path', sa.String(), nullable=True))
    op.create_index(op.f('ix_cascade_task_id'), 'cascade', ['task_id'], unique=False)
    op.create_index(op.f('ix_cascade_wn_task_id'), 'cascade', ['wn_task_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_cascade_wn_task_id'), table_name='cascade')
    op.drop_index(op.f('ix_cascade_task_id'), table_name='cascade')
    op.drop_column('cascade', 'original_file_local_path')
    op.drop_column('cascade', 'original_file_content_type')
    op.drop_column('cascade', 'original_file_name')
    # ### end Alembic commands ###
