"""API e página do analista de vendas."""
from __future__ import annotations

import os
import time
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agente import Simulado, criar_modelo
from .analise import DF, FIM, INICIO, resumo

app = FastAPI(title="Analista de vendas com IA — Mercadinho Exemplo")
STATIC = Path(__file__).parent / "static"
modelo = criar_modelo()
HIST: dict[str, tuple[list, int, float]] = {}
LIMITE_SESSAO = int(os.environ.get("LIMITE_PERGUNTAS_SESSAO", 20))
LIMITE_DIA = int(os.environ.get("LIMITE_PERGUNTAS_DIA", 250))
_uso = {"dia": date.today(), "total": 0}


class Pergunta(BaseModel):
    sessao: str | None = None
    pergunta: str = Field(min_length=2, max_length=400)


@app.post("/api/perguntar")
def perguntar(p: Pergunta):
    agora = time.time()
    for k, (_, _, t) in list(HIST.items()):
        if agora - t > 3600:
            del HIST[k]
    sid = p.sessao if p.sessao in HIST else uuid.uuid4().hex[:12]
    hist, n, _ = HIST.get(sid, ([], 0, agora))
    if _uso["dia"] != date.today():
        _uso.update(dia=date.today(), total=0)
    if _uso["total"] >= LIMITE_DIA or n >= LIMITE_SESSAO:
        return {"sessao": sid, "resposta": "A demonstração atingiu o limite de perguntas. Recarregue a página ou volte amanhã.", "passos": [], "graficos": []}
    _uso["total"] += 1
    try:
        texto, passos, hist = modelo.responder(hist, p.pergunta.strip())
    except Exception as e:
        raise HTTPException(503, f"O modelo não respondeu agora ({type(e).__name__}). Tente de novo em instantes.")
    HIST[sid] = (hist, n + 1, agora)
    graficos = [x["resultado"]["grafico"] for x in passos if isinstance(x.get("resultado"), dict) and "grafico" in x["resultado"]]
    for x in passos:
        if isinstance(x.get("resultado"), dict):
            x["resultado"] = {k: v for k, v in x["resultado"].items() if k != "grafico"}
    return {"sessao": sid, "resposta": texto, "passos": passos, "graficos": graficos[-2:]}


@app.get("/api/visao-geral")
def visao_geral():
    return {"inicio": INICIO.isoformat(), "fim": FIM.isoformat(), "linhas": len(DF), "resumo": resumo()}


@app.get("/api/health")
def health():
    return {"ok": True, "modo": "simulado" if isinstance(modelo, Simulado) else "gemini"}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
