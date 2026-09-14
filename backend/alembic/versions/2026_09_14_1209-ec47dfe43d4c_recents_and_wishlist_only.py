"""recents and wishlist only

Items remember which browser searched them (for Recents), and the shopping bag is
removed: bag entries are folded into the wishlist.

Revision ID: ec47dfe43d4c
Revises: ec4d3c87e88d
Create Date: 2026-09-14 12:09:20.297699

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec47dfe43d4c'
down_revision: Union[str, Sequence[str], None] = 'ec4d3c87e88d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('items', sa.Column('client_id', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_items_client_id'), 'items', ['client_id'], unique=False)

    # Fold bag entries into the wishlist, dropping ones already wishlisted.
    op.execute(
        """
        DELETE FROM saved_items bag
        USING saved_items wish
        WHERE bag.list = 'bag' AND wish.list = 'wishlist'
          AND bag.client_id = wish.client_id AND bag.url = wish.url
        """
    )
    op.drop_constraint('saved_items_client_id_list_url_key', 'saved_items', type_='unique')
    op.drop_column('saved_items', 'list')  # also drops the saved_list check constraint
    op.create_unique_constraint(
        'saved_items_client_id_url_key', 'saved_items', ['client_id', 'url']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('saved_items_client_id_url_key', 'saved_items', type_='unique')
    op.add_column(
        'saved_items',
        sa.Column(
            'list',
            sa.Enum('bag', 'wishlist', name='saved_list', native_enum=False, create_constraint=True, length=24),
            server_default='wishlist',
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        'saved_items_client_id_list_url_key', 'saved_items', ['client_id', 'list', 'url']
    )
    op.drop_index(op.f('ix_items_client_id'), table_name='items')
    op.drop_column('items', 'client_id')
