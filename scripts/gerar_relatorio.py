"""Gera docs/Relatorio_AV03_Grupo6.pdf e docs/matriz_rastreabilidade.md a partir dos resultados reais."""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
from matriz import MATRIZ  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

EV = os.path.join(RAIZ, "docs", "evidencias")
ler = lambda n: open(os.path.join(EV, n), encoding="utf-8").read()  # noqa: E731

pytest_txt = ler("pytest_resultado.txt")
passou = re.findall(r"tests/(\w+\.py)::(\w+) PASSED", pytest_txt)
resumo = re.search(r"(\d+) passed in ([\d.]+)s", pytest_txt)
assert resumo and int(resumo.group(1)) == len(passou), "resultado do pytest inconsistente"
n_testes, tempo = resumo.group(1), resumo.group(2)
smoke = ler("smoke_http.txt").strip()
desempenho = ler("desempenho.txt").strip()
cenario = ler("log_cenario.txt").strip()

# matriz em Markdown
with open(os.path.join(RAIZ, "docs", "matriz_rastreabilidade.md"), "w", encoding="utf-8") as f:
    f.write("# Matriz de rastreabilidade\n\nRequisitos das Atividades 1, 2 e 3 relacionados à implementação e à evidência.\n"
            "Situações: Atendido, Parcial, Pendente, Não aplicável.\n\n| ID | Requisito | Situação | Implementação | Evidência |\n|---|---|---|---|---|\n")
    for r in MATRIZ:
        f.write("| " + " | ".join(c.replace("|", "/") for c in r) + " |\n")
    from collections import Counter
    c = Counter(r[2] for r in MATRIZ)
    f.write("\nTotais: " + ", ".join(f"{k} {v}" for k, v in c.items()) + f" (de {len(MATRIZ)}).\n")

st = getSampleStyleSheet()
corpo = ParagraphStyle("c", parent=st["BodyText"], fontSize=10, leading=14, alignment=4, spaceAfter=6)
peq = ParagraphStyle("p", parent=corpo, fontSize=7.5, leading=9, alignment=0, spaceAfter=0)
cod = ParagraphStyle("cod", parent=st["Code"], fontSize=7, leading=8.5)
h1 = ParagraphStyle("h1", parent=st["Heading1"], fontSize=14, spaceBefore=12, spaceAfter=6)
h2 = ParagraphStyle("h2", parent=st["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=4)
centro = ParagraphStyle("ce", parent=corpo, alignment=1)
P = lambda t, s=corpo: Paragraph(t, s)  # noqa: E731


def tabela(linhas, larguras, cab=True, estilo=peq):
    dados = [[Paragraph(str(c), estilo) for c in l] for l in linhas]
    t = Table(dados, colWidths=[w * mm for w in larguras], repeatRows=1 if cab else 0)
    s = [("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if cab:
        s.append(("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey))
    t.setStyle(TableStyle(s))
    return t


def imagem(nome, largura=165):
    w, h = ImageReader(os.path.join(EV, nome)).getSize()
    return Image(os.path.join(EV, nome), width=largura * mm, height=largura * mm * h / w)


def rodape(c, d):
    c.saveState(); c.setFont("Helvetica", 8)
    c.drawString(18 * mm, 10 * mm, "Projeto Aplicado III - Grupo 6 - AV03")
    c.drawRightString(192 * mm, 10 * mm, f"Página {d.page}")
    c.restoreState()


S = []
S += [Spacer(1, 25 * mm), P("CENTRO UNIVERSITÁRIO SENAI SANTA CATARINA", centro),
      P("Curso Superior de Tecnologia em Análise e Desenvolvimento de Sistemas", centro),
      P("Unidade Curricular: Projeto Aplicado III - Professor: Hugo Menezes Barra", centro), Spacer(1, 40 * mm),
      P("<b>AV03 (Parte 1) - Construção da Aplicação Transacional do MVP</b>", ParagraphStyle("t", parent=centro, fontSize=16, leading=20)),
      P("Automação da emissão de certificados de calibração - Schulz S.A.", centro), Spacer(1, 30 * mm),
      P("Grupo 6", centro), P("Gustavo Borges<br/>Wesley Wiltuschnig<br/>Gabriel Colombo<br/>Thiago Hoegen", centro),
      Spacer(1, 40 * mm), P("Florianópolis/SC - 2026", centro), PageBreak()]

S += [P("1. Introdução e escopo", h1),
      P("Este relatório documenta o MVP construído para a AV03 do Projeto Aplicado III. A aplicação recebe uma planilha .xlsx com leituras "
        "de instrumento e valores do padrão, calcula a média das leituras, o erro sistemático e a classificação de cada ponto contra o Limite de "
        "Erro Admissível (LEA), atribui o parecer final e produz o certificado em PDF após análise e finalização por um usuário distinto do elaborador."),
      P("O desenvolvimento partiu exclusivamente dos três documentos entregues: Atividade 1 (levantamento de requisitos, Tema 01), Atividade 2 "
        "(arquitetura AWS, Tema 02) e Atividade 3 (orientação da AV03). Não houve acesso às planilhas reais da Schulz, ao relatório Calypso "
        "nem ao método de balanço de incerteza. Todos os dados usados nos testes são sintéticos e foram gerados pelo próprio projeto."),
      P("Observação sobre o enunciado: a Atividade 3 numera os itens como Item 1 e Item 3, sem Item 2. Foi implementada também a interface web "
        "(exigida na visão geral do documento). Se o Item 2 existir em outra parte da AV03, ele não foi considerado."),
      P("2. Requisitos selecionados", h1),
      P("Foram priorizados os requisitos do Quadro 14 marcados como MVP, as regras de negócio aplicáveis ao fluxo de cálculo e parecer e os critérios "
        "de aceite da seção 9.1 da Atividade 2. Ficaram fora, por falta de insumos, o balanço de incerteza (RF08, RF09, RN12, RN13) e a comparação "
        "com a planilha vigente (RNF03). A matriz completa está na seção 7."),
      P("3. Arquitetura e decisões técnicas", h1),
      P("A Atividade 2 propõe uma arquitetura serverless na AWS. Como não há conta, créditos nem recursos criados, o MVP foi construído como "
        "aplicação monolítica executável localmente, preservando a separação de responsabilidades e as regras da arquitetura proposta. "
        "Nenhum serviço AWS foi usado, implantado ou testado."),
      tabela([["Componente da Atividade 2", "Equivalente no MVP", "Diferença relevante"],
              ["CloudFront + S3 (frontend)", "Templates HTML renderizados pelo Flask", "Sem CDN e sem HTTPS próprio"],
              ["Cognito", "Login por sessão, perfis e CSRF", "Sem MFA e sem JWT"],
              ["API Gateway + Lambda API", "Rotas Flask com decorador de perfil", "Processo único"],
              ["S3 de entrada", "instance/uploads (arquivo original guardado)", "Sem URL pré-assinada nem evento"],
              ["Lambda ETL + SQS + Lambda certificado", "Funções síncronas em app/servicos.py, uma transação", "Sem fila nem reprocessamento"],
              ["DynamoDB", "SQLite com o modelo relacional do Tema 01", "Mudança deliberada: transações e gatilhos de imutabilidade"],
              ["S3 de certificados", "instance/certificados com SHA-256 no banco", "Sem versionamento de objeto"],
              ["CloudWatch / CloudTrail", "Tabelas auditoria e rejeicoes", "Sem métricas nem alarmes"],
              ["IAM", "Perfis de aplicação (executor, emissor, signatário, administrador, auditor)", "Não há papéis de serviço"],
              ["Budgets", "Não aplicável", "Nada implantado"]], [52, 70, 52]), Spacer(1, 3 * mm),
      P("<b>Tecnologias.</b> Python 3.12, Flask (web e rotas), openpyxl (leitura de .xlsx sem executar macros), Decimal (aritmética exata), SQLite "
        "(persistência transacional), reportlab (PDF), pytest (testes). O Dockerfile atende à orientação do RNF05, mas não foi construído por falta de Docker no ambiente."),
      P("<b>Decisões.</b> (a) Decimal em todo o cálculo e persistência em texto, para preservar sete casas (RNF04). (b) Importação, cálculo e persistência em "
        "uma única transação. (c) Numeração do certificado na mesma transação da finalização, de modo que falha não consome número. (d) Gatilhos SQLite "
        "que impedem UPDATE e DELETE em certificados e em calibrações finalizadas. (e) Hash SHA-256 do PDF conferido a cada download. (f) A planilha traz "
        "o LEA por ponto (ou um LEA geral), conforme a Atividade 3; o cadastro de critérios do Tema 01 não foi modelado."),
      P("4. Funcionamento", h1),
      P("<b>Leiaute da planilha.</b> Bloco de cabeçalho com pares rótulo/valor (Instrumento, Denominação, Plano de medição, Data da medição, "
        "Temperatura ambiente, Padrão do relatório, Metrologista, LEA geral opcional), seguido de uma tabela com as colunas Ponto, Valor_Padrao, "
        "Leitura_1, Leitura_2, LEA e, opcionalmente, Desvio. É um leiaute simplificado definido pelo grupo; não reproduz o relatório Calypso."),
      P("<b>Fluxo.</b> O executor escolhe o padrão e envia o arquivo. O sistema valida e higieniza, recalcula, grava e exibe o resultado em situação "
        "AGUARDANDO_ANALISE. Um emissor ou signatário diferente do elaborador finaliza (gera número e PDF) ou devolve com justificativa. "
        "Consulta, download e trilha de auditoria ficam disponíveis por perfil."),
      tabela([["Cálculo", "Definição implementada"],
              ["Média", "Média aritmética das leituras do ponto"],
              ["Desvio padrão", "Amostral (n-1) sobre as leituras"],
              ["Erro sistemático", "Média - valor padrão"],
              ["Classificação", "|erro| <= LEA: DENTRO_DA_TOLERANCIA; caso contrário FORA_DA_TOLERANCIA"],
              ["Parecer", "APROVADO se todos os pontos estão dentro; REPROVADO caso contrário"]], [40, 134]),
      Spacer(1, 3 * mm),
      P("<b>Validações de ingestão.</b> Recusa de arquivo que não seja .xlsx válido ou acima de 5 MB; campos obrigatórios; plano com sufixo _TESTE (RN10); "
        "padrão do relatório divergente do selecionado (RN03); número de leituras diferente de 2 (RN01); data-sentinela; temperatura não numérica (RN14); "
        "leitura ou LEA ausente ou inválido; ponto duplicado; arquivo já importado. Linhas sem identificação do ponto são suprimidas, não tratadas como zero. "
        "Avisos (não bloqueantes): desvio informado divergente do recalculado e padrão com calibração vencida na data da medição.")]

S += [PageBreak(), P("5. Testes realizados", h1),
      P(f"A suíte automatizada foi executada com pytest neste ambiente: <b>{n_testes} testes passaram, 0 falharam</b>, em {tempo} s. "
        "Durante o desenvolvimento um teste falhou por premissa incorreta do próprio teste (padrão vencido com data de medição ainda dentro da validade) "
        "e dois pontos foram corrigidos ao gerar as evidências: o teste de duplicidade dependia do relógio, porque cada geração do .xlsx produz bytes diferentes, "
        "e passou a reutilizar o mesmo arquivo. Os resultados abaixo são os da execução final."),
      tabela([["Arquivo de teste", "Testes", "Cobertura"],
              ["tests/test_metrologia.py", str(sum(1 for a, _ in passou if a == "test_metrologia.py")), "Média, desvio, erro, limite exato, parecer, precisão"],
              ["tests/test_ingestao.py", str(sum(1 for a, _ in passou if a == "test_ingestao.py")), "Leitura, higienização e cada motivo de recusa"],
              ["tests/test_fluxo.py", str(sum(1 for a, _ in passou if a == "test_fluxo.py")), "Fluxo ponta a ponta, perfis, segregação, imutabilidade, PDF, busca"]],
             [55, 20, 99]), Spacer(1, 3 * mm),
      P("<b>Teste de fumaça com servidor HTTP real</b> (gunicorn em 127.0.0.1, clientes HTTP externos ao framework):"),
      Paragraph(smoke.replace("\n", "<br/>").replace(" ", "&nbsp;"), cod), Spacer(1, 3 * mm),
      P("<b>Cenário de evidências</b> (scripts/gerar_evidencias.py, cliente de teste do Flask):"),
      Paragraph(cenario.replace("\n", "<br/>").replace(" ", "&nbsp;"), cod), Spacer(1, 3 * mm),
      P("<b>Desempenho</b> (dados sintéticos, SQLite local, processo único; não representa a AWS nem o volume de produção):"),
      Paragraph(desempenho.replace("\n", "<br/>").replace(" ", "&nbsp;"), cod)]

S += [PageBreak(), P("6. Evidências", h1),
      P("As imagens foram geradas a partir do HTML real devolvido pela aplicação durante o cenário (renderização com wkhtmltoimage). "
        "Os arquivos estão em docs/evidencias/."),
      KeepTogether([P("Figura 1 - Calibração aprovada, aguardando análise", h2), imagem("02_detalhe_aprovada.png", 150)]),
      KeepTogether([P("Figura 2 - Calibração reprovada (ponto P3 fora da tolerância)", h2), imagem("03_detalhe_reprovada.png", 150)]),
      KeepTogether([P("Figura 3 - Ingestão recusada por sufixo _TESTE", h2), imagem("04_recusa_teste.png", 150)]),
      KeepTogether([P("Figura 4 - Certificado finalizado, integridade e trilha de auditoria", h2), imagem("05_detalhe_finalizado.png", 150)]),
      KeepTogether([P("Figura 5 - Lista com filtro por situação", h2), imagem("07_lista_filtrada.png", 150)]),
      KeepTogether([P("Figura 6 - Certificado em PDF gerado pela aplicação", h2), imagem("certificado_exemplo-1.png", 95)])]

S += [PageBreak(), P("7. Matriz de rastreabilidade", h1),
      P("Situações: Atendido (implementado e com evidência), Parcial (implementado com limitação descrita), Pendente (não implementado), Não aplicável. "
        "Nomes de testes abreviados; os arquivos estão em tests/."),
      tabela([["ID", "Requisito", "Situação", "Implementação", "Evidência"]] + [list(r) for r in MATRIZ], [14, 34, 17, 62, 47])]

S += [P("8. Limitações e pendências", h1),
      P("Não implementados: balanço de incerteza e seleção do bloco aplicável (método e dados não fornecidos); comparação com a planilha vigente; "
        "reemissão com versão vinculada; leiaute parametrizável; cadastro de critérios, procedimentos e usuários; MFA; disponibilidade e implantação. "
        "O certificado gerado informa que a incerteza não foi apurada, portanto não substitui o certificado emitido pelo laboratório."),
      P("Não validados: leitura do relatório Calypso real e das planilhas da Schulz (apenas o leiaute simplificado foi testado); construção da imagem Docker; "
        "volume de 700 calibrações por mês (testadas 50 sintéticas); qualquer componente AWS; teste de usabilidade com usuários. "
        "A coleção de usuários e padrões de demonstração é fictícia e a senha padrão é apenas para uso local."),
      P("Pendências manuais do grupo: publicar o código em repositório público do GitHub e informar o link no AVA; anexar este relatório no AVA; "
        "decidir com o professor se o leiaute simplificado é aceito ou se será fornecido o relatório real."),
      P("9. Execução", h1),
      P("Instruções completas no README.md: instalar dependências (pip install -r requirements.txt), executar python wsgi.py e acessar http://127.0.0.1:5000; "
        "testes com python -m pytest; evidências com python scripts/gerar_evidencias.py.")]

S += [PageBreak(), P("Apêndice A - Testes executados", h1),
      tabela([["Arquivo", "Teste", "Resultado"]] + [[a, t, "PASSED"] for a, t in passou], [40, 110, 24])]

os.makedirs(os.path.join(RAIZ, "docs"), exist_ok=True)
SimpleDocTemplate(os.path.join(RAIZ, "docs", "Relatorio_AV03_Grupo6.pdf"), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                  topMargin=16 * mm, bottomMargin=18 * mm, title="Relatório AV03 - Grupo 6").build(S, onFirstPage=rodape, onLaterPages=rodape)
print("relatorio gerado")
