"""
Gerador de dados sintéticos da "Vértice Bebidas Distribuidora".

Distribuidora que vende cervejas, refrigerantes, águas, energéticos, sucos e
destilados para bares, restaurantes, mercados e atacados, com 16 vendedores
em 4 regionais. Dois anos de vendas (2024 e 2025).

Arquivos gerados em data/raw/:
    vendas/vendas_AAAA-MM.csv   um arquivo por mês. Em julho/2024 o ERP foi trocado:
                                jan-jun/2024 seguem o layout ANTIGO (';', vírgula decimal,
                                SKU antigo, desconto em R$, devolução com quantidade negativa)
                                e jul/2024 em diante o layout NOVO (',', SKU novo, desconto
                                em %, preço líquido, tipo de operação, canal).
                                Março/2025 foi reexportado: existe um arquivo "(1)" duplicado.
    metas_2025.xlsx             metas em formato LARGO (um mês por coluna), com nomes dos
                                vendedores em vez do código, valores em texto e linha TOTAL
    vendedores.csv · clientes.json · produtos.csv · tabela_precos.csv · depara_sku.csv

Empresas, pessoas e valores são fictícios.

Uso:
    python scripts/generate_data.py
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 404
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
VENDAS_DIR = RAW_DIR / "vendas"

INICIO, FIM = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")
MIGRACAO_ERP = pd.Timestamp("2024-07-01")
FERIADOS = pd.to_datetime([
    "2024-01-01", "2024-02-12", "2024-02-13", "2024-03-29", "2024-05-01", "2024-05-30", "2024-11-15",
    "2024-11-20", "2024-12-25", "2025-01-01", "2025-03-03", "2025-03-04", "2025-04-18", "2025-04-21",
    "2025-05-01", "2025-06-19", "2025-11-20", "2025-12-25",
])
DIAS_UTEIS = pd.bdate_range(INICIO, FIM, freq="C", holidays=FERIADOS)

REGIONAIS = {"Capital": "Marina Duarte", "Grande SP": "Rogério Tavares", "Interior": "Cláudia Menezes",
             "Litoral": "Fábio Nogueira"}
NOMES_VENDEDORES = ["João Carlos Pereira", "Ana Paula Ribeiro", "Marcos Vinícius Lima", "Juliana Costa",
                    "Ricardo Almeida", "Fernanda Souza", "Thiago Martins", "Patrícia Gomes", "Eduardo Barbosa",
                    "Camila Rocha", "Leonardo Dias", "Beatriz Nunes", "Rafael Moreira", "Larissa Araújo",
                    "Gustavo Henrique", "Simone Freitas", "Diego Cardoso"]

# (categoria, nome, embalagem, preço de lista por caixa em jan/2024, sazonal?)
PRODUTOS = [
    ("Cerveja", "Cerveja Pilsen Original", "Lata 350ml cx 12", 42.0, True),
    ("Cerveja", "Cerveja Pilsen Original", "Garrafa 600ml cx 24", 118.0, True),
    ("Cerveja", "Cerveja Pilsen Original", "Long neck 355ml cx 24", 96.0, True),
    ("Cerveja", "Cerveja Puro Malte", "Lata 350ml cx 12", 52.0, True),
    ("Cerveja", "Cerveja Puro Malte", "Long neck 355ml cx 24", 118.0, True),
    ("Cerveja", "Cerveja IPA Artesanal", "Garrafa 500ml cx 12", 129.0, True),
    ("Cerveja", "Cerveja Zero Álcool", "Lata 350ml cx 12", 48.0, True),
    ("Cerveja", "Chope Pilsen", "Barril 30L", 390.0, True),
    ("Refrigerante", "Refrigerante Cola", "Pet 2L cx 6", 39.0, True),
    ("Refrigerante", "Refrigerante Cola", "Lata 350ml cx 12", 36.0, True),
    ("Refrigerante", "Refrigerante Guaraná", "Pet 2L cx 6", 33.0, True),
    ("Refrigerante", "Refrigerante Guaraná", "Lata 350ml cx 12", 31.0, True),
    ("Refrigerante", "Refrigerante Laranja", "Pet 2L cx 6", 31.0, True),
    ("Refrigerante", "Refrigerante Cola Zero", "Lata 350ml cx 12", 37.0, True),
    ("Água", "Água Mineral sem Gás", "Garrafa 500ml cx 12", 14.0, True),
    ("Água", "Água Mineral com Gás", "Garrafa 500ml cx 12", 17.0, True),
    ("Água", "Água Mineral sem Gás", "Galão 20L", 16.0, False),
    ("Energético", "Energético Tradicional", "Lata 250ml cx 6", 39.0, False),
    ("Energético", "Energético Sem Açúcar", "Lata 250ml cx 6", 41.0, False),
    ("Energético", "Energético Tropical", "Lata 473ml cx 6", 52.0, False),
    ("Suco", "Suco de Uva Integral", "Garrafa 1L cx 6", 64.0, False),
    ("Suco", "Néctar de Pêssego", "Caixa 1L cx 12", 58.0, False),
    ("Suco", "Néctar de Manga", "Caixa 1L cx 12", 58.0, False),
    ("Destilados", "Vodka Premium", "Garrafa 1L cx 6", 285.0, False),
    ("Destilados", "Gin Seco", "Garrafa 750ml cx 6", 330.0, False),
    ("Destilados", "Cachaça Envelhecida", "Garrafa 700ml cx 6", 198.0, False),
    ("Destilados", "Whisky 8 anos", "Garrafa 1L cx 6", 540.0, False),
]
# produtos lançados em 2025 (não existem no ano-base: entram como "novos produtos" na análise PVM)
LANCAMENTOS = [("Cerveja", "Cerveja Puro Malte", "Lata 473ml cx 12", 66.0, True, "2025-03-01"),
               ("Energético", "Energético Melancia", "Lata 250ml cx 6", 42.0, False, "2025-06-01")]

REAJUSTES = {"2024-03-01": 0.05, "2024-10-01": 0.04, "2025-04-01": 0.07}  # tabela de preços
SAZONALIDADE = np.array([1.30, 1.25, 1.10, 0.95, 0.85, 0.80, 0.80, 0.85, 0.95, 1.05, 1.15, 1.35])

# segmento -> (pedidos/mês, itens por pedido, caixas por item, preferência por categoria)
SEGMENTOS = {
    "Bar": (3.0, (2, 4), (1, 6), {"Cerveja": 6, "Refrigerante": 2, "Água": 1.5, "Energético": 1, "Suco": 0.3, "Destilados": 2}),
    "Restaurante": (2.0, (2, 5), (1, 5), {"Cerveja": 3, "Refrigerante": 3, "Água": 3, "Energético": 0.3, "Suco": 2, "Destilados": 1}),
    "Mercado": (3.5, (4, 8), (2, 12), {"Cerveja": 4, "Refrigerante": 4, "Água": 3, "Energético": 2, "Suco": 2, "Destilados": 1}),
    "Atacado": (2.0, (5, 10), (15, 60), {"Cerveja": 5, "Refrigerante": 4, "Água": 3, "Energético": 1.5, "Suco": 1, "Destilados": 0.5}),
}


def sem_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def br(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- #
# Cadastros
# --------------------------------------------------------------------------- #
def gerar_produtos(rng) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    linhas = [(*p, "2023-01-01") for p in PRODUTOS] + LANCAMENTOS
    produtos = pd.DataFrame(linhas, columns=["categoria", "nome", "embalagem", "preco_base", "sazonal", "lancamento"])
    produtos.insert(0, "sku", [str(1001 + i) for i in range(len(produtos))])
    abreviacoes = {"Cerveja": "CRV", "Refrigerante": "REF", "Água": "AGU", "Energético": "ENE", "Suco": "SUC", "Destilados": "DST"}
    produtos["sku_antigo"] = [f"{abreviacoes[c]}-{i:03d}" for i, c in enumerate(produtos["categoria"], start=11)]

    precos = []
    for p in produtos.itertuples():
        preco = p.preco_base
        precos.append((p.sku, max(pd.Timestamp(p.lancamento), pd.Timestamp("2023-01-01")), preco))
        for data, alta in REAJUSTES.items():
            preco = round(preco * (1 + alta + rng.uniform(-0.015, 0.015)), 2)
            if pd.Timestamp(data) > pd.Timestamp(p.lancamento):
                precos.append((p.sku, pd.Timestamp(data), preco))
    tabela = pd.DataFrame(precos, columns=["sku", "vigente_desde", "preco_lista"])
    # de-para da migração: dois SKUs antigos ficaram de fora (erro na carga)
    depara = produtos.loc[produtos["lancamento"] < "2024-01-01", ["sku_antigo", "sku"]].rename(columns={"sku": "sku_novo"})
    depara = depara.drop(index=rng.choice(depara.index, 2, replace=False))
    return produtos, tabela, depara


def gerar_vendedores(rng) -> pd.DataFrame:
    linhas = []
    for i, nome in enumerate(NOMES_VENDEDORES[:16], start=1):
        regional = list(REGIONAIS)[(i - 1) // 4]
        linhas.append({"vendedor_id": f"V{i:02d}", "nome": nome, "regional": regional, "gerente": REGIONAIS[regional],
                       "admissao": pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(rng.integers(0, 1800))),
                       "desligamento": pd.NaT, "perfil_desconto": float(rng.uniform(0.01, 0.07))})
    # turnover: V07 sai em jun/2025 e é substituído por V17, que herda a carteira
    linhas[6]["desligamento"] = pd.Timestamp("2025-06-30")
    linhas.append({"vendedor_id": "V17", "nome": NOMES_VENDEDORES[16], "regional": linhas[6]["regional"],
                   "gerente": linhas[6]["gerente"], "admissao": pd.Timestamp("2025-07-01"), "desligamento": pd.NaT,
                   "perfil_desconto": 0.09})  # novato dá mais desconto para conquistar a carteira
    return pd.DataFrame(linhas)


def gerar_clientes(rng, vendedores: pd.DataFrame) -> pd.DataFrame:
    cidades = {"Capital": ["São Paulo"], "Grande SP": ["Guarulhos", "Osasco", "Santo André", "São Bernardo do Campo"],
               "Interior": ["Campinas", "Jundiaí", "Sorocaba", "Piracicaba"], "Litoral": ["Santos", "Guarujá", "Praia Grande"]}
    ativos = vendedores[vendedores["vendedor_id"] != "V17"]
    linhas = []
    for i in range(1, 651):
        segmento = str(rng.choice(list(SEGMENTOS), p=[0.40, 0.25, 0.25, 0.10]))
        vendedor = ativos.iloc[rng.integers(len(ativos))]
        cadastro = pd.Timestamp("2019-01-01") + pd.Timedelta(days=int(rng.beta(2.2, 1.0) * 2500))
        churn = cadastro + pd.Timedelta(days=int(rng.integers(120, 900))) if rng.random() < 0.22 else pd.NaT
        linhas.append({"cliente_id": f"CLI-{i:04d}", "razao_social": f"{segmento} {i:04d} Ltda", "segmento": segmento,
                       "cidade": str(rng.choice(cidades[vendedor["regional"]])), "regional": vendedor["regional"],
                       "vendedor_id": vendedor["vendedor_id"], "data_cadastro": cadastro, "churn": churn,
                       "potencial": float(rng.lognormal(0, 0.45))})
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------- #
# Vendas
# --------------------------------------------------------------------------- #
def preco_vigente(tabela: pd.DataFrame, sku: str, data: pd.Timestamp) -> float:
    linhas = tabela[(tabela["sku"] == sku) & (tabela["vigente_desde"] <= data)]
    return float(linhas["preco_lista"].iat[-1])


def gerar_vendas(rng, clientes, vendedores, produtos, tabela) -> pd.DataFrame:
    perfil = vendedores.set_index("vendedor_id")["perfil_desconto"]
    meses = pd.date_range(INICIO, FIM, freq="MS")
    cache_precos = {(s, m): None for s in produtos["sku"] for m in meses}
    for sku, mes in cache_precos:
        if pd.Timestamp(produtos.set_index("sku").at[sku, "lancamento"]) <= mes + pd.offsets.MonthEnd(0):
            cache_precos[(sku, mes)] = preco_vigente(tabela, sku, mes + pd.offsets.MonthEnd(0))

    linhas, nf = [], 500_000
    for c in clientes.itertuples():
        pedidos_mes, itens, caixas, preferencia = SEGMENTOS[c.segmento]
        for mes in meses:
            fim_mes = mes + pd.offsets.MonthEnd(0)
            if c.data_cadastro > fim_mes or (pd.notna(c.churn) and c.churn < mes):
                continue
            # crescimento de 6% ao ano na frequência + sazonalidade + potencial do cliente
            tendencia = 1 + 0.06 * (mes.year - 2024 + mes.month / 12)
            n = rng.poisson(pedidos_mes * c.potencial * tendencia * (0.6 + 0.4 * SAZONALIDADE[mes.month - 1]))
            dias = DIAS_UTEIS[(DIAS_UTEIS >= max(mes, c.data_cadastro)) & (DIAS_UTEIS <= fim_mes)]
            if n == 0 or len(dias) == 0:
                continue
            vendedor = c.vendedor_id if not (c.vendedor_id == "V07" and mes >= pd.Timestamp("2025-07-01")) else "V17"
            disponiveis = produtos[[cache_precos[(s, mes)] is not None for s in produtos["sku"]]]
            pesos = disponiveis["categoria"].map(preferencia).to_numpy()
            pesos = pesos * np.where(disponiveis["sazonal"], SAZONALIDADE[mes.month - 1], 1.0)
            for data in np.sort(rng.choice(dias, size=n)):
                nf += 1
                k = min(int(rng.integers(itens[0], itens[1] + 1)), len(disponiveis))
                for idx in rng.choice(len(disponiveis), size=k, replace=False, p=pesos / pesos.sum()):
                    produto = disponiveis.iloc[idx]
                    preco = cache_precos[(produto["sku"], mes)]
                    desconto = perfil[vendedor] + (0.05 if c.segmento == "Atacado" else 0) + rng.normal(0, 0.015)
                    tipo = "BONIFICACAO" if rng.random() < 0.015 else "VENDA"
                    linhas.append({
                        "data": pd.Timestamp(data), "nf": nf, "vendedor_id": vendedor, "cliente_id": c.cliente_id,
                        "sku": produto["sku"], "sku_antigo": produto["sku_antigo"],
                        "quantidade": int(rng.integers(caixas[0], caixas[1] + 1)), "preco_lista": preco,
                        "desconto_pct": 0.0 if tipo == "BONIFICACAO" else round(float(np.clip(desconto, 0, 0.2)) * 200) / 200,
                        "tipo": tipo, "canal": str(rng.choice(["visita", "televendas", "app_b2b"],
                                                              p=[0.55, 0.25, 0.20] if mes.year == 2024 else [0.45, 0.25, 0.30])),
                    })
    vendas = pd.DataFrame(linhas)

    # devoluções: ~1,5% dos itens voltam alguns dias depois, em nota própria
    devolvidos = vendas[vendas["tipo"] == "VENDA"].sample(frac=0.015, random_state=SEED).copy()
    devolvidos["data"] = [DU_proximo(d + pd.Timedelta(days=int(rng.integers(2, 15)))) for d in devolvidos["data"]]
    devolvidos["quantidade"] = [max(1, int(q * rng.uniform(0.2, 1))) for q in devolvidos["quantidade"]]
    devolvidos["tipo"] = "DEVOLUCAO"
    devolvidos["nf"] = range(900_001, 900_001 + len(devolvidos))
    vendas = pd.concat([vendas, devolvidos[devolvidos["data"] <= FIM]], ignore_index=True)
    vendas["preco_liquido"] = (vendas["preco_lista"] * (1 - vendas["desconto_pct"])).round(2)
    vendas.loc[vendas["tipo"] == "BONIFICACAO", "preco_liquido"] = 0.0

    # numeração das notas em ordem cronológica, como o ERP emite (série própria para devoluções)
    vendas = vendas.sort_values(["data", "nf", "sku"]).reset_index(drop=True)
    for serie, inicio in [(vendas["tipo"] != "DEVOLUCAO", 500_001), (vendas["tipo"] == "DEVOLUCAO", 900_001)]:
        ordem = pd.factorize(vendas.loc[serie, "nf"])[0]
        vendas.loc[serie, "nf"] = inicio + ordem
    return vendas


def DU_proximo(data: pd.Timestamp) -> pd.Timestamp:  # noqa: N802
    return pd.offsets.CustomBusinessDay(holidays=FERIADOS).rollforward(data)


def exportar_vendas(rng, vendas: pd.DataFrame) -> None:
    VENDAS_DIR.mkdir(parents=True, exist_ok=True)
    for arquivo in VENDAS_DIR.glob("*.csv"):
        arquivo.unlink()
    for mes, bloco in vendas.groupby(vendas["data"].dt.to_period("M")):
        nome = VENDAS_DIR / f"vendas_{mes}.csv"
        if mes.start_time < MIGRACAO_ERP:
            # ERP antigo: código do vendedor digitado livremente, SKU antigo, preço bruto,
            # desconto em R$ na linha e devolução como quantidade negativa
            sinal = np.where(bloco["tipo"] == "DEVOLUCAO", -1, 1)
            preco_bruto = np.where(bloco["tipo"] == "BONIFICACAO", 0.0, bloco["preco_lista"])
            desconto_rs = (bloco["quantidade"] * preco_bruto * bloco["desconto_pct"]).round(2)
            codigos = [str(rng.choice([v, v.lower(), v[1:].lstrip("0"), f"v-{v[1:]}"])) for v in bloco["vendedor_id"]]
            pd.DataFrame({
                "data": bloco["data"].dt.strftime("%d/%m/%Y"), "nf": bloco["nf"], "cod_vendedor": codigos,
                "cod_cliente": bloco["cliente_id"], "sku": bloco["sku_antigo"], "qtd": bloco["quantidade"] * sinal,
                "vlr_unit": [br(v) for v in preco_bruto], "vlr_desc": [br(v) for v in desconto_rs * sinal],
            }).to_csv(nome, sep=";", index=False)
        else:
            saida = pd.DataFrame({
                "data_emissao": bloco["data"].dt.strftime("%Y-%m-%d"), "numero_nf": bloco["nf"],
                "vendedor_id": bloco["vendedor_id"], "cliente_id": bloco["cliente_id"], "produto_sku": bloco["sku"],
                "quantidade": bloco["quantidade"], "preco_unitario": bloco["preco_liquido"].map(lambda v: f"{v:.2f}"),
                "desconto_pct": (bloco["desconto_pct"] * 100).round(1), "tipo_operacao": bloco["tipo"],
                "canal": bloco["canal"],
            })
            # erros de digitação: quantidade 100x em poucas linhas (caixas digitadas como unidades)
            erros = rng.choice(saida.index, size=max(1, len(saida) // 2500), replace=False)
            saida.loc[erros, "quantidade"] = saida.loc[erros, "quantidade"] * 100
            saida.to_csv(nome, index=False)
            if str(mes) == "2025-03":  # reexportação: arquivo duplicado na pasta
                saida.to_csv(VENDAS_DIR / f"vendas_{mes} (1).csv", index=False)


# --------------------------------------------------------------------------- #
# Metas
# --------------------------------------------------------------------------- #
def gerar_metas(vendas: pd.DataFrame, vendedores: pd.DataFrame, produtos: pd.DataFrame) -> None:
    """
    Metas de 2025 = realizado do mesmo mês em 2024 x 1,12, arredondado ao milhar.
    O vendedor novo (V17) herda a meta da carteira do V07 a partir de julho.
    A planilha é feita por pessoas: formato largo, nomes e valores em texto.
    """
    receita = vendas.assign(receita=vendas["quantidade"] * vendas["preco_liquido"]
                            * np.where(vendas["tipo"] == "DEVOLUCAO", -1, 1))
    base = receita[receita["data"].dt.year == 2024].assign(mes=lambda d: d["data"].dt.month)
    base["vendedor_id"] = base["vendedor_id"]
    mensal = base.groupby(["vendedor_id", "mes"])["receita"].sum().unstack(fill_value=0)
    metas = (mensal * 1.12 / 1000).round() * 1000
    metas.loc["V17"] = 0.0
    metas.loc["V17", 7:] = metas.loc["V07", 7:]
    metas.loc["V07", 7:] = np.nan  # desligado em junho
    metas.loc["V17", :6] = np.nan

    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    nomes = vendedores.set_index("vendedor_id")
    planilha = pd.DataFrame({
        "Vendedor": [sem_acentos(nomes.at[v, "nome"]).upper() if i % 3 == 0 else nomes.at[v, "nome"]
                     for i, v in enumerate(metas.index)],
        "Regional": [nomes.at[v, "regional"] for v in metas.index],
        **{m: [("" if pd.isna(x) else (f"R$ {br(x)}" if j % 2 else x)) for j, x in enumerate(metas[i + 1])]
           for i, m in enumerate(meses)},
    })
    planilha["Total"] = metas.sum(axis=1).values
    total = {"Vendedor": "TOTAL", "Regional": "", **{m: metas[i + 1].sum() for i, m in enumerate(meses)},
             "Total": metas.to_numpy()[~np.isnan(metas.to_numpy())].sum()}
    planilha = pd.concat([planilha, pd.DataFrame([total])], ignore_index=True)

    # meta da diretoria por regional x categoria x trimestre (também em formato largo)
    categoria = receita.merge(produtos[["sku", "categoria"]], on="sku").merge(
        vendedores[["vendedor_id", "regional"]], on="vendedor_id")
    categoria = categoria[categoria["data"].dt.year == 2024]
    trimestral = categoria.groupby(["regional", "categoria", categoria["data"].dt.quarter])["receita"].sum().unstack()
    trimestral = (trimestral * 1.10 / 1000).round() * 1000
    trimestral.columns = [f"T{t}" for t in trimestral.columns]

    with pd.ExcelWriter(RAW_DIR / "metas_2025.xlsx", engine="openpyxl") as writer:
        planilha.to_excel(writer, sheet_name="Metas Vendedores", index=False, startrow=2)
        writer.sheets["Metas Vendedores"]["A1"] = "METAS DE FATURAMENTO 2025 - APROVADO PELA DIRETORIA"
        trimestral.reset_index().to_excel(writer, sheet_name="Metas Regionais", index=False)


# --------------------------------------------------------------------------- #
def main() -> None:
    rng = np.random.default_rng(SEED)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    produtos, tabela, depara = gerar_produtos(rng)
    vendedores = gerar_vendedores(rng)
    clientes = gerar_clientes(rng, vendedores)
    vendas = gerar_vendas(rng, clientes, vendedores, produtos, tabela)

    exportar_vendas(rng, vendas)
    gerar_metas(vendas, vendedores, produtos)
    produtos.drop(columns=["preco_base", "sazonal", "sku_antigo"]).to_csv(RAW_DIR / "produtos.csv", index=False)
    tabela.assign(vigente_desde=tabela["vigente_desde"].dt.strftime("%Y-%m-%d")).to_csv(RAW_DIR / "tabela_precos.csv", index=False)
    depara.to_csv(RAW_DIR / "depara_sku.csv", index=False)
    vendedores.drop(columns="perfil_desconto").assign(
        admissao=vendedores["admissao"].dt.strftime("%Y-%m-%d"),
        desligamento=vendedores["desligamento"].dt.strftime("%Y-%m-%d"),
    ).to_csv(RAW_DIR / "vendedores.csv", index=False)
    registros = clientes.drop(columns=["churn", "potencial"]).assign(
        data_cadastro=clientes["data_cadastro"].dt.strftime("%Y-%m-%d"))
    registros["segmento"] = [s.upper() if i % 7 == 0 else s for i, s in enumerate(registros["segmento"])]
    (RAW_DIR / "clientes.json").write_text(json.dumps(registros.to_dict("records"), ensure_ascii=False, indent=1),
                                           encoding="utf-8")

    print(f"Linhas de venda: {len(vendas):,} | NFs: {vendas['nf'].nunique():,} | clientes: {len(clientes)}")
    for arquivo in sorted(RAW_DIR.rglob("*.*"))[:6] + [VENDAS_DIR]:
        tamanho = sum(f.stat().st_size for f in arquivo.glob("*")) if arquivo.is_dir() else arquivo.stat().st_size
        print(f"  {arquivo.relative_to(ROOT)!s:<35} {tamanho / 1024:>9.1f} KB")


if __name__ == "__main__":
    main()
