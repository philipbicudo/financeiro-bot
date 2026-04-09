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

        # 1. Limpa todas as transações existentes (dados de teste)
        db.execute(text("DELETE FROM transacoes"))
        print("✅ Transações limpas")

        # 2. Limpa usuários antigos
        db.execute(text("DELETE FROM usuarios"))
        print("✅ Usuários limpos")

        # 3. Adiciona coluna usuario_id na tabela transacoes se não existir
        try:
            db.execute(text("ALTER TABLE transacoes ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id)"))
            print("✅ Coluna usuario_id adicionada em transacoes")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Coluna usuario_id já existe em transacoes")
            else:
                print(f"⚠️ Erro ao adicionar coluna: {e}")

        # 4. Adiciona coluna ativo em usuarios se não existir
        try:
            db.execute(text("ALTER TABLE usuarios ADD COLUMN ativo BOOLEAN DEFAULT 1"))
            print("✅ Coluna ativo adicionada em usuarios")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Coluna ativo já existe")
            else:
                print(f"⚠️ {e}")

        # 5. Adiciona coluna email em usuarios se não existir
        try:
            db.execute(text("ALTER TABLE usuarios ADD COLUMN email TEXT"))
            print("✅ Coluna email adicionada")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Coluna email já existe")

        # 6. Adiciona coluna mp_payer_id se não existir
        try:
            db.execute(text("ALTER TABLE usuarios ADD COLUMN mp_payer_id TEXT"))
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
