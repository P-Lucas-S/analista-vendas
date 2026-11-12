from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import agente, analise
from app.main import app

c = TestClient(app)


def test_funcoes_principais():
    assert analise.resumo("2026-10-01", "2026-10-31")["vendas"] > 0
    assert len(analise.ranking(n=5)["ranking"]) == 5
    ev = analise.evolucao(granularidade="mes")
    assert len(ev["serie"]) == 12 and ev["maior"]["periodo"] == "dez/25"
    canais = {v["canal"] for v in analise.distribuicao("canal")["valores"]}
    assert canais == {"Loja", "Entrega"}
    comp = analise.comparar("categoria", "2026-01-01", "2026-03-31", "2026-07-01", "2026-09-30")
    assert comp["comparacao"][-1]["categoria"] == "Bebidas"  # cai fora do calor


def test_erros_viram_resultado():
    assert "erro" in analise.executar("distribuicao", {"dimensao": "cor"})
    assert "erro" in analise.executar("nao_existe", {})


def test_api_modo_simulado():
    j = c.post("/api/perguntar", json={"pergunta": "Quais os 5 produtos que mais faturaram?"}).json()
    assert j["passos"][0]["funcao"] == "ranking"
    assert j["graficos"] and j["graficos"][0]["tipo"] == "barra_h"
    assert "grafico" not in j["passos"][0]["resultado"]
    assert c.get("/api/visao-geral").json()["linhas"] > 1000


def test_laco_gemini():
    from google.genai import types
    g = agente.Gemini.__new__(agente.Gemini)
    g.t, g.modelo, g.config = types, "x", None
    rodadas = [
        SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role="model", parts=[types.Part.from_function_call(name="distribuicao", args={"dimensao": "canal"})]))],
                        function_calls=[types.FunctionCall(name="distribuicao", args={"dimensao": "canal"})], text=None),
        SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role="model", parts=[types.Part.from_text(text="A loja vende 79%.")]))],
                        function_calls=None, text="A loja vende 79%."),
    ]
    enviados = []

    def gerar(model, contents, config):
        enviados.append(list(contents))
        return rodadas.pop(0)

    g.client = SimpleNamespace(models=SimpleNamespace(generate_content=gerar))
    texto, passos, hist = g.responder([], "Quanto vem da entrega?")
    assert texto == "A loja vende 79%."
    resposta_funcao = enviados[1][-1].parts[0].function_response.response["result"]
    assert "grafico" not in resposta_funcao and "valores" in resposta_funcao
    assert "grafico" in passos[0]["resultado"]
