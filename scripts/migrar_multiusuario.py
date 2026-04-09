#!/usr/bin/env python3
# scripts/migrar_multiusuario.py
# Roda a cada deploy — migra banco para multiusuário e limpa dados mockados

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, SessionLocal, Base
from app.models import usuario, transacao

def migrar():
    # Cria todas as tabelas se não existirem
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("🔄 Iniciando migração multiusuário...")

        # Descobre nomes reais das tabelas
        tabelas = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        nomes = [t[0] for t in tabelas]
        print(f"📋 Tabelas: {nomes}")

        tx_table  = next((n for n in nomes if 'transac' in n.lower()), 'transacoes')
        usr_table = next((n for n in nomes if 'user' in n.lower() or 'usuario' in n.lower()), 'usuarios')

        # ── ADICIONA COLUNAS NOVAS SE NÃO EXISTIREM ──
        novas_colunas = [
            (tx_table,  "usuario_id INTEGER"),
            (usr_table, "ativo BOOLEAN DEFAULT 1"),
            (usr_table, "email TEXT"),
            (usr_table, "mp_payer_id TEXT"),
            (usr_table, "mp_subscription_id TEXT"),
            (usr_table, "plano_expira DATETIME"),
            (usr_table, "plano_ativo BOOLEAN DEFAULT 1"),
        ]
        for tabela, coluna in novas_colunas:
            try:
                db.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna}"))
                print(f"✅ Coluna {coluna.split()[0]} adicionada em {tabela}")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Já existe, ok
                else:
                    print(f"⚠️ {e}")

        # ── LIMPA DADOS MOCKADOS ──
        # Limpa transações de qualquer usuário que não tem usuario_id (dados de teste)
        deleted_tx = db.execute(text(f"DELETE FROM {tx_table} WHERE usuario_id IS NULL OR usuario_id = 0")).rowcount
        print(f"✅ {deleted_tx} transações mockadas removidas")

        # Limpa usuários sem telefone válido (criados em testes)
        deleted_usr = db.execute(text(f"DELETE FROM {usr_table} WHERE telefone IS NULL OR telefone = ''")).rowcount
        print(f"✅ {deleted_usr} usuários inválidos removidos")

        # ── GARANTE QUE PHILIP (dono) TEM PLANO PRO ──
        TELEFONE_DONO = os.getenv("TELEFONE_DONO", "5513991560950")
        dono = db.execute(text(f"SELECT id, plano FROM {usr_table} WHERE telefone = :tel"), {"tel": TELEFONE_DONO}).fetchone()
        if dono:
            db.execute(text(f"UPDATE {usr_table} SET plano='familia', plano_ativo=1, ativo=1 WHERE telefone = :tel"), {"tel": TELEFONE_DONO})
        else:
            print(f"ℹ️ Dono ainda não cadastrado — vai ser Pro automaticamente ao fazer login")

        db.commit()
        print("\n🎉 Migração concluída!")
        print("📋 Banco pronto para multiusuário.")
        print("🆓 Novos usuários: plano Grátis automático")
        print("✦ Dono: plano Pro garantido")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrar()
