"""Estudo de Retorno sobre o Investimento (ROI) da automacao - AV05 (Schulz S.A.).

Calcula, a partir das premissas abaixo, as horas economizadas, a Economia Bruta Anual
(OPEX Saved), a Economia Liquida, o ROI pela formula do roteiro da AV05 e o payback:

    ROI (%) = (Economia Liquida - Investimento) / Investimento * 100
    Payback (meses) = Investimento / (Economia Liquida / 12)

Saidas em docs/roi/: roi_resultados.json, estudo_roi_schulz.xlsx (com formulas, para
alterar as premissas) e graficos PNG usados no relatorio.
Uso: python scripts/calcular_roi.py [--sem-graficos] [--sem-planilha]
"""
import argparse
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "roi")

FONTE_CAGED_METRO = ("salario.com.br, Metrologista de Calibracoes (CBO 2012-10), media Brasil, Novo CAGED "
                     "(ultimos 12 meses), atualizado em 05/11/2026")
FONTE_CAGED_METRO_CONS = ("salario.com.br, Metrologista (CBO 3523-05), media Brasil, Novo CAGED, "
                          "atualizado em 08/10/2026")
FONTE_CAGED_DEV = ("salario.com.br, Analista de Desenvolvimento de Sistemas (CBO 2124-05), "
                   "Florianopolis-SC, Novo CAGED, atualizado em 05/11/2026")
FONTE_ENCARGOS = ("ValorFinal - Guia de custo do funcionario CLT 2026: custo total de 1,44 a 1,71 vez o "
                  "salario; 1,71 para empresa fora do Simples, com beneficios")

# (chave, valor, unidade, descricao, fonte)
PREMISSAS = [
    ("volume_mensal", 650, "certificados/mes", "Volume de certificados emitidos",
     "AV01: 600 a 700 calibracoes/mes (ponto medio)"),
    ("tempo_manual_min", 25, "min/certificado", "Tempo medio por certificado no fluxo manual (planilha)",
     "Roteiro AV05 (referencia 25 min) + etapas manuais mapeadas na AV01; a validar por cronometragem"),
    ("tempo_auto_min", 2, "min/certificado", "Tempo medio por certificado no fluxo automatizado",
     "Roteiro AV05 (referencia 2 min); processamento do sistema medido em < 0,2 s"),
    ("salario_metrologista", 4970.26, "R$/mes", "Salario base do metrologista emissor", FONTE_CAGED_METRO),
    ("fator_custo_total", 1.71, "x salario", "Fator de custo total do empregado (encargos, provisoes e beneficios)",
     FONTE_ENCARGOS),
    ("horas_mes", 220, "h/mes", "Divisor de horas mensais (jornada de 44 h semanais)", "CLT, art. 58 e 64"),
    ("salario_dev", 12498.84, "R$/mes", "Salario base do desenvolvedor (investimento e sustentacao)",
     FONTE_CAGED_DEV),
    ("custo_nuvem_mensal", 0.0, "R$/mes", "Infraestrutura em nuvem (AWS Free Tier)",
     "Premissa do roteiro AV05; AWS Cost Explorer US$ 0,00 de 01 a 26/10/2026 (AV04)"),
    ("sustentacao_h_mes", 4, "h/mes", "Sustentacao e manutencao corretiva da aplicacao",
     "Estimativa do grupo"),
    ("h_dev_mvp", 200, "h", "Desenvolvimento do MVP ja realizado (AV03 a AV05), valorado a preco de mercado",
     "Estimativa do grupo: 4 integrantes x 50 h"),
    ("h_dev_producao", 320, "h", "Adequacao para producao (Calypso real, incerteza EA-4/02, HTTPS, banco gerenciado)",
     "Estimativa do grupo a partir das pendencias registradas nas AV03 e AV04"),
    ("h_validacao", 35, "h", "Validacao metrologica paralela (100 certificados x 15 min + 10 h do responsavel)",
     "Estimativa do grupo"),
    ("h_treino_usuarios", 12, "h", "Treinamento dos usuarios (6 pessoas x 2 h)", "Estimativa do grupo"),
    ("h_treino_instrutor", 4, "h", "Preparacao e conducao do treinamento (desenvolvedor)", "Estimativa do grupo"),
]


def premissas_base():
    return {k: v for k, v, *_ in PREMISSAS}


def calcular(p):
    r = {}
    r["volume_anual"] = p["volume_mensal"] * 12
    r["hora_tecnica"] = p["salario_metrologista"] * p["fator_custo_total"] / p["horas_mes"]
    r["hora_dev"] = p["salario_dev"] * p["fator_custo_total"] / p["horas_mes"]
    r["horas_manual"] = r["volume_anual"] * p["tempo_manual_min"] / 60
    r["horas_auto"] = r["volume_anual"] * p["tempo_auto_min"] / 60
    r["horas_economizadas"] = r["horas_manual"] - r["horas_auto"]
    r["reducao_tempo_pct"] = 1 - p["tempo_auto_min"] / p["tempo_manual_min"]
    r["custo_mo_manual"] = r["horas_manual"] * r["hora_tecnica"]
    r["custo_mo_auto"] = r["horas_auto"] * r["hora_tecnica"]
    r["custo_nuvem_anual"] = p["custo_nuvem_mensal"] * 12
    r["custo_sustentacao_anual"] = p["sustentacao_h_mes"] * 12 * r["hora_dev"]
    r["custo_total_manual"] = r["custo_mo_manual"]
    r["custo_total_auto"] = r["custo_mo_auto"] + r["custo_nuvem_anual"] + r["custo_sustentacao_anual"]
    r["economia_bruta"] = r["custo_mo_manual"] - r["custo_mo_auto"]  # OPEX Saved
    r["custos_recorrentes"] = r["custo_nuvem_anual"] + r["custo_sustentacao_anual"]
    r["economia_liquida"] = r["economia_bruta"] - r["custos_recorrentes"]
    inv = {
        "dev_mvp": p["h_dev_mvp"] * r["hora_dev"],
        "dev_producao": p["h_dev_producao"] * r["hora_dev"],
        "validacao": p["h_validacao"] * r["hora_tecnica"],
        "treinamento": p["h_treino_usuarios"] * r["hora_tecnica"] + p["h_treino_instrutor"] * r["hora_dev"],
    }
    inv = {k: v * p.get("multiplicador_investimento", 1) for k, v in inv.items()}
    r["investimento_itens"] = inv
    r["investimento"] = sum(inv.values())
    r["economia_liquida_mensal"] = r["economia_liquida"] / 12
    r["roi_1ano"] = (r["economia_liquida"] - r["investimento"]) / r["investimento"]
    r["roi_3anos"] = (3 * r["economia_liquida"] - r["investimento"]) / r["investimento"]
    r["payback_meses"] = (r["investimento"] / r["economia_liquida_mensal"]
                          if r["economia_liquida_mensal"] > 0 else float("inf"))
    r["fte_liberado"] = r["horas_economizadas"] / (p["horas_mes"] * 12)
    # minimo de minutos economizados por certificado para ROI = 0 em 12 meses
    r["breakeven_min_por_cert"] = ((r["investimento"] + r["custos_recorrentes"]) * 60
                                  / (r["volume_anual"] * r["hora_tecnica"]))
    return r


def cenarios():
    base = premissas_base()
    cons = dict(base, volume_mensal=600, tempo_manual_min=15, tempo_auto_min=3, salario_metrologista=3416.43,
                multiplicador_investimento=1.3)
    otim = dict(base, volume_mensal=700)
    nuvem = dict(base, custo_nuvem_mensal=100.0)
    return [
        ("Conservador", cons, "600 cert./mes; 15 -> 3 min; salario CBO 3523-05 (R$ 3.416,43); investimento +30%"),
        ("Base", base, "650 cert./mes; 25 -> 2 min; salario CBO 2012-10 (R$ 4.970,26)"),
        ("Otimista", otim, "700 cert./mes; 25 -> 2 min; salario CBO 2012-10"),
        ("Base + nuvem paga", nuvem, "Base com R$ 100/mes de nuvem (apos o Free Tier; valor arbitrado)"),
    ]


def fluxo_acumulado(r, meses=36):
    return [-r["investimento"] + r["economia_liquida_mensal"] * m for m in range(meses + 1)]


# ------------------------------------------------------------------ planilha com formulas
def gerar_planilha(caminho):
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    azul, preto, verde = Font(name="Arial", color="0000FF"), Font(name="Arial"), Font(name="Arial", color="008000")
    negrito = Font(name="Arial", bold=True)
    titulo = Font(name="Arial", bold=True, size=13)
    cab_fill = PatternFill("solid", fgColor="1F3A5F")
    cab_font = Font(name="Arial", bold=True, color="FFFFFF")
    amarelo = PatternFill("solid", fgColor="FFFF00")
    fino = Side(style="thin", color="BBBBBB")
    borda = Border(left=fino, right=fino, top=fino, bottom=fino)
    moeda = 'R$ #,##0.00;(R$ #,##0.00);"-"'
    num = '#,##0.00;(#,##0.00);"-"'
    pct = '0.0%;(0.0%);"-"'

    def cabecalho(ws, linha, textos):
        for j, t in enumerate(textos, start=1):
            c = ws.cell(linha, j, t)
            c.font, c.fill, c.border = cab_font, cab_fill, borda
            c.alignment = Alignment(wrap_text=True, vertical="center")

    # Premissas
    ws = wb.active
    ws.title = "Premissas"
    ws["A1"] = "Estudo de ROI - Automacao de certificados de calibracao (Schulz S.A.) - Premissas"
    ws["A1"].font = titulo
    ws["A2"] = ("Legenda: valores em AZUL sao entradas (altere aqui); fundo AMARELO = premissas-chave a validar "
                "com a Schulz. As demais abas recalculam automaticamente.")
    ws["A2"].font = Font(name="Arial", italic=True, size=9)
    cabecalho(ws, 4, ["Parametro", "Valor", "Unidade", "Descricao", "Fonte"])
    ref = {}
    chave_amarela = {"volume_mensal", "tempo_manual_min", "tempo_auto_min", "salario_metrologista"}
    for i, (k, v, u, d, f) in enumerate(PREMISSAS, start=5):
        ws.cell(i, 1, k).font = preto
        c = ws.cell(i, 2, v)
        c.font = azul
        c.number_format = moeda if k.startswith("salario") or k.startswith("custo") else num
        if k in chave_amarela:
            c.fill = amarelo
        ws.cell(i, 3, u).font = preto
        ws.cell(i, 4, d).font = preto
        ws.cell(i, 5, f).font = Font(name="Arial", size=9)
        for j in range(1, 6):
            ws.cell(i, j).border = borda
            ws.cell(i, j).alignment = Alignment(wrap_text=True, vertical="top")
        ref[k] = f"Premissas!$B${i}"
    for col, w in zip("ABCDE", (22, 14, 16, 52, 70)):
        ws.column_dimensions[col].width = w

    # Calculo
    wc = wb.create_sheet("Calculo")
    wc["A1"] = "Calculo do ROI - cenario base (formulas ligadas a aba Premissas)"
    wc["A1"].font = titulo
    cabecalho(wc, 3, ["Indicador", "Valor", "Formula / observacao"])
    P = lambda k: ref[k]  # noqa: E731
    linhas = [
        ("volume_anual", "Volume anual (certificados)", f"={P('volume_mensal')}*12", num, "volume mensal x 12"),
        ("hora_tecnica", "Custo da hora tecnica (R$/h)",
         f"={P('salario_metrologista')}*{P('fator_custo_total')}/{P('horas_mes')}", moeda,
         "salario x fator de custo total / horas mensais"),
        ("hora_dev", "Custo da hora do desenvolvedor (R$/h)",
         f"={P('salario_dev')}*{P('fator_custo_total')}/{P('horas_mes')}", moeda, "idem, para o desenvolvedor"),
        ("horas_manual", "Horas/ano - fluxo manual", f"=B4*{P('tempo_manual_min')}/60", num, "volume anual x min / 60"),
        ("horas_auto", "Horas/ano - fluxo automatizado", f"=B4*{P('tempo_auto_min')}/60", num, ""),
        ("horas_economizadas", "Horas economizadas por ano", "=B7-B8", num, "manual - automatizado"),
        ("custo_mo_manual", "Custo anual de mao de obra - manual", "=B7*B5", moeda, ""),
        ("custo_mo_auto", "Custo anual de mao de obra - automatizado", "=B8*B5", moeda, ""),
        ("economia_bruta", "ECONOMIA BRUTA ANUAL (OPEX Saved)", "=B10-B11", moeda, "custo manual - custo automatizado"),
        ("custo_nuvem_anual", "Custo anual de nuvem", f"={P('custo_nuvem_mensal')}*12", moeda, "Free Tier = R$ 0,00"),
        ("custo_sustentacao_anual", "Custo anual de sustentacao", f"={P('sustentacao_h_mes')}*12*B6", moeda, ""),
        ("economia_liquida", "ECONOMIA LIQUIDA ANUAL", "=B12-B13-B14", moeda, "bruta - nuvem - sustentacao"),
        ("inv_dev_mvp", "Investimento: desenvolvimento do MVP", f"={P('h_dev_mvp')}*B6", moeda, ""),
        ("inv_dev_producao", "Investimento: adequacao para producao", f"={P('h_dev_producao')}*B6", moeda, ""),
        ("inv_validacao", "Investimento: validacao metrologica", f"={P('h_validacao')}*B5", moeda, ""),
        ("inv_treinamento", "Investimento: treinamento",
         f"={P('h_treino_usuarios')}*B5+{P('h_treino_instrutor')}*B6", moeda, ""),
        ("investimento", "INVESTIMENTO TOTAL", "=SUM(B16:B19)", moeda, ""),
        ("roi_1ano", "ROI em 12 meses", "=IFERROR((B15-B20)/B20,0)", pct,
         "(Economia Liquida - Investimento) / Investimento"),
        ("payback_meses", "Payback (meses)", "=IFERROR(B20/(B15/12),0)", num, "Investimento / (Economia Liquida / 12)"),
        ("roi_3anos", "ROI em 36 meses", "=IFERROR((3*B15-B20)/B20,0)", pct, ""),
        ("fte_liberado", "Capacidade liberada (postos em tempo integral)", f"=B9/({P('horas_mes')}*12)", num, ""),
        ("breakeven_min_por_cert", "Minutos economizados/certificado para ROI = 0 em 12 meses",
         "=IFERROR((B20+B13+B14)*60/(B4*B5),0)", num, "ponto de equilibrio do 1o ano"),
    ]
    for i, (_, rotulo, formula, fmt, obs) in enumerate(linhas, start=4):
        wc.cell(i, 1, rotulo).font = negrito if rotulo.isupper() or rotulo.startswith(("ROI", "Payback")) else preto
        c = wc.cell(i, 2, formula)
        c.font, c.number_format = preto, fmt
        wc.cell(i, 3, obs).font = Font(name="Arial", size=9)
        for j in range(1, 4):
            wc.cell(i, j).border = borda
    for col, w in zip("ABC", (52, 18, 52)):
        wc.column_dimensions[col].width = w

    # Fluxo acumulado
    wf = wb.create_sheet("Fluxo_36_meses")
    wf["A1"] = "Fluxo de caixa acumulado (a partir da entrada em operacao)"
    wf["A1"].font = titulo
    cabecalho(wf, 3, ["Mes", "Economia liquida do mes (R$)", "Saldo acumulado (R$)"])
    for m in range(0, 37):
        i = 4 + m
        wf.cell(i, 1, m).font = preto
        wf.cell(i, 2, "=0" if m == 0 else "=Calculo!$B$15/12").font = verde
        wf.cell(i, 3, "=-Calculo!$B$20" if m == 0 else f"=C{i - 1}+B{i}").font = preto
        wf.cell(i, 2).number_format = wf.cell(i, 3).number_format = moeda
    for col, w in zip("ABC", (8, 28, 24)):
        wf.column_dimensions[col].width = w

    # Cenarios (entradas proprias + mesmas formulas)
    wsn = wb.create_sheet("Cenarios")
    wsn["A1"] = "Analise de sensibilidade (entradas em azul por cenario)"
    wsn["A1"].font = titulo
    cen = cenarios()
    cabecalho(wsn, 3, ["Item"] + [n for n, _, _ in cen])
    entradas = [("Volume mensal", "volume_mensal", num), ("Tempo manual (min)", "tempo_manual_min", num),
                ("Tempo automatizado (min)", "tempo_auto_min", num), ("Salario do metrologista", "salario_metrologista", moeda),
                ("Custo de nuvem (R$/mes)", "custo_nuvem_mensal", moeda),
                ("Multiplicador do investimento", "multiplicador_investimento", num)]
    for i, (rot, k, fmt) in enumerate(entradas, start=4):
        wsn.cell(i, 1, rot).font = preto
        for j, (_, pc, _) in enumerate(cen, start=2):
            c = wsn.cell(i, j, pc.get(k, 1))
            c.font, c.number_format = azul, fmt
    # linhas 4..9 sao entradas; 10.. formulas
    saidas = [
        ("Hora tecnica (R$/h)", "={c}7*" + P("fator_custo_total") + "/" + P("horas_mes"), moeda),
        ("Horas economizadas/ano", "={c}4*12*({c}5-{c}6)/60", num),
        ("Economia bruta anual", "={c}11*{c}10", moeda),
        ("Custos recorrentes", "={c}8*12+Calculo!$B$14", moeda),
        ("Economia liquida anual", "={c}12-{c}13", moeda),
        ("Investimento", "=((" + P("h_dev_mvp") + "+" + P("h_dev_producao") + "+" + P("h_treino_instrutor")
         + ")*Calculo!$B$6+(" + P("h_validacao") + "+" + P("h_treino_usuarios") + ")*{c}10)*{c}9", moeda),
        ("ROI 12 meses", "=IFERROR(({c}14-{c}15)/{c}15,0)", pct),
        ("Payback (meses)", "=IFERROR({c}15/({c}14/12),0)", num),
        ("ROI 36 meses", "=IFERROR((3*{c}14-{c}15)/{c}15,0)", pct),
    ]
    for i, (rot, f, fmt) in enumerate(saidas, start=10):
        wsn.cell(i, 1, rot).font = negrito if rot.startswith(("ROI", "Payback")) else preto
        for j in range(2, 2 + len(cen)):
            col = chr(ord("A") + j - 1)
            c = wsn.cell(i, j, f.format(c=col))
            c.font, c.number_format = preto, fmt
    for i, (_, _, desc) in enumerate(cen, start=2):
        wsn.cell(20, i, desc).font = Font(name="Arial", size=8, italic=True)
        wsn.cell(20, i).alignment = Alignment(wrap_text=True, vertical="top")
    wsn.cell(20, 1, "Descricao").font = preto
    wsn.column_dimensions["A"].width = 32
    for col in "BCDE":
        wsn.column_dimensions[col].width = 24
    wsn.cell(4, 5).comment = Comment("Valor arbitrado para teste de sensibilidade apos o Free Tier.", "Grupo 6")
    wb.save(caminho)


# ------------------------------------------------------------------ graficos (impressao)
def gerar_graficos(r, cen):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    AZUL, LARANJA, TINTA, TINTA2, GRADE = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRADE,
                         "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2})
    br = lambda v, casas=0: f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731

    def limpar(ax):
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color=GRADE, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(length=0)

    # 1) Comparativo manual x automatizado (dois paineis, escalas proprias)
    fig, eixos = plt.subplots(1, 2, figsize=(8.6, 3.4), dpi=200)
    dados = [("Horas de trabalho por ano", r["horas_manual"], r["horas_auto"], lambda v: f"{br(v)} h"),
             ("Custo anual de mão de obra (R$)", r["custo_mo_manual"], r["custo_mo_auto"], lambda v: f"R$ {br(v)}")]
    for ax, (tit, vm, va, fmt) in zip(eixos, dados):
        barras = ax.bar(["Manual\n(planilha)", "Automatizado\n(MVP)"], [vm, va], color=[LARANJA, AZUL], width=0.5)
        for b, v in zip(barras, (vm, va)):
            ax.text(b.get_x() + b.get_width() / 2, v, fmt(v), ha="center", va="bottom", fontsize=9, color=TINTA)
        ax.set_title(tit, fontsize=10, color=TINTA, loc="left")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: br(v)))
        ax.set_ylim(0, vm * 1.15)
        limpar(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDA, "grafico_comparativo.png"))
    plt.close(fig)

    # 2) Fluxo de caixa acumulado e payback
    fluxo = fluxo_acumulado(r, 24)
    fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=200)
    ax.plot(range(len(fluxo)), fluxo, color=AZUL, linewidth=2, marker="o", markersize=3)
    ax.axhline(0, color=TINTA2, linewidth=1)
    pb = r["payback_meses"]
    ax.plot([pb, pb], [0, fluxo[-1] * 1.05], color=TINTA2, linewidth=1, linestyle="--")
    ax.annotate(f"Payback ≈ {br(pb, 1)} meses", xy=(pb, 0), xytext=(pb + 0.6, -r["investimento"] * 0.3),
                fontsize=9, color=TINTA)
    ax.annotate(f"Investimento: R$ {br(r['investimento'])}", xy=(0, fluxo[0]), xytext=(1.2, fluxo[0]),
                fontsize=9, color=TINTA, va="center")
    ax.annotate(f"Saldo em 24 meses: R$ {br(fluxo[-1])}", xy=(24, fluxo[-1]), xytext=(11.5, fluxo[-1]),
                fontsize=9, color=TINTA, va="center")
    ax.set_ylim(fluxo[0] * 1.3, fluxo[-1] * 1.12)
    ax.set_xlabel("Meses após a entrada em operação")
    ax.set_title("Saldo acumulado (R$) - cenário base", fontsize=10, color=TINTA, loc="left")
    ax.set_xticks(range(0, 25, 3))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: br(v)))
    limpar(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDA, "grafico_payback.png"))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-graficos", action="store_true")
    ap.add_argument("--sem-planilha", action="store_true")
    a = ap.parse_args()
    os.makedirs(SAIDA, exist_ok=True)
    base = calcular(premissas_base())
    cen = [(n, calcular(p), d) for n, p, d in cenarios()]
    saida = {"premissas": [{"chave": k, "valor": v, "unidade": u, "descricao": d, "fonte": f}
                           for k, v, u, d, f in PREMISSAS],
             "base": base,
             "cenarios": [{"nome": n, "descricao": d, **{k: v for k, v in r.items() if k != "investimento_itens"}}
                          for n, r, d in cen],
             "fluxo_24_meses": fluxo_acumulado(base, 24)}
    with open(os.path.join(SAIDA, "roi_resultados.json"), "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    if not a.sem_planilha:
        gerar_planilha(os.path.join(SAIDA, "estudo_roi_schulz.xlsx"))
    if not a.sem_graficos:
        gerar_graficos(base, cen)
    print(f"Hora tecnica: R$ {base['hora_tecnica']:.2f} | horas economizadas: {base['horas_economizadas']:.0f} h/ano")
    print(f"Economia bruta: R$ {base['economia_bruta']:.2f} | liquida: R$ {base['economia_liquida']:.2f}")
    print(f"Investimento: R$ {base['investimento']:.2f} | ROI 12m: {base['roi_1ano'] * 100:.1f}% | "
          f"payback: {base['payback_meses']:.1f} meses | ROI 36m: {base['roi_3anos'] * 100:.1f}%")
    for n, r, _ in cen:
        print(f"  {n:18s} EL R$ {r['economia_liquida']:>11.2f}  I R$ {r['investimento']:>10.2f}  "
              f"ROI {r['roi_1ano'] * 100:6.1f}%  payback {r['payback_meses']:5.1f} m  ROI36 {r['roi_3anos'] * 100:6.1f}%")


if __name__ == "__main__":
    main()
