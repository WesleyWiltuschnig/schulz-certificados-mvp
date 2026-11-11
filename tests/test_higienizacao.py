"""AV05 - Modulo de Ingestao: regras de higienizacao, caracteres especiais e valores nulos."""
from decimal import Decimal as D

import pytest

from app.ingestao import (IngestaoInvalida, codigo_normalizado, ler_planilha, limpar_texto, normalizar_chave,
                          para_decimal)


def test_limpar_texto_remove_controle_invisiveis_e_espacos():
    assert limpar_texto("  MP-0042\t\t ") == "MP-0042"
    assert limpar_texto("Micrômetro​  externo  0-25\x07mm") == "Micrômetro externo 0-25mm"
    assert limpar_texto("﻿703.1208\r\n") == "703.1208"
    assert limpar_texto(None) == ""


def test_normalizar_chave_ignora_acento_caixa_e_pontuacao():
    assert normalizar_chave("Plano de Medição") == "plano_de_medicao"
    assert normalizar_chave("  Valor_Padrão ") == "valor_padrao"
    assert normalizar_chave("Padrão do relatório:") == "padrao_do_relatorio"


def test_codigo_do_padrao_sem_pontuacao():
    assert codigo_normalizado(" 500.008 ") == codigo_normalizado("500008") == "500008"


def test_para_decimal_virgula_espacos_e_nulos():
    assert para_decimal(" 5,0010 ") == D("5.0010")
    assert para_decimal(5.0006) == D("5.0006")
    assert para_decimal(None) is None and para_decimal("   ") is None
    for invalido in ("5,00 mm", "abc", "1.2.3", True):
        with pytest.raises(ValueError):
            para_decimal(invalido)


def test_cabecalho_com_espacos_e_acentos_e_reconhecido(xlsx):
    d = ler_planilha(xlsx(meta={"Instrumento": "  MP-0042 ​", "Metrologista": "José  A.   Rosa Jr"}), "500008")
    assert d["instrumento"] == "MP-0042" and d["metrologista"] == "José A. Rosa Jr"


def test_lea_nulo_no_ponto_usa_lea_geral(xlsx):
    pontos = [("P1", 5.0, [5.001, 5.0006], None), ("P2", 10.0, [10.0012, 10.0016], None)]
    d = ler_planilha(xlsx(meta={"LEA geral": "0,002"}, pontos=pontos), "500008")
    assert [p["lea"] for p in d["pontos"]] == [D("0.002"), D("0.002")]


def test_leitura_nula_e_recusada_sem_virar_zero(xlsx):
    pontos = [("P1", 5.0, [5.001, None], 0.002)]
    with pytest.raises(IngestaoInvalida) as e:
        ler_planilha(xlsx(pontos=pontos), "500008")
    assert "leitura ausente" in str(e.value)
