from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.transacao import TipoTransacao, StatusTransacao

# Schema para CRIAR uma transação
class TransacaoCreate(BaseModel):
    descricao : str                = Field(..., example="Mercado Livre")
    valor     : float              = Field(..., gt=0, example=110.00)
    tipo      : TipoTransacao      = Field(..., example="despesa")
    categoria : Optional[str]      = Field("Outros", example="Casa")
    status    : Optional[StatusTransacao] = StatusTransacao.nao_pago
    metodo    : Optional[str]      = Field("PIX", example="Cartão Crédito Inter")
    data      : Optional[datetime] = None

# Schema para RETORNAR uma transação
class TransacaoResponse(BaseModel):
    id        : int
    descricao : str
    valor     : float
    tipo      : TipoTransacao
    categoria : str
    status    : StatusTransacao
    metodo    : str
    data      : datetime
    criado_em : datetime

    class Config:
        from_attributes = True

# Schema do resumo mensal
class ResumoMensal(BaseModel):
    mes              : str
    ano              : int
    total_receitas   : float
    total_despesas   : float
    saldo            : float
    receitas_pagas   : float
    receitas_a_receber: float
    despesas_pagas   : float
    despesas_a_pagar : float
    por_categoria    : dict
