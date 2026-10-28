"""
Validação: identidades que os números precisam respeitar antes de serem publicados.

- "critica": interrompe o pipeline
- "alerta":  registrada no relatório (fato do negócio que alguém precisa saber)
"""

from __future__ import annotations

import pandas as pd

from src.config import ANO_ANALISE, FAIXAS_COMISSAO, PERCENTUAIS_COMISSAO
from src.utils import configurar_logger

log = configurar_logger("validate")


class ErroDeValidacao(Exception):
    pass


def _regra(r: list, grupo: str, regra: str, falhas, severidade: str = "critica") -> None:
    qtd = int(falhas.sum()) if isinstance(falhas, pd.Series) else int(falhas)
    r.append({"grupo": grupo, "regra": regra, "severidade": severidade, "ocorrencias": qtd, "passou": qtd == 0})


def validar(res: dict) -> pd.DataFrame:
    fato, desemp, cresc, cli = res["fato"], res["desempenho"], res["crescimento"], res["clientes"]
    vendas = fato[fato["tipo"] == "VENDA"]
    r: list[dict] = []

    # modelo
    _regra(r, "modelo", "toda linha tem SKU, categoria, cliente e segmento",
           fato[["sku", "categoria", "cliente_id", "segmento"]].isna().any(axis=1))
    _regra(r, "modelo", "toda linha tem preço de tabela vigente", fato["preco_tabela"].isna())
    _regra(r, "modelo", "quantidade positiva", ~fato["quantidade"].gt(0))
    _regra(r, "modelo", "preço praticado não acima da tabela", vendas["desconto_real"] < -0.001)
    _regra(r, "modelo", "desconto informado = desconto real (±0,5 p.p.)",
           (vendas["desconto_pct"].astype("float64") - vendas["desconto_real"]).abs() > 0.005)

    # consistência entre agregações
    ano = fato[fato["ano"] == ANO_ANALISE]
    total = ano["receita_liquida"].sum()
    for dimensao in ["regional", "vendedor_id", "categoria", "segmento"]:
        _regra(r, "agregações", f"soma por {dimensao} = receita total",
               abs(ano.groupby(dimensao)["receita_liquida"].sum().sum() - total) > 0.01)
    _regra(r, "agregações", "realizado de metas x realizado = receita total",
           abs(desemp["metas_x_realizado_mensal"]["realizado"].sum() - total) > 0.01)

    # metas e comissões
    _regra(r, "metas", "soma das metas após melt = linha TOTAL da planilha",
           res["controle_metas"]["diferenca"].abs().gt(0.01))
    mensal = desemp["metas_x_realizado_mensal"].dropna(subset=["meta"])
    percentual = pd.cut(mensal["atingimento"], FAIXAS_COMISSAO, labels=PERCENTUAIS_COMISSAO, right=False).astype(float)
    _regra(r, "metas", "comissão coerente com a faixa de atingimento",
           (mensal["realizado"] * percentual - mensal["comissao"]).abs() > 0.01)

    # identidades analíticas
    pvm = cresc["preco_volume_mix"]
    _regra(r, "crescimento", "PVM: soma dos efeitos = variação da receita (por categoria)",
           (pvm["soma_dos_efeitos"] - pvm["variacao"]).abs() > 0.05)
    ponte = cresc["ponte_clientes"]["valor"]
    _regra(r, "crescimento", "ponte de clientes fecha (início + etapas = fim)",
           abs(ponte.iloc[0] + ponte.iloc[1:4].sum() - ponte.iloc[4]) > 0.05)
    rfm = cli["rfm_clientes"]
    _regra(r, "clientes", "notas RFM entre 1 e 5", ~rfm[["R", "F", "M"]].isin([1, 2, 3, 4, 5]).all(axis=1))
    _regra(r, "clientes", "retenção no mês 0 = 100%", ~cli["coortes_retencao"][0].sub(1.0).abs().lt(1e-9))

    # alertas: fatos do negócio
    sem_meta = desemp["metas_x_realizado_mensal"]["meta"].isna()
    _regra(r, "metas", "vendedor-mês com venda e sem meta", sem_meta, "alerta")
    _regra(r, "dados", "quantidades corrigidas (digitadas 100x)", fato["corr_quantidade_100x"], "alerta")
    _regra(r, "dados", "SKUs antigos com de-para reconstruído pelo preço", len(res["depara_inferido"]), "alerta")
    _regra(r, "dados", "linhas descartadas por reexportação duplicada",
           res["rejeitados"]["motivo_rejeicao"].eq("linha_duplicada_em_reexportacao"), "alerta")
    _regra(r, "clientes", "clientes em risco (RFM) com histórico frequente",
           rfm["segmento_rfm"].eq("Em risco"), "alerta")
    return pd.DataFrame(r)


def garantir_qualidade(resultado: pd.DataFrame) -> None:
    for linha in resultado.query("not passou").itertuples():
        nivel = log.error if linha.severidade == "critica" else log.warning
        nivel("[%s] %s: %s -> %d", linha.severidade, linha.grupo, linha.regra, linha.ocorrencias)
    criticas = resultado.query("severidade == 'critica' and not passou")
    if not criticas.empty:
        raise ErroDeValidacao(f"regras críticas falharam: {criticas['regra'].tolist()}")
    log.info("%d regras verificadas: todas as críticas passaram (%d alertas)", len(resultado), (~resultado["passou"]).sum())
