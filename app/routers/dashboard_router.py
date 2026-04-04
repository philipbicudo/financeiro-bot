from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database import get_db
from app.models.transacao import Transacao

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def mes_atual():
    now = datetime.now()
    return now.month, now.year

@router.get("/resumo")
def get_resumo(db: Session = Depends(get_db)):
    mes, ano = mes_atual()
    mes_str = f"{mes:02d}"
    ano_str = str(ano)
    txs = db.query(Transacao).filter(
        func.strftime('%m', Transacao.data) == mes_str,
        func.strftime('%Y', Transacao.data) == ano_str
    ).all()
    receitas = sum(t.valor for t in txs if str(t.tipo) == "receita")
    gastos   = sum(t.valor for t in txs if str(t.tipo) == "despesa")
    a_pagar  = sum(t.valor for t in txs if str(t.tipo) == "despesa" and str(t.status) in ("pendente", "nao_pago", "StatusTransacao.nao_pago"))
    saldo    = receitas - gastos
    return {
        "mes": mes, "ano": ano,
        "receitas": round(receitas, 2),
        "gastos":   round(gastos,   2),
        "a_pagar":  round(a_pagar,  2),
        "saldo":    round(saldo,    2),
        "total_transacoes": len(txs),
    }

@router.get("/transacoes")
def get_transacoes(
    tipo: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    mes, ano = mes_atual()
    mes_str = f"{mes:02d}"
    ano_str = str(ano)
    q = db.query(Transacao).filter(
        func.strftime('%m', Transacao.data) == mes_str,
        func.strftime('%Y', Transacao.data) == ano_str
    )
    if tipo:   q = q.filter(Transacao.tipo == tipo)
    if status: q = q.filter(Transacao.status == status)
    txs = q.order_by(Transacao.data.desc()).limit(limit).all()
    return [
        {
            "id":        t.id,
            "descricao": t.descricao,
            "valor":     round(t.valor, 2),
            "tipo":      str(t.tipo).replace("TipoTransacao.", ""),
            "categoria": t.categoria,
            "forma_pag": t.metodo or "PIX",
            "status":    str(t.status).replace("StatusTransacao.", ""),
            "data":      t.data.strftime("%d/%m") if t.data else "",
        }
        for t in txs
    ]

@router.get("/categorias")
def get_categorias(db: Session = Depends(get_db)):
    mes, ano = mes_atual()
    mes_str = f"{mes:02d}"
    ano_str = str(ano)
    txs = db.query(Transacao).filter(
        func.strftime('%m', Transacao.data) == mes_str,
        func.strftime('%Y', Transacao.data) == ano_str,
        Transacao.tipo == "despesa"
    ).all()
    cats = {}
    for t in txs:
        cat = t.categoria or "Outros"
        cats[cat] = cats.get(cat, 0) + t.valor
    total = sum(cats.values()) or 1
    CAT_ICONS = {
        "alimentação":"🛒","moradia":"🏠","transporte":"🚗","lazer":"🎬",
        "saúde":"💊","educação":"📚","renda":"💰","outros":"📦","casa":"🏠",
    }
    return [
        {
            "categoria":  cat,
            "total":      round(val, 2),
            "percentual": round(val / total * 100, 1),
            "icone":      CAT_ICONS.get(cat.lower(), "📦"),
        }
        for cat, val in sorted(cats.items(), key=lambda x: x[1], reverse=True)
    ]

@router.get("/historico")
def get_historico(meses: int = 6, db: Session = Depends(get_db)):
    now = datetime.now()
    resultado = []
    MESES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    for i in range(meses - 1, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        a = now.year - ((now.month - i - 1) // 12 + (1 if (now.month - i - 1) < 0 else 0))
        txs = db.query(Transacao).filter(
            func.strftime('%m', Transacao.data) == f"{m:02d}",
            func.strftime('%Y', Transacao.data) == str(a)
        ).all()
        resultado.append({
            "mes":      MESES_PT[m - 1],
            "receitas": round(sum(t.valor for t in txs if str(t.tipo) == "receita"), 2),
            "gastos":   round(sum(t.valor for t in txs if str(t.tipo) == "despesa"), 2),
        })
    return resultado

@router.patch("/transacoes/{tx_id}/pagar")
def marcar_pago(tx_id: int, db: Session = Depends(get_db)):
    from app.models.transacao import StatusTransacao
    from fastapi import HTTPException
    tx = db.query(Transacao).filter(Transacao.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    tx.status = StatusTransacao.pago
    db.commit()
    return {"ok": True, "id": tx_id, "status": "pago"}
