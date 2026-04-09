# app/routers/assinaturas.py
# Assinaturas recorrentes via Mercado Pago Preapproval
# Substitui o pagamentos.py para cobranças mensais automáticas
#
# Adicione no main.py:
#   from app.routers import assinaturas
#   app.include_router(assinaturas.router)

import os
import hmac
import hashlib
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models.usuario import Usuario

router = APIRouter(prefix="/assinaturas", tags=["Assinaturas"])

MP_TOKEN         = os.getenv("MP_ACCESS_TOKEN", "")
MP_SECRET        = os.getenv("MP_WEBHOOK_SECRET", "finia2026")
BASE_URL         = os.getenv("BASE_URL", "https://financeiro-bot-production-571e.up.railway.app")
EVOLUTION_URL    = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_KEY    = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INST   = os.getenv("EVOLUTION_INSTANCE", "financeiro-bot")

# Planos com preços e IDs do Mercado Pago
PLANOS = {
    "pro": {
        "nome":      "finia Pro",
        "descricao": "Assistente financeiro completo via WhatsApp",
        "preco":     19.90,
        "frequencia": "monthly",
        "frequencia_tipo": "months",
        "frequencia_valor": 1,
    },
    "familia": {
        "nome":      "finia Família",
        "descricao": "finia Pro para até 5 membros da família",
        "preco":     34.90,
        "frequencia": "monthly",
        "frequencia_tipo": "months",
        "frequencia_valor": 1,
    },
}

# ─────────────────────────────────────────────────────
# CRIAR PLANO NO MERCADO PAGO (fazer uma vez)
# ─────────────────────────────────────────────────────

@router.post("/criar-plano-mp")
async def criar_plano_mp(plano: str):
    """
    Cria um plano de assinatura no Mercado Pago.
    Execute UMA VEZ para cada plano e salve os IDs retornados
    como variáveis de ambiente: MP_PLAN_ID_PRO e MP_PLAN_ID_FAMILIA
    """
    if plano not in PLANOS:
        raise HTTPException(status_code=400, detail="Plano inválido")

    p = PLANOS[plano]

    payload = {
        "reason":           p["nome"],
        "auto_recurring": {
            "frequency":      p["frequencia_valor"],
            "frequency_type": p["frequencia_tipo"],
            "transaction_amount": p["preco"],
            "currency_id":    "BRL",
        },
        "back_url":         f"{BASE_URL}/assinaturas/sucesso",
        "payment_methods_allowed": {
            "payment_types": [{"id": "credit_card"}],
        },
        "status": "active",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.mercadopago.com/preapproval_plan",
            json=payload,
            headers={"Authorization": f"Bearer {MP_TOKEN}"},
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Erro MP: {resp.text}")

    data = resp.json()
    return {
        "ok":      True,
        "plan_id": data["id"],
        "plano":   plano,
        "link":    data.get("init_point"),
        "instrucao": f"Salve como variável: MP_PLAN_ID_{plano.upper()}={data['id']}"
    }


# ─────────────────────────────────────────────────────
# GERAR LINK DE ASSINATURA PARA O CLIENTE
# ─────────────────────────────────────────────────────

@router.post("/assinar")
async def criar_assinatura(
    plano: str,
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Gera link de assinatura recorrente para o cliente.
    O MP vai cobrar automaticamente todo mês.
    """
    if plano not in PLANOS:
        raise HTTPException(status_code=400, detail="Plano inválido")

    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Busca o ID do plano salvo como env var
    plan_id_env = f"MP_PLAN_ID_{plano.upper()}"
    plan_id = os.getenv(plan_id_env, "")

    if not plan_id:
        # Se não tem plano criado, cria na hora (fallback)
        p = PLANOS[plano]
        payload_plano = {
            "reason": p["nome"],
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": p["preco"],
                "currency_id": "BRL",
            },
            "back_url": f"{BASE_URL}/assinaturas/sucesso?usuario_id={usuario_id}&plano={plano}",
            "status": "active",
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.mercadopago.com/preapproval_plan",
                json=payload_plano,
                headers={"Authorization": f"Bearer {MP_TOKEN}"},
            )
        if r.status_code in (200, 201):
            plan_id = r.json()["id"]

    p = PLANOS[plano]
    payload = {
        "preapproval_plan_id": plan_id,
        "reason":              p["nome"],
        "payer_email":         user.email or "",
        "external_reference":  f"{usuario_id}:{plano}",
        "back_url":            f"{BASE_URL}/assinaturas/sucesso?usuario_id={usuario_id}&plano={plano}",
        "auto_recurring": {
            "frequency":           1,
            "frequency_type":      "months",
            "transaction_amount":  p["preco"],
            "currency_id":         "BRL",
            "start_date":          datetime.utcnow().isoformat() + "Z",
            "end_date":            (datetime.utcnow() + timedelta(days=3650)).isoformat() + "Z",
        },
        "status": "pending",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.mercadopago.com/preapproval",
            json=payload,
            headers={"Authorization": f"Bearer {MP_TOKEN}"},
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Erro MP: {resp.text}")

    data = resp.json()

    return {
        "ok":                True,
        "subscription_id":   data["id"],
        "link":              data["init_point"],
        "plano":             plano,
        "preco":             p["preco"],
    }


# ─────────────────────────────────────────────────────
# WEBHOOK MERCADO PAGO — recebe eventos automáticos
# ─────────────────────────────────────────────────────

@router.post("/webhook")
async def webhook_mp(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(None),
):
    """Recebe notificações automáticas do Mercado Pago."""
    body = await request.body()

    # Valida assinatura
    if MP_SECRET and x_signature:
        expected = hmac.new(MP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        sig_val = x_signature.split("=")[-1] if "=" in x_signature else x_signature
        if not hmac.compare_digest(expected, sig_val):
            raise HTTPException(status_code=401, detail="Assinatura inválida")

    data = await request.json()
    tipo = data.get("type", "")
    obj_id = str(data.get("data", {}).get("id", ""))

    if tipo == "subscription_preapproval" and obj_id:
        await processar_assinatura(obj_id, db)
    elif tipo == "subscription_authorized_payment" and obj_id:
        await processar_pagamento_recorrente(obj_id, db)

    return {"ok": True}


async def processar_assinatura(sub_id: str, db: Session):
    """Ativa, renova ou cancela plano baseado no status da assinatura."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.mercadopago.com/preapproval/{sub_id}",
            headers={"Authorization": f"Bearer {MP_TOKEN}"},
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
        user.mp_payer_id         = str(sub.get("payer_id", ""))
        db.commit()
        await enviar_wpp(user.telefone, f"✅ Assinatura finia {plano.capitalize()} ativa! Próxima cobrança em {(datetime.now() + timedelta(days=30)).strftime('%d/%m/%Y')}. Dashboard: {BASE_URL}")

    elif status in ("cancelled", "paused"):
        user.plano_ativo = False
        db.commit()
        await enviar_wpp(user.telefone, f"⚠️ Sua assinatura finia foi {'cancelada' if status == 'cancelled' else 'pausada'}. Para reativar acesse: {BASE_URL}/landing.html")


async def processar_pagamento_recorrente(pag_id: str, db: Session):
    """Processa pagamento mensal recorrente — renova o plano."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.mercadopago.com/authorized_payments/{pag_id}",
            headers={"Authorization": f"Bearer {MP_TOKEN}"},
        )

    if resp.status_code != 200:
        return

    pag    = resp.json()
    sub_id = pag.get("preapproval_id")
    status = pag.get("status")

    if status != "approved" or not sub_id:
        return

    user = db.query(Usuario).filter(Usuario.mp_subscription_id == sub_id).first()
    if not user:
        return

    # Renova por mais 30 dias
    user.plano_ativo  = True
    user.plano_expira = datetime.utcnow() + timedelta(days=30)
    db.commit()

    valor = pag.get("transaction_amount", 0)
    await enviar_wpp(
        user.telefone,
        f"✅ Pagamento de R$ {valor:.2f} confirmado!\nSua assinatura finia {user.plano.capitalize()} foi renovada até {user.plano_expira.strftime('%d/%m/%Y')}. 💚"
    )


# ─────────────────────────────────────────────────────
# CANCELAR ASSINATURA
# ─────────────────────────────────────────────────────

@router.post("/cancelar")
async def cancelar_assinatura(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """Cancela a assinatura recorrente do usuário."""
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if not user.mp_subscription_id:
        raise HTTPException(status_code=400, detail="Nenhuma assinatura ativa encontrada")

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"https://api.mercadopago.com/preapproval/{user.mp_subscription_id}",
            json={"status": "cancelled"},
            headers={"Authorization": f"Bearer {MP_TOKEN}"},
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Erro ao cancelar no Mercado Pago")

    user.plano_ativo = False
    db.commit()

    await enviar_wpp(
        user.telefone,
        f"😢 Sua assinatura finia foi cancelada.\nVocê continua com acesso até {user.plano_expira.strftime('%d/%m/%Y') if user.plano_expira else 'hoje'}.\n\nSentiremos sua falta! Se mudar de ideia: {BASE_URL}/landing.html"
    )

    return {"ok": True, "cancelado": True}


# ─────────────────────────────────────────────────────
# PAUSAR / REATIVAR ASSINATURA
# ─────────────────────────────────────────────────────

@router.post("/pausar")
async def pausar_assinatura(usuario_id: int, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user or not user.mp_subscription_id:
        raise HTTPException(status_code=400, detail="Sem assinatura ativa")

    async with httpx.AsyncClient() as client:
        await client.put(
            f"https://api.mercadopago.com/preapproval/{user.mp_subscription_id}",
            json={"status": "paused"},
            headers={"Authorization": f"Bearer {MP_TOKEN}"},
        )

    user.plano_ativo = False
    db.commit()
    return {"ok": True, "status": "paused"}


@router.post("/reativar")
async def reativar_assinatura(usuario_id: int, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user or not user.mp_subscription_id:
        raise HTTPException(status_code=400, detail="Sem assinatura encontrada")

    async with httpx.AsyncClient() as client:
        await client.put(
            f"https://api.mercadopago.com/preapproval/{user.mp_subscription_id}",
            json={"status": "authorized"},
            headers={"Authorization": f"Bearer {MP_TOKEN}"},
        )

    user.plano_ativo  = True
    user.plano_expira = datetime.utcnow() + timedelta(days=30)
    db.commit()
    return {"ok": True, "status": "authorized"}


# ─────────────────────────────────────────────────────
# BUSCAR STATUS DA ASSINATURA
# ─────────────────────────────────────────────────────

@router.get("/status/{usuario_id}")
async def status_assinatura(usuario_id: int, db: Session = Depends(get_db)):
    """Retorna status completo da assinatura para o dashboard."""
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    resultado = {
        "plano":          user.plano,
        "ativo":          user.plano_ativo,
        "expira":         user.plano_expira.isoformat() if user.plano_expira else None,
        "subscription_id": user.mp_subscription_id,
        "historico":      [],
    }

    # Busca histórico de pagamentos no MP se tiver subscription_id
    if user.mp_subscription_id:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.mercadopago.com/preapproval/{user.mp_subscription_id}",
                    headers={"Authorization": f"Bearer {MP_TOKEN}"},
                    timeout=5,
                )
            if resp.status_code == 200:
                sub = resp.json()
                resultado["mp_status"]        = sub.get("status")
                resultado["proximo_debito"]   = sub.get("next_payment_date")
                resultado["valor_mensal"]     = sub.get("auto_recurring", {}).get("transaction_amount")
        except Exception:
            pass

    return resultado


# ─────────────────────────────────────────────────────
# PÁGINA DE SUCESSO
# ─────────────────────────────────────────────────────

@router.get("/sucesso")
async def pagamento_sucesso(
    usuario_id: int | None = None,
    plano: str | None = None,
    db: Session = Depends(get_db)
):
    if usuario_id and plano:
        user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        if user:
            user.plano        = plano
            user.plano_ativo  = True
            user.plano_expira = datetime.utcnow() + timedelta(days=30)
            db.commit()

    html = f"""<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>finia — Assinatura ativa!</title>
<style>
  body{{font-family:'Plus Jakarta Sans',sans-serif;background:#f0fdf4;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
  .box{{background:white;border-radius:20px;padding:48px;text-align:center;max-width:420px;box-shadow:0 8px 32px rgba(0,0,0,0.08)}}
  h1{{color:#111827;font-size:1.4rem;margin-bottom:8px}}
  p{{color:#64748b;margin-bottom:24px;line-height:1.6}}
  .badge{{background:#dcfce7;color:#16a34a;padding:8px 20px;border-radius:20px;font-weight:700;font-size:0.9rem;display:inline-block;margin-bottom:20px}}
  a{{background:#111827;color:white;padding:12px 28px;border-radius:12px;text-decoration:none;font-weight:700;font-size:0.9rem;display:inline-block}}
  a:hover{{background:#1e293b}}
</style></head><body>
<div class="box">
  <div style="font-size:3rem;margin-bottom:16px">🎉</div>
  <div class="badge">✓ Assinatura ativa!</div>
  <h1>Bem-vindo ao finia {(plano or '').capitalize()}!</h1>
  <p>Sua assinatura recorrente foi ativada com sucesso. O Mercado Pago vai cobrar automaticamente todo mês. Você receberá confirmação pelo WhatsApp.</p>
  <a href="/">Acessar meu dashboard</a>
</div></body></html>"""
    return HTMLResponse(html)


# ─────────────────────────────────────────────────────
# HELPER — ENVIAR WHATSAPP
# ─────────────────────────────────────────────────────

async def enviar_wpp(telefone: str, texto: str):
    if not EVOLUTION_URL or not telefone:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INST}",
                json={"number": telefone, "textMessage": {"text": texto}},
                headers={"apikey": EVOLUTION_KEY},
            )
    except Exception:
        pass
