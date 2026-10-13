# MVP - Emissão de Certificados de Calibração (AV03, Projeto Aplicado III)

Aplicação web que importa planilhas .xlsx com leituras de instrumento, calcula média, desvio padrão e erro sistemático por ponto,
compara o erro absoluto com o LEA, atribui o parecer (APROVADO/REPROVADO) e emite o certificado em PDF após análise por usuário distinto do elaborador.

Repositório público: https://github.com/WesleyWiltuschnig/schulz-certificados-mvp.git

## Tecnologias

Python 3.12, Flask, openpyxl, SQLite, reportlab, pytest. Cálculo com `decimal.Decimal`.

## Execução

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py            # http://127.0.0.1:5000
```

Docker (não validado no ambiente de desenvolvimento): `docker build -t certificados . && docker run -p 8000:8000 certificados`.

Usuários de demonstração (senha `senha123`, alterável pela variável `SENHA_DEMO`): `executor1`, `emissor1`, `signatario1`, `admin`, `auditor1`.
Padrões de demonstração fictícios: 500008 e 500011. Variáveis: `SECRET_KEY`, `INSTANCE_DIR`.

## Uso

1. Entrar como `executor1`, abrir "Nova calibração", escolher o padrão e enviar uma planilha (modelo em `/modelo.xlsx`; amostras em `samples/`).
2. O sistema valida, calcula e mostra o resultado em situação AGUARDANDO_ANALISE.
3. Entrar como `emissor1` (ou `signatario1`), abrir a calibração e finalizar ou devolver com justificativa.
4. Baixar o PDF e consultar por instrumento, número, situação ou período.

Leiaute da planilha: cabeçalho com pares rótulo/valor (Instrumento, Denominação, Plano de medição, Data da medição, Temperatura ambiente,
Padrão do relatório, Metrologista, LEA geral opcional), seguido de tabela com Ponto, Valor_Padrao, Leitura_1, Leitura_2, LEA e, opcionalmente, Desvio.
É um leiaute simplificado definido pelo grupo; não é o relatório Calypso real.

## Regras implementadas

Média, desvio padrão amostral, erro = média - padrão; DENTRO_DA_TOLERANCIA quando |erro| <= LEA; APROVADO somente se todos os pontos estão dentro.
Recusa de plano `_TESTE`, padrão divergente, número de leituras diferente de 2, data-sentinela, temperatura não numérica, campos obrigatórios ausentes
e arquivo repetido. Bloqueio de marcadores (XX, YY, {{ }}) antes do PDF. Segregação de funções, numeração NNNNN/AAAA transacional,
certificado imutável (gatilhos no banco), hash SHA-256 do PDF conferido no download, trilha de auditoria.

## Estrutura

```
app/            código (ingestao, metrologia, servicos, pdfgen, views, db, templates)
tests/          54 testes automatizados
scripts/        gerar_amostras, gerar_evidencias, smoke_http, gerar_relatorio, matriz
samples/        planilhas sintéticas
docs/           relatório PDF, matriz de rastreabilidade, evidencias/
```

## Testes

```
python -m pytest                                  # 54 testes
python scripts/gerar_evidencias.py                # cenário, desempenho, capturas
python wsgi.py &  python scripts/smoke_http.py http://127.0.0.1:5000
```

Resultado da última execução neste ambiente: 54 passaram, 0 falharam; 9 de 9 verificações do teste de fumaça HTTP. Detalhes em `docs/evidencias/`.
