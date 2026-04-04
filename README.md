# 💰 Assistente Financeiro Bot

Bot de WhatsApp com IA para gestão financeira pessoal.

---

## 🚀 Como rodar em 5 passos

### 1. Instalar dependências
```bash
cd financeiro-bot
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente
```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Abra o .env e coloque sua chave da Anthropic
# Pegue em: https://console.anthropic.com/
ANTHROPIC_API_KEY=sua_chave_aqui
```

### 3. Popular banco com dados de teste (opcional)
```bash
python scripts/popular_banco.py
```

### 4. Rodar o servidor
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Acessar a documentação interativa
Abra no navegador: **http://localhost:8000/docs**

Lá você pode testar todas as rotas sem precisar do WhatsApp!

---

## 📁 Estrutura do projeto

```
financeiro-bot/
├── app/
│   ├── main.py          # Ponto de entrada da API
│   ├── database.py      # Conexão com banco de dados
│   ├── models/
│   │   └── transacao.py # Estrutura da tabela no banco
│   ├── schemas/
│   │   └── transacao.py # Validação de dados (Pydantic)
│   └── routers/
│       ├── transacoes.py # CRUD de transações
│       ├── resumo.py     # Resumo mensal
│       └── webhook.py    # Recebe mensagens do WhatsApp
├── scripts/
│   └── popular_banco.py # Dados de teste
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔌 Rotas disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/transacoes/` | Lista todas as transações |
| POST | `/transacoes/` | Cria uma transação |
| GET | `/transacoes/{id}` | Busca por ID |
| PATCH | `/transacoes/{id}/pagar` | Marca como pago |
| DELETE | `/transacoes/{id}` | Remove transação |
| GET | `/resumo/` | Resumo mensal em JSON |
| GET | `/resumo/texto` | Resumo formatado para WhatsApp |
| POST | `/webhook/whatsapp` | Recebe mensagens (Evolution API) |
| POST | `/webhook/testar` | Testa o bot sem WhatsApp |

---

## 🤖 Como o bot entende as mensagens

O Claude AI interpreta as mensagens e detecta automaticamente:

| Mensagem | Ação |
|----------|------|
| "gastei 50 no mercado" | Registra despesa R$50 - Alimentação |
| "recebi salário de 3000" | Registra receita R$3000 - Salário |
| "paguei 180 de conta de luz" | Registra despesa R$180 - Casa |
| "quero ver meu resumo" | Envia resumo mensal |
| "mostre meus gastos" | Lista últimas transações |

---

## 📦 Próximas fases

- **Fase 2**: Integração com Evolution API (WhatsApp)
- **Fase 3**: Geração de PDF do resumo mensal
- **Fase 4**: Dashboard web com Streamlit
