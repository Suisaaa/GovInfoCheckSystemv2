"""add CrawlRule model

Revision ID: 56fe5e4e8bc8
Revises: 526983a09a63
Create Date: 2025-12-04 21:14:39.562656

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '56fe5e4e8bc8'
down_revision = '526983a09a63'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()
    if 'crawl_rule' not in tables:
        op.create_table(
            'crawl_rule',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('site', sa.String(length=256), nullable=False, unique=True),
            sa.Column('title_xpath', sa.Text()),
            sa.Column('content_xpath', sa.Text()),
            sa.Column('request_headers', sa.Text()),
            sa.Column('enabled', sa.Boolean(), server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime()),
        )
    else:
        with op.batch_alter_table('crawl_rule', schema=None) as batch_op:
            batch_op.add_column(sa.Column('site', sa.String(length=256), nullable=False))
            batch_op.alter_column('title_xpath', existing_type=sa.VARCHAR(length=512), type_=sa.Text(), existing_nullable=True)
            batch_op.alter_column('content_xpath', existing_type=sa.VARCHAR(length=1024), type_=sa.Text(), existing_nullable=True)
            batch_op.create_unique_constraint('uq_crawl_rule_site', ['site'])
            try:
                batch_op.drop_column('site_name')
            except Exception:
                pass
            try:
                batch_op.drop_column('site_domain')
            except Exception:
                pass


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()
    if 'crawl_rule' in tables:
        op.drop_table('crawl_rule')
