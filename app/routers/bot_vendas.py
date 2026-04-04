# ═══════════════════════════════════════════════════════
# app/routers/bot_vendas.py
# Bot de vendas — número separado do bot financeiro
# ═══════════════════════════════════════════════════════
#
# Este router recebe mensagens do número de vendas
# (chip pré-pago conectado como segunda instância na Evolution API)
# Instance name: "finia-vendas"
#
# No Railway adicione:
#   EVOLUTION_INSTANCE_VENDAS = finia-vendas

import os
import httpx
from fastapi import APIRouter, Request
from anthropic import Anthropic

router = APIRouter(prefix="/webhook/vendas", tags=["Bot de Vendas"])

EVOLUTION_URL   = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_KEY   = os.getenv("EVOLUTION_API_KEY", "")
INSTANCE_VENDAS = os.getenv("EVOLUTION_INSTANCE_VENDAS", "finia-vendas")
BASE_URL        = os.getenv("BASE_URL", "https://financeiro-bot-production-571e.up.railway.app")
claude          = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

SYSTEM_VENDAS = """Você é o assistente de vendas do finia, um app de gestão financeira pelo WhatsApp.

Seu objetivo é apresentar os planos e ajudar o cliente a escolher o melhor.

PLANOS DISPONÍVEIS:
- Grátis: R$ 0 — 50 transações/mês, 1 conta, resumo no zap (sem bot dedicado nem dashboard)
- Pro: R$ 19,90/mês — ilimitado, bot WhatsApp dedicado, dashboard web, relatório PDF
- Família: R$ 34,90/mês — tudo do Pro + até 5 membros, cada um com seu bot

COMO FUNCIONA:
- O cliente fala com o bot no WhatsApp, sem precisar baixar nada
- Ex: "gastei 50 no mercado" → bot registra e categoriza automaticamente
- Dashboard em: """ + BASE_URL + """

REGRAS:
- Seja simpático, direto e use linguagem informal (brasileiro)
- Não invente funcionalidades que não existem
- Quando o cliente escolher um plano, gere o link de pagamento com: GERAR_LINK:pro ou GERAR_LINK:familia
- Se o cliente quiser começar no grátis, responda: CRIAR_GRATIS
- Mantenha respostas curtas — máximo 5 linhas no WhatsApp
- Use emojis moderadamente"""

# Histórico de conversa em memória (simples — para produção use Redis)
conversas: dict[str, list] = {}


@router.post("")
async def webhook_vendas(request: Request):
    """Recebe mensagens do número de vendas e responde com o bot de vendas."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False}

    data = body.get("data", {})
    key  = data.get("key", {})

    # Ignora mensagens próprias
    if key.get("fromMe"):
        return {"ok": True}

    remote_jid = key.get("remoteJid", "")
    msg_obj    = data.get("message", {})
    texto      = (
        msg_obj.get("conversation") or
        msg_obj.get("extendedTextMessage", {}).get("text") or ""
    ).strip()
    nome       = data.get("pushName", "")

    if not texto or "@lid" in remote_jid:
        return {"ok": True}

    telefone = remote_jid.replace("@s.whatsapp.net", "")

    # Inicializa histórico
    if telefone not in conversas:
        conversas[telefone] = []

    conversas[telefone].append({"role": "user", "content": texto})

    # Limita histórico a 10 mensagens
    if len(conversas[telefone]) > 10:
        conversas[telefone] = conversas[telefone][-10:]

    # Chama Claude
    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=SYSTEM_VENDAS,
            messages=conversas[telefone],
        )
        resposta = resp.content[0].text.strip()
    except Exception as e:
        resposta = "Oi! Estou com uma instabilidade agora. Tenta novamente em instantes 🙏"

    # Processa comandos especiais
    msg_final = resposta

    if "GERAR_LINK:pro" in resposta:
        link = await gerar_link_pagamento(telefone, nome, "pro")
        msg_final = resposta.replace(
            "GERAR_LINK:pro",
            f"\n\n💳 Link de pagamento Pro:\n{link}"
        )

    elif "GERAR_LINK:familia" in resposta:
        link = await gerar_link_pagamento(telefone, nome, "familia")
        msg_final = resposta.replace(
            "GERAR_LINK:familia",
            f"\n\n💳 Link de pagamento Família:\n{link}"
        )

    elif "CRIAR_GRATIS" in resposta:
        await criar_usuario_gratis(telefone, nome)
        msg_final = resposta.replace(
            "CRIAR_GRATIS",
            f"\n\n✅ Conta criada! Agora adiciona o número do finia bot e manda 'oi':\n📱 Salva este número: {obter_numero_bot()}"
        )

    # Adiciona resposta ao histórico
    conversas[telefone].append({"role": "assistant", "content": msg_final})

    # Envia resposta
    await enviar_mensagem(remote_jid, msg_final, key)

    return {"ok": True}


async def gerar_link_pagamento(telefone: str, nome: str, plano: str) -> str:
    """Gera link de pagamento e retorna a URL."""
    try:
        async with httpx.AsyncClient() as client:
            # Primeiro garante que o usuário existe
            r = await client.post(
                f"{BASE_URL}/usuarios/criar",
                params={"telefone": telefone, "nome": nome or "Cliente"},
                timeout=10,
            )
            user_id = r.json().get("id") if r.status_code in (200, 201) else None

            if not user_id:
                # Busca se já existe
                r2 = await client.get(
                    f"{BASE_URL}/usuarios/por-telefone/{telefone}",
                    timeout=10,
                )
                user_id = r2.json().get("id") if r2.status_code == 200 else None

            if not user_id:
                return f"{BASE_URL}/planos"

            # Gera link
            r3 = await client.post(
                f"{BASE_URL}/pagamentos/criar-link",
                params={"plano": plano, "usuario_id": user_id},
                timeout=15,
            )
            if r3.status_code == 200:
                return r3.json().get("link", f"{BASE_URL}/planos")

    except Exception:
        pass

    return f"{BASE_URL}/planos"


async def criar_usuario_gratis(telefone: str, nome: str):
    """Cria conta gratuita para o usuário."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{BASE_URL}/usuarios/criar",
                params={"telefone": telefone, "nome": nome or "Usuário"},
                timeout=10,
            )
    except Exception:
        pass


def obter_numero_bot() -> str:
    """Retorna o número do bot financeiro formatado."""
    return os.getenv("BOT_NUMERO", "+55 XX XXXXX-XXXX")


async def enviar_mensagem(remote_jid: str, texto: str, quoted_key: dict | None = None):
    """Envia mensagem via Evolution API usando a instância de vendas."""
    payload: dict = {
        "number": remote_jid,
        "textMessage": {"text": texto},
    }
    if quoted_key:
        payload["quoted"] = {"key": quoted_key}

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{EVOLUTION_URL}/message/sendText/{INSTANCE_VENDAS}",
                json=payload,
                headers={"apikey": EVOLUTION_KEY},
                timeout=10,
            )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# INSTRUÇÕES DE CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════
#
# 1. CHIP PRÉ-PAGO
#    - Compre um chip (Vivo/Claro/Tim, ~R$10)
#    - Conecte na Evolution API como nova instância:
#      POST /instance/create
#      { "instanceName": "finia-vendas", "qrcode": true }
#    - Escaneie o QR Code com o WhatsApp do chip novo
#
# 2. WEBHOOK DA INSTÂNCIA DE VENDAS
#    - Configure o webhook da instância finia-vendas:
#      POST /webhook/set/finia-vendas
#      {
#        "url": "https://financeiro-bot-production-571e.up.railway.app/webhook/vendas",
#        "events": ["MESSAGES_UPSERT"]
#      }
#
# 3. VARIÁVEIS NO RAILWAY
#    EVOLUTION_INSTANCE_VENDAS = finia-vendas
#    BOT_NUMERO = +55 13 9XXXX-XXXX  (número do bot financeiro)
#    MP_ACCESS_TOKEN = seu_token_mercado_pago
#
# 4. REGISTRAR O ROUTER NO main.py
#    from app.routers import bot_vendas
#    app.include_router(bot_vendas.router)
