
# MVP - Emissão de Certificados de Calibração (AV03, AV04 e AV05, Projeto Aplicado III)

Aplicação web que importa planilhas `.xlsx` com leituras de instrumento, calcula média, desvio padrão e erro sistemático por ponto, compara o erro absoluto com o LEA, atribui o parecer (APROVADO/REPROVADO) e emite o certificado em PDF após análise por usuário distinto do elaborador.

**Repositório público:**  
https://github.com/WesleyWiltuschnig/schulz-certificados-mvp

## Execução rápida no Windows — AV05

1. Instale o **Python 3.10 ou superior** (https://www.python.org/downloads/) marcando *Add python.exe to PATH*.
2. Baixe este repositório (*Code → Download ZIP*) e extraia a pasta, ou `git clone`.
3. Dê dois cliques em **`iniciar_aplicacao_schulz.bat`** (na raiz do repositório).

O script verifica o Python 3.10+ no PATH, cria e ativa o ambiente virtual `.venv`, instala o `requirements.txt`, inicia a API backend (`app.py`) numa janela própria e abre a interface no navegador padrão (http://127.0.0.1:5000). Na segunda execução, a instalação é pulada se o `requirements.txt` não mudou.

- Usuários locais de demonstração: `executor1`, `emissor1`, `signatario1`, `admin`, `auditor1` — senha `senha123`.
- Planilha de teste: `samples/01_valida_aprovada.xlsx` (entre como `executor1` → *Nova calibração*).
- Para validar pelo **celular** na mesma rede Wi-Fi: `iniciar_aplicacao_schulz.bat rede` (o QR Code passa a usar o IP da máquina; o Windows pode pedir liberação no firewall).
- Para encerrar: feche a janela **"Schulz MVP - API backend"**.

Em Linux/macOS: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python app.py --abrir-navegador`.

### Novidades da AV05

- **QR Code de validação mobile** impresso em todo certificado finalizado. A leitura pela câmera do celular abre `/validar/<código>`, página pública (sem login) com parecer, resultado por ponto, situação e integridade do PDF (SHA-256). A página também permite **conferir um PDF recebido** contra o hash registrado. Cada consulta entra na trilha de auditoria.
- **API**: `GET /api/status` (saúde, usada pelo .bat) e `GET /api/validar/<código>` (validação em JSON).
- **`app.py`** na raiz: ponto de entrada da aplicação (`--porta`, `--rede`, `--abrir-navegador`).
- **Testes**: 75 testes automatizados (54 da AV03 + 21 da AV05), executados em Python 3.10, 3.13 e 3.14. `pypdf` foi incluído no `requirements.txt` (era exigido por um teste e faltava).
- Relatório da AV05: `docs/Relatorio_AV05_Grupo6.pdf`. Evidências em `docs/evidencias_av05/` (geradas por `scripts/gerar_evidencias_av05.py`) e estudo de ROI em `docs/roi/` (`scripts/calcular_roi.py` e `estudo_roi_schulz.xlsx`, com fórmulas).

## Implantação na AWS — AV04

O MVP funcional foi implantado na Amazon Web Services (AWS), utilizando o serviço **Elastic Beanstalk**, com aplicação desenvolvida em Flask e banco de dados SQLite.

**Acesse a aplicação:**  
http://schulz-mvp-teste.us-east-2.elasticbeanstalk.com/

**Informações da implantação:**

- **Provedor:** Amazon Web Services (AWS)
- **Serviço:** AWS Elastic Beanstalk
- **Região:** us-east-2 (Ohio)
- **Ambiente:** schulz-mvp-teste
- **Aplicação:** Python / Flask
- **Banco de dados:** SQLite

A implantação permite demonstrar autenticação, importação de planilhas, cálculos metrológicos, análise de calibrações, emissão de certificados PDF e trilha de auditoria.

## Scripts Serverless — AV04

O repositório também disponibiliza uma implementação de referência utilizando **AWS SAM, AWS Lambda e Amazon API Gateway**.

**Arquivos disponíveis:**

- `serverless/template.yaml` — definição da infraestrutura AWS SAM.
- `serverless/src/app.py` — função Lambda demonstrativa com rota de status.
- `serverless/README.md` — instruções para construção e implantação do exemplo.

**Acesse a pasta Serverless:**  
https://github.com/WesleyWiltuschnig/schulz-certificados-mvp/tree/main/serverless

**Observação:** os scripts Serverless foram publicados como referência arquitetural. Eles não representam a implantação completa do MVP. A aplicação funcional demonstrada na AV04 está hospedada no AWS Elastic Beanstalk.

## Tecnologias

Python 3.12, Flask, openpyxl, SQLite, reportlab, pytest. Cálculo com `decimal.Decimal`.

Na implantação da AV04 também foram utilizados AWS Elastic Beanstalk e serviços da AWS. O exemplo de infraestrutura Serverless utiliza AWS SAM, Lambda e API Gateway.

## Execução

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py
```

Acesso local: http://127.0.0.1:5000

Docker (não validado no ambiente de desenvolvimento):

```bash
docker build -t certificados .
docker run -p 8000:8000 certificados
```

Usuários de demonstração: `executor1`, `emissor1`, `signatario1`, `admin`, `auditor1`.

A senha de demonstração pode ser configurada pela variável de ambiente `SENHA_DEMO`.

Padrões de demonstração fictícios: `500008` e `500011`.

Variáveis: `SECRET_KEY`, `INSTANCE_DIR`.

## Uso

1. Entrar como `executor1`, abrir "Nova calibração", escolher o padrão e enviar uma planilha (modelo em `/modelo.xlsx`; amostras em `samples/`).
2. O sistema valida, calcula e mostra o resultado em situação `AGUARDANDO_ANALISE`.
3. Entrar como `emissor1` (ou `signatario1`), abrir a calibração e finalizar ou devolver com justificativa.
4. Baixar o PDF e consultar por instrumento, número, situação ou período.

Leiaute da planilha: cabeçalho com pares rótulo/valor (Instrumento, Denominação, Plano de medição, Data da medição, Temperatura ambiente, Padrão do relatório, Metrologista, LEA geral opcional), seguido de tabela com Ponto, Valor_Padrao, Leitura_1, Leitura_2, LEA e, opcionalmente, Desvio.

É um leiaute simplificado definido pelo grupo; não é o relatório Calypso real.

## Regras implementadas

Média, desvio padrão amostral, erro = média - padrão; `DENTRO_DA_TOLERANCIA` quando `|erro| <= LEA`; `APROVADO` somente se todos os pontos estão dentro.

Recusa de plano `_TESTE`, padrão divergente, número de leituras diferente de 2, data-sentinela, temperatura não numérica, campos obrigatórios ausentes e arquivo repetido.

Bloqueio de marcadores (`XX`, `YY`, `{{ }}`) antes do PDF.

Segregação de funções, numeração `NNNNN/AAAA` transacional, certificado imutável (gatilhos no banco), hash SHA-256 do PDF conferido no download e trilha de auditoria.

## Estrutura

```text
app.py          ponto de entrada (API backend + interface web) — AV05
iniciar_aplicacao_schulz.bat   instalação e execução automatizadas no Windows — AV05
app/            código (ingestao, metrologia, servicos, pdfgen, validacao, views, db, templates)
tests/          75 testes automatizados
scripts/        gerar_amostras, gerar_evidencias, smoke_http, gerar_relatorio, matriz
samples/        planilhas sintéticas
serverless/     scripts de referência AWS SAM, Lambda e API Gateway
docs/           relatórios PDF, matriz de rastreabilidade, evidencias/, evidencias_av05/, roi/
```

## Testes

```bash
python -m pytest
python scripts/gerar_evidencias.py
python wsgi.py
```

Com a aplicação em execução, em outro terminal:

```bash
python scripts/smoke_http.py http://127.0.0.1:5000
```

**Resultado da última execução documentada:**

- AV05: 75 testes automatizados aprovados, 0 com falha (Python 3.10, 3.13 e 3.14); 9 de 9 verificações do teste de fumaça HTTP contra o servidor iniciado pelo `app.py`.
- AV03: 54 testes aprovados e 9 de 9 verificações HTTP.

Detalhes em `docs/evidencias/` e `docs/evidencias_av05/`.

## Demonstração funcional — AV04

A aplicação publicada na AWS foi utilizada para demonstrar o processamento de uma calibração com dados sintéticos.

**Cenário demonstrado:**

- Instrumento: `MP-0042`
- Quantidade de pontos: 4
- Parecer: `APROVADO`
- Certificado: `00001/2026`
- Versão: 1
- Finalização por usuário autorizado
- Download do certificado PDF
- Registro de eventos na trilha de auditoria

O cenário demonstra o fluxo de processamento, análise e emissão do certificado.

## Custos da AWS

O acompanhamento dos custos foi realizado por meio do AWS Cost Explorer.

Na consulta documentada entre **1º e 26 de outubro de 2026**, o valor apresentado foi de **US$ 0,00**.

Esse resultado corresponde ao período consultado e não garante gratuidade futura.

## Vídeo de demonstração — AV04

O vídeo narrado apresenta a aplicação funcionando na AWS, o processamento de calibrações, a emissão do certificado e os arquivos publicados no GitHub.

**Link do vídeo no YouTube:**
https://youtu.be/-BUnlBlhwDs

## Considerações finais

O projeto demonstra a viabilidade de automatizar etapas do processo de emissão de certificados de calibração por meio de uma aplicação web.

A AV03 consolidou a implementação e os testes do MVP. A AV04 acrescentou a implantação e a demonstração funcional na AWS, além da publicação dos scripts Serverless de referência no GitHub.

A solução foi desenvolvida como prova de conceito acadêmica, utilizando dados fictícios, e pode ser aprimorada futuramente para atender a requisitos corporativos.
