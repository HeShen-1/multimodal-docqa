"""
Phase 5: 添加查询历史表

Revision ID: phase5_query_history
Revises: previous_revision
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector


# revision identifiers
revision = 'phase5_query_history'
down_revision = None  # 如果有之前的迁移，请设置为上一个revision ID
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库"""
    # 创建 pgvector 扩展（如果尚未创建）
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # 创建 query_history 表
    op.create_table(
        'query_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('question_embedding', Vector(1024)),
        sa.Column('document_id', sa.String(), sa.ForeignKey('documents.id', ondelete='SET NULL')),
        sa.Column('document_name', sa.String(255)),
        sa.Column('query_count', sa.Integer(), default=1, nullable=False),
        sa.Column('last_queried', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # 创建索引
    op.create_index('idx_query_history_user_id', 'query_history', ['user_id'])
    op.create_index('idx_query_history_document_id', 'query_history', ['document_id'])
    op.create_index('idx_query_history_query_count', 'query_history', ['query_count'])
    op.create_index('idx_query_history_last_queried', 'query_history', ['last_queried'])
    op.create_index('idx_query_history_user_question', 'query_history', ['user_id', 'question'])
    
    # 创建向量索引（使用 IVFFlat）
    op.execute("""
        CREATE INDEX idx_query_history_embedding 
        ON query_history 
        USING ivfflat (question_embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade():
    """降级数据库"""
    # 删除索引
    op.drop_index('idx_query_history_embedding', 'query_history')
    op.drop_index('idx_query_history_user_question', 'query_history')
    op.drop_index('idx_query_history_last_queried', 'query_history')
    op.drop_index('idx_query_history_query_count', 'query_history')
    op.drop_index('idx_query_history_document_id', 'query_history')
    op.drop_index('idx_query_history_user_id', 'query_history')
    
    # 删除表
    op.drop_table('query_history')
