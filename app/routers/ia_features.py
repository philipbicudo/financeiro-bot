# ─────────────────────────────────────────────────────
# 💬 PROXY CHAT IA (evita CORS no browser)
# ─────────────────────────────────────────────────────

from pydantic import BaseModel
from typing import List

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    system: str | None = None

@router.post("/chat")
async def chat_proxy(req: ChatRequest):
    """Proxy para o chat IA — evita CORS no browser."""
    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=req.system or "Você é o finia, assistente financeiro pessoal. Seja direto e informal.",
            messages=[{"role": m.role, "content": m.content} for m in req.messages],
        )
        return {"ok": True, "text": resp.content[0].text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
