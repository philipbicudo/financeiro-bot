from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.database import engine, Base
from app.models import usuario, transacao
from app.routers import (
    transacoes, resumo, webhook, dashboard_router,
    usuarios, pagamentos, bot_vendas, ia_features,
    boas_vindas, assinaturas, auth
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="finia — Assistente Financeiro",
    description="Gestão financeira via WhatsApp",
    version="2.0.0",
    docs_url=None,      # Desativa /docs em produção
    redoc_url=None,     # Desativa /redoc em produção
)

# ── SEGURANÇA ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://financeiro-bot-production-571e.up.railway.app",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

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
    return {"status": "ok"}
