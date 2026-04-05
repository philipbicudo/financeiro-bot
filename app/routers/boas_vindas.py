# app/routers/boas_vindas.py
# Mensagens de boas-vindas ao assinar + upgrade de plano
# Adicione no main.py: from app.routers import boas_vindas
#                      app.include_router(boas_vindas.router)

import os
import httpx
from fastapi import APIRouter, BackgroundTasks
from datetime import datetime

router = APIRouter(prefix="/boas-vindas", tags=["Boas-vindas"])

EVOLUTION_URL   = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_KEY   = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INST  = os.getenv("EVOLUTION_INSTANCE", "financeiro-bot")
BASE_URL        = os.getenv("BASE_URL", "https://financeiro-bot-production-571e.up.railway.app")

PLANOS = {
    "gratis": {
        "nome":  "Grátis",
        "preco": "R$ 0",
        "limite": "50 transações/mês",
    },
    "pro": {
        "nome":  "Pro",
        "preco": "R$ 19,90/mês",
        "limite": "Transações ilimitadas",
    },
    "familia": {
        "nome":  "Família",
        "preco": "R$ 34,90/mês",
        "limite": "Até 5 membros",
    },
}

# ─────────────────────────────────────────────────────
# MENSAGENS DE BOAS-VINDAS POR PLANO
# ─────────────────────────────────────────────────────

def msg_gratis(nome: str) -> str:
    return f"""✨ *Olá, {nome}! Seja bem-vindo(a) ao finia!* ✨

Você acaba de ativar sua conta *gratuita* e já pode começar a organizar suas finanças agora mesmo! 🎉

━━━━━━━━━━━━━━━━
📋 *O que você pode fazer:*
• Registrar até *50 transações por mês*
• Consultar seu resumo financeiro
• Pedir análises para a IA

━━━━━━━━━━━━━━━━
💬 *Como registrar um gasto:*
Basta mandar uma mensagem como:
→ "gastei 50 no mercado"
→ "paguei 180 de luz"
→ "recebi salário de 3000"

📊 *Para ver seu resumo:*
Mande "resumo" a qualquer hora

━━━━━━━━━━━━━━━━
🚀 *Quer mais recursos?*
Assine o *finia Pro* por R$ 19,90/mês e tenha:
✅ Transações ilimitadas
✅ Dashboard web completo
✅ Chat com IA por voz
✅ Foto de nota fiscal automática
✅ Simulador de decisões financeiras

👉 {BASE_URL}/landing.html

_Qualquer dúvida é só mandar mensagem aqui!_ 💚"""


def msg_pro(nome: str) -> str:
    return f"""🎉 *Parabéns, {nome}! Bem-vindo(a) ao finia Pro!* 🎉

Seu plano *Pro* está ativo e você tem acesso completo a todas as funcionalidades! ✨

━━━━━━━━━━━━━━━━
⚡ *Seus recursos Pro:*
✅ Transações *ilimitadas*
✅ Dashboard web completo
✅ Chat com IA por texto e *voz*
✅ Registro por *foto de nota fiscal*
✅ *Simulador* de decisões financeiras
✅ 3 contas bancárias
✅ Relatório PDF mensal
✅ Alertas de contas a pagar

━━━━━━━━━━━━━━━━
💬 *Comece agora — mande uma mensagem:*
→ "gastei 50 no mercado"
→ "recebi salário de 3000"
→ "resumo do mês"

🌐 *Seu dashboard:*
{BASE_URL}

🤖 *Chat com IA + nota fiscal:*
{BASE_URL}/chat.html

━━━━━━━━━━━━━━━━
📖 *Manual completo:*
Em anexo você recebe o manual de funcionalidades com tudo que o finia pode fazer por você!

_Obrigado por escolher o finia! Qualquer dúvida é só chamar aqui._ 💚"""


def msg_familia(nome: str) -> str:
    return f"""🏡 *Olá, {nome}! Bem-vindo(a) ao finia Família!* 🏡

Seu plano *Família* está ativo! Agora vocês podem organizar as finanças juntos com até 5 membros! 💚

━━━━━━━━━━━━━━━━
⚡ *Seus recursos Família:*
✅ Tudo do plano Pro
✅ Até *5 membros* conectados
✅ Cada membro com seu *próprio bot*
✅ *Dashboard compartilhado* — vejam tudo juntos
✅ Alertas para todos os membros
✅ Contas bancárias ilimitadas

━━━━━━━━━━━━━━━━
👥 *Para adicionar membros da família:*
Acesse o dashboard > Configurações > Membros

🌐 *Dashboard compartilhado:*
{BASE_URL}

🤖 *Chat com IA:*
{BASE_URL}/chat.html

━━━━━━━━━━━━━━━━
💬 *Comece agora:*
→ "gastei 50 no mercado"
→ "recebi salário de 5000"
→ "resumo da família"

_Obrigado por escolher o finia Família! Qualquer dúvida é só chamar._ 💚"""


def msg_upgrade_pro(nome: str) -> str:
    return f"""🚀 *{nome}, você fez um upgrade incrível!*

Seu plano foi atualizado para *finia Pro*! Agora você tem acesso a tudo! 🎉

✅ Transações ilimitadas — desbloqueadas!
✅ Dashboard web completo — disponível!
✅ Chat IA com voz — ativado!
✅ Foto de nota fiscal — funcionando!
✅ Simulador de decisões — pronto!

🌐 Acesse agora: {BASE_URL}

_Obrigado por confiar no finia!_ 💚"""


# ─────────────────────────────────────────────────────
# ENVIAR VIA WHATSAPP
# ─────────────────────────────────────────────────────

async def enviar_whatsapp(telefone: str, mensagem: str):
    """Envia mensagem de boas-vindas via WhatsApp."""
    if not EVOLUTION_URL or not telefone:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INST}",
                json={"number": telefone, "textMessage": {"text": mensagem}},
                headers={"apikey": EVOLUTION_KEY},
            )
    except Exception as e:
        print(f"[boas-vindas] Erro WhatsApp: {e}")


async def enviar_manual_whatsapp(telefone: str, nome: str):
    """Envia o link do manual por WhatsApp."""
    if not EVOLUTION_URL or not telefone:
        return
    msg = (
        f"📖 *{nome}, aqui está seu manual completo!*\n\n"
        f"O manual de funcionalidades do finia está disponível no link abaixo. "
        f"Guarde — ele tem tudo que você precisa saber para aproveitar ao máximo!\n\n"
        f"👉 {BASE_URL}/static/finia_manual.pdf\n\n"
        f"_Qualquer dúvida, é só perguntar aqui!_ 💚"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INST}",
                json={"number": telefone, "textMessage": {"text": msg}},
                headers={"apikey": EVOLUTION_KEY},
            )
    except Exception as e:
        print(f"[boas-vindas] Erro manual WhatsApp: {e}")


# ─────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────

@router.post("/novo-usuario")
async def boas_vindas_novo(
    telefone: str,
    nome: str,
    plano: str = "gratis",
    background_tasks: BackgroundTasks = None
):
    """
    Chamado quando um novo usuário se cadastra.
    Envia boas-vindas no WhatsApp conforme o plano.
    """
    plano = plano.lower()
    msgs = {
        "gratis":  msg_gratis(nome),
        "pro":     msg_pro(nome),
        "familia": msg_familia(nome),
    }
    mensagem = msgs.get(plano, msg_gratis(nome))

    if background_tasks:
        background_tasks.add_task(enviar_whatsapp, telefone, mensagem)
        if plano in ("pro", "familia"):
            background_tasks.add_task(enviar_manual_whatsapp, telefone, nome)
    else:
        await enviar_whatsapp(telefone, mensagem)
        if plano in ("pro", "familia"):
            await enviar_manual_whatsapp(telefone, nome)

    return {
        "ok": True,
        "plano": plano,
        "telefone": telefone,
        "nome": nome,
        "mensagem_enviada": True
    }


@router.post("/upgrade")
async def boas_vindas_upgrade(
    telefone: str,
    nome: str,
    plano_novo: str,
    background_tasks: BackgroundTasks = None
):
    """
    Chamado quando o usuário faz upgrade de plano.
    """
    plano_novo = plano_novo.lower()
    msgs_upgrade = {
        "pro":     msg_upgrade_pro(nome),
        "familia": msg_familia(nome),
    }
    mensagem = msgs_upgrade.get(plano_novo, msg_pro(nome))

    if background_tasks:
        background_tasks.add_task(enviar_whatsapp, telefone, mensagem)
        background_tasks.add_task(enviar_manual_whatsapp, telefone, nome)
    else:
        await enviar_whatsapp(telefone, mensagem)
        await enviar_manual_whatsapp(telefone, nome)

    return {"ok": True, "upgrade_para": plano_novo}


@router.post("/lembrete-limite")
async def lembrete_limite(
    telefone: str,
    nome: str,
    uso_atual: int,
    limite: int = 50,
    background_tasks: BackgroundTasks = None
):
    """
    Envia lembrete quando o usuário está próximo do limite do plano grátis.
    """
    restantes = limite - uso_atual
    if restantes > 10:
        return {"ok": False, "motivo": "Ainda longe do limite"}

    msg = (
        f"⚠️ *{nome}, você está quase no limite!*\n\n"
        f"Você já usou *{uso_atual} de {limite} transações* do plano Grátis este mês.\n"
        f"Restam apenas *{restantes} transações*.\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🚀 *Assine o finia Pro e nunca mais se preocupe com limites:*\n"
        f"✅ Transações ilimitadas\n"
        f"✅ Dashboard web completo\n"
        f"✅ Chat IA com voz\n"
        f"✅ Foto de nota fiscal\n\n"
        f"👉 *Apenas R$ 19,90/mês*\n"
        f"{BASE_URL}/landing.html\n\n"
        f"_Não perca seus registros — assine agora!_ 💚"
    )

    if background_tasks:
        background_tasks.add_task(enviar_whatsapp, telefone, msg)
    else:
        await enviar_whatsapp(telefone, msg)

    return {"ok": True, "lembrete_enviado": True, "restantes": restantes}


# ─────────────────────────────────────────────────────
# INTEGRAR COM O WEBHOOK DE PAGAMENTO
# ─────────────────────────────────────────────────────
# Em app/routers/pagamentos.py, dentro de processar_pagamento(),
# após ativar o plano, adicione:
#
# from app.routers.boas_vindas import boas_vindas_novo
# await boas_vindas_novo(
#     telefone=user.telefone,
#     nome=user.nome,
#     plano=plano
# )
#
# E em app/routers/usuarios.py, dentro de get_or_create_user(),
# após criar um novo usuário, adicione:
#
# from app.routers.boas_vindas import boas_vindas_novo
# await boas_vindas_novo(
#     telefone=telefone,
#     nome=nome,
#     plano="gratis"
# )
