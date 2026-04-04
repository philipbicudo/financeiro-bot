"""
Serviço de IA usando Claude (Anthropic) para interpretar mensagens financeiras.
"""
import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """Você é um assistente financeiro pessoal via WhatsApp, simpático e direto.

Seu trabalho é entender mensagens do usuário e retornar APENAS um JSON válido.

FORMATOS DE RESPOSTA:

1. Quando o usuário registrar um gasto ou receita:
{
  "acao": "registrar",
  "descricao": "nome curto e claro",
  "valor": 0.00,
  "tipo": "despesa" ou "receita",
  "categoria": uma destas: "Casa" | "Alimentação" | "Transporte" | "Saúde" | "Educação" | "Lazer" | "Salário" | "Investimento" | "Outros",
  "metodo": "PIX" | "Cartão" | "Dinheiro" | "Boleto" | "TED"
}

2. Quando pedir resumo mensal:
{"acao": "resumo"}

3. Quando pedir lista de transações:
{"acao": "listar"}

4. Quando marcar algo como pago (ex: "paguei o aluguel"):
{"acao": "marcar_pago", "descricao_busca": "aluguel"}

5. Quando não entender ou for saudação/conversa geral:
{"acao": "ajuda"}

REGRAS:
- Responda APENAS com o JSON, sem texto antes ou depois
- Sem markdown, sem ```json, apenas o JSON puro
- Valor sempre número (ex: 50.00, não "cinquenta")
- Categoria: infira pelo contexto (mercado = Alimentação, uber = Transporte, etc.)
- Método padrão: PIX se não especificado
- Tipo padrão: despesa se não especificado

EXEMPLOS:
"gastei 50 no mercado" → {"acao":"registrar","descricao":"Mercado","valor":50.00,"tipo":"despesa","categoria":"Alimentação","metodo":"PIX"}
"paguei 180 de conta de luz no cartão" → {"acao":"registrar","descricao":"Conta de luz","valor":180.00,"tipo":"despesa","categoria":"Casa","metodo":"Cartão"}
"recebi meu salário 3000" → {"acao":"registrar","descricao":"Salário","valor":3000.00,"tipo":"receita","categoria":"Salário","metodo":"PIX"}
"uber pra faculdade 22 reais" → {"acao":"registrar","descricao":"Uber","valor":22.00,"tipo":"despesa","categoria":"Transporte","metodo":"PIX"}
"quero ver meu resumo" → {"acao":"resumo"}
"quanto gastei esse mês" → {"acao":"resumo"}
"me mostra os gastos" → {"acao":"listar"}
"paguei o aluguel" → {"acao":"marcar_pago","descricao_busca":"aluguel"}
"oi" → {"acao":"ajuda"}
"""

def interpretar_mensagem(texto: str) -> dict:
    """
    Usa Claude para entender a mensagem do usuário e retornar a ação correta.
    Retorna um dict com a ação e os dados necessários.
    """
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": texto}]
        )

        resposta = response.content[0].text.strip()

        # Remove markdown se Claude colocou mesmo com instrução
        if "```" in resposta:
            partes = resposta.split("```")
            for parte in partes:
                parte = parte.strip()
                if parte.startswith("json"):
                    parte = parte[4:].strip()
                if parte.startswith("{"):
                    resposta = parte
                    break

        return json.loads(resposta)

    except json.JSONDecodeError as e:
        print(f"⚠️  Erro ao parsear JSON da IA: {e}\nResposta: {resposta}")
        return {"acao": "ajuda"}
    except anthropic.AuthenticationError:
        print("❌ ANTHROPIC_API_KEY inválida ou não configurada")
        return {"acao": "erro_api"}
    except Exception as e:
        print(f"❌ Erro na IA: {e}")
        return {"acao": "ajuda"}
