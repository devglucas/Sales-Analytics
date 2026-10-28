import pandas as pd

from src.model import calendario, montar_fato_vendas, preco_de_tabela

TABELA = pd.DataFrame({"sku": ["1001", "1001"], "vigente_desde": pd.to_datetime(["2023-01-01", "2024-03-01"]),
                       "preco_lista": [100.0, 110.0]})


def test_preco_de_tabela_vigente_na_data():
    itens = pd.DataFrame({"sku": ["1001", "1001"], "data": pd.to_datetime(["2024-02-29", "2024-03-01"])})
    assert preco_de_tabela(itens, TABELA).tolist() == [100.0, 110.0]


def test_receita_por_tipo_de_operacao():
    itens = pd.DataFrame({
        "data": pd.to_datetime(["2024-03-05"] * 3), "sku": ["1001"] * 3, "cliente_id": ["C1"] * 3,
        "tipo": ["VENDA", "DEVOLUCAO", "BONIFICACAO"], "quantidade": [10, 2, 1],
        "preco_liquido": pd.array([99.0, 99.0, 0.0], dtype="Float64"),
    })
    cadastros = {
        "produtos": pd.DataFrame({"sku": ["1001"], "nome": ["X"], "embalagem": ["cx"], "categoria": ["Cerveja"],
                                  "lancamento": pd.to_datetime(["2023-01-01"])}),
        "clientes": pd.DataFrame({"cliente_id": ["C1"], "segmento": ["Bar"], "cidade": ["Santos"],
                                  "regional": ["Litoral"], "data_cadastro": pd.to_datetime(["2020-01-01"])}),
        "tabela_precos": TABELA,
    }
    fato = montar_fato_vendas(itens, cadastros)
    assert fato["receita_liquida"].tolist() == [990.0, -198.0, 0.0]
    assert fato["caixas"].tolist() == [10, -2, 0] and fato["caixas_bonificadas"].tolist() == [0, 0, 1]
    assert round(fato["desconto_real"].iat[0], 4) == 0.1      # 99 sobre tabela de 110


def test_calendario_conta_dias_uteis():
    cal = calendario(pd.Timestamp("2025-03-01"), pd.Timestamp("2025-03-31")).iloc[0]
    assert cal["dias_corridos"] == 31 and cal["dias_uteis"] == 19   # carnaval (3 e 4/03) não é dia útil
