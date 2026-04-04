from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.transacao import Transacao, TipoTransacao
from app.schemas.transacao import TransacaoCreate, TransacaoResponse

router = APIRouter()

# ── Listar transações (com filtros opcionais) ──────────────────────────────────
@router.get("/", response_model=List[TransacaoResponse])
def listar_transacoes(
    mes   : Optional[int] = Query(None, ge=1, le=12),
    ano   : Optional[int] = Query(None),
    tipo  : Optional[TipoTransacao] = None,
    db    : Session = Depends(get_db)
):
    query = db.query(Transacao)
    if mes:
        query = query.filter(extract("month", Transacao.data) == mes)
    if ano:
        query = query.filter(extract("year", Transacao.data) == ano)
    if tipo:
        query = query.filter(Transacao.tipo == tipo)
    return query.order_by(Transacao.data.desc()).all()

# ── Criar transação ────────────────────────────────────────────────────────────
@router.post("/", response_model=TransacaoResponse, status_code=201)
def criar_transacao(dados: TransacaoCreate, db: Session = Depends(get_db)):
    transacao = Transacao(
        descricao  = dados.descricao,
        valor      = dados.valor,
        tipo       = dados.tipo,
        categoria  = dados.categoria or "Outros",
        status     = dados.status,
        metodo     = dados.metodo or "PIX",
        data       = dados.data or datetime.now(),
    )
    db.add(transacao)
    db.commit()
    db.refresh(transacao)
    return transacao

# ── Buscar por ID ──────────────────────────────────────────────────────────────
@router.get("/{id}", response_model=TransacaoResponse)
def buscar_transacao(id: int, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    return t

# ── Marcar como pago ───────────────────────────────────────────────────────────
@router.patch("/{id}/pagar", response_model=TransacaoResponse)
def marcar_pago(id: int, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    t.status = "pago"
    db.commit()
    db.refresh(t)
    return t

# ── Deletar ────────────────────────────────────────────────────────────────────
@router.delete("/{id}", status_code=204)
def deletar_transacao(id: int, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    db.delete(t)
    db.commit()
