from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum

class TipoTransacao(str, enum.Enum):
    receita  = "receita"
    despesa  = "despesa"

class StatusTransacao(str, enum.Enum):
    pago     = "pago"
    nao_pago = "nao_pago"

class Transacao(Base):
    __tablename__ = "transacoes"

    id         = Column(Integer, primary_key=True, index=True)
    descricao  = Column(String, nullable=False)          # ex: "Mercado Livre"
    valor      = Column(Float, nullable=False)
    tipo       = Column(Enum(TipoTransacao), nullable=False)
    categoria  = Column(String, default="Outros")        # Casa, Educação, etc.
    status     = Column(Enum(StatusTransacao), default=StatusTransacao.nao_pago)
    metodo     = Column(String, default="PIX")           # PIX, Cartão, etc.
    data       = Column(DateTime(timezone=True), server_default=func.now())
    criado_em  = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Transacao {self.descricao} R${self.valor}>"
