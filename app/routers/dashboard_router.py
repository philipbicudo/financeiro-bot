# app/routers/dashboard.py
# Adicione este arquivo em app/routers/dashboard.py
# e registre no main.py: app.include_router(dashboard.router)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from app.database import get_db
from app.models.transacao import Transacao

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def mes_atual():
    now = datetime.now()
    return now.month, now.year


@router.get("/resumo")
def get_resumo(
    mes: int | None = None,
    ano: int | None = None,
    db: Session = Depends(get_db)
):
    """Resumo financeiro — mês atual ou mês específico."""
    if mes is None or ano is None:
        mes, ano = mes_atual()

    txs = db.query(Transacao).filter(
        extract('month', Transacao.data) == mes,
        extract('year',  Transacao.data) == ano
    ).all()

    receitas  = sum(t.valor for t in txs if t.tipo == "receita")
    gastos    = sum(t.valor for t in txs if t.tipo == "despesa")
    a_pagar   = sum(t.valor for t in txs if t.tipo == "despesa" and t.status == "pendente")
    saldo     = receitas - gastos

    return {
        "mes": mes,
        "ano": ano,
        "receitas":  round(receitas, 2),
        "gastos":    round(gastos,   2),
        "a_pagar":   round(a_pagar,  2),
        "saldo":     round(saldo,    2),
        "total_transacoes": len(txs),
    }


@router.get("/transacoes")
def get_transacoes(
    tipo:   str | None = None,
    status: str | None = None,
    mes:    int | None = None,
    ano:    int | None = None,
    limit:  int = 50,
    db: Session = Depends(get_db)
):
    """Lista transações com filtros opcionais."""
    if mes is None or ano is None:
        mes, ano = mes_atual()

    q = db.query(Transacao).filter(
        extract('month', Transacao.data) == mes,
        extract('year',  Transacao.data) == ano
    )

    if tipo:
        q = q.filter(Transacao.tipo == tipo)
    if status:
        q = q.filter(Transacao.status == status)

    txs = q.order_by(Transacao.data.desc()).limit(limit).all()

    return [
        {
            "id":          t.id,
            "descricao":   t.descricao,
            "valor":       round(t.valor, 2),
            "tipo":        t.tipo,
            "categoria":   t.categoria,
            "forma_pag":   getattr(t, "forma_pagamento", "PIX"),
            "status":      t.status,
            "data":        t.data.strftime("%d/%m") if t.data else "",
            "data_iso":    t.data.isoformat()        if t.data else "",
        }
        for t in txs
    ]


@router.get("/categorias")
def get_categorias(db: Session = Depends(get_db)):
    """Gastos agrupados por categoria no mês atual."""
    mes, ano = mes_atual()

    rows = (
        db.query(Transacao.categoria, func.sum(Transacao.valor).label("total"))
        .filter(
            Transacao.tipo == "despesa",
            extract('month', Transacao.data) == mes,
            extract('year',  Transacao.data) == ano
        )
        .group_by(Transacao.categoria)
        .order_by(func.sum(Transacao.valor).desc())
        .all()
    )

    total = sum(r.total for r in rows) or 1  # evita divisão por zero

    CAT_ICONS = {
        "alimentação": "🛒", "moradia": "🏠", "transporte": "🚗",
        "lazer": "🎬",       "saúde": "💊",   "educação": "📚",
        "renda": "💰",       "outros": "📦",
    }

    return [
        {
            "categoria":  r.categoria or "Outros",
            "total":      round(r.total, 2),
            "percentual": round(r.total / total * 100, 1),
            "icone":      CAT_ICONS.get((r.categoria or "").lower(), "📦"),
        }
        for r in rows
    ]


@router.get("/historico")
def get_historico(meses: int = 6, db: Session = Depends(get_db)):
    """Receitas x Gastos dos últimos N meses para o gráfico."""
    now = datetime.now()
    resultado = []

    for i in range(meses - 1, -1, -1):
        # calcula mês/ano retrocedendo
        m = (now.month - i - 1) % 12 + 1
        a = now.year - ((now.month - i - 1) // 12 + (1 if (now.month - i - 1) < 0 else 0))

        txs = db.query(Transacao).filter(
            extract('month', Transacao.data) == m,
            extract('year',  Transacao.data) == a
        ).all()

        receitas = sum(t.valor for t in txs if t.tipo == "receita")
        gastos   = sum(t.valor for t in txs if t.tipo == "despesa")

        MESES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun",
                    "Jul","Ago","Set","Out","Nov","Dez"]

        resultado.append({
            "mes":      MESES_PT[m - 1],
            "mes_num":  m,
            "ano":      a,
            "receitas": round(receitas, 2),
            "gastos":   round(gastos,   2),
        })

    return resultado


@router.patch("/transacoes/{tx_id}/pagar")
def marcar_pago(tx_id: int, db: Session = Depends(get_db)):
    """Marca uma transação como paga (usado pelo botão do dashboard)."""
    tx = db.query(Transacao).filter(Transacao.id == tx_id).first()
    if not tx:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    tx.status = "pago"
    db.commit()
    return {"ok": True, "id": tx_id, "status": "pago"}
