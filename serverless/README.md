
# Arquitetura Serverless — Schulz MVP

Este diretório contém uma implementação de referência
utilizando AWS SAM, AWS Lambda e API Gateway.

## Arquivos

- `template.yaml`: infraestrutura como código.
- `src/app.py`: função Lambda de exemplo.

## Implantação com AWS SAM

```bash
sam build --template-file template.yaml
sam deploy --guided
```

Os comandos devem ser executados dentro da pasta
`serverless`, com AWS CLI e SAM CLI configurados.

## Situação do projeto

O MVP funcional foi implantado no AWS Elastic Beanstalk,
utilizando Flask e SQLite.

Esta arquitetura Serverless é uma referência acadêmica
e não foi implantada na AWS.
