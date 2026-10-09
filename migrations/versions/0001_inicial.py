"""tabelas de eventos de webhook e vendas

Revision ID: 0001
Revises:
Create Date: 2026-10-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eventos_webhook",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plataforma", sa.String(30), nullable=False),
        sa.Column(
            "recebido_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("assinatura_valida", sa.Boolean(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("processado", sa.Boolean(), nullable=False),
        sa.Column("erro", sa.Text(), nullable=True),
    )
    op.create_table(
        "vendas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plataforma", sa.String(30), nullable=False),
        sa.Column("id_transacao", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("produto", sa.String(200), nullable=False),
        sa.Column("valor_centavos", sa.Integer(), nullable=False),
        sa.Column("comprador_email_hash", sa.String(64), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("plataforma", "id_transacao", name="uq_vendas_plataforma_transacao"),
        sa.CheckConstraint(
            "status IN ('pendente', 'recusada', 'aprovada', 'reembolsada', 'cancelada', "
            "'chargeback')",
            name="ck_vendas_status",
        ),
        sa.CheckConstraint("valor_centavos >= 0", name="ck_vendas_valor"),
    )
    op.create_index("ix_vendas_comprador", "vendas", ["comprador_email_hash"])
    op.create_index("ix_vendas_criado_em", "vendas", ["criado_em"])


def downgrade() -> None:
    op.drop_table("vendas")
    op.drop_table("eventos_webhook")
