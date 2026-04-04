"""
Webhook principal — recebe mensagens da Evolution API,
processa com IA e responde via WhatsApp.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import datetime

from app.database import get_db
from app.models.transacao import Transacao, TipoTransacao, StatusTransacao
from app.services.ia import interpretar_mensagem
from app.services import whatsapp as wp
from app.routers.resumo import resumo_em_texto

router = APIRouter()


def _extrair_numero_e_texto(body: dict) -> tuple:
    """Extrai número do remetente e texto da mensagem (formato Evolution API)."""
    try:
        data = body.get("data", {})
        key  = data.get("key", {})
        if key.get("fromMe"):
            return "", ""
        numero = key.get("remoteJid", "")
        # Se vier @lid, tenta pegar o número real do campo 'owner'
        if "@lid" in numero:
            owner = data.get("owner", "")
            if owner:
                numero = owner
            else:
                return "", ""
        if "@g.us" in numero:
            return "", ""
        msg = data.get("message", {})
        texto = (
            msg.get("conversation")
            or msg.get("extendedTextMessage", {}).get("text")
            or ""
        )
        return numero, texto.strip()
    except Exception:
        return "", ""


def _formatar_registro(t: Transacao) -> str:
    emoji  = "💰" if t.tipo == TipoTransacao.receita else "💸"
    status = "✅ Pago" if t.status == StatusTransacao.pago else "⏳ A pagar"
    return (
        f"{emoji} *Registrado!*\n\n"
        f"📝 {t.descricao}\n"
        f"💵 R$ {t.valor:,.2f}\n"
        f"📂 {t.categoria}  •  {t.metodo}\n"
        f"📅 {t.data.strftime('%d/%m/%Y')}  •  {status}\n\n"
        f"_Digite 'resumo' para ver o balanço do mês._"
    )


def _mensagem_ajuda() -> str:
    return (
        "🤖 *Assistente Financeiro*\n\n"
        "Pode me falar naturalmente! Exemplos:\n\n"
        "💸 *Registrar gasto:*\n"
        "  • _gastei 50 no mercado_\n"
        "  • _paguei 180 de luz no cartão_\n"
        "  • _uber pra faculdade 22 reais_\n\n"
        "💰 *Registrar receita:*\n"
        "  • _recebi meu salário de 3000_\n"
        "  • _entrou 500 de freela_\n\n"
        "📊 *Ver resumo:*\n"
        "  • _quero ver meu resumo_\n"
        "  • _quanto gastei esse mês_\n\n"
        "📋 *Listar transações:*\n"
        "  • _me mostra os gastos_\n\n"
        "✅ *Marcar como pago:*\n"
        "  • _paguei o aluguel_"
    )


async def processar_acao(acao_dict: dict, numero: str, db: Session, responder: bool = True) -> str:
    acao     = acao_dict.get("acao", "ajuda")
    resposta = ""

    if acao == "registrar":
        valor = float(acao_dict.get("valor", 0))
        if valor <= 0:
            resposta = "⚠️ Não consegui identificar o valor. Pode repetir? Ex: _gastei 50 no mercado_"
        else:
            t = Transacao(
                descricao = acao_dict.get("descricao", "Sem descrição"),
                valor     = valor,
                tipo      = acao_dict.get("tipo", "despesa"),
                categoria = acao_dict.get("categoria", "Outros"),
                metodo    = acao_dict.get("metodo", "PIX"),
                status    = StatusTransacao.nao_pago,
                data      = datetime.now(),
            )
            db.add(t)
            db.commit()
            db.refresh(t)
            resposta = _formatar_registro(t)

    elif acao == "resumo":
        agora    = datetime.now()
        resultado = resumo_em_texto(mes=agora.month, ano=agora.year, db=db)
        resposta = resultado["texto"]

    elif acao == "listar":
        agora = datetime.now()
        lista = (
            db.query(Transacao)
            .filter(
                extract("month", Transacao.data) == agora.month,
                extract("year",  Transacao.data) == agora.year,
            )
            .order_by(Transacao.data.desc())
            .limit(8)
            .all()
        )
        if lista:
            linhas = [f"📋 *Últimos lançamentos ({agora.strftime('%B/%Y')}):*\n"]
            for t in lista:
                e = "💰" if t.tipo == TipoTransacao.receita else "💸"
                s = "✅" if t.status == StatusTransacao.pago else "⏳"
                linhas.append(f"{e}{s} {t.descricao} — R$ {t.valor:,.2f}")
            resposta = "\n".join(linhas)
        else:
            resposta = "📋 Nenhuma transação registrada este mês ainda."

    elif acao == "marcar_pago":
        busca = acao_dict.get("descricao_busca", "")
        t = (
            db.query(Transacao)
            .filter(Transacao.descricao.ilike(f"%{busca}%"))
            .filter(Transacao.status == StatusTransacao.nao_pago)
            .order_by(Transacao.data.desc())
            .first()
        )
        if t:
            t.status = StatusTransacao.pago
            db.commit()
            resposta = f"✅ *{t.descricao}* marcado como pago!\n💵 R$ {t.valor:,.2f}"
        else:
            resposta = f"⚠️ Não encontrei nenhum lançamento pendente com '{busca}'."

    elif acao == "erro_api":
        resposta = "❌ Serviço de IA temporariamente indisponível. Tente novamente."

    else:
        resposta = _mensagem_ajuda()

    if responder and numero:
        try:
            await wp.enviar_texto(numero, resposta)
        except Exception as e:
            print(f"⚠️ Erro ao enviar WhatsApp para {numero}: {e}")

    return resposta


@router.post("/whatsapp")
async def webhook_whatsapp(request: Request, db: Session = Depends(get_db)):
    body           = await request.json()
    print(f"📦 BODY: {body}")
    numero, texto  = _extrair_numero_e_texto(body)

    if not texto:
        return {"status": "ignorado", "motivo": "sem_texto"}

    print(f"📩 [{numero}] {texto}")
    acao_dict = interpretar_mensagem(texto)
    print(f"🤖 Ação: {acao_dict}")

    resposta = await processar_acao(acao_dict, numero, db, responder=True)

    return {
        "status"          : "processado",
        "numero"          : numero,
        "mensagem"        : texto,
        "acao"            : acao_dict.get("acao"),
        "resposta_enviada": resposta[:120] + "..." if len(resposta) > 120 else resposta,
    }


@router.post("/testar", summary="Testa o bot sem precisar do WhatsApp")
async def testar_bot(mensagem: str, db: Session = Depends(get_db)):
    acao_dict = interpretar_mensagem(mensagem)
    resposta  = await processar_acao(acao_dict, numero="", db=db, responder=False)
    return {
        "mensagem_enviada"   : mensagem,
        "interpretado_pela_ia": acao_dict,
        "resposta_do_bot"    : resposta,
    }


@router.get("/setup/status", summary="Status da conexão WhatsApp")
async def status_whatsapp():
    try:
        status = await wp.status_instancia()
        return {"evolution_api": "acessível", "detalhes": status}
    except Exception as e:
        return {"evolution_api": "inacessível", "erro": str(e)}


@router.post("/setup/criar-instancia", summary="Cria instância na Evolution API (1x só)")
async def criar_instancia():
    try:
        return {"status": "criado", "detalhes": await wp.criar_instancia()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/setup/qrcode", summary="QR Code para conectar o WhatsApp")
async def obter_qrcode():
    try:
        return await wp.obter_qrcode()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/setup/configurar-webhook", summary="Registra URL pública na Evolution API")
async def configurar_webhook(url_publica: str):
    try:
        resultado = await wp.configurar_webhook(url_publica)
        return {"status": "configurado", "url": url_publica, "detalhes": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
