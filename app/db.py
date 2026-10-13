import contextlib
import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios(
  id INTEGER PRIMARY KEY, login TEXT UNIQUE NOT NULL, nome TEXT NOT NULL,
  papel TEXT NOT NULL CHECK(papel IN ('executor','emissor','signatario','administrador','auditor')),
  senha_hash TEXT NOT NULL, ativo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS padroes(
  id INTEGER PRIMARY KEY, codigo TEXT UNIQUE NOT NULL, denominacao TEXT NOT NULL, fabricante TEXT,
  numero_serie TEXT NOT NULL, certificado_rastreabilidade TEXT NOT NULL,
  data_ultima_calibracao TEXT NOT NULL, data_proxima_calibracao TEXT NOT NULL,
  CHECK(data_proxima_calibracao > data_ultima_calibracao));
CREATE TABLE IF NOT EXISTS calibracoes(
  id INTEGER PRIMARY KEY, instrumento TEXT NOT NULL, denominacao TEXT NOT NULL,
  plano_medicao TEXT NOT NULL, data_medicao TEXT NOT NULL, temperatura TEXT NOT NULL,
  metrologista_relatorio TEXT, padrao_id INTEGER NOT NULL REFERENCES padroes(id),
  executor_id INTEGER NOT NULL REFERENCES usuarios(id), arquivo_nome TEXT NOT NULL,
  arquivo_sha256 TEXT NOT NULL, blocos INTEGER NOT NULL,
  parecer TEXT NOT NULL CHECK(parecer IN ('APROVADO','REPROVADO')),
  avisos TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL CHECK(status IN ('AGUARDANDO_ANALISE','FINALIZADO','DEVOLVIDO')),
  justificativa_devolucao TEXT, criado_em TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cal_arquivo ON calibracoes(arquivo_sha256, padrao_id)
  WHERE status <> 'DEVOLVIDO';
CREATE TABLE IF NOT EXISTS pontos(
  id INTEGER PRIMARY KEY, calibracao_id INTEGER NOT NULL REFERENCES calibracoes(id),
  ordem INTEGER NOT NULL, nome TEXT NOT NULL, referencia TEXT NOT NULL, leituras TEXT NOT NULL,
  media TEXT NOT NULL, desvio_padrao TEXT NOT NULL, erro TEXT NOT NULL, erro_abs TEXT NOT NULL,
  lea TEXT NOT NULL,
  classificacao TEXT NOT NULL CHECK(classificacao IN ('DENTRO_DA_TOLERANCIA','FORA_DA_TOLERANCIA')),
  UNIQUE(calibracao_id, ordem));
CREATE TABLE IF NOT EXISTS contador_certificados(ano INTEGER PRIMARY KEY, ultimo INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS certificados(
  id INTEGER PRIMARY KEY, calibracao_id INTEGER NOT NULL REFERENCES calibracoes(id),
  versao INTEGER NOT NULL DEFAULT 1, numero TEXT UNIQUE NOT NULL, arquivo TEXT NOT NULL,
  pdf_sha256 TEXT NOT NULL, finalizado_por INTEGER NOT NULL REFERENCES usuarios(id),
  finalizado_em TEXT NOT NULL, UNIQUE(calibracao_id, versao));
CREATE TABLE IF NOT EXISTS auditoria(
  id INTEGER PRIMARY KEY, calibracao_id INTEGER, usuario_id INTEGER, acao TEXT NOT NULL,
  detalhe TEXT, criado_em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rejeicoes(
  id INTEGER PRIMARY KEY, usuario_id INTEGER, arquivo TEXT, arquivo_sha256 TEXT,
  motivos TEXT NOT NULL, criado_em TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS trg_cert_upd BEFORE UPDATE ON certificados
  BEGIN SELECT RAISE(ABORT, 'certificado finalizado e imutavel'); END;
CREATE TRIGGER IF NOT EXISTS trg_cert_del BEFORE DELETE ON certificados
  BEGIN SELECT RAISE(ABORT, 'certificado finalizado e imutavel'); END;
CREATE TRIGGER IF NOT EXISTS trg_cal_upd BEFORE UPDATE ON calibracoes WHEN OLD.status = 'FINALIZADO'
  BEGIN SELECT RAISE(ABORT, 'calibracao finalizada e imutavel'); END;
CREATE TRIGGER IF NOT EXISTS trg_cal_del BEFORE DELETE ON calibracoes WHEN OLD.status = 'FINALIZADO'
  BEGIN SELECT RAISE(ABORT, 'calibracao finalizada e imutavel'); END;
CREATE TRIGGER IF NOT EXISTS trg_pontos_upd BEFORE UPDATE ON pontos
  WHEN (SELECT status FROM calibracoes WHERE id = OLD.calibracao_id) = 'FINALIZADO'
  BEGIN SELECT RAISE(ABORT, 'calibracao finalizada e imutavel'); END;
CREATE TRIGGER IF NOT EXISTS trg_pontos_del BEFORE DELETE ON pontos
  WHEN (SELECT status FROM calibracoes WHERE id = OLD.calibracao_id) = 'FINALIZADO'
  BEGIN SELECT RAISE(ABORT, 'calibracao finalizada e imutavel'); END;
"""

USUARIOS_DEMO = [
    ("executor1", "Executor Demonstração", "executor"),
    ("emissor1", "Emissor Demonstração", "emissor"),
    ("signatario1", "Signatário Demonstração", "signatario"),
    ("admin", "Administrador Demonstração", "administrador"),
    ("auditor1", "Auditor Demonstração", "auditor"),
]
# Dados ficticios de demonstracao (nao sao dados da Schulz).
PADROES_DEMO = [
    ("500008", "Máquina de medição por coordenadas (demo A)", "Fabricante Demo", "SN-0008",
     "CERT-DEMO-0008", "2025-11-20", "2027-06-30"),
    ("500011", "Máquina de medição por coordenadas (demo B)", "Fabricante Demo", "SN-0011",
     "CERT-DEMO-0011", "2024-11-20", "2026-08-31"),
]


def get_db():
    if "db" not in g:
        con = sqlite3.connect(current_app.config["DATABASE"], isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        g.db = con
    return g.db


def close_db(_e=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


@contextlib.contextmanager
def transacao(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except BaseException:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


def init_db(app):
    con = sqlite3.connect(app.config["DATABASE"], isolation_level=None)
    con.executescript(SCHEMA)
    if con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        senha = app.config["SENHA_DEMO"]
        for login, nome, papel in USUARIOS_DEMO:
            con.execute("INSERT INTO usuarios(login,nome,papel,senha_hash) VALUES(?,?,?,?)",
                        (login, nome, papel, generate_password_hash(senha)))
        for p in PADROES_DEMO:
            con.execute("INSERT INTO padroes(codigo,denominacao,fabricante,numero_serie,"
                        "certificado_rastreabilidade,data_ultima_calibracao,data_proxima_calibracao)"
                        " VALUES(?,?,?,?,?,?,?)", p)
    con.close()
