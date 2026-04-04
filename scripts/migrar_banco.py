import sqlite3
import os

db_path = os.getenv("DATABASE_URL", "sqlite:///./financeiro.db").replace("sqlite:///", "")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Adiciona coluna usuario_id se não existir
try:
    cursor.execute("ALTER TABLE transacoes ADD COLUMN usuario_id INTEGER")
    print("✅ Coluna usuario_id adicionada!")
except Exception as e:
    print(f"ℹ️ {e}")

# Cria tabela usuarios se não existir
cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR NOT NULL,
    telefone VARCHAR UNIQUE NOT NULL,
    email VARCHAR UNIQUE,
    senha_hash VARCHAR,
    plano VARCHAR DEFAULT 'gratis',
    plano_ativo BOOLEAN DEFAULT 1,
    plano_expira DATETIME,
    mp_subscription_id VARCHAR,
    mp_payer_id VARCHAR,
    ativo BOOLEAN DEFAULT 1,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    atualizado DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
print("✅ Tabela usuarios ok!")

conn.commit()
conn.close()
print("✅ Migração concluída!")
