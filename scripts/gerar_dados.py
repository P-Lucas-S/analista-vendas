"""Gera app/data/vendas.csv: um ano de vendas fictícias do Mercadinho Exemplo.

Padrões embutidos para a análise encontrar: pico em dezembro, bebidas em alta no
calor (out–mar), domingo com meio expediente, entrega crescendo a partir de jun/2026
e uma promoção de café em ago/2026.
"""
import csv, json, math, random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
RAIZ = Path(__file__).resolve().parent.parent / "app" / "data"
produtos = json.loads((RAIZ / "produtos.json").read_text(encoding="utf-8"))
pop = {p["codigo"]: random.uniform(0.4, 2.2) for p in produtos}
for p in produtos:
    if p["categoria"] in ("Padaria", "Hortifrúti") or p["nome"].startswith(("Leite integral", "Arroz branco", "Ovos")):
        pop[p["codigo"]] *= 1.8

ini, fim = date(2025, 11, 1), date(2026, 10, 31)
linhas, vid, d = [], 10000, ini
while d <= fim:
    dow = d.weekday()
    base = 52 * (0.55 if dow == 6 else 1.12 if dow == 5 else 1.0)
    if d.month == 12: base *= 1.35
    if d.month in (1, 2): base *= 0.9
    base *= 1 + 0.03 * math.sin(d.toordinal() / 9)
    n_vendas = max(5, int(random.gauss(base, base * 0.12)))
    p_entrega = 0.18 if d < date(2026, 6, 1) else 0.18 + 0.025 * ((d - date(2026, 6, 1)).days / 30)
    for _ in range(n_vendas):
        vid += 1
        canal = "Entrega" if random.random() < min(p_entrega, 0.42) else "Loja"
        hora = random.choice([7, 8, 9, 10, 11, 12] if dow == 6 else [7, 8, 9, 10, 11, 12, 16, 17, 18, 19, 20])
        pag = random.choices(["Pix", "Cartão", "Dinheiro"], [0.5, 0.35, 0.15] if d.year == 2026 else [0.4, 0.38, 0.22])[0]
        for p in random.sample(produtos, random.randint(1, 6)):
            peso = pop[p["codigo"]]
            if p["categoria"] == "Bebidas" and d.month in (10, 11, 12, 1, 2, 3): peso *= 1.7
            if p["nome"].startswith("Café") and d.month == 8: peso *= 2.4
            if random.random() > min(0.95, peso / 2.6):
                continue
            preco = p["preco"] * (0.8 if p["nome"].startswith("Café") and d.month == 8 else 1) * (1 + 0.004 * (d - ini).days / 30)
            qtd = random.choices([1, 2, 3], [0.7, 0.22, 0.08])[0]
            linhas.append([vid, d.isoformat(), hora, canal, pag, p["codigo"], p["nome"], p["categoria"], qtd, f"{preco:.2f}", f"{preco * qtd:.2f}"])
    d += timedelta(days=1)

with open(RAIZ / "vendas.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["venda_id", "data", "hora", "canal", "pagamento", "codigo", "produto", "categoria", "quantidade", "preco_unitario", "total"])
    w.writerows(linhas)
print(len(linhas), "linhas")
