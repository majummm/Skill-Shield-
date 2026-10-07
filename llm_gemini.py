

import json
import os

from ml_core import FEATURES, CATEGORIES

_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


class GeminiNotConfigured(RuntimeError):
    pass


def _get_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiNotConfigured(
            "GOOGLE_API_KEY nao configurada. Defina a variavel de ambiente "
            "(veja o .env.example) com uma chave criada em "
            "https://aistudio.google.com/apikey"
        )
    from google import genai
    return genai.Client(api_key=api_key)


_FEATURE_DESCRICOES = {
    "identified_risk": "a propria descricao do usuario ja demonstra que ele percebe que ha algum risco na tarefa",
    "protected_data": "o usuario ja demonstra cuidado em nao expor dados pessoais sensiveis",
    "avoided_sharing": "o usuario ja demonstra que evitaria compartilhar a informacao sem cuidados adicionais",
    "used_anonymization": "o usuario ja menciona ou demonstra intencao de anonimizar/mascarar dados",
    "checked_policy": "o usuario ja menciona verificar a politica da empresa antes de agir",
    "verified_information": "o usuario ja demonstra que verificaria a confiabilidade da informacao/fonte",
    "recognized_social_engineering": "o usuario ja demonstra reconhecer sinais de golpe/engenharia social, se aplicavel",
    "questioned_ai": "o usuario ja demonstra que questionaria/verificaria a resposta da IA antes de confiar nela",
    "considered_intellectual_property": "o usuario ja demonstra preocupacao com direitos autorais/propriedade intelectual, se aplicavel",
}


def _montar_prompt(tarefa_descrita: str) -> str:
    categorias_txt = "\n".join(f"- {c}" for c in CATEGORIES)
    caracteristicas_txt = "\n".join(f"- {k}: {v}" for k, v in _FEATURE_DESCRICOES.items())
    return f"""Voce e um assistente de seguranca da informacao especializado em uso de IA no trabalho.

Um funcionario descreveu a seguinte tarefa que pretende resolver usando uma
ferramenta de IA (ChatGPT, Gemini, Copilot etc.):

\"\"\"{tarefa_descrita}\"\"\"

Faca tres coisas:

1. Classifique essa tarefa em UMA destas categorias de risco:
{categorias_txt}

2. Para cada um dos pontos abaixo, diga se a propria descricao do usuario JA
demonstra esse cuidado (true) ou nao (false) — avalie apenas o que foi
escrito, sem presumir nada que a pessoa nao disse:
{caracteristicas_txt}

3. Escreva um "prompt seguro": um texto pronto para o usuario colar
diretamente em uma ferramenta de IA generativa para realizar a tarefa dele
COM SEGURANCA. O prompt deve:
- pedir explicitamente que nenhum dado pessoal real (nomes, CPFs, emails,
  numeros de documento, dados financeiros) seja incluido — usar
  marcadores genericos tipo [NOME], [CPF] no lugar;
- incluir instrucoes de anonimizacao/mascaramento quando fizer sentido
  para a tarefa;
- deixar claro o escopo exato da tarefa, para evitar que a IA peca ou
  assuma dados além do necessário;
- incluir um lembrete relevante para a categoria identificada (ex.:
  checar política interna, verificar a fonte, não reproduzir obra
  protegida, desconfiar de pedidos incomuns, conforme o caso).
O prompt deve ser directamente utilizavel, escrito como instrucao para a
IA que vai executar a tarefa — nao um resumo nem uma explicacao sobre o
prompt.

Responda apenas com um objeto JSON com exatamente estas chaves:
"categoria" (uma string, exatamente igual a uma das categorias listadas),
"caracteristicas" (objeto com as 9 chaves acima, valores true/false), e
"prompt_seguro" (string com o prompt pronto)."""


def _schema():
    from google.genai import types
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "categoria": types.Schema(type=types.Type.STRING, enum=CATEGORIES),
            "caracteristicas": types.Schema(
                type=types.Type.OBJECT,
                properties={f: types.Schema(type=types.Type.BOOLEAN) for f in FEATURES},
                required=FEATURES,
            ),
            "prompt_seguro": types.Schema(type=types.Type.STRING),
        },
        required=["categoria", "caracteristicas", "prompt_seguro"],
    )


def analisar_tarefa(tarefa_descrita: str) -> dict:
    """Retorna {"categoria": str, "caracteristicas": {feature: 0/1}, "prompt_seguro": str}.
    Levanta excecao em caso de erro — o app.py decide como avisar o usuario,
    nunca inventamos um resultado quando a chamada falha."""
    from google.genai import types

    client = _get_client()
    prompt = _montar_prompt(tarefa_descrita)

    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_schema(),
        ),
    )
    dados = json.loads(response.text)

    categoria = dados.get("categoria")
    if categoria not in CATEGORIES:
        # fallback de seguranca: se a LLM devolver algo fora do enum por
        # qualquer motivo, nao travamos o fluxo, so caimos na primeira categoria.
        categoria = CATEGORIES[0]

    caracteristicas_brutas = dados.get("caracteristicas", {})
    caracteristicas = {f: int(bool(caracteristicas_brutas.get(f, False))) for f in FEATURES}

    prompt_seguro = (dados.get("prompt_seguro") or "").strip()
    if not prompt_seguro:
        raise ValueError("A IA nao retornou um prompt_seguro valido.")

    return {"categoria": categoria, "caracteristicas": caracteristicas, "prompt_seguro": prompt_seguro}
