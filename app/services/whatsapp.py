"""
Cliente para a Evolution API (WhatsApp).
Documentação: https://doc.evolution-api.com
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

EVOLUTION_URL      = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY  = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "financeiro-bot")

HEADERS = {
    "Content-Type": "application/json",
    "apikey": EVOLUTION_API_KEY,
}

async def enviar_texto(numero: str, mensagem: str) -> dict:
    """
    Envia mensagem de texto simples via WhatsApp.
    numero: formato '5511999999999' (sem + e sem @s.whatsapp.net)
    """
    numero = _limpar_numero(numero)
    url    = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"

    payload = {
        "number": numero,
        "text": mensagem,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


async def enviar_pdf(numero: str, caminho_pdf: str, nome_arquivo: str, legenda: str = "") -> dict:
    """
    Envia um arquivo PDF via WhatsApp.
    caminho_pdf: caminho local do arquivo .pdf
    """
    numero = _limpar_numero(numero)
    url    = f"{EVOLUTION_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"

    # Lê o arquivo e converte para base64
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
        resp = await client.post(url, json=payload, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


async def criar_instancia() -> dict:
    """
    Cria a instância do bot na Evolution API (roda uma vez só na configuração).
    """
    url     = f"{EVOLUTION_URL}/instance/create"
    payload = {
        "instanceName": EVOLUTION_INSTANCE,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=HEADERS)
        return resp.json()


async def obter_qrcode() -> dict:
    """
    Retorna o QR Code para conectar o WhatsApp.
    Acesse /setup/qrcode no navegador após subir o servidor.
    """
    url = f"{EVOLUTION_URL}/instance/connect/{EVOLUTION_INSTANCE}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=HEADERS)
        return resp.json()


async def status_instancia() -> dict:
    """Verifica se o WhatsApp está conectado."""
    url = f"{EVOLUTION_URL}/instance/connectionState/{EVOLUTION_INSTANCE}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=HEADERS)
        return resp.json()


async def configurar_webhook(webhook_url: str) -> dict:
    """
    Registra a URL do seu backend na Evolution API para receber mensagens.
    webhook_url: URL pública do seu servidor, ex: https://meu-app.railway.app/webhook/whatsapp
    """
    url     = f"{EVOLUTION_URL}/webhook/set/{EVOLUTION_INSTANCE}"
    payload = {
        "url": webhook_url,
        "webhook_by_events": False,
        "webhook_base64": False,
        "events": [
            "MESSAGES_UPSERT",   # nova mensagem recebida
            "CONNECTION_UPDATE",  # status de conexão
        ],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=HEADERS)
        return resp.json()


def _limpar_numero(numero: str) -> str:
    """Remove caracteres inválidos do número. Ex: '55 (11) 9 9999-9999' → '5511999999999'"""
    import re
    numero = re.sub(r"[^\d]", "", numero)
    # Remove sufixo @s.whatsapp.net se vier do Evolution
    if "@" in numero:
        numero = numero.split("@")[0]
    return numero
