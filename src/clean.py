"""
Limpeza e harmonização.

O ponto central é unir os dois layouts do ERP em um esquema único:

| Campo         | ERP antigo (até jun/2024)              | ERP novo (desde jul/2024)            |
|---------------|----------------------------------------|--------------------------------------|
| vendedor      | 'V03', 'v03', '3', 'v-03'              | 'V03'                                |
| produto       | SKU antigo ('CRV-015') -> de-para      | SKU novo ('1005')                    |
| preço         | BRUTO (de tabela)                      | LÍQUIDO (já com desconto)            |
| desconto      | valor em R$ na linha                   | percentual                           |
| devolução     | quantidade negativa                    | tipo_operacao = DEVOLUCAO            |
| bonificação   | preço zero                             | tipo_operacao = BONIFICACAO          |
| canal         | não existia                            | visita / televendas / app_b2b        |

Esquema harmonizado: quantidade sempre positiva + tipo; preço líquido unitário
e desconto em fração, nos dois casos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import FATOR_QUANTIDADE_ATIPICA, QUANTIDADE_MAXIMA_CAIXAS
from src.utils import chave_texto, configurar_logger, parse_numero, separar_rejeitados

log = configurar_logger("clean")

COLUNAS_ITENS = ["data", "nf", "vendedor_id", "cliente_id", "sku", "tipo", "quantidade", "preco_liquido",
                 "desconto_pct", "canal", "layout", "arquivo", "linha_origem"]
MESES = {"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6, "Jul": 7, "Ago": 8, "Set": 9, "Out": 10,
         "Nov": 11, "Dez": 12}


# --------------------------------------------------------------------------- #
# Cadastros
# --------------------------------------------------------------------------- #
def limpar_cadastros(dados: dict) -> dict[str, pd.DataFrame]:
    clientes = dados["clientes"].assign(
        segmento=dados["clientes"]["segmento"].str.strip().str.title(),
        data_cadastro=pd.to_datetime(dados["clientes"]["data_cadastro"]),
    )
    vendedores = dados["vendedores"].assign(
        admissao=pd.to_datetime(dados["vendedores"]["admissao"]),
        desligamento=pd.to_datetime(dados["vendedores"]["desligamento"]),
    )
    produtos = dados["produtos"].assign(lancamento=pd.to_datetime(dados["produtos"]["lancamento"]))
    tabela = dados["tabela_precos"].assign(
        vigente_desde=pd.to_datetime(dados["tabela_precos"]["vigente_desde"]),
        preco_lista=parse_numero(dados["tabela_precos"]["preco_lista"]),
    )
    return {"clientes": clientes, "vendedores": vendedores, "produtos": produtos, "tabela_precos": tabela}


# --------------------------------------------------------------------------- #
# Vendas: harmonização dos dois layouts
# --------------------------------------------------------------------------- #
def inferir_depara_por_preco(antigo: pd.DataFrame, tabela: pd.DataFrame, candidatos: set[str]) -> pd.Series:
    """
    SKUs antigos sem de-para: o ERP antigo gravava o preço BRUTO, que é o preço de
    tabela vigente. O SKU novo cujo preço vigente bate com o praticado em
    (quase) todas as linhas é o correspondente. merge_asof busca o preço vigente
    de cada candidato em cada data.
    """
    vendas = antigo.loc[antigo["preco_bruto"] > 0, ["sku_antigo", "data", "preco_bruto"]].sort_values("data")
    precos = tabela[tabela["sku"].isin(candidatos)].sort_values("vigente_desde")
    resultado = {}
    for sku_antigo, linhas in vendas.groupby("sku_antigo"):
        cruzado = pd.concat([
            pd.merge_asof(linhas, precos[precos["sku"] == sku], left_on="data", right_on="vigente_desde")
            for sku in candidatos
        ])
        aderencia = cruzado.assign(bate=np.isclose(cruzado["preco_bruto"], cruzado["preco_lista"])).groupby("sku")["bate"].mean()
        if aderencia.max() >= 0.95:
            resultado[sku_antigo] = aderencia.idxmax()
            log.info("de-para inferido pelo preço: %s -> %s (%.0f%% das linhas batem)", sku_antigo, aderencia.idxmax(),
                     aderencia.max() * 100)
    return pd.Series(resultado, dtype="string")


def harmonizar_layout_antigo(df: pd.DataFrame, depara: pd.DataFrame, tabela: pd.DataFrame) -> pd.DataFrame:
    quantidade = pd.to_numeric(df["qtd"], errors="coerce")
    preco_bruto = parse_numero(df["vlr_unit"])
    desconto_rs = parse_numero(df["vlr_desc"]).abs()
    df = df.assign(data=pd.to_datetime(df["data"], format="%d/%m/%Y"), preco_bruto=preco_bruto, sku_antigo=df["sku"])

    mapa = depara.set_index("sku_antigo")["sku_novo"]
    sem_depara = ~df["sku_antigo"].isin(mapa.index)
    if sem_depara.any():
        candidatos = set(tabela["sku"]) - set(mapa.values)
        mapa = pd.concat([mapa, inferir_depara_por_preco(df[sem_depara], tabela, candidatos)])

    tipo = np.select([quantidade < 0, preco_bruto == 0], ["DEVOLUCAO", "BONIFICACAO"], default="VENDA")
    bruto_linha = quantidade.abs() * preco_bruto
    return df.assign(
        nf=df["nf"],
        # 'v03', '3' e 'v-03' -> 'V03'
        vendedor_id="V" + df["cod_vendedor"].str.extract(r"(\d+)", expand=False).str.zfill(2),
        cliente_id=df["cod_cliente"],
        sku=df["sku_antigo"].map(mapa),
        tipo=tipo,
        quantidade=quantidade.abs(),
        preco_liquido=((bruto_linha - desconto_rs) / quantidade.abs()).round(2),
        desconto_pct=(desconto_rs / bruto_linha).where(bruto_linha > 0, 0.0).round(4),
        canal="nao_registrado",
        layout="antigo",
    )


def harmonizar_layout_novo(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        data=pd.to_datetime(df["data_emissao"], format="%Y-%m-%d"),
        nf=df["numero_nf"],
        sku=df["produto_sku"],
        tipo=df["tipo_operacao"].str.upper(),
        quantidade=pd.to_numeric(df["quantidade"], errors="coerce"),
        preco_liquido=parse_numero(df["preco_unitario"]),
        desconto_pct=parse_numero(df["desconto_pct"]) / 100,
        layout="novo",
    )


def limpar_vendas(vendas: dict, depara: pd.DataFrame, tabela: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    itens = pd.concat([
        harmonizar_layout_antigo(vendas["antigo"], depara, tabela)[COLUNAS_ITENS],
        harmonizar_layout_novo(vendas["novo"])[COLUNAS_ITENS],
    ], ignore_index=True)
    itens["nf"] = itens["nf"].astype("int64")

    # Quantidade digitada em unidades em vez de caixas (100x). Um limite fixo não serve: 300 caixas
    # é normal para um atacado e absurdo para um bar que compra 3. Compara com a mediana do cliente.
    mediana_cliente = itens.groupby("cliente_id")["quantidade"].transform("median")
    digitada_errada = (itens["quantidade"] % 100 == 0) & (itens["quantidade"] >= FATOR_QUANTIDADE_ATIPICA * mediana_cliente)
    itens["corr_quantidade_100x"] = digitada_errada
    itens.loc[digitada_errada, "quantidade"] = itens.loc[digitada_errada, "quantidade"] // 100

    regras = [
        (itens["sku"].isna(), "sku_antigo_sem_de_para"),
        # a reexportação de mar/2025 repete as mesmas notas em outro arquivo
        (itens.duplicated(subset=["nf", "sku", "tipo"]), "linha_duplicada_em_reexportacao"),
        (itens["quantidade"].isna() | itens["quantidade"].le(0) | itens["quantidade"].gt(QUANTIDADE_MAXIMA_CAIXAS),
         "quantidade_invalida"),
        (itens["preco_liquido"].isna() | itens["preco_liquido"].lt(0), "preco_invalido"),
    ]
    rejeitados = []
    for invalido, motivo in regras:
        itens, rej = separar_rejeitados(itens, invalido.reindex(itens.index), motivo)
        rejeitados.append(rej)
    itens["quantidade"] = itens["quantidade"].astype("int64")
    rejeitados = pd.concat(rejeitados)
    log.info("itens: %d válidos | %d corrigidos (100x) | rejeitados: %s", len(itens), itens["corr_quantidade_100x"].sum(),
             rejeitados["motivo_rejeicao"].value_counts().to_dict())
    return itens.sort_values(["data", "nf", "sku"]).reset_index(drop=True), rejeitados


# --------------------------------------------------------------------------- #
# Metas: planilha larga -> formato longo
# --------------------------------------------------------------------------- #
def limpar_metas(metas: dict, vendedores: pd.DataFrame, ano: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    A aba de vendedores tem um mês por coluna (formato LARGO). `melt` transforma
    cada célula (vendedor x mês) em uma linha (formato LONGO), que é o formato
    que se cruza com as vendas. A linha TOTAL vira um controle: a soma das
    metas depois do melt precisa bater com ela.
    """
    planilha = metas["vendedores"]
    total = planilha[planilha["Vendedor"].astype(str).str.upper().eq("TOTAL")]
    planilha = planilha.drop(index=total.index)

    # a planilha usa o nome do vendedor (com e sem acento, CAIXA ALTA): cruza pela chave normalizada
    ids = vendedores.assign(chave=chave_texto(vendedores["nome"])).set_index("chave")["vendedor_id"]
    planilha = planilha.assign(vendedor_id=chave_texto(planilha["Vendedor"]).map(ids))
    longas = planilha.melt(id_vars=["vendedor_id", "Vendedor"], value_vars=list(MESES), var_name="mes_nome",
                           value_name="meta_texto")
    longas = longas.assign(
        mes=pd.PeriodIndex.from_fields(year=[ano] * len(longas), month=longas["mes_nome"].map(MESES), freq="M"),
        meta=parse_numero(longas["meta_texto"]),
    ).dropna(subset=["meta"])  # célula vazia = vendedor não estava na empresa naquele mês

    controle = pd.DataFrame({
        "mes": list(MESES),
        "total_planilha": [float(parse_numero(total[m]).iat[0]) for m in MESES],
        "soma_apos_melt": [longas.loc[longas["mes_nome"] == m, "meta"].sum() for m in MESES],
    }).assign(diferenca=lambda d: d["total_planilha"] - d["soma_apos_melt"])

    regionais = metas["regionais"].melt(id_vars=["regional", "categoria"], var_name="trimestre", value_name="meta")
    regionais["trimestre"] = regionais["trimestre"].str.removeprefix("T").astype(int)
    regionais["meta"] = parse_numero(regionais["meta"])

    sem_id = longas["vendedor_id"].isna().sum()
    log.info("metas: %d vendedor-mês (%d sem cadastro) | %d regional-categoria-trimestre | controle TOTAL: %s",
             len(longas), sem_id, len(regionais), "ok" if controle["diferenca"].abs().max() < 0.01 else "DIVERGENTE")
    return longas[["vendedor_id", "mes", "meta"]], regionais, controle
