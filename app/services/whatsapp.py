"""
Cliente para a Evolution API (WhatsApp).
"""
import httpx
import os
import re
from dotenv import load_dotenv

load_dotenv()

EVOLUTION_URL      = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "financeiro-bot")


def _get_headers():
    return {
        "Content-Type": "application/json",
        "apikey": os.getenv("EVOLUTION_API_KEY", ""),
    }


def _limpar_numero(numero: str) -> str:
    if "@lid" in numero:
        return numero
    if "@" in numero:
        numero = numero.split("@")[0]
    numero = re.sub(r"[^\d]", "", numero)
    return numero


async def _resolver_lid(lid: str) -> str:
    """Resolve um @lid para o número real usando a Evolution API."""
    try:
        url = f"{EVOLUTION_URL}/chat/findContacts/{EVOLUTION_INSTANCE}"
        payload = {"where": {"id": lid}}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=_get_headers())
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                numero = data[0].get("phoneNumber") or data[0].get("number") or data[0].get("id", "")
                if numero and "@" in numero:
                    numero = numero.split("@")[0]
                numero = re.sub(r"[^\d]", "", numero)
                if numero:
                    return numero
    except Exception as e:
        print(f"⚠️ Erro ao resolver lid {lid}: {e}")
    return ""


async def enviar_texto(numero: str, mensagem: str) -> dict:
    if "@lid" in numero:
        numero_real = await _resolver_lid(numero)
        if numero_real:
            numero = numero_real
            print(f"✅ LID resolvido para: {numero}")
        else:
            print(f"⚠️ Não foi possível resolver LID: {numero}")
            return {}
    else:
        numero = _limpar_numero(numero)
    
    print(f"📤 Enviando para: {numero}")
    url    = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    payload = {
        "number": numero,
        "textMessage": {"text": mensagem},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=_get_headers())
        resp.raise_for_status()
        return resp.json()


async def enviar_pdf(numero: str, caminho_pdf: str, nome_arquivo: str, legenda: str = "") -> dict:
    numero = _limpar_numero(numero)
    url    = f"{EVOLUTION_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    import base64
    with open(caminho_pdf, "rb") as f:
        conteudo_b64 = base64.b64encode(f.read()).decode("utf-8")
    payload = {
        "number": numero,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "caption": legenda,
        "media": conteudo_b64,
        "fileName": nome_arquivo,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=_get_headers())
        resp.raise_for_status()
        return resp.json()


async def criar_instancia() -> dict:
    url     = f"{EVOLUTION_URL}/instance/create"
    payload = {
        "instanceName": EVOLUTION_INSTANCE,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=_get_headers())
        return resp.json()


async def obter_qrcode() -> dict:
    url = f"{EVOLUTION_URL}/instance/connect/{EVOLUTION_INSTANCE}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=_get_headers())
        return resp.json()


async def status_instancia() -> dict:
    url = f"{EVOLUTION_URL}/instance/connectionState/{EVOLUTION_INSTANCE}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=_get_headers())
        return resp.json()


async def configurar_webhook(webhook_url: str) -> dict:
    url     = f"{EVOLUTION_URL}/webhook/set/{EVOLUTION_INSTANCE}"
    payload = {
        "url": webhook_url,
        "webhook_by_events": False,
        "webhook_base64": False,
        "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=_get_headers())
        return resp.json()
