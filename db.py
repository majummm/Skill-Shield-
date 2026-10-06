

import sqlite3
import os
import secrets
import string
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from ml_core import FEATURES

DB_PATH = os.environ.get("SKILLSHIELD_DB_PATH", os.path.join(os.path.dirname(__file__), "skillshield.db"))

_FEATURE_COLS_SQL = ", ".join(f"{f} INTEGER NOT NULL" for f in FEATURES)
_CODIGO_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem O/0 e I/1, pra evitar confusao


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            empresa_id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            codigo_convite TEXT NOT NULL UNIQUE,
            criado_em TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            empresa_id INTEGER,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(empresa_id) REFERENCES empresas(empresa_id)
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS respostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            {_FEATURE_COLS_SQL},
            decision_score REAL NOT NULL,
            risk_level_previsto TEXT NOT NULL,
            tarefa_texto TEXT NOT NULL,
            prompt_gerado TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES usuarios(user_id)
        )
    """)
    conn.commit()
    conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _gerar_codigo_convite(conn, tamanho=6):
    while True:
        codigo = "".join(secrets.choice(_CODIGO_ALFABETO) for _ in range(tamanho))
        existe = conn.execute("SELECT 1 FROM empresas WHERE codigo_convite = ?", (codigo,)).fetchone()
        if not existe:
            return codigo


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------

def email_em_uso(email: str) -> bool:
    conn = get_conn()
    u = conn.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,)).fetchone()
    e = conn.execute("SELECT 1 FROM empresas WHERE email = ?", (email,)).fetchone()
    conn.close()
    return bool(u or e)


def criar_empresa(nome: str, email: str, senha: str) -> dict:
    conn = get_conn()
    codigo = _gerar_codigo_convite(conn)
    cur = conn.execute(
        "INSERT INTO empresas (nome, email, senha_hash, codigo_convite, criado_em) VALUES (?, ?, ?, ?, ?)",
        (nome, email, generate_password_hash(senha), codigo, _now()),
    )
    conn.commit()
    empresa_id = cur.lastrowid
    conn.close()
    return {"empresa_id": empresa_id, "nome": nome, "email": email, "codigo_convite": codigo}


def buscar_empresa_por_email(email: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM empresas WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def buscar_empresa_por_codigo(codigo: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM empresas WHERE codigo_convite = ?", (codigo.strip().upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def buscar_empresa(empresa_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM empresas WHERE empresa_id = ?", (empresa_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Usuarios (pessoais ou funcionarios de uma empresa)
# ---------------------------------------------------------------------------

def criar_usuario(nome: str, email: str, senha: str, empresa_id=None) -> dict:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO usuarios (nome, email, senha_hash, empresa_id, criado_em) VALUES (?, ?, ?, ?, ?)",
        (nome, email, generate_password_hash(senha), empresa_id, _now()),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return {"user_id": user_id, "nome": nome, "email": email, "empresa_id": empresa_id}


def buscar_usuario_por_email(email: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def buscar_usuario(user_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM usuarios WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def contar_funcionarios(empresa_id: int) -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) AS n FROM usuarios WHERE empresa_id = ?", (empresa_id,)).fetchone()
    conn.close()
    return row["n"] if row else 0


def verificar_senha(senha_hash: str, senha: str) -> bool:
    return check_password_hash(senha_hash, senha)


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------

def salvar_resposta(user_id, category, feat: dict, decision_score, risk_level_previsto,
                     tarefa_texto, prompt_gerado):
    conn = get_conn()
    cols = ["user_id", "category"] + FEATURES + [
        "decision_score", "risk_level_previsto", "tarefa_texto", "prompt_gerado", "criado_em"]
    placeholders = ", ".join("?" for _ in cols)
    values = [user_id, category] + [feat[f] for f in FEATURES] + [
        decision_score, risk_level_previsto, tarefa_texto, prompt_gerado, _now()]
    conn.execute(f"INSERT INTO respostas ({', '.join(cols)}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()


def historico_usuario(user_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM respostas WHERE user_id = ? ORDER BY id ASC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def historico_empresa(empresa_id: int) -> list:
    """Todas as respostas de todos os funcionarios vinculados a essa empresa,
    usado para calcular o perfil/SSI AGREGADO da equipe."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.* FROM respostas r
        JOIN usuarios u ON u.user_id = r.user_id
        WHERE u.empresa_id = ?
        ORDER BY r.id ASC
    """, (empresa_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
