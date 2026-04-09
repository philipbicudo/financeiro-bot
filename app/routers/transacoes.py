# Adicione estes endpoints no app/routers/transacoes.py
# (ou substitua o arquivo completo)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
import re

from app.database import get_db
from app.models.transacao import Transacao, TipoTransacao, StatusTransacao

router = APIRouter()

# ── SCHEMAS com validação ──

class TransacaoCreate(BaseModel):
    descricao:  str
    valor:      float
    tipo:       str = "despesa"
    categoria:  str = "Outros"
    metodo:     str = "PIX"
    status:     str = "pago"
    data:       Optional[str] = None

    @validator('descricao')
    def sanitize_descricao(cls, v):
        v = v.strip()[:200]
        # Remove tags HTML e scripts
        v = re.sub(r'<[^>]+>', '', v)
        v = re.sub(r'javascript:', '', v, flags=re.IGNORECASE)
        if not v:
            raise ValueError('Descrição inválida')
        return v

    @validator('valor')
    def validate_valor(cls, v):
        if v <= 0 or v > 999_999_999:
            raise ValueError('Valor deve ser positivo e menor que 1 bilhão')
        return round(v, 2)

    @validator('tipo')
    def validate_tipo(cls, v):
        if v not in ('despesa', 'receita'):
            raise ValueError('Tipo deve ser despesa ou receita')
        return v

    @validator('categoria')
    def sanitize_categoria(cls, v):
        return v.strip()[:100]

    @validator('metodo')
    def sanitize_metodo(cls, v):
        allowed = ('PIX','Cartão de Crédito','Cartão de Débito','Boleto','TED','Dinheiro','App','Outros')
        return v if v in allowed else 'PIX'

    @validator('status')
    def validate_status(cls, v):
        if v not in ('pago', 'nao_pago', 'pendente'):
            return 'pago'
        return v


class TransacaoUpdate(BaseModel):
    descricao:  Optional[str] = None
    valor:      Optional[float] = None
    tipo:       Optional[str] = None
    categoria:  Optional[str] = None
    metodo:     Optional[str] = None
    status:     Optional[str] = None
    data:       Optional[str] = None

    @validator('descricao')
    def sanitize_descricao(cls, v):
        if v is None: return v
        v = v.strip()[:200]
        v = re.sub(r'<[^>]+>', '', v)
        v = re.sub(r'javascript:', '', v, flags=re.IGNORECASE)
        return v or None

    @validator('valor')
    def validate_valor(cls, v):
        if v is None: return v
        if v <= 0 or v > 999_999_999:
            raise ValueError('Valor inválido')
        return round(v, 2)

    @validator('status')
    def validate_status(cls, v):
        if v is None: return v
        return v if v in ('pago', 'nao_pago', 'pendente') else 'pago'


# ── ENDPOINTS ──

@router.get("/")
def listar_transacoes(
    mes:    int | None = None,
    ano:    int | None = None,
    tipo:   str | None = None,
    status: str | None = None,
    limit:  int = 100,
    db: Session = Depends(get_db)
):
    q = db.query(Transacao)
    if mes:
        q = q.filter(Transacao.data != None)
    q = q.order_by(Transacao.data.desc()).limit(min(limit, 500))
    return q.all()


@router.post("/")
def criar_transacao(tx: TransacaoCreate, db: Session = Depends(get_db)):
    nova = Transacao(
        descricao = tx.descricao,
        valor     = tx.valor,
        tipo      = TipoTransacao.despesa if tx.tipo == 'despesa' else TipoTransacao.receita,
        categoria = tx.categoria,
        metodo    = tx.metodo,
        status    = StatusTransacao.pago if tx.status == 'pago' else StatusTransacao.nao_pago,
        data      = datetime.now(),
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova


@router.patch("/{tx_id}")
def editar_transacao(
    tx_id: int,
    dados: TransacaoUpdate,
    db: Session = Depends(get_db)
):
    """Edita uma transação existente."""
    tx = db.query(Transacao).filter(Transacao.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    if dados.descricao is not None:
        tx.descricao = dados.descricao
    if dados.valor is not None:
        tx.valor = dados.valor
    if dados.tipo is not None:
        tx.tipo = TipoTransacao.despesa if dados.tipo == 'despesa' else TipoTransacao.receita
    if dados.categoria is not None:
        tx.categoria = dados.categoria.strip()[:100]
    if dados.metodo is not None:
        tx.metodo = dados.metodo
    if dados.status is not None:
        tx.status = StatusTransacao.pago if dados.status == 'pago' else StatusTransacao.nao_pago

    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}")
def deletar_transacao(tx_id: int, db: Session = Depends(get_db)):
    """Deleta uma transação permanentemente."""
    tx = db.query(Transacao).filter(Transacao.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    db.delete(tx)
    db.commit()
    return {"ok": True, "deletado": tx_id}
