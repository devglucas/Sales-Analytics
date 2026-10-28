"""
Orquestrador da análise comercial.

    extração -> harmonização e limpeza -> modelo -> desempenho (metas, comissões)
             -> crescimento (YoY, ponte, PVM) -> clientes (RFM, coortes, Pareto)
             -> validação -> exportação, relatório e gráficos

Uso:
    python main.py
"""

from __future__ import annotations

import time

from src.clean import limpar_cadastros, limpar_metas, limpar_vendas
from src.config import ANO_ANALISE, ANO_BASE
from src.customers import analisar_clientes
from src.extract import extrair_dados
from src.growth import analisar_crescimento
from src.model import calendario, montar_fato_vendas
from src.performance import analisar_desempenho
from src.utils import configurar_logger
from src.validate import garantir_qualidade, validar

log = configurar_logger("pipeline")


def executar_pipeline(exportar: bool = True) -> dict:
    inicio = time.perf_counter()

    log.info("1/7 Extração")
    dados = extrair_dados()

    log.info("2/7 Harmonização e limpeza")
    cadastros = limpar_cadastros(dados)
    itens, rejeitados, depara_inferido = limpar_vendas(dados["vendas"], dados["depara_sku"], cadastros["tabela_precos"])
    metas, metas_regionais, controle_metas = limpar_metas(dados["metas"], cadastros["vendedores"], ANO_ANALISE)

    log.info("3/7 Modelo analítico")
    fato = montar_fato_vendas(itens, cadastros)
    cal = calendario(fato["data"].min().replace(month=1, day=1))

    log.info("4/7 Desempenho, crescimento e clientes")
    res = {
        "fato": fato, "calendario": cal, "cadastros": cadastros, "rejeitados": rejeitados,
        "depara_inferido": depara_inferido, "controle_metas": controle_metas,
        "desempenho": analisar_desempenho(metas, metas_regionais, fato, cadastros["vendedores"], cal),
        "crescimento": analisar_crescimento(fato),
        "clientes": analisar_clientes(fato, cadastros["clientes"]),
    }

    log.info("5/7 Validação")
    res["validacoes"] = validar(res)
    garantir_qualidade(res["validacoes"])  # interrompe aqui se alguma regra crítica falhar

    if exportar:
        from src.load import exportar_dados, exportar_relatorios
        from src.report import gerar_relatorio, tabelas_relatorio
        from src.visualize import gerar_graficos

        log.info("6/7 Exportação")
        tabelas = tabelas_relatorio(res)
        exportar_dados(res)
        exportar_relatorios(tabelas)
        log.info("7/7 Relatório e gráficos")
        gerar_relatorio(res, tabelas)
        gerar_graficos(res)

    log.info("Pipeline concluído em %.1fs (%d x %d)", time.perf_counter() - inicio, ANO_ANALISE, ANO_BASE)
    return res


if __name__ == "__main__":
    executar_pipeline()
