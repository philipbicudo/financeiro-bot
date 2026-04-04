from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.database import engine, Base
from app.models import usuario, transacao
from app.routers import transacoes, resumo, webhook, dashboard_router, usuarios

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="finia — Assistente Financeiro",
    description="Gestão financeira via WhatsApp",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transacoes.router,      prefix="/transacoes", tags=["Transações"])
app.include_router(resumo.router,          prefix="/resumo",     tags=["Resumo"])
app.include_router(webhook.router,         prefix="/webhook",    tags=["WhatsApp"])
app.include_router(dashboard_router.router)
app.include_router(usuarios.router)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
def index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"status": "online", "versao": "2.0.0"}

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
