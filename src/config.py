"""Caminhos, calendário e regras de negócio da área comercial."""

from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw"
VENDAS_DIR = RAW_DIR / "vendas"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
OUTPUT_DIR = ROOT_DIR / "output"
REPORTS_DIR = OUTPUT_DIR / "reports"
CHARTS_DIR = OUTPUT_DIR / "charts"

ANO_BASE, ANO_ANALISE = 2024, 2025
DATA_CORTE = pd.Timestamp("2025-12-31")
FERIADOS = pd.to_datetime([
    "2024-01-01", "2024-02-12", "2024-02-13", "2024-03-29", "2024-05-01", "2024-05-30", "2024-11-15",
    "2024-11-20", "2024-12-25", "2025-01-01", "2025-03-03", "2025-03-04", "2025-04-18", "2025-04-21",
    "2025-05-01", "2025-06-19", "2025-11-20", "2025-12-25",
])

# Quantidade digitada em unidades em vez de caixas (100x): múltiplo de 100 e muito acima
# do que o cliente costuma comprar por linha
FATOR_QUANTIDADE_ATIPICA = 20
QUANTIDADE_MAXIMA_CAIXAS = 1_000

# Comissão sobre a receita líquida do mês, pela faixa de atingimento da meta
FAIXAS_COMISSAO = [0, 0.80, 1.00, 1.20, float("inf")]
PERCENTUAIS_COMISSAO = [0.0, 0.02, 0.03, 0.04]

# RFM: janela de 12 meses até a data de corte. A recência usa faixas de negócio (dias desde
# a última compra -> nota), porque os clientes compram com frequência e quintis criariam
# distinções artificiais entre 3 e 5 dias.
JANELA_RFM_MESES = 12
FAIXAS_RECENCIA_DIAS = [-1, 7, 15, 30, 60, float("inf")]
