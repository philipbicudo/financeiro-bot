from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
import os
import time
import logging

from app.database import engine, Base
from app.models import usuario, transacao
from app.routers import (
    transacoes, resumo, webhook, dashboard_router,
    usuarios, pagamentos, bot_vendas, ia_features,
    boas_vindas, assinaturas, auth
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finia")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="finia",
    version="2.0.0",
    docs_url=None,    # Desativa /docs em produção
    redoc_url=None,   # Desativa /redoc em produção
    openapi_url=None, # Desativa /openapi.json
)

# ── CORS RESTRITO AO DOMÍNIO PRÓPRIO ──
ALLOWED_ORIGINS = [
    "https://financeiro-bot-production-571e.up.railway.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# ── MIDDLEWARE DE SEGURANÇA ──
@app.middleware("http")
async def security_headers(request: Request, call_next):
    start = time.time()

    # Bloqueia métodos não permitidos
    if request.method not in ("GET", "POST", "PATCH", "DELETE", "OPTIONS", "HEAD"):
        return JSONResponse(status_code=405, content={"detail": "Method not allowed"})

    # Bloqueia User-Agents suspeitos (scanners, bots maliciosos)
    ua = request.headers.get("user-agent", "").lower()
    blocked_ua = ["sqlmap", "nikto", "nmap", "masscan", "zgrab", "dirbuster", "gobuster", "nuclei"]
    if any(b in ua for b in blocked_ua):
        logger.warning(f"[BLOCKED] Suspicious UA: {ua} from {request.client.host if request.client else 'unknown'}")
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    response = await call_next(request)

    # Headers de segurança em todas as respostas
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]           = "SAMEORIGIN"
    response.headers["X-XSS-Protection"]          = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]        = "camera=(), microphone=(self), geolocation=()"
    response.headers["Cache-Control"]             = "no-store, no-cache, must-revalidate"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"]   = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://api.anthropic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.anthropic.com https://financeiro-bot-production-571e.up.railway.app https://viacep.com.br; "
        "frame-ancestors 'none';"
    )

    # Log de tempo de resposta
    duration = round((time.time() - start) * 1000)
    if duration > 3000:
        logger.warning(f"[SLOW] {request.method} {request.url.path} — {duration}ms")

    return response


# ── RATE LIMITING GLOBAL SIMPLES ──
_request_counts: dict = {}

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # Rotas sensíveis têm limite mais estrito
    sensitive = ["/auth/", "/transacoes/", "/assinaturas/"]
    is_sensitive = any(request.url.path.startswith(s) for s in sensitive)

    ip = request.client.host if request.client else "unknown"
    now = int(time.time())
    window = now // 60  # janela de 1 minuto
    key = f"{ip}:{window}"

    _request_counts[key] = _request_counts.get(key, 0) + 1

    # Limpa entradas antigas a cada 1000 requests
    if len(_request_counts) > 1000:
        old_window = window - 2
        _request_counts.clear()

    limit = 30 if is_sensitive else 200
    if _request_counts[key] > limit:
        logger.warning(f"[RATE LIMIT] {ip} — {_request_counts[key]} req/min em {request.url.path}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Muitas requisições. Aguarde um momento."},
            headers={"Retry-After": "60"}
        )

    return await call_next(request)


# ── ROUTERS ──
app.include_router(auth.router)
app.include_router(transacoes.router,      prefix="/transacoes",   tags=["Transações"])
app.include_router(resumo.router,          prefix="/resumo",       tags=["Resumo"])
app.include_router(webhook.router,         prefix="/webhook",      tags=["WhatsApp"])
app.include_router(dashboard_router.router)
app.include_router(usuarios.router)
app.include_router(pagamentos.router)
app.include_router(bot_vendas.router)
app.include_router(ia_features.router)
app.include_router(boas_vindas.router)
app.include_router(assinaturas.router)


# ── STATIC FILES ──
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ── PÁGINAS ──
@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")

@app.get("/login.html", include_in_schema=False)
def login():
    return FileResponse("static/login.html")

@app.get("/chat.html", include_in_schema=False)
def chat():
    return FileResponse("static/chat.html")

@app.get("/landing.html", include_in_schema=False)
def landing():
    return FileResponse("static/landing.html")

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "versao": "2.0.0"}

# ── HANDLER DE ERROS GENÉRICO ──
@app.exception_handler(404)
async def not_found(request: Request, exc):
    # Redireciona para login se tentar acessar página inexistente
    if not request.url.path.startswith("/api") and not request.url.path.startswith("/auth"):
        return FileResponse("static/login.html", status_code=200)
    return JSONResponse(status_code=404, content={"detail": "Não encontrado"})

@app.exception_handler(500)
async def server_error(request: Request, exc):
    logger.error(f"[500] {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Erro interno. Tente novamente."})
