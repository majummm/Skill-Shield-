

import os
import functools

from flask import Flask, jsonify, request, render_template, session

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db
import ml_core
from llm_gemini import analisar_tarefa, GeminiNotConfigured

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao-" + os.urandom(8).hex())
if not os.environ.get("SECRET_KEY"):
    print("[AVISO] SECRET_KEY nao definida no ambiente — usando uma chave gerada so para esta execucao. "
          "As sessoes de login serao invalidadas toda vez que o servidor reiniciar. "
          "Defina SECRET_KEY no .env para producao.")

print("Treinando o nucleo preditivo do SkillShield (dados sinteticos)...")
ENGINE = ml_core.train_predictive_engine()
print(f"Modelo selecionado: {ENGINE.model_name} "
      f"(F1 macro = {ENGINE.metrics['models'][ENGINE.model_name]['f1_macro']})")

db.init_db()


# ---------------------------------------------------------------------------
# Auxiliares de sessao
# ---------------------------------------------------------------------------

def login_requerido(tipo_esperado=None):
    """Decorator: exige sessao ativa. Se tipo_esperado for 'pessoa' ou
    'empresa', exige tambem que a conta logada seja desse tipo."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if "tipo" not in session:
                return jsonify({"erro": "Voce precisa entrar (login) para acessar isso."}), 401
            if tipo_esperado and session["tipo"] != tipo_esperado:
                return jsonify({"erro": "Essa acao nao esta disponivel para esse tipo de conta."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _sessao_publica() -> dict:
    if "tipo" not in session:
        return {"logado": False}
    if session["tipo"] == "empresa":
        empresa = db.buscar_empresa(session["empresa_id"])
        if not empresa:
            session.clear()
            return {"logado": False}
        return {"logado": True, "tipo": "empresa", "nome": empresa["nome"], "email": empresa["email"]}
    usuario = db.buscar_usuario(session["user_id"])
    if not usuario:
        session.clear()
        return {"logado": False}
    return {"logado": True, "tipo": "pessoa", "nome": usuario["nome"], "email": usuario["email"],
            "empresa_id": usuario["empresa_id"]}


def _perfil_payload(user_id: int) -> dict:
    hist = db.historico_usuario(user_id)
    ssi = ml_core.compute_ssi(hist)
    perfil = ml_core.compute_vulnerability_profile(hist)
    nivel = ml_core.determine_level(ssi, len(hist))
    return {"cenarios_respondidos": len(hist), "ssi": ssi, "nivel": nivel, "perfil_vulnerabilidade": perfil}


def _equipe_payload(empresa_id: int) -> dict:
    hist = db.historico_empresa(empresa_id)
    ssi = ml_core.compute_ssi(hist)
    perfil = ml_core.compute_vulnerability_profile(hist)
    nivel = ml_core.determine_level(ssi, len(hist))
    return {
        "respostas_registradas": len(hist),
        "funcionarios_cadastrados": db.contar_funcionarios(empresa_id),
        "ssi_equipe": ssi, "nivel_equipe": nivel, "perfil_vulnerabilidade_equipe": perfil,
    }


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "modelo_selecionado": ENGINE.model_name,
        "metricas": ENGINE.metrics,
        "gemini_configurado": bool(os.environ.get("GOOGLE_API_KEY")),
    })


@app.route("/api/me")
def me():
    return jsonify(_sessao_publica())


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------

def _validar_cadastro(data):
    nome = (data.get("nome") or "").strip()
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""
    if not nome:
        return None, None, None, "Informe um nome."
    if "@" not in email or "." not in email:
        return None, None, None, "Informe um e-mail valido."
    if len(senha) < 6:
        return None, None, None, "A senha precisa ter pelo menos 6 caracteres."
    if db.email_em_uso(email):
        return None, None, None, "Ja existe uma conta com esse e-mail."
    return nome, email, senha, None


@app.route("/api/cadastro/pessoal", methods=["POST"])
def cadastro_pessoal():
    data = request.get_json(force=True) or {}
    nome, email, senha, erro = _validar_cadastro(data)
    if erro:
        return jsonify({"erro": erro}), 400
    usuario = db.criar_usuario(nome, email, senha, empresa_id=None)
    session.clear()
    session["tipo"] = "pessoa"
    session["user_id"] = usuario["user_id"]
    return jsonify(_sessao_publica())


@app.route("/api/cadastro/empresa", methods=["POST"])
def cadastro_empresa():
    data = request.get_json(force=True) or {}
    nome, email, senha, erro = _validar_cadastro(data)
    if erro:
        return jsonify({"erro": erro}), 400
    empresa = db.criar_empresa(nome, email, senha)
    session.clear()
    session["tipo"] = "empresa"
    session["empresa_id"] = empresa["empresa_id"]
    payload = _sessao_publica()
    payload["codigo_convite"] = empresa["codigo_convite"]
    return jsonify(payload)


@app.route("/api/cadastro/funcionario", methods=["POST"])
def cadastro_funcionario():
    data = request.get_json(force=True) or {}
    codigo = (data.get("codigo_empresa") or "").strip()
    if not codigo:
        return jsonify({"erro": "Informe o codigo da empresa."}), 400
    empresa = db.buscar_empresa_por_codigo(codigo)
    if not empresa:
        return jsonify({"erro": "Codigo de empresa invalido."}), 404
    nome, email, senha, erro = _validar_cadastro(data)
    if erro:
        return jsonify({"erro": erro}), 400
    usuario = db.criar_usuario(nome, email, senha, empresa_id=empresa["empresa_id"])
    session.clear()
    session["tipo"] = "pessoa"
    session["user_id"] = usuario["user_id"]
    return jsonify(_sessao_publica())


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""
    if not email or not senha:
        return jsonify({"erro": "Informe e-mail e senha."}), 400

    usuario = db.buscar_usuario_por_email(email)
    if usuario and db.verificar_senha(usuario["senha_hash"], senha):
        session.clear()
        session["tipo"] = "pessoa"
        session["user_id"] = usuario["user_id"]
        return jsonify(_sessao_publica())

    empresa = db.buscar_empresa_por_email(email)
    if empresa and db.verificar_senha(empresa["senha_hash"], senha):
        session.clear()
        session["tipo"] = "empresa"
        session["empresa_id"] = empresa["empresa_id"]
        return jsonify(_sessao_publica())

    return jsonify({"erro": "E-mail ou senha incorretos."}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"logado": False})


# ---------------------------------------------------------------------------
# Gerador de prompt seguro (contas pessoais/funcionario)
# ---------------------------------------------------------------------------

@app.route("/api/gerar-prompt", methods=["POST"])
@login_requerido(tipo_esperado="pessoa")
def gerar_prompt():
    user_id = session["user_id"]
    data = request.get_json(force=True) or {}
    tarefa_descrita = (data.get("tarefa_descrita") or "").strip()

    if not tarefa_descrita:
       # return jsonify({"erro": "Descreva a tarefa que voce quer fazer com uma IA."}), 400
       return jsonify({"erro": "testesss"}), 400
    if len(tarefa_descrita) < 10:
        return jsonify({"erro": "Descreva a tarefa com um pouco mais de detalhe."}), 400

    try:
        resultado = analisar_tarefa(tarefa_descrita)
    except GeminiNotConfigured as e:
        return jsonify({"erro": str(e)}), 503
    except Exception as e:
        return jsonify({"erro": f"Nao foi possivel analisar a tarefa com a IA do Google agora ({e}). "
                                 f"Tente novamente em instantes."}), 502

    categoria = resultado["categoria"]
    feat = resultado["caracteristicas"]
    prompt_seguro = resultado["prompt_seguro"]

    decision_score = ml_core.compute_decision_score(feat, categoria)
    risco_previsto = ml_core.predict_risk(ENGINE, feat, categoria)

    db.salvar_resposta(
        user_id=user_id, category=categoria, feat=feat,
        decision_score=decision_score, risk_level_previsto=risco_previsto,
        tarefa_texto=tarefa_descrita, prompt_gerado=prompt_seguro,
    )

    hist_atualizado = db.historico_usuario(user_id)
    categoria_dica, texto_dica = ml_core.escolher_dica_personalizada(hist_atualizado)

    return jsonify({
        "prompt_seguro": prompt_seguro,
        "categoria_identificada": categoria,
        "caracteristicas_identificadas": feat,
        "risco_da_tarefa_original": risco_previsto,
        "dica_personalizada": {"categoria": categoria_dica, "texto": texto_dica},
        "perfil": _perfil_payload(user_id),
    })


@app.route("/api/perfil")
@login_requerido(tipo_esperado="pessoa")
def perfil():
    return jsonify(_perfil_payload(session["user_id"]))


# ---------------------------------------------------------------------------
# Painel da empresa (agregado da equipe)
# ---------------------------------------------------------------------------

@app.route("/api/equipe")
@login_requerido(tipo_esperado="empresa")
def equipe():
    empresa = db.buscar_empresa(session["empresa_id"])
    payload = _equipe_payload(session["empresa_id"])
    payload["codigo_convite"] = empresa["codigo_convite"]
    payload["nome_empresa"] = empresa["nome"]
    return jsonify(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
