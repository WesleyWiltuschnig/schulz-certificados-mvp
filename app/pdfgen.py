"""Composicao do certificado (documento + PDF) e varredura de marcadores (RN06)."""
import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .metrologia import arredondar

MARCADORES = {"XX", "YY", "TODO", "PREENCHER"}


def _br(valor, casas):
    return str(arredondar(valor, casas)).replace(".", ",")


def _data_br(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso and len(iso) >= 10 else iso


def montar_documento(ctx):
    cal, padrao = ctx["cal"], ctx["padrao"]
    campos = [
        ("Número do certificado", ctx["numero"]),
        ("Data de emissão (UTC)", ctx["emitido_em"]),
        ("Instrumento", f"{cal['instrumento']} - {cal['denominacao']}"),
        ("Plano de medição", cal["plano_medicao"]),
        ("Data da medição", _data_br(cal["data_medicao"])),
        ("Temperatura ambiente (°C)", _br(cal["temperatura"], 1)),
        ("Padrão utilizado", f"{padrao['codigo']} - {padrao['denominacao']}"),
        ("Série do padrão", padrao["numero_serie"]),
        ("Certificado do padrão", padrao["certificado_rastreabilidade"]),
        ("Calibração do padrão", f"{_data_br(padrao['data_ultima_calibracao'])} (próxima: {_data_br(padrao['data_proxima_calibracao'])})"),
        ("Executor", ctx["executor"]),
        ("Finalizado por", ctx["finalizador"]),
        ("SHA-256 da planilha de origem", cal["arquivo_sha256"]),
    ]
    cabecalho = ["Ponto", "Valor padrão", "Média", "Desvio padrão", "Erro", "LEA", "Classificação"]
    linhas = [[p["nome"], _br(p["referencia"], 4), _br(p["media"], 4), _br(p["desvio_padrao"], 4),
               _br(p["erro"], 4), _br(p["lea"], 4), p["classificacao"]] for p in ctx["pontos"]]
    notas = [
        f"Cada resultado é a média de {cal['blocos']} leituras. Erro sistemático = média - valor padrão. "
        "Ponto dentro da tolerância quando |erro| <= LEA.",
        "Incerteza de medição: não apurada nesta versão do MVP (balanço de incerteza não implementado).",
        "Documento sem assinatura digital qualificada; integridade verificável pelo hash SHA-256 registrado.",
    ]
    return {"titulo": "Certificado de Calibração", "campos": campos, "cabecalho": cabecalho,
            "linhas": linhas, "parecer": cal["parecer"], "notas": notas}


def texto_plano(doc):
    partes = [doc["titulo"]]
    partes += [f"{r}: {v}" for r, v in doc["campos"]]
    partes += doc["cabecalho"]
    partes += [c for linha in doc["linhas"] for c in linha]
    partes += ["Parecer final: " + doc["parecer"]] + doc["notas"]
    return "\n".join(partes)


def detectar_marcadores(texto):
    """Procura tokens de preenchimento nao substituidos (XX, YY, {{...}}, TODO)."""
    achados = []
    if "{{" in texto or "}}" in texto:
        achados.append("{{ }}")
    for token in re.split(r"\s+", texto):
        t = token.strip(".,;:()[]\"'")
        if t.upper() in MARCADORES and t not in achados:
            achados.append(t)
    return achados


def gerar_pdf(doc):
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=doc["titulo"])
    st = getSampleStyleSheet()
    pequeno = st["BodyText"].clone("pequeno", fontSize=8, leading=10)
    story = [Paragraph(doc["titulo"], st["Title"]), Spacer(1, 4 * mm)]
    t = Table([[Paragraph(f"<b>{r}</b>", pequeno), Paragraph(str(v), pequeno)] for r, v in doc["campos"]],
              colWidths=[55 * mm, 119 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [t, Spacer(1, 6 * mm), Paragraph("Resultados", st["Heading3"])]
    dados = [doc["cabecalho"]] + [[Paragraph(str(c), pequeno) for c in linha] for linha in doc["linhas"]]
    tab = Table(dados, repeatRows=1, colWidths=[26 * mm, 22 * mm, 22 * mm, 24 * mm, 20 * mm, 18 * mm, 42 * mm])
    tab.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                             ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                             ("FONTSIZE", (0, 0), (-1, 0), 8)]))
    story += [tab, Spacer(1, 6 * mm), Paragraph(f"<b>Parecer final: {doc['parecer']}</b>", st["Heading3"])]
    story += [Paragraph(n, pequeno) for n in doc["notas"]]
    pdf.build(story)
    return buf.getvalue()
