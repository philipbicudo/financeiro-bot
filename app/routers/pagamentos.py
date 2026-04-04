# ═══════════════════════════════════════════════════════
# app/routers/pagamentos.py
# Integração completa com Mercado Pago
# ═══════════════════════════════════════════════════════
#
# Variáveis de ambiente necessárias no Railway:
#   MP_ACCESS_TOKEN  = seu token do Mercado Pago (produção)
#   MP_WEBHOOK_SECRET = string secreta para validar webhooks
#   BASE_URL         = https://financeiro-bot-production-571e.up.railway.app

import os
import hmac
import hashlib
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models.usuario import Usuario

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])

MP_ACCESS_TOKEN   = os.getenv("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
BASE_URL          = os.getenv("BASE_URL", "https://financeiro-bot-production-571e.up.railway.app")

PLANOS = {
    "pro": {
        "nome":      "finia Pro",
        "descricao": "Acesso completo ao finia — bot WhatsApp + dashboard web",
        "preco":     19.90,
        "reason":    "finia Pro — Assinatura Mensal",
    },
    "familia": {
        "nome":      "finia Família",
        "descricao": "finia para até 5 membros da família",
        "preco":     34.90,
        "reason":    "finia Família — Assinatura Mensal",
    },
}


# ─────────────────────────────────
# Gerar link de pagamento (Preference)
# ─────────────────────────────────
@router.post("/criar-link")
async def criar_link_pagamento(
    plano: str,
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """Gera um link de pagamento do Mercado Pago para o plano escolhido."""
    if plano not in PLANOS:
        raise HTTPException(status_code=400, detail="Plano inválido")

    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    p = PLANOS[plano]

    payload = {
        "items": [{
            "title":       p["nome"],
            "description": p["descricao"],
            "quantity":    1,
            "unit_price":  p["preco"],
            "currency_id": "BRL",
        }],
        "payer": {
            "name":  user.nome,
            "phone": {"number": user.telefone},
        },
        "back_urls": {
            "success": f"{BASE_URL}/pagamentos/sucesso?usuario_id={usuario_id}&plano={plano}",
            "failure": f"{BASE_URL}/pagamentos/falha",
            "pending": f"{BASE_URL}/pagamentos/pendente",
        },
        "auto_return":        "approved",
        "external_reference": f"{usuario_id}:{plano}",
        "notification_url":   f"{BASE_URL}/pagamentos/webhook",
        "statement_descriptor": "FINIA APP",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.mercadopago.com/checkout/preferences",
            json=payload,
            headers={
                "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
                "Content-Type":  "application/json",
            },
        )

    if resp.status_code != 201:
        raise HTTPException(status_code=502, detail=f"Erro MP: {resp.text}")

    data = resp.json()
    return {
        "link":        data["init_point"],       # link para produção
        "link_sandbox": data["sandbox_init_point"],  # link para testes
        "id":          data["id"],
    }


# ─────────────────────────────────
# Webhook do Mercado Pago
# ─────────────────────────────────
@router.post("/webhook")
async def webhook_mercadopago(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(None),
):
    """Recebe notificações do Mercado Pago e ativa/cancela planos."""
    body = await request.body()

    # Valida assinatura (segurança)
    if MP_WEBHOOK_SECRET and x_signature:
        expected = hmac.new(
            MP_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, x_signature.split("=")[-1]):
            raise HTTPException(status_code=401, detail="Assinatura inválida")

    data = await request.json()
    evento = data.get("type", "")
    obj_id = data.get("data", {}).get("id")

    if evento == "payment" and obj_id:
        await processar_pagamento(str(obj_id), db)

    elif evento in ("subscription_preapproval", "subscription_authorized_payment"):
        await processar_assinatura(str(obj_id), db)

    return {"ok": True}


async def processar_pagamento(payment_id: str, db: Session):
    """Busca detalhes do pagamento na API do MP e libera acesso."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"},
        )

    if resp.status_code != 200:
        return

    p = resp.json()
    status = p.get("status")
    ref    = p.get("external_reference", "")  # "usuario_id:plano"

    if status != "approved" or ":" not in ref:
        return

    usuario_id, plano = ref.split(":", 1)
    user = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
    if not user:
        return

    user.plano        = plano
    user.plano_ativo  = True
    user.plano_expira = datetime.utcnow() + timedelta(days=30)
    user.mp_payer_id  = str(p.get("payer", {}).get("id", ""))
    db.commit()

    # Envia mensagem de boas-vindas via WhatsApp
    await enviar_boas_vindas(user.telefone, plano, user.nome)


async def processar_assinatura(sub_id: str, db: Session):
    """Processa eventos de assinatura recorrente."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.mercadopago.com/preapproval/{sub_id}",
            headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"},
        )

    if resp.status_code != 200:
        return

    sub    = resp.json()
    status = sub.get("status")
    ref    = sub.get("external_reference", "")

    if ":" not in ref:
        return

    usuario_id, plano = ref.split(":", 1)
    user = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
    if not user:
        return

    if status == "authorized":
        user.plano               = plano
        user.plano_ativo         = True
        user.plano_expira        = datetime.utcnow() + timedelta(days=30)
        user.mp_subscription_id  = sub_id
    elif status in ("cancelled", "paused"):
        user.plano_ativo = False

    db.commit()


# ─────────────────────────────────
# Páginas de retorno
# ─────────────────────────────────
@router.get("/sucesso")
async def pagamento_sucesso(usuario_id: int, plano: str):
    """Página de retorno após pagamento aprovado."""
    from fastapi.responses import HTMLResponse
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>finia — Pagamento aprovado!</title>
    <style>
      body {{ font-family: sans-serif; display:flex; align-items:center; justify-content:center;
              min-height:100vh; background:#f0fdf4; margin:0; }}
      .box {{ text-align:center; padding:48px; background:white; border-radius:20px;
              box-shadow:0 4px 24px rgba(0,0,0,0.08); max-width:400px; }}
      h1 {{ color:#111827; font-size:1.5rem; margin-bottom:8px; }}
      p  {{ color:#64748b; margin-bottom:24px; }}
      .badge {{ background:#dcfce7; color:#16a34a; padding:8px 20px; border-radius:20px;
                font-weight:700; font-size:0.9rem; display:inline-block; margin-bottom:20px; }}
      a {{ background:#111827; color:white; padding:12px 28px; border-radius:10px;
           text-decoration:none; font-weight:700; font-size:0.9rem; }}
    </style></head><body>
    <div class="box">
      <div style="font-size:3rem; margin-bottom:16px">🎉</div>
      <div class="badge">✓ Pagamento aprovado</div>
      <h1>Bem-vindo ao finia {plano.capitalize()}!</h1>
      <p>Seu acesso foi liberado. Você já pode usar o bot no WhatsApp e o dashboard web.</p>
      <a href="/">Ir para o dashboard</a>
    </div>
    </body></html>
    """
    return HTMLResponse(html)


@router.get("/falha")
async def pagamento_falha():
    from fastapi.responses import HTMLResponse
    return HTMLResponse("<h2>Pagamento não aprovado. Tente novamente.</h2>")


# ─────────────────────────────────
# Enviar boas-vindas pelo WhatsApp
# ─────────────────────────────────
async def enviar_boas_vindas(telefone: str, plano: str, nome: str):
    """Envia mensagem de boas-vindas via Evolution API após pagamento."""
    EVOLUTION_URL  = os.getenv("EVOLUTION_API_URL", "")
    EVOLUTION_KEY  = os.getenv("EVOLUTION_API_KEY", "")
    EVOLUTION_INST = os.getenv("EVOLUTION_INSTANCE", "financeiro-bot")

    if not EVOLUTION_URL:
        return

    preco = "R$ 19,90" if plano == "pro" else "R$ 34,90"
    msg = (
        f"🎉 *Olá {nome}! Bem-vindo ao finia {plano.capitalize()}!*\n\n"
        f"✅ Seu plano {plano.capitalize()} ({preco}/mês) está ativo.\n\n"
        f"Pode começar a usar agora:\n"
        f"• Mande 'gastei X em Y' para registrar um gasto\n"
        f"• Mande 'recebi X de Y' para registrar uma receita\n"
        f"• Mande 'resumo' para ver o balanço do mês\n\n"
        f"Dashboard: {BASE_URL}\n\n"
        f"Qualquer dúvida é só mandar mensagem aqui! 💚"
    )

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INST}",
                json={"number": telefone, "textMessage": {"text": msg}},
                headers={"apikey": EVOLUTION_KEY},
                timeout=10,
            )
    except Exception:
        pass
