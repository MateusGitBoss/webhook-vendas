"""Formatos de entrada e saída validados com Pydantic."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

StatusVenda = Literal["pendente", "recusada", "aprovada", "reembolsada", "cancelada", "chargeback"]


class VendaNormalizada(BaseModel):
    """Formato interno único: cada plataforma é traduzida para isto pelo seu adaptador."""

    id_transacao: str = Field(min_length=1, max_length=100)
    status: StatusVenda
    produto: str = Field(min_length=1, max_length=200)
    valor_centavos: int = Field(ge=0)
    comprador_email: EmailStr


class RespostaWebhook(BaseModel):
    recebido: bool = True
    venda_id: int | None = None
    mudanca: Literal["nova", "status_atualizado", "sem_mudanca"]


class VendaPorHora(BaseModel):
    hora: int
    quantidade: int
    valor_centavos: int


class VendaPorProduto(BaseModel):
    produto: str
    quantidade: int
    valor_centavos: int


class ResumoDia(BaseModel):
    dia: str
    vendas_aprovadas: int
    faturamento_centavos: int
    reembolsos: int
    chargebacks: int
    ticket_medio_centavos: int
    por_hora: list[VendaPorHora]
    por_produto: list[VendaPorProduto]


class VendaPublica(BaseModel):
    id: int
    plataforma: str
    id_transacao: str
    status: str
    produto: str
    valor_centavos: int
    criado_em: datetime
    atualizado_em: datetime


class ConsultaStatus(BaseModel):
    email: EmailStr


class StatusCompra(BaseModel):
    produto: str
    status: str
    plataforma: str
    atualizado_em: datetime
