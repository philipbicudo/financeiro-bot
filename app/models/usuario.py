# ═══════════════════════════════════════════════════════
# ARQUIVO 1: app/models/usuario.py
# ═══════════════════════════════════════════════════════
# from app.models.usuario import Usuario  (adicionar no database.py)

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id           = Column(Integer, primary_key=True, index=True)
    nome         = Column(String, nullable=False)
    telefone     = Column(String, unique=True, index=True, nullable=False)  # ex: 5513991560950
    email        = Column(String, unique=True, index=True, nullable=True)
    senha_hash   = Column(String, nullable=True)  # para login web

    # Plano
    plano        = Column(Enum("gratis", "pro", "familia", name="plano_enum"), default="gratis")
    plano_ativo  = Column(Boolean, default=True)
    plano_expira = Column(DateTime, nullable=True)

    # Mercado Pago
    mp_subscription_id = Column(String, nullable=True)
    mp_payer_id        = Column(String, nullable=True)

    # Controle
    ativo      = Column(Boolean, default=True)
    criado_em  = Column(DateTime, default=datetime.utcnow)
    atualizado = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamento com transações
    transacoes = relationship("Transacao", back_populates="usuario", cascade="all, delete-orphan")

    def pode_registrar(self, total_mes: int) -> bool:
        """Verifica se o usuário pode registrar mais transações."""
        if not self.plano_ativo:
            return False
        if self.plano == "gratis" and total_mes >= 50:
            return False
        return True

    def limite_contas(self) -> int:
        limites = {"gratis": 1, "pro": 3, "familia": 999}
        return limites.get(self.plano, 1)
