# ═══════════════════════════════════════════════════════
# app/routers/ia_features.py
# Funcionalidades IA: Leitura de nota fiscal + Simulador
# ═══════════════════════════════════════════════════════

import os
import base64
import json
import httpx
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from anthropic import Anthropic
from app.database import get_db
from app.models.transacao import Transacao, TipoTransacao, StatusTransacao

router = APIRouter(prefix="/ia", tags=["IA Features"])
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


# ─────────────────────────────────────────────────────
# 📸 LEITURA DE NOTA FISCAL POR IMAGEM
# ─────────────────────────────────────────────────────

@router.post("/nota-fiscal")
async def ler_nota_fiscal(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Recebe uma imagem de nota fiscal, extrai os itens com IA
    e registra as transações automaticamente.
    """
    # Lê e converte a imagem para base64
    image_data = await file.read()
    image_b64  = base64.standard_b64encode(image_data).decode("utf-8")

    # Detecta tipo da imagem
    content_type = file.content_type or "image/jpeg"
    if content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        content_type = "image/jpeg"

    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": content_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": """Analise esta nota fiscal/cupom fiscal/recibo e extraia as informações.

Retorne APENAS um JSON válido neste formato exato (sem texto antes ou depois):
{
  "estabelecimento": "nome do estabelecimento",
  "data": "DD/MM/AAAA ou hoje se não encontrar",
  "total": 0.00,
  "categoria": "Alimentação|Moradia|Transporte|Saúde|Lazer|Educação|Outros",
  "itens": [
    {"descricao": "nome do item", "valor": 0.00, "quantidade": 1}
  ],
  "forma_pagamento": "PIX|Cartão|Dinheiro|Débito|Crédito",
  "resumo": "descrição curta para registrar como transação"
}

Se não conseguir ler a imagem, retorne: {"erro": "Não foi possível ler a nota fiscal"}
Se for um recibo simples sem itens, coloque apenas 1 item com o total."""
                    }
                ],
            }],
        )

        raw = resp.content[0].text.strip()

        # Remove markdown se tiver
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)

        if "erro" in data:
            return JSONResponse({"ok": False, "erro": data["erro"]}, status_code=422)

        # Registra a transação principal no banco
        tx = Transacao(
            descricao   = data.get("resumo") or data.get("estabelecimento", "Nota Fiscal"),
            valor       = float(data.get("total", 0)),
            tipo        = TipoTransacao.despesa,
            categoria   = data.get("categoria", "Outros"),
            metodo      = data.get("forma_pagamento", "PIX"),
            status      = StatusTransacao.pago,
            data        = datetime.now(),
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)

        return {
            "ok":             True,
            "transacao_id":   tx.id,
            "estabelecimento": data.get("estabelecimento"),
            "total":          data.get("total"),
            "categoria":      data.get("categoria"),
            "itens":          data.get("itens", []),
            "forma_pagamento": data.get("forma_pagamento"),
            "mensagem":       f"✅ Nota de {data.get('estabelecimento', 'estabelecimento')} registrada — R$ {data.get('total', 0):.2f}"
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Não consegui interpretar a nota fiscal. Tente uma foto mais nítida.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar: {str(e)}")


# ─────────────────────────────────────────────────────
# 📸 NOTA FISCAL VIA URL DE IMAGEM (para Evolution API/WhatsApp)
# ─────────────────────────────────────────────────────

@router.post("/nota-fiscal-url")
async def ler_nota_fiscal_url(
    image_url: str,
    db: Session = Depends(get_db)
):
    """Baixa imagem de uma URL e processa como nota fiscal."""
    try:
        async with httpx.AsyncClient() as client:
            img_resp = await client.get(image_url, timeout=15)
        image_b64 = base64.standard_b64encode(img_resp.content).decode("utf-8")
        content_type = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
    except Exception:
        raise HTTPException(status_code=400, detail="Não consegui baixar a imagem.")

    # Reutiliza a lógica acima
    fake_file = type("F", (), {"read": lambda s: img_resp.content, "content_type": content_type})()

    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": image_b64}},
                    {"type": "text", "text": """Analise esta nota fiscal e retorne APENAS JSON:
{"estabelecimento":"nome","total":0.00,"categoria":"Alimentação|Moradia|Transporte|Saúde|Lazer|Outros","itens":[{"descricao":"item","valor":0.00}],"forma_pagamento":"PIX","resumo":"descrição curta"}
Se não conseguir: {"erro":"mensagem"}"""}
                ],
            }],
        )
        raw  = resp.content[0].text.strip().strip("```json").strip("```").strip()
        data = json.loads(raw)

        if "erro" in data:
            return {"ok": False, "erro": data["erro"]}

        tx = Transacao(
            descricao = data.get("resumo") or data.get("estabelecimento", "Nota Fiscal"),
            valor     = float(data.get("total", 0)),
            tipo      = TipoTransacao.despesa,
            categoria = data.get("categoria", "Outros"),
            metodo    = data.get("forma_pagamento", "PIX"),
            status    = StatusTransacao.pago,
            data      = datetime.now(),
        )
        db.add(tx); db.commit(); db.refresh(tx)

        return {
            "ok": True,
            "transacao_id": tx.id,
            "estabelecimento": data.get("estabelecimento"),
            "total": data.get("total"),
            "itens": data.get("itens", []),
            "mensagem": f"✅ {data.get('estabelecimento','Nota')} — R$ {data.get('total',0):.2f} registrado!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────
# 🔮 SIMULADOR DE DECISÃO FINANCEIRA
# ─────────────────────────────────────────────────────

@router.post("/simular")
async def simular_decisao(
    descricao: str,
    valor_mensal: float,
    meses: int = 12,
    db: Session = Depends(get_db)
):
    """
    Simula o impacto financeiro de uma decisão de compra/gasto.
    Ex: "comprar um carro" com valor_mensal=1500
    """
    # Busca dados financeiros reais do usuário
    now = datetime.now()
    txs = db.query(Transacao).filter(
        func.strftime('%m', Transacao.data) == f"{now.month:02d}",
        func.strftime('%Y', Transacao.data) == str(now.year)
    ).all()

    if not txs:
        txs = db.query(Transacao).all()

    receitas = sum(t.valor for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "receita")
    gastos   = sum(t.valor for t in txs if str(t.tipo).replace("TipoTransacao.", "") == "despesa")
    saldo    = receitas - gastos

    # Pede análise ao Claude
    prompt = f"""Você é um consultor financeiro do finia analisando uma decisão de compra.

DADOS FINANCEIROS ATUAIS:
- Receitas mensais: R$ {receitas:.2f}
- Gastos mensais: R$ {gastos:.2f}
- Saldo atual: R$ {saldo:.2f}
- Margem disponível: R$ {saldo:.2f}

DECISÃO A ANALISAR:
- Descrição: {descricao}
- Custo mensal: R$ {valor_mensal:.2f}
- Período: {meses} meses
- Custo total: R$ {valor_mensal * meses:.2f}

Retorne APENAS este JSON (sem texto extra):
{{
  "viavel": true|false,
  "novo_saldo_mensal": 0.00,
  "percentual_comprometido": 0.0,
  "impacto": "positivo|negativo|neutro",
  "analise": "2-3 frases diretas sobre a viabilidade",
  "sugestao": "sugestão prática e direta",
  "alerta": "null ou aviso importante se houver risco",
  "economia_necessaria": 0.00,
  "meses_reserva": 0
}}"""

    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw  = resp.content[0].text.strip().strip("```json").strip("```").strip()
        analise = json.loads(raw)
    except Exception:
        # Fallback se Claude falhar
        novo_saldo = saldo - valor_mensal
        analise = {
            "viavel": novo_saldo >= 0,
            "novo_saldo_mensal": round(novo_saldo, 2),
            "percentual_comprometido": round(valor_mensal / receitas * 100, 1) if receitas > 0 else 0,
            "impacto": "negativo" if novo_saldo < 0 else "neutro",
            "analise": f"Este gasto comprometeria R$ {valor_mensal:.2f} do seu orçamento mensal.",
            "sugestao": "Avalie se é possível reduzir outros gastos antes de assumir este compromisso.",
            "alerta": "Saldo ficará negativo!" if novo_saldo < 0 else None,
            "economia_necessaria": max(0, -novo_saldo),
            "meses_reserva": 0,
        }

    return {
        "ok": True,
        "descricao": descricao,
        "valor_mensal": valor_mensal,
        "meses": meses,
        "custo_total": round(valor_mensal * meses, 2),
        "financeiro_atual": {
            "receitas": round(receitas, 2),
            "gastos": round(gastos, 2),
            "saldo": round(saldo, 2),
        },
        "simulacao": analise,
        "projecao_mensal": [
            {
                "mes": i + 1,
                "saldo_acumulado": round(saldo * (i + 1) - valor_mensal * (i + 1), 2)
            }
            for i in range(min(meses, 12))
        ]
    }


# ─────────────────────────────────────────────────────
# 🔮 SIMULADOR VIA TEXTO LIVRE (para chat IA)
# ─────────────────────────────────────────────────────

@router.post("/simular-texto")
async def simular_texto(
    mensagem: str,
    db: Session = Depends(get_db)
):
    """
    Interpreta uma mensagem de texto livre e gera simulação.
    Ex: "se eu comprar um carro de 1500 por mes"
    """
    # Extrai valor e descrição do texto
    extract_resp = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""Extraia do texto a seguir o valor mensal e a descrição da compra/gasto.
Texto: "{mensagem}"
Retorne APENAS JSON: {{"descricao": "nome da compra", "valor_mensal": 0.00, "meses": 12}}
Se não encontrar valor, use 0. Se não encontrar meses, use 12."""
        }],
    )

    try:
        raw = extract_resp.content[0].text.strip().strip("```json").strip("```").strip()
        extracted = json.loads(raw)
    except Exception:
        return {"ok": False, "erro": "Não consegui entender o valor. Tente: 'simular carro de R$ 1.500 por mês'"}

    if extracted.get("valor_mensal", 0) == 0:
        return {"ok": False, "erro": "Não encontrei o valor. Informe o valor mensal, ex: 'comprar carro de R$ 1.500/mês'"}

    # Chama o simulador principal
    return await simular_decisao(
        descricao    = extracted["descricao"],
        valor_mensal = extracted["valor_mensal"],
        meses        = extracted.get("meses", 12),
        db           = db
    )


# ─────────────────────────────────────────────────────
# 💬 PROXY CHAT IA (evita CORS no browser)
# ─────────────────────────────────────────────────────

from pydantic import BaseModel
from typing import List

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    system: str | None = None

@router.post("/chat")
async def chat_proxy(req: ChatRequest):
    """Proxy para o chat IA — evita CORS no browser."""
    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=req.system or "Você é o finia, assistente financeiro pessoal. Seja direto e informal.",
            messages=[{"role": m.role, "content": m.content} for m in req.messages],
        )
        return {"ok": True, "text": resp.content[0].text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
