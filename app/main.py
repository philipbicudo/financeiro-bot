from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import transacoes, resumo, webhook

# Cria todas as tabelas no banco ao iniciar
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Assistente Financeiro Bot",
    description="Backend do assistente financeiro via WhatsApp",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas da API
app.include_router(transacoes.router, prefix="/transacoes", tags=["Transações"])
app.include_router(resumo.router,     prefix="/resumo",     tags=["Resumo"])
app.include_router(webhook.router,    prefix="/webhook",    tags=["WhatsApp"])

@app.get("/")
def root():
    return {"status": "online", "mensagem": "Assistente Financeiro rodando!"}
