from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import datetime, timedelta
from app.database import get_db
from app.models.usuario import Usuario
from app.models.transacao import Transacao

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


def get_or_create_user(telefone: str, nome: str, db: Session) -> Usuario:
    user = db.query(Usuario).filter(Usuario.telefone == telefone).first()
    if not user:
        user = Usuario(telefone=telefone, nome=nome or "Usuário", plano="gratis")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/por-telefone/{telefone}")
def buscar_por_telefone(telefone: str, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.telefone == telefone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {
        "id":        user.id,
        "nome":      user.nome,
        "telefone":  user.telefone,
        "plano":     user.plano,
        "ativo":     user.plano_ativo,
        "expira":    user.plano_expira,
        "criado_em": user.criado_em,
    }


@router.post("/criar")
def criar_usuario(telefone: str, nome: str, db: Session = Depends(get_db)):
    existente = db.query(Usuario).filter(Usuario.telefone == telefone).first()
    if existente:
        return {"id": existente.id, "telefone": existente.telefone, "plano": existente.plano}
    user = Usuario(telefone=telefone, nome=nome, plano="gratis")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "telefone": user.telefone, "plano": user.plano}


@router.patch("/{user_id}/plano")
def atualizar_plano(
    user_id: int,
    plano: str,
    mp_subscription_id: str | None = None,
    db: Session = Depends(get_db)
):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.plano               = plano
    user.plano_ativo         = True
    user.plano_expira        = datetime.utcnow() + timedelta(days=30)
    user.mp_subscription_id  = mp_subscription_id or user.mp_subscription_id
    user.atualizado          = datetime.utcnow()
    db.commit()
    return {"ok": True, "plano": plano, "expira": user.plano_expira}


@router.get("/{user_id}/status")
def status_usuario(user_id: int, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    now = datetime.now()
    total_mes = db.query(Transacao).filter(
        Transacao.usuario_id == user_id,
        extract('month', Transacao.data) == now.month,
        extract('year',  Transacao.data) == now.year,
    ).count()
    limites = {"gratis": 50, "pro": 999999, "familia": 999999}
    limite  = limites.get(user.plano, 50)
    return {
        "id":             user.id,
        "nome":           user.nome,
        "plano":          user.plano,
        "ativo":          user.plano_ativo,
        "expira":         user.plano_expira,
        "uso_mes":        total_mes,
        "limite_mes":     limite,
        "pode_registrar": user.pode_registrar(total_mes),
    }
