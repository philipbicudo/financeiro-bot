#!/usr/bin/env python3
# scripts/migrar_multiusuario.py
# Roda UMA VEZ para migrar o banco para multiusuário
# Comando: python scripts/migrar_multiusuario.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, SessionLocal

def migrar():
    db = SessionLocal()
    try:
        print("🔄 Iniciando migração para multiusuário...")

        # 0. Cria tabelas se não existirem (via SQLAlchemy models)
        from app.models import usuario, transacao
        from app.database import Base, engine as _engine
        Base.metadata.create_all(bind=_engine)
        print("✅ Tabelas criadas/verificadas")

        # Descobre nome real das tabelas
        tabelas = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        nomes = [t[0] for t in tabelas]
        print(f"📋 Tabelas encontradas: {nomes}")

        # 1. Limpa transações
        tx_table = next((n for n in nomes if 'transac' in n.lower()), None)
        if tx_table:
            db.execute(text(f"DELETE FROM {tx_table}"))
            print(f"✅ {tx_table} limpa")

        # 2. Limpa usuários
        usr_table = next((n for n in nomes if 'user' in n.lower() or 'usuario' in n.lower()), None)
        if usr_table:
            db.execute(text(f"DELETE FROM {usr_table}"))
            print(f"✅ {usr_table} limpa")

        # 3. Adiciona coluna usuario_id na tabela transacoes se não existir
        try:
            tx_t = next((n for n in nomes if 'transac' in n.lower()), 'transacoes')
            db.execute(text(f"ALTER TABLE {tx_t} ADD COLUMN usuario_id INTEGER"))
            print("✅ Coluna usuario_id adicionada em transacoes")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Coluna usuario_id já existe em transacoes")
            else:
                print(f"⚠️ Erro ao adicionar coluna: {e}")

        # 4. Adiciona coluna ativo em usuarios se não existir
        try:
            usr_t = next((n for n in nomes if 'user' in n.lower() or 'usuario' in n.lower()), 'usuarios')
            db.execute(text(f"ALTER TABLE {usr_t} ADD COLUMN ativo BOOLEAN DEFAULT 1"))
            print("✅ Coluna ativo adicionada em usuarios")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Coluna ativo já existe")
            else:
                print(f"⚠️ {e}")

        # 5. Adiciona coluna email em usuarios se não existir
        try:
            db.execute(text(f"ALTER TABLE {usr_t} ADD COLUMN email TEXT"))
            print("✅ Coluna email adicionada")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Coluna email já existe")

        # 6. Adiciona coluna mp_payer_id se não existir
        try:
            db.execute(text(f"ALTER TABLE {usr_t} ADD COLUMN mp_payer_id TEXT"))
            print("✅ Coluna mp_payer_id adicionada")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Coluna mp_payer_id já existe")

        db.commit()
        print("\n🎉 Migração concluída com sucesso!")
        print("📋 Banco limpo e pronto para multiusuário.")
        print("🚀 Cada usuário verá apenas seus próprios dados.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro na migração: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrar()
