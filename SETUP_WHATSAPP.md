# 📱 Guia de Configuração — Evolution API + WhatsApp

## O que é a Evolution API?

É um projeto open source gratuito que conecta qualquer aplicação ao WhatsApp
sem pagar a API oficial do Meta. Funciona via WhatsApp Web (como se fosse
você logado no celular, mas automatizado).

Repositório: https://github.com/EvolutionAPI/evolution-api

---

## Passo 1 — Instalar Docker

A Evolution API roda dentro do Docker. Instale em:
- Windows/Mac: https://www.docker.com/products/docker-desktop
- Ubuntu: `sudo apt install docker.io docker-compose`

---

## Passo 2 — Subir a Evolution API

```bash
# Cria uma pasta para a Evolution
mkdir evolution && cd evolution

# Baixa o docker-compose pronto
curl -O https://raw.githubusercontent.com/EvolutionAPI/evolution-api/main/docker-compose.yaml

# Sobe o servidor
docker-compose up -d
```

Aguarda 30 segundos e acessa: http://localhost:8080

---

## Passo 3 — Criar a instância do bot

Acesse no navegador:
http://localhost:8000/webhook/setup/criar-instancia

Ou via terminal:
```bash
curl -X POST http://localhost:8000/webhook/setup/criar-instancia
```

---

## Passo 4 — Conectar seu WhatsApp

Acesse no navegador:
http://localhost:8000/webhook/setup/qrcode

Vai aparecer um JSON com uma imagem base64 do QR Code.
Copie o valor do campo "base64" e cole neste site para visualizar:
https://base64.guru/converter/decode/image

Então escaneie com o WhatsApp do seu celular
(assim como você escaneia o WhatsApp Web).

---

## Passo 5 — Testar sem WhatsApp

Enquanto configura, você pode testar o bot direto pelo navegador:
http://localhost:8000/docs

Vá em `POST /webhook/testar` e envie mensagens como:
- "gastei 50 no mercado"
- "recebi meu salário de 3000"
- "quero ver meu resumo"

---

## Passo 6 — Configurar o webhook (em produção)

Depois de fazer o deploy na Railway/Render, rode:

```bash
curl -X POST "http://localhost:8000/webhook/setup/configurar-webhook?url_publica=https://SEU-APP.railway.app/webhook/whatsapp"
```

Isso diz à Evolution API para onde enviar as mensagens que chegarem.

---

## Resumo do fluxo

```
Celular → WhatsApp → Evolution API (porta 8080)
                            ↓ webhook
                     Seu backend FastAPI (porta 8000)
                            ↓ interpreta
                       Claude AI (Anthropic)
                            ↓ salva
                        Banco de dados
                            ↓ responde
                     Evolution API → WhatsApp → Celular
```

---

## Variáveis de ambiente necessárias (.env)

```
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=change-me          ← mude no docker-compose.yaml
EVOLUTION_INSTANCE=financeiro-bot
ANTHROPIC_API_KEY=sua_chave_aqui
```

---

## Problemas comuns

**Evolution API não responde:**
- Verifique se o Docker está rodando: `docker ps`
- Verifique os logs: `docker-compose logs -f`

**QR Code expirou:**
- Acesse `/webhook/setup/qrcode` novamente — gera um novo

**Mensagens não chegam no webhook:**
- Confirme que rodou o passo 6 (configurar-webhook)
- Em desenvolvimento local, use o ngrok para expor sua porta:
  `ngrok http 8000`  → use a URL https gerada como url_publica
