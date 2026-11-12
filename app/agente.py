"""Analista de vendas: o Gemini escolhe funções de análise e explica o resultado."""
from __future__ import annotations

import os
import re
import unicodedata

from .analise import CATEGORIAS, FERRAMENTAS, FIM, INICIO, executar

MAX_PASSOS = 5

SISTEMA = f"""Você é um analista de dados que ajuda a dona do Mercadinho Exemplo (loja de bairro fictícia) a entender as vendas.
Os dados vão de {INICIO.isoformat()} a {FIM.isoformat()}. Considere {FIM.isoformat()} como "hoje" ao interpretar "este mês", "mês passado", "este ano".
Categorias: {", ".join(CATEGORIAS)}. Canais: Loja e Entrega. Pagamentos: Pix, Cartão, Dinheiro.

Regras:
- Todo número da resposta tem que vir de uma função. Nunca estime nem invente.
- Use quantas funções precisar (por exemplo, evolução e depois distribuição) antes de responder.
- Responda em português, em até 5 frases: comece pela resposta direta com o número, diga o período, aponte o que chama atenção e termine com uma sugestão prática ou uma pergunta de aprofundamento.
- Se a pergunta não puder ser respondida com estes dados (lucro, estoque, clientes individuais), diga isso e sugira o que dá para analisar.
- Não use tabelas nem markdown pesado; o gráfico aparece sozinho na tela."""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


class Gemini:
    def __init__(self, api_key: str, modelo: str):
        from google import genai
        from google.genai import types
        self.t = types
        self.client = genai.Client(api_key=api_key)
        self.modelo = modelo
        self.config = types.GenerateContentConfig(
            system_instruction=SISTEMA, temperature=0.2,
            tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**f) for f in FERRAMENTAS])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))

    def responder(self, historico: list, pergunta: str) -> tuple[str, list[dict], list]:
        t = self.t
        conteudo = list(historico) + [t.Content(role="user", parts=[t.Part.from_text(text=pergunta)])]
        passos, texto = [], ""
        for _ in range(MAX_PASSOS):
            r = self.client.models.generate_content(model=self.modelo, contents=conteudo, config=self.config)
            if not r.candidates or not r.candidates[0].content:
                texto = "Não consegui analisar agora. Pode reformular a pergunta?"
                break
            conteudo.append(r.candidates[0].content)
            chamadas = r.function_calls or []
            if not chamadas:
                texto = r.text or ""
                break
            partes = []
            for fc in chamadas:
                args = dict(fc.args or {})
                res = executar(fc.name, args)
                passos.append({"funcao": fc.name, "argumentos": args, "resultado": res})
                envio = {k: v for k, v in res.items() if k != "grafico"}  # o modelo não precisa dos vetores do gráfico
                partes.append(t.Part.from_function_response(name=fc.name, response={"result": envio}))
            conteudo.append(t.Content(role="user", parts=partes))
        else:
            texto = "A análise ficou longa demais. Tente uma pergunta mais específica."
        return texto.strip(), passos, conteudo[-24:]


class Simulado:
    """Sem GEMINI_API_KEY: escolhe a função por palavras-chave. Serve para testes e para a página abrir sem chave."""

    def responder(self, historico: list, pergunta: str) -> tuple[str, list[dict], list]:
        m = _norm(pergunta)
        cat = next((c for c in CATEGORIAS if _norm(c) in m), None)
        if any(w in m for w in ("mais vend", "mais fatur", "ranking", "top", "produtos")):
            nome, args = "ranking", {"n": 5, "categoria": cat}
        elif "canal" in m or "entrega" in m:
            nome, args = "evolucao", {"metrica": "vendas", "granularidade": "mes", "canal": "Entrega"}
        elif "dia da semana" in m or "dias da semana" in m:
            nome, args = "distribuicao", {"dimensao": "dia_semana", "metrica": "vendas"}
        elif "pagamento" in m or "pix" in m:
            nome, args = "distribuicao", {"dimensao": "pagamento"}
        elif "categoria" in m:
            nome, args = "distribuicao", {"dimensao": "categoria"}
        elif "mes" in m or "evolu" in m or "longo do ano" in m:
            nome, args = "evolucao", {"granularidade": "mes", "categoria": cat}
        else:
            nome, args = "resumo", {"categoria": cat}
        args = {k: v for k, v in args.items() if v is not None}
        res = executar(nome, args)
        passo = {"funcao": nome, "argumentos": args, "resultado": res}
        corpo = {k: v for k, v in res.items() if k != "grafico"}
        txt = "(modo simulado, sem IA) Resultado de " + nome + ": " + re.sub(r"[{}\[\]']", "", str(corpo))[:400]
        return txt, [passo], historico


def criar_modelo():
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    return Gemini(chave, os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")) if chave else Simulado()
