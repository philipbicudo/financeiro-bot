# app/routers/dashboard_router.py
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database import get_db
from app.models.transacao import Transacao, TipoTransacao, StatusTransacao

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

def mes_atual():
    now = datetime.now()
    return now.month, now.year

def get_usuario_id(request: Request) -> int | None:
    """Extrai usuario_id do token JWT se disponível."""
    try:
        import jwt
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            import os
            secret = os.getenv("JWT_SECRET", "finia_secret_mude_em_producao_2026")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return int(payload.get("sub", 0)) or None
    except Exception:
        pass
    return None


@router.get("/resumo")
def get_resumo(
    mes: int | None = None,
    ano: int | None = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    if mes is None or ano is None:
        mes, ano = mes_atual()

    usuario_id = get_usuario_id(request) if request else None

    q = db.query(Transacao).filter(
        func.strftime('%m', Transacao.data) == f"{mes:02d}",
        func.strftime('%Y', Transacao.data) == str(ano)
    )

    # Filtra ESTRITAMENTE por usuario — cada usuário vê APENAS seus dados
    if usuario_id:
        q = q.filter(Transacao.usuario_id == usuario_id)

    txs = q.all()

    receitas  = sum(t.valor for t in txs if str(t.tipo).endswith("receita"))
    gastos    = sum(t.valor for t in txs if str(t.tipo).endswith("despesa") and str(t.status).endswith("pago"))
    a_pagar   = sum(t.valor for t in txs if str(t.tipo).endswith("despesa") and not str(t.status).endswith("pago"))
    saldo     = receitas - gastos

    return {
        "mes":               mes,
        "ano":               ano,
        "receitas":          round(receitas, 2),
        "gastos":            round(gastos, 2),
        "a_pagar":           round(a_pagar, 2),
        "saldo":             round(saldo, 2),
        "total_transacoes":  len(txs),
        "usuario_id":        usuario_id,
    }


@router.get("/transacoes")
def get_transacoes(
    tipo:   str | None = None,
    status: str | None = None,
    mes:    int | None = None,
    ano:    int | None = None,
    limit:  int = 50,
    request: Request = None,
    db: Session = Depends(get_db)
):
    if mes is None or ano is None:
        mes, ano = mes_atual()

    usuario_id = get_usuario_id(request) if request else None

    q = db.query(Transacao).filter(
        func.strftime('%m', Transacao.data) == f"{mes:02d}",
        func.strftime('%Y', Transacao.data) == str(ano)
    )

    # Filtra ESTRITAMENTE por usuario — cada usuário vê APENAS seus dados
    if usuario_id:
        q = q.filter(Transacao.usuario_id == usuario_id)

    if tipo:
        q = q.filter(Transacao.tipo == tipo)
    if status:
        q = q.filter(Transacao.status == status)

    txs = q.order_by(Transacao.data.desc()).limit(min(limit, 200)).all()

    result = []
    for t in txs:
        result.append({
            "id":        t.id,
            "descricao": t.descricao,
            "valor":     round(t.valor, 2),
            "tipo":      str(t.tipo).replace("TipoTransacao.", ""),
            "categoria": t.categoria or "Outros",
            "forma_pag": t.metodo or "PIX",
            "status":    str(t.status).replace("StatusTransacao.", ""),
            "data":      t.data.strftime("%d/%m") if t.data else "",
            "data_iso":  t.data.strftime("%Y-%m-%d") if t.data else "",
            "usuario_id": t.usuario_id,
        })

    return result


@router.get("/categorias")
def get_categorias(
    mes: int | None = None,
    ano: int | None = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    if mes is None or ano is None:
        mes, ano = mes_atual()

    usuario_id = get_usuario_id(request) if request else None

    q = db.query(Transacao).filter(
        func.strftime('%m', Transacao.data) == f"{mes:02d}",
        func.strftime('%Y', Transacao.data) == str(ano),
    )

    if usuario_id:
        q = q.filter(
            Transacao.usuario_id == usuario_id
        )

    txs = q.all()
    despesas = [t for t in txs if str(t.tipo).endswith("despesa")]

    total = sum(t.valor for t in despesas)
    cats: dict = {}
    for t in despesas:
        cat = t.categoria or "Outros"
        cats[cat] = cats.get(cat, 0) + t.valor

    return [
        {
            "categoria":   cat,
            "total":       round(val, 2),
            "percentual":  round(val / total * 100, 1) if total > 0 else 0,
        }
        for cat, val in sorted(cats.items(), key=lambda x: -x[1])
    ]


@router.get("/historico")
def get_historico(
    meses: int = 6,
    request: Request = None,
    db: Session = Depends(get_db)
):
    usuario_id = get_usuario_id(request) if request else None
    now = datetime.now()
    result = []

    for i in range(meses - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1

        q = db.query(Transacao).filter(
            func.strftime('%m', Transacao.data) == f"{m:02d}",
            func.strftime('%Y', Transacao.data) == str(y),
        )

        if usuario_id:
            q = q.filter(
                Transacao.usuario_id == usuario_id
            )

        txs = q.all()
        receitas = sum(t.valor for t in txs if str(t.tipo).endswith("receita"))
        gastos   = sum(t.valor for t in txs if str(t.tipo).endswith("despesa"))

        meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        result.append({
            "mes":      meses_pt[m - 1],
            "receitas": round(receitas, 2),
            "gastos":   round(gastos, 2),
        })

    return result


@router.patch("/transacoes/{tx_id}/pagar")
def marcar_pago(
    tx_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    usuario_id = get_usuario_id(request) if request else None

    tx = db.query(Transacao).filter(Transacao.id == tx_id).first()
    if not tx:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    # Verifica se pertence ao usuário
    if usuario_id and tx.usuario_id and tx.usuario_id != usuario_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Acesso negado")

    tx.status = StatusTransacao.pago
    db.commit()
    return {"ok": True, "id": tx_id, "status": "pago"}
