from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from datetime import datetime
from collections import defaultdict

from app.database import get_db
from app.models.transacao import Transacao, TipoTransacao, StatusTransacao
from app.schemas.transacao import ResumoMensal

router = APIRouter()

MESES = [
    "", "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
]

@router.get("/", response_model=ResumoMensal)
def resumo_mensal(
    mes : int = Query(default=datetime.now().month, ge=1, le=12),
    ano : int = Query(default=datetime.now().year),
    db  : Session = Depends(get_db)
):
    transacoes = (
        db.query(Transacao)
        .filter(
            extract("month", Transacao.data) == mes,
            extract("year",  Transacao.data) == ano,
        )
        .all()
    )

    total_receitas    = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.receita)
    total_despesas    = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.despesa)
    receitas_pagas    = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.receita  and t.status == StatusTransacao.pago)
    receitas_a_receber= sum(t.valor for t in transacoes if t.tipo == TipoTransacao.receita  and t.status == StatusTransacao.nao_pago)
    despesas_pagas    = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.despesa  and t.status == StatusTransacao.pago)
    despesas_a_pagar  = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.despesa  and t.status == StatusTransacao.nao_pago)

    # Agrupa despesas por categoria
    por_categoria = defaultdict(float)
    for t in transacoes:
        if t.tipo == TipoTransacao.despesa:
            por_categoria[t.categoria] += t.valor

    # Calcula percentual de cada categoria
    categorias_formatadas = {
        cat: {
            "valor": round(val, 2),
            "percentual": round((val / total_despesas * 100), 2) if total_despesas > 0 else 0
        }
        for cat, val in sorted(por_categoria.items(), key=lambda x: -x[1])
    }

    return ResumoMensal(
        mes               = MESES[mes],
        ano               = ano,
        total_receitas    = round(total_receitas, 2),
        total_despesas    = round(total_despesas, 2),
        saldo             = round(total_receitas - total_despesas, 2),
        receitas_pagas    = round(receitas_pagas, 2),
        receitas_a_receber= round(receitas_a_receber, 2),
        despesas_pagas    = round(despesas_pagas, 2),
        despesas_a_pagar  = round(despesas_a_pagar, 2),
        por_categoria     = categorias_formatadas,
    )

@router.get("/texto")
def resumo_em_texto(
    mes : int = Query(default=datetime.now().month, ge=1, le=12),
    ano : int = Query(default=datetime.now().year),
    db  : Session = Depends(get_db)
):
    """Retorna o resumo formatado como texto — usado pelo WhatsApp bot"""
    r = resumo_mensal(mes=mes, ano=ano, db=db)

    categorias_txt = "\n".join(
        f"  {cat} → R$ {dados['valor']:.2f} ({dados['percentual']}%)"
        for cat, dados in r.por_categoria.items()
    )

    texto = f"""📊 *Resumo Financeiro - {r.mes}/{r.ano}*

🏦 *Seu Saldo*
Disponível: R$ {r.saldo:.2f}

💰 *Receitas*
Recebido: R$ {r.receitas_pagas:.2f}
A receber: R$ {r.receitas_a_receber:.2f}
Total: R$ {r.total_receitas:.2f}

💸 *Despesas*
Pago: R$ {r.despesas_pagas:.2f}
A pagar: R$ {r.despesas_a_pagar:.2f}
Total: R$ {r.total_despesas:.2f}

📂 *Por categoria:*
{categorias_txt if categorias_txt else "  Nenhuma despesa registrada"}"""

    return {"texto": texto}
