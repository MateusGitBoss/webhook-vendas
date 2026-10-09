"""Tabelas do banco (ORM). A migração equivalente fica em migrations/versions."""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vendas.db import Base

STATUS_VENDA = ("pendente", "recusada", "aprovada", "reembolsada", "cancelada", "chargeback")


class EventoWebhook(Base):
    """Todo aviso recebido, válido ou não, exatamente como chegou. Serve de auditoria."""

    __tablename__ = "eventos_webhook"

    id: Mapped[int] = mapped_column(primary_key=True)
    plataforma: Mapped[str] = mapped_column(String(30))
    recebido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    assinatura_valida: Mapped[bool]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    processado: Mapped[bool] = mapped_column(default=False)
    erro: Mapped[str | None] = mapped_column(Text)


class Venda(Base):
    __tablename__ = "vendas"
    __table_args__ = (
        UniqueConstraint("plataforma", "id_transacao", name="uq_vendas_plataforma_transacao"),
        CheckConstraint(f"status IN {STATUS_VENDA}", name="ck_vendas_status"),
        CheckConstraint("valor_centavos >= 0", name="ck_vendas_valor"),
        Index("ix_vendas_comprador", "comprador_email_hash"),
        Index("ix_vendas_criado_em", "criado_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plataforma: Mapped[str] = mapped_column(String(30))
    id_transacao: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    produto: Mapped[str] = mapped_column(String(200))
    valor_centavos: Mapped[int]
    comprador_email_hash: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
