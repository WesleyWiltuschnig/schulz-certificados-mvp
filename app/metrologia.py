"""Calculos metrologicos do MVP (Atividade 3, Item 1).

Todo calculo usa Decimal para preservar a precisao original (RNF04).
"""
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28

DENTRO = "DENTRO_DA_TOLERANCIA"
FORA = "FORA_DA_TOLERANCIA"
APROVADO = "APROVADO"
REPROVADO = "REPROVADO"


def media(valores):
    if not valores:
        raise ValueError("lista de leituras vazia")
    return sum(valores, Decimal(0)) / Decimal(len(valores))


def desvio_padrao_amostral(valores):
    """Desvio padrao amostral (n-1), regra T02 do Tema 01."""
    n = len(valores)
    if n < 2:
        raise ValueError("desvio padrao amostral exige ao menos 2 leituras")
    m = media(valores)
    variancia = sum(((v - m) ** 2 for v in valores), Decimal(0)) / Decimal(n - 1)
    return variancia.sqrt()


def erro_sistematico(media_lida, valor_padrao):
    """Erro sistematico = media lida - valor padrao de referencia (T03)."""
    return media_lida - valor_padrao


def classificar(erro, lea):
    """|erro| <= LEA -> DENTRO_DA_TOLERANCIA; caso contrario FORA_DA_TOLERANCIA."""
    return DENTRO if abs(erro) <= lea else FORA


def parecer_final(classificacoes):
    if not classificacoes:
        raise ValueError("nenhum ponto avaliado")
    return APROVADO if all(c == DENTRO for c in classificacoes) else REPROVADO


def calcular_ponto(referencia, leituras, lea):
    m = media(leituras)
    erro = erro_sistematico(m, referencia)
    return {
        "media": m,
        "desvio_padrao": desvio_padrao_amostral(leituras),
        "erro": erro,
        "erro_abs": abs(erro),
        "classificacao": classificar(erro, lea),
    }


def arredondar(valor, casas):
    """Arredondamento apenas para apresentacao (RNF04)."""
    q = Decimal(1).scaleb(-casas)
    return Decimal(valor).quantize(q, rounding=ROUND_HALF_UP)


def texto_decimal(valor):
    """Decimal em notacao posicional (sem expoente) para persistencia."""
    return format(Decimal(valor), "f")
