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

def filtrar_mes(txs, mes, ano):
    """Filtra transações pelo mês/ano considerando múltiplos formatos de data."""
    resultado = []
    mes_str = f"{mes:02d}"
    ano_str = str(ano)
    for t in txs:
        if not t.data:
            continue
        # Formato completo datetime
        try:
            if t.data.month == mes and t.data.year == ano:
                resultado.append(t)
        except Exception:
            pass
    return resultado

@router.get("/resumo")
def get_resumo(db: Session = Depends(get_db)):
    mes, ano = mes_atual()
    todas = db.query(Transacao).all()
    txs = filtrar_mes(todas, mes, ano)

    # Se não encontrar nada no mês atual, usa todas
    if not txs:
        txs = todas

    receitas = sum(t.valor for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "receita")
    gastos   = sum(t.valor for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "despesa")
    a_pagar  = sum(t.valor for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "despesa" and str(t.status).replace("StatusTransacao.", "") in ("pendente", "nao_pago"))
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
    todas = db.query(Transacao).order_by(Transacao.data.desc()).all()
    mes, ano = mes_atual()
    txs = filtrar_mes(todas, mes, ano)
    if not txs:
        txs = todas

    if tipo:
        txs = [t for t in txs if str(t.tipo).replace("TipoTransacao.", "") == tipo]
    if status:
        txs = [t for t in txs if str(t.status).replace("StatusTransacao.", "") == status]

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
        for t in txs[:limit]
    ]

@router.get("/categorias")
def get_categorias(db: Session = Depends(get_db)):
    mes, ano = mes_atual()
    todas = db.query(Transacao).all()
    txs = filtrar_mes(todas, mes, ano)
    if not txs:
        txs = todas

    txs = [t for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "despesa"]
    cats = {}
    for t in txs:
        cat = t.categoria or "Outros"
        cats[cat] = cats.get(cat, 0) + t.valor

    total = sum(cats.values()) or 1
    CAT_ICONS = {
        "alimentação":"🛒","moradia":"🏠","transporte":"🚗","lazer":"🎬",
        "saúde":"💊","educação":"📚","salário":"💰","outros":"📦","casa":"🏠",
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
    todas = db.query(Transacao).all()
    now = datetime.now()
    resultado = []
    MESES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    for i in range(meses - 1, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        a = now.year - ((now.month - i - 1) // 12 + (1 if (now.month - i - 1) < 0 else 0))
        txs = filtrar_mes(todas, m, a)
        resultado.append({
            "mes":      MESES_PT[m - 1],
            "receitas": round(sum(t.valor for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "receita"), 2),
            "gastos":   round(sum(t.valor for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "despesa"), 2),
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
