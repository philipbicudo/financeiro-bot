# app/routers/auth.py
# Autenticação via OTP WhatsApp + JWT
# Adicione no main.py:
#   from app.routers import auth
#   app.include_router(auth.router)
# Instale: pip install python-jose[cryptography] passlib[bcrypt]

import os
import random
import string
import hashlib
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError as JWTError
from pydantic import BaseModel, validator
import re

from app.database import get_db
from app.models.usuario import Usuario

router = APIRouter(prefix="/auth", tags=["Autenticação"])

# ── CONFIG ──
JWT_SECRET      = os.getenv("JWT_SECRET", "finia_secret_mude_em_producao_2026")
JWT_ALGO        = "HS256"
JWT_EXPIRE_DAYS = 30
OTP_EXPIRE_MIN  = 10

EVOLUTION_URL   = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_KEY   = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INST  = os.getenv("EVOLUTION_INSTANCE", "financeiro-bot")

# Armazena OTPs em memória (em produção use Redis)
# { telefone_normalizado: { "code": "123456", "expires": datetime, "tentativas": 0 } }
_otp_store: dict = {}
_MAX_TENTATIVAS = 5


# ── SCHEMAS ──

class SolicitarOTPRequest(BaseModel):
    telefone: str

    @validator('telefone')
    def validar_telefone(cls, v):
        nums = re.sub(r'\D', '', v)
        if len(nums) < 10 or len(nums) > 13:
            raise ValueError('Número de telefone inválido')
        return nums

class VerificarOTPRequest(BaseModel):
    telefone: str
    codigo:   str
    nome:     str | None = None

    @validator('telefone')
    def validar_telefone(cls, v):
        return re.sub(r'\D', '', v)

    @validator('codigo')
    def validar_codigo(cls, v):
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Código deve ter 6 dígitos')
        return v

    @validator('nome')
    def sanitizar_nome(cls, v):
        if not v: return v
        v = re.sub(r'<[^>]+>', '', v.strip())[:100]
        return v or None


# ── HELPERS ──

def normalizar_telefone(tel: str) -> str:
    nums = re.sub(r'\D', '', tel)
    if not nums.startswith('55'):
        nums = '55' + nums
    return nums

def gerar_otp() -> str:
    return ''.join(random.choices(string.digits, k=6))

def criar_token(usuario_id: int, telefone: str) -> str:
    payload = {
        "sub":  str(usuario_id),
        "tel":  telefone,
        "iat":  datetime.utcnow(),
        "exp":  datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def verificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

async def enviar_wpp(telefone: str, mensagem: str):
    if not EVOLUTION_URL:
        print(f"[OTP] Código para {telefone}: {mensagem}")
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INST}",
                json={"number": telefone, "textMessage": {"text": mensagem}},
                headers={"apikey": EVOLUTION_KEY},
            )
    except Exception as e:
        print(f"[auth] Erro WhatsApp: {e}")


# ── ENDPOINTS ──

@router.post("/solicitar-otp")
async def solicitar_otp(req: SolicitarOTPRequest, request: Request):
    """
    Passo 1: Usuário informa o WhatsApp.
    Gera OTP de 6 dígitos e envia pelo bot.
    """
    tel = normalizar_telefone(req.telefone)

    # Rate limiting simples — máx 3 OTPs por hora por IP
    client_ip = request.client.host if request.client else "unknown"
    ip_key = f"ip:{client_ip}"
    if ip_key in _otp_store:
        entry = _otp_store[ip_key]
        if isinstance(entry, dict) and entry.get("count", 0) >= 3:
            if datetime.utcnow() < entry.get("reset_at", datetime.utcnow()):
                raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 1 hora.")
            else:
                del _otp_store[ip_key]

    codigo = gerar_otp()
    expires = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MIN)

    # Armazena OTP com hash para segurança
    _otp_store[tel] = {
        "code_hash": hashlib.sha256(codigo.encode()).hexdigest(),
        "expires":   expires,
        "tentativas": 0,
    }

    # Registra contagem por IP
    if ip_key not in _otp_store:
        _otp_store[ip_key] = {"count": 0, "reset_at": datetime.utcnow() + timedelta(hours=1)}
    if isinstance(_otp_store.get(ip_key), dict) and "count" in _otp_store[ip_key]:
        _otp_store[ip_key]["count"] += 1

    msg = (
        f"🔐 *Código de acesso finia*\n\n"
        f"Seu código é: *{codigo}*\n\n"
        f"⏱️ Válido por {OTP_EXPIRE_MIN} minutos.\n"
        f"❌ Não compartilhe com ninguém.\n\n"
        f"Se não foi você, ignore esta mensagem."
    )
    await enviar_wpp(tel, msg)

    return {
        "ok":      True,
        "telefone": tel[-4:],  # Retorna só os últimos 4 dígitos por segurança
        "expira_em": OTP_EXPIRE_MIN,
        "mensagem": f"Código enviado para WhatsApp terminado em {tel[-4:]}"
    }


@router.post("/verificar-otp")
async def verificar_otp(req: VerificarOTPRequest, db: Session = Depends(get_db)):
    """
    Passo 2: Usuário informa o código recebido.
    Valida, cria/busca usuário e retorna token JWT.
    """
    tel = normalizar_telefone(req.telefone)
    entry = _otp_store.get(tel)

    # Verifica se existe OTP
    if not entry:
        raise HTTPException(status_code=400, detail="Código não encontrado. Solicite um novo.")

    # Verifica expiração
    if datetime.utcnow() > entry["expires"]:
        del _otp_store[tel]
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo.")

    # Verifica tentativas
    if entry["tentativas"] >= _MAX_TENTATIVAS:
        del _otp_store[tel]
        raise HTTPException(status_code=429, detail="Muitas tentativas incorretas. Solicite um novo código.")

    # Verifica código (compara hash)
    codigo_hash = hashlib.sha256(req.codigo.encode()).hexdigest()
    if codigo_hash != entry["code_hash"]:
        _otp_store[tel]["tentativas"] += 1
        restantes = _MAX_TENTATIVAS - entry["tentativas"]
        raise HTTPException(status_code=400, detail=f"Código incorreto. {restantes} tentativas restantes.")

    # Código correto — limpa OTP
    del _otp_store[tel]

    # Busca ou cria usuário
    user = db.query(Usuario).filter(Usuario.telefone == tel).first()
    novo_usuario = False

    if not user:
        user = Usuario(
            telefone    = tel,
            nome        = req.nome or f"Usuário {tel[-4:]}",
            plano       = "gratis",
            plano_ativo = True,
            ativo       = True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        novo_usuario = True

        # Boas-vindas para novo usuário
        msg_bv = (
            f"🎉 *Bem-vindo ao finia, {user.nome}!*\n\n"
            f"Sua conta foi criada com sucesso!\n\n"
            f"📱 Você já pode:\n"
            f"• Registrar gastos mandando mensagem aqui\n"
            f"• Acessar seu dashboard no site\n"
            f"• Consultar resumo digitando 'resumo'\n\n"
            f"_Comece agora: 'gastei 50 no mercado'_ 💚"
        )
        await enviar_wpp(tel, msg_bv)

    if not user.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada. Entre em contato com o suporte.")

    # Gera JWT
    token = criar_token(user.id, tel)

    return {
        "ok":          True,
        "token":       token,
        "usuario_id":  user.id,
        "nome":        user.nome,
        "plano":       user.plano,
        "plano_ativo": user.plano_ativo,
        "novo_usuario": novo_usuario,
        "expira_em":   JWT_EXPIRE_DAYS * 24 * 3600,
    }


@router.get("/me")
def perfil_atual(request: Request, db: Session = Depends(get_db)):
    """Retorna dados do usuário autenticado."""
    token = _extrair_token(request)
    payload = verificar_token(token)
    user = db.query(Usuario).filter(Usuario.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {
        "id":          user.id,
        "nome":        user.nome,
        "telefone":    user.telefone,
        "email":       user.email,
        "plano":       user.plano,
        "plano_ativo": user.plano_ativo,
        "plano_expira": user.plano_expira.isoformat() if user.plano_expira else None,
    }


@router.post("/logout")
def logout():
    """Logout — o cliente deve apagar o token."""
    return {"ok": True, "mensagem": "Token removido no cliente"}


# ── DEPENDENCY para proteger rotas ──

def _extrair_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # Tenta cookie como fallback
    token = request.cookies.get("finia_token", "")
    if token:
        return token
    raise HTTPException(status_code=401, detail="Token não fornecido")

def get_usuario_atual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Dependency — use em qualquer endpoint protegido."""
    token   = _extrair_token(request)
    payload = verificar_token(token)
    user    = db.query(Usuario).filter(Usuario.id == int(payload["sub"])).first()
    if not user or not user.ativo:
        raise HTTPException(status_code=401, detail="Usuário inválido ou desativado")
    return user
