"""Geracao de planilhas .xlsx sinteticas (modelo e amostras de teste). Nao contem dados reais."""
import io
from datetime import date

from openpyxl import Workbook

META_PADRAO = {
    "Instrumento": "MP-0042",
    "Denominação": "Micrômetro externo 0-25 mm",
    "Plano de medição": "703.1208",
    "Data da medição": date(2026, 8, 13),
    "Temperatura ambiente": "20,4°",
    "Padrão do relatório": "500008",
    "Metrologista": "José A. Rosa Jr",
}
PONTOS_APROVADO = [
    ("P1 5,000 mm", 5.0, [5.0010, 5.0006], 0.002),
    ("P2 10,000 mm", 10.0, [10.0012, 10.0016], 0.002),
    ("P3 15,000 mm", 15.0, [15.0004, 15.0000], 0.002),
    ("P4 20,000 mm", 20.0, [20.0011, 20.0013], 0.002),
]
PONTOS_REPROVADO = [PONTOS_APROVADO[0], PONTOS_APROVADO[1],
                    ("P3 15,000 mm", 15.0, [15.0031, 15.0035], 0.002), PONTOS_APROVADO[3]]


def gerar_xlsx(meta=None, pontos=None, n_leituras=2, remover_meta=(), coluna_desvio=None):
    m = dict(META_PADRAO)
    m.update(meta or {})
    for k in remover_meta:
        m.pop(k, None)
    pontos = PONTOS_APROVADO if pontos is None else pontos
    wb = Workbook()
    ws = wb.active
    ws.title = "Calibracao"
    for k, v in m.items():
        ws.append([k, v])
    ws.append([])
    cab = ["Ponto", "Valor_Padrao"] + [f"Leitura_{i}" for i in range(1, n_leituras + 1)] + ["LEA"]
    if coluna_desvio is not None:
        cab.append("Desvio")
    ws.append(cab)
    for i, (nome, ref, leituras, lea) in enumerate(pontos):
        linha = [nome, ref] + list(leituras)[:n_leituras]
        while len(linha) < 2 + n_leituras:
            linha.append(None)
        linha.append(lea)
        if coluna_desvio is not None:
            linha.append(coluna_desvio[i])
        ws.append(linha)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
