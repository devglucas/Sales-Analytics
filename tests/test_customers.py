import pandas as pd

from src.customers import coortes, pareto_clientes, rfm


def _vendas(linhas):
    df = pd.DataFrame(linhas, columns=["cliente_id", "data", "nf", "receita_liquida"])
    df["data"] = pd.to_datetime(df["data"])
    return df.assign(tipo="VENDA", mes=df["data"].dt.to_period("M"), ano=df["data"].dt.year)


CLIENTES = pd.DataFrame({
    "cliente_id": [f"C{i}" for i in range(1, 11)], "segmento": "Bar", "regional": "Capital", "vendedor_id": "V01",
    "data_cadastro": pd.to_datetime(["2020-01-01"] * 8 + ["2025-01-15", "2025-02-10"]),
})


def test_rfm_notas_e_segmentos():
    linhas = []
    for i in range(1, 11):
        for k in range(i):  # C10 compra 10 vezes, C1 uma vez
            linhas.append((f"C{i}", pd.Timestamp("2025-12-31") - pd.Timedelta(days=(10 - i) * 20 + k), 1000 * i + k, 100.0 * i))
    tabela = rfm(_vendas(linhas), CLIENTES).set_index("cliente_id")
    assert tabela.loc["C10", ["R", "F", "M"]].tolist() == [5, 5, 5]
    assert tabela.loc["C10", "segmento_rfm"] == "Campeões"
    assert tabela.loc["C1", "R"] == 1 and tabela.loc["C1", "segmento_rfm"] == "Perdidos"   # 180 dias sem comprar
    assert tabela["F"].value_counts().tolist() == [2] * 5                                   # quintis equilibrados


def test_coorte_so_com_clientes_novos():
    vendas = _vendas([
        ("C1", "2025-01-05", 1, 10.0),                                     # cliente antigo: fica fora
        ("C9", "2025-01-20", 2, 10.0), ("C9", "2025-03-03", 3, 10.0),      # coorte jan, volta no mês 2
        ("C10", "2025-02-12", 4, 10.0), ("C10", "2025-03-01", 5, 10.0),    # coorte fev, volta no mês 1
    ])
    retencao, curva = coortes(vendas, CLIENTES)
    retencao = retencao.set_index("coorte")
    assert retencao["clientes"].tolist() == [1, 1]
    assert retencao.loc["2025-01", 1] == 0.0                           # observado e ninguém voltou
    assert retencao.loc["2025-01", 2] == 1.0 and retencao.loc["2025-02", 1] == 1.0
    assert pd.isna(retencao.loc["2025-02", 2])                         # ainda não observável
    assert curva.loc[curva["mes_relativo"] == 0, "retencao_media"].iat[0] == 1.0


def test_pareto():
    vendas = _vendas([("C1", "2025-05-01", 1, 800.0), ("C2", "2025-05-01", 2, 150.0), ("C3", "2025-05-01", 3, 50.0)])
    tabela, resumo = pareto_clientes(vendas)
    assert tabela["classe_abc"].astype(str).tolist() == ["A", "B", "C"]
    assert resumo["pct_clientes_para_80pct_receita"] == 33.3
