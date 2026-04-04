"""
Script para popular o banco com dados de teste.
Rode com: python scripts/popular_banco.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models.transacao import Transacao, TipoTransacao, StatusTransacao
from datetime import datetime, timedelta
import random

Base.metadata.create_all(bind=engine)

DESPESAS_EXEMPLO = [
    ("Aluguel",           2000.00, "Casa",         "Boleto",  "pago"),
    ("Condomínio",         160.00, "Casa",         "Boleto",  "nao_pago"),
    ("Faculdade - Philip", 236.00, "Educação",     "PIX",     "nao_pago"),
    ("Internet + Vivo",    377.00, "Casa",         "PIX",     "nao_pago"),
    ("Jiu-Jitsu",          110.00, "Saúde",        "PIX",     "nao_pago"),
    ("Condução RD",        340.00, "Transporte",   "PIX",     "pago"),
    ("Mercado Livre",      110.00, "Casa",         "Cartão",  "nao_pago"),
    ("Jazz Valentina",     175.75, "Educação",     "PIX",     "nao_pago"),
    ("DAS - Aline",         85.15, "Outros",       "PIX",     "nao_pago"),
]

RECEITAS_EXEMPLO = [
    ("Salário Philip",    5000.00, "Salário", "PIX",    "nao_pago"),
    ("Salário Aline",     1427.00, "Salário", "PIX",    "nao_pago"),
    ("Bônus Vendas",       800.00, "Salário", "PIX",    "nao_pago"),
]

def popular():
    db = SessionLocal()
    try:
        # Limpa dados existentes
        db.query(Transacao).delete()
        db.commit()

        hoje = datetime.now()
        mes_atual = hoje.replace(day=1)

        # Adiciona despesas
        for desc, valor, cat, metodo, status in DESPESAS_EXEMPLO:
            dia = random.randint(1, 28)
            t = Transacao(
                descricao = desc,
                valor     = valor,
                tipo      = TipoTransacao.despesa,
                categoria = cat,
                metodo    = metodo,
                status    = StatusTransacao.pago if status == "pago" else StatusTransacao.nao_pago,
                data      = mes_atual.replace(day=dia),
            )
            db.add(t)

        # Adiciona receitas
        for desc, valor, cat, metodo, status in RECEITAS_EXEMPLO:
            t = Transacao(
                descricao = desc,
                valor     = valor,
                tipo      = TipoTransacao.receita,
                categoria = cat,
                metodo    = metodo,
                status    = StatusTransacao.pago if status == "pago" else StatusTransacao.nao_pago,
                data      = mes_atual.replace(day=5),
            )
            db.add(t)

        db.commit()
        print(f"✅ Banco populado com {len(DESPESAS_EXEMPLO)} despesas e {len(RECEITAS_EXEMPLO)} receitas!")
        print(f"   Total despesas: R$ {sum(v for _,v,*_ in DESPESAS_EXEMPLO):.2f}")
        print(f"   Total receitas: R$ {sum(v for _,v,*_ in RECEITAS_EXEMPLO):.2f}")
    finally:
        db.close()

if __name__ == "__main__":
    popular()
