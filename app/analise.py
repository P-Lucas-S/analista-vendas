"""Funções de análise sobre app/data/vendas.csv.

O modelo nunca executa código: ele escolhe uma destas funções e os
parâmetros, e a resposta sai dos números que elas calculam. Cada função
devolve os dados e, quando faz sentido, um gráfico pronto para a página.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

DF = pd.read_csv(Path(__file__).parent / "data" / "vendas.csv", parse_dates=["data"])
INICIO, FIM = DF["data"].min().date(), DF["data"].max().date()
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CATEGORIAS = sorted(DF["categoria"].unique())
METRICAS = {"faturamento", "quantidade", "vendas", "ticket_medio"}


def brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _periodo(inicio: str | None, fim: str | None) -> tuple[date, date]:
    a = date.fromisoformat(inicio) if inicio else INICIO
    b = date.fromisoformat(fim) if fim else FIM
    if a > b:
        a, b = b, a
    return max(a, INICIO), min(b, FIM)


def _filtro(inicio=None, fim=None, categoria=None, canal=None) -> tuple[pd.DataFrame, date, date]:
    a, b = _periodo(inicio, fim)
    d = DF[(DF["data"].dt.date >= a) & (DF["data"].dt.date <= b)]
    if categoria:
        d = d[d["categoria"].str.lower() == categoria.lower()]
    if canal:
        d = d[d["canal"].str.lower() == canal.lower()]
    return d, a, b


def _metrica(g, metrica: str) -> pd.Series:
    if metrica == "faturamento":
        return g["total"].sum()
    if metrica == "quantidade":
        return g["quantidade"].sum()
    if metrica == "vendas":
        return g["venda_id"].nunique()
    if metrica == "ticket_medio":
        return g["total"].sum() / g["venda_id"].nunique()
    raise ValueError(f"métrica inválida: {metrica}")


def _fmt(metrica: str, v: float) -> str:
    return brl(v) if metrica in ("faturamento", "ticket_medio") else f"{int(round(v)):,}".replace(",", ".")


def resumo(inicio=None, fim=None, categoria=None, canal=None) -> dict:
    d, a, b = _filtro(inicio, fim, categoria, canal)
    dias = (b - a).days + 1
    ant, _, _ = _filtro((pd.Timestamp(a) - pd.Timedelta(days=dias)).date().isoformat(), (pd.Timestamp(a) - pd.Timedelta(days=1)).date().isoformat(), categoria, canal)
    fat, n = float(d["total"].sum()), int(d["venda_id"].nunique())
    out = {"periodo": f"{a.isoformat()} a {b.isoformat()}", "faturamento": brl(fat), "vendas": n,
           "ticket_medio": brl(fat / n) if n else "—", "itens_vendidos": int(d["quantidade"].sum())}
    if len(ant) and (pd.Timestamp(a) - pd.Timedelta(days=dias)).date() >= INICIO:
        f0 = float(ant["total"].sum())
        out["variacao_vs_periodo_anterior"] = f"{(fat / f0 - 1) * 100:+.1f}%".replace(".", ",")
    return out


def ranking(metrica="faturamento", inicio=None, fim=None, n=10, categoria=None, ordem="maiores") -> dict:
    d, a, b = _filtro(inicio, fim, categoria)
    s = _metrica(d.groupby("produto"), metrica).sort_values(ascending=(ordem == "menores")).head(int(n or 10))
    return {"periodo": f"{a} a {b}", "metrica": metrica,
            "ranking": [{"produto": k, "valor": _fmt(metrica, v)} for k, v in s.items()],
            "grafico": {"tipo": "barra_h", "titulo": f"{'Menos' if ordem == 'menores' else 'Mais'} vendidos por {metrica.replace('_', ' ')}",
                        "rotulos": list(s.index), "valores": [round(float(v), 2) for v in s.values]}}


def evolucao(metrica="faturamento", granularidade="mes", inicio=None, fim=None, categoria=None, canal=None) -> dict:
    d, a, b = _filtro(inicio, fim, categoria, canal)
    regra = {"dia": "D", "semana": "W-MON", "mes": "MS"}.get(granularidade, "MS")
    s = d.groupby(pd.Grouper(key="data", freq=regra)).apply(lambda g: _metrica(g, metrica) if len(g) else 0.0)
    if granularidade == "mes":
        rot = [f"{MESES[t.month - 1]}/{str(t.year)[2:]}" for t in s.index]
    else:
        rot = [t.strftime("%d/%m") for t in s.index]
    serie = [{"periodo": r, "valor": _fmt(metrica, v)} for r, v in zip(rot, s.values)]
    pico = int(s.values.argmax()) if len(s) else 0
    return {"periodo": f"{a} a {b}", "metrica": metrica, "serie": serie[-60:],
            "maior": serie[pico] if serie else None, "menor": serie[int(s.values.argmin())] if serie else None,
            "grafico": {"tipo": "linha", "titulo": f"{metrica.replace('_', ' ').capitalize()} por {dict(mes='mês').get(granularidade, granularidade)}" + (f" · {categoria}" if categoria else "") + (f" · {canal}" if canal else ""),
                        "rotulos": rot[-60:], "valores": [round(float(v), 2) for v in s.values][-60:]}}


def distribuicao(dimensao="categoria", metrica="faturamento", inicio=None, fim=None) -> dict:
    d, a, b = _filtro(inicio, fim)
    if dimensao == "dia_semana":
        chave = d["data"].dt.weekday
    elif dimensao in ("categoria", "canal", "pagamento", "hora"):
        chave = d[dimensao]
    else:
        raise ValueError(f"dimensão inválida: {dimensao}")
    s = _metrica(d.groupby(chave), metrica)
    if dimensao == "dia_semana":
        s.index = [DIAS[i] for i in s.index]
    elif dimensao == "hora":
        s.index = [f"{int(h)}h" for h in s.index]
    else:
        s = s.sort_values(ascending=False)
    total = float(s.sum()) if metrica != "ticket_medio" else None
    return {"periodo": f"{a} a {b}", "dimensao": dimensao, "metrica": metrica,
            "valores": [{dimensao: k, "valor": _fmt(metrica, v), **({"participacao": f"{v / total * 100:.1f}%".replace(".", ",")} if total else {})} for k, v in s.items()],
            "grafico": {"tipo": "barra", "titulo": f"{metrica.replace('_', ' ').capitalize()} por {dimensao.replace('_', ' ')}",
                        "rotulos": [str(k) for k in s.index], "valores": [round(float(v), 2) for v in s.values]}}


def comparar(dimensao, a_inicio, a_fim, b_inicio, b_fim, metrica="faturamento") -> dict:
    if dimensao not in ("categoria", "canal", "pagamento", "produto"):
        raise ValueError(f"dimensão inválida: {dimensao}")
    da, a1, a2 = _filtro(a_inicio, a_fim)
    db, b1, b2 = _filtro(b_inicio, b_fim)
    sa, sb = _metrica(da.groupby(dimensao), metrica), _metrica(db.groupby(dimensao), metrica)
    t = pd.DataFrame({"a": sa, "b": sb}).fillna(0)
    t["var"] = (t["b"] / t["a"].where(t["a"] != 0) - 1) * 100
    t = t.sort_values("var", ascending=False, key=lambda c: c.fillna(-1e9))
    if dimensao == "produto":
        t = pd.concat([t.head(5), t.tail(5)])
    linhas = [{dimensao: k, "periodo_a": _fmt(metrica, r.a), "periodo_b": _fmt(metrica, r.b),
               "variacao": "novo" if pd.isna(r["var"]) else f"{r['var']:+.1f}%".replace(".", ",")} for k, r in t.iterrows()]
    return {"periodo_a": f"{a1} a {a2}", "periodo_b": f"{b1} a {b2}", "metrica": metrica, "comparacao": linhas,
            "grafico": {"tipo": "barra", "titulo": f"Variação de {metrica.replace('_', ' ')} (%) por {dimensao}",
                        "rotulos": [str(k) for k in t.index], "valores": [round(float(v), 1) if not pd.isna(v) else 0 for v in t["var"]]}}


FUNCOES = {"resumo": resumo, "ranking": ranking, "evolucao": evolucao, "distribuicao": distribuicao, "comparar": comparar}

_data = {"type": "string", "description": "Data no formato AAAA-MM-DD"}
_metr = {"type": "string", "enum": sorted(METRICAS)}
FERRAMENTAS = [
    {"name": "resumo", "description": "Faturamento, número de vendas, ticket médio e variação contra o período anterior de mesmo tamanho.",
     "parameters_json_schema": {"type": "object", "properties": {"inicio": _data, "fim": _data, "categoria": {"type": "string", "enum": CATEGORIAS}, "canal": {"type": "string", "enum": ["Loja", "Entrega"]}}}},
    {"name": "ranking", "description": "Ranking de produtos por uma métrica (mais ou menos vendidos).",
     "parameters_json_schema": {"type": "object", "properties": {"metrica": _metr, "inicio": _data, "fim": _data, "n": {"type": "integer"}, "categoria": {"type": "string", "enum": CATEGORIAS}, "ordem": {"type": "string", "enum": ["maiores", "menores"]}}}},
    {"name": "evolucao", "description": "Série temporal de uma métrica por dia, semana ou mês, opcionalmente filtrada por categoria ou canal.",
     "parameters_json_schema": {"type": "object", "properties": {"metrica": _metr, "granularidade": {"type": "string", "enum": ["dia", "semana", "mes"]}, "inicio": _data, "fim": _data, "categoria": {"type": "string", "enum": CATEGORIAS}, "canal": {"type": "string", "enum": ["Loja", "Entrega"]}}}},
    {"name": "distribuicao", "description": "Divide uma métrica por categoria, canal (Loja/Entrega), forma de pagamento, dia da semana ou hora.",
     "parameters_json_schema": {"type": "object", "properties": {"dimensao": {"type": "string", "enum": ["categoria", "canal", "pagamento", "dia_semana", "hora"]}, "metrica": _metr, "inicio": _data, "fim": _data}, "required": ["dimensao"]}},
    {"name": "comparar", "description": "Compara dois períodos, quebrando por categoria, canal, pagamento ou produto, com a variação percentual.",
     "parameters_json_schema": {"type": "object", "properties": {"dimensao": {"type": "string", "enum": ["categoria", "canal", "pagamento", "produto"]}, "a_inicio": _data, "a_fim": _data, "b_inicio": _data, "b_fim": _data, "metrica": _metr},
                                "required": ["dimensao", "a_inicio", "a_fim", "b_inicio", "b_fim"]}},
]


def executar(nome: str, args: dict) -> dict:
    f = FUNCOES.get(nome)
    if not f:
        return {"erro": f"função desconhecida: {nome}"}
    try:
        return f(**{k: v for k, v in args.items() if v not in (None, "")})
    except Exception as e:
        return {"erro": str(e)}
