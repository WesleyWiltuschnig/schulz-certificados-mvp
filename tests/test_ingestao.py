from datetime import date
from decimal import Decimal as D

import pytest

from app.ingestao import IngestaoInvalida, ler_planilha, interpretar_data, extrair_temperatura


def codigos(exc):
    return {e["codigo"] for e in exc.value.erros}


def test_planilha_valida(xlsx):
    d = ler_planilha(xlsx(), padrao_esperado="500008")
    assert d["instrumento"] == "MP-0042" and len(d["pontos"]) == 4 and d["blocos"] == 2
    assert d["data_medicao"] == "2026-08-13"
    assert d["temperatura"] == D("20.4")
    assert d["pontos"][0]["leituras"] == [D("5.001"), D("5.0006")]


def test_sufixo_de_teste_e_recusado(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(meta={"Plano de medição": "703.1208_TESTE"}), "500008")
    assert "RN10" in codigos(e)


def test_padrao_divergente_e_recusado(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(meta={"Padrão do relatório": "500011"}), "500008")
    assert "RN03" in codigos(e)


def test_codigo_do_padrao_ignora_pontuacao(xlsx):
    ler_planilha(xlsx(meta={"Padrão do relatório": "500.008"}), "500008")


def test_um_bloco_e_recusado(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(n_leituras=1), "500008")
    assert "RN01" in codigos(e)


def test_tres_blocos_e_recusado(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(n_leituras=3, pontos=[("P1", 1.0, [1.0, 1.0, 1.0], 0.1)]), "500008")
    assert "RN01" in codigos(e)


def test_data_sentinela_e_recusada(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(meta={"Data da medição": "00/00/0000"}), "500008")
    assert "H03" in codigos(e)


def test_temperatura_nao_numerica_e_recusada(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(meta={"Temperatura ambiente": "quente"}), "500008")
    assert "RN14" in codigos(e)


def test_campo_obrigatorio_ausente(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(remover_meta=["Instrumento"]), "500008")
    assert "H10" in codigos(e)


def test_leitura_nao_numerica_e_recusada(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(pontos=[("P1", 1.0, ["abc", 1.0], 0.1)]), "500008")
    assert "EST" in codigos(e)


def test_lea_ausente_e_recusado(xlsx):
    with pytest.raises(IngestaoInvalida):
        ler_planilha(xlsx(pontos=[("P1", 1.0, [1.0, 1.0], None)]), "500008")


def test_lea_geral_substitui_lea_ausente_por_ponto(xlsx):
    d = ler_planilha(xlsx(meta={"LEA geral": 0.05}, pontos=[("P1", 1.0, [1.0, 1.0], None)]), "500008")
    assert d["pontos"][0]["lea"] == D("0.05")


def test_linha_sem_ponto_e_suprimida_sem_virar_zero(xlsx):
    d = ler_planilha(xlsx(pontos=[("P1", 1.0, [1.0, 1.0], 0.1), (None, None, [None, None], None)]), "500008")
    assert len(d["pontos"]) == 1


def test_arquivo_que_nao_e_xlsx():
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(b"isto nao e uma planilha")
    assert "ARQ" in codigos(e)


def test_planilha_sem_cabecalho_de_pontos():
    from openpyxl import Workbook
    import io
    wb = Workbook(); wb.active.append(["a", "b"]); b = io.BytesIO(); wb.save(b)
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(b.getvalue())
    assert "EST" in codigos(e)


def test_varios_erros_sao_acumulados(xlsx):
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(meta={"Plano de medição": "X_TESTE", "Temperatura ambiente": "?"}), "500011")
    assert {"RN10", "RN14", "RN03"} <= codigos(e)


def test_interpretar_data_formatos():
    assert interpretar_data("13/08/2026") == "2026-08-13"
    assert interpretar_data(date(2026, 8, 13)) == "2026-08-13"
    with pytest.raises(ValueError):
        interpretar_data("0/0/0")


def test_extrair_temperatura():
    assert extrair_temperatura("20,4°") == D("20.4")
    assert extrair_temperatura("21 °C") == D("21")
    assert extrair_temperatura(19.5) == D("19.5")
