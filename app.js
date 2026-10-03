const FEATURE_LABELS = {
  identified_risk: "Percebeu o risco da situação",
  protected_data: "Evitou expor dados pessoais",
  avoided_sharing: "Evitou compartilhar sem cuidado",
  used_anonymization: "Considerou anonimizar/mascarar",
  checked_policy: "Verificaria a política da empresa",
  verified_information: "Verificaria a fonte/confiabilidade",
  recognized_social_engineering: "Reconheceu sinais de golpe",
  questioned_ai: "Questionaria a resposta da IA",
  considered_intellectual_property: "Considerou direitos autorais",
};
const RISK_LABEL = { Baixo: "BAIXO RISCO", Medio: "MÉDIO RISCO", Alto: "ALTO RISCO" };
const RISK_CLASS = { Baixo: "risco-baixo", Medio: "risco-medio", Alto: "risco-alto" };

const state = { sessao: null };
const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.erro || `Erro ${res.status}`);
  return data;
}

function mostrarSoTela(id) {
  ["tela-landing", "tela-dashboard", "tela-empresa"].forEach((t) => {
    el(t).classList.toggle("hidden", t !== id);
  });
}

/* --------------------------- Barras / anel reutilizaveis --------------------------- */
function corVulnerabilidade(valor) {
  if (valor === null || valor === undefined) return "#223258";
  if (valor < 34) return "#2FD9A5";
  if (valor < 67) return "#FFB020";
  return "#FF5470";
}

function renderBarrasVulnerabilidade(containerId, perfil) {
  const cont = el(containerId);
  cont.innerHTML = "";
  Object.entries(perfil).forEach(([categoria, valor]) => {
    const linha = document.createElement("div");
    linha.className = "vuln-linha";
    const label = document.createElement("div");
    label.className = "vuln-linha-label";
    label.innerHTML = `<span>${categoria}</span><span class="vuln-linha-valor">${valor === null ? "—" : Math.round(valor)}</span>`;
    const fundo = document.createElement("div");
    fundo.className = "vuln-barra-fundo";
    const preenchimento = document.createElement("div");
    preenchimento.className = "vuln-barra-preenchimento";
    preenchimento.style.width = (valor === null ? 0 : valor) + "%";
    preenchimento.style.background = corVulnerabilidade(valor);
    fundo.appendChild(preenchimento);
    linha.appendChild(label);
    linha.appendChild(fundo);
    cont.appendChild(linha);
  });
}

function renderAnelSSI(anelId, valorId, ssi) {
  el(valorId).textContent = ssi === null ? "—" : Math.round(ssi);
  const pct = ssi === null ? 0 : Math.max(0, Math.min(100, ssi));
  el(anelId).style.background = `conic-gradient(var(--blue-bright) ${pct * 3.6}deg, var(--border) ${pct * 3.6}deg)`;
}

/* --------------------------- Sessao / navegacao --------------------------- */
async function atualizarTopbar() {
  const conta = el("topbar-conta");
  if (state.sessao && state.sessao.logado) {
    conta.classList.remove("hidden");
    el("topbar-nome").textContent = state.sessao.nome;
  } else {
    conta.classList.add("hidden");
  }
}

async function carregarSessaoEIrParaTela() {
  state.sessao = await api("/api/me");
  await atualizarTopbar();
  if (!state.sessao.logado) {
    mostrarSoTela("tela-landing");
  } else if (state.sessao.tipo === "empresa") {
    mostrarSoTela("tela-empresa");
    await carregarPainelEmpresa();
  } else {
    mostrarSoTela("tela-dashboard");
    await entrarNoDashboardPessoal();
  }
}

/* --------------------------- Dashboard pessoal --------------------------- */
async function entrarNoDashboardPessoal() {
  el("dossie-nome").textContent = state.sessao.nome;
  const perfil = await api("/api/perfil");
  renderPerfilPessoal(perfil);

  el("bloco-boasvindas").classList.remove("hidden");
  el("tarefa-card").classList.add("hidden");
  el("resultado").classList.add("hidden");

  if (perfil.cenarios_respondidos > 0) {
    el("boasvindas-titulo").textContent = "Tem outra tarefa pra fazer com IA?";
    el("boasvindas-texto").textContent =
      "Descreva a tarefa e a gente te devolve um prompt seguro pra usar — e vai ajustando as dicas conforme sua maior dificuldade.";
    el("btn-iniciar-teste").textContent = "Descrever tarefa →";
  } else {
    el("boasvindas-titulo").textContent = "Vamos começar?";
    el("boasvindas-texto").textContent =
      "Descreva uma tarefa real que você precisa fazer com ajuda de uma IA. A gente identifica os riscos e já devolve um prompt pronto e seguro.";
    el("btn-iniciar-teste").textContent = "Descrever minha primeira tarefa →";
  }
}

function renderPerfilPessoal(perfil) {
  renderAnelSSI("ssi-anel", "ssi-valor", perfil.ssi);
  el("dossie-nivel-texto").textContent = perfil.nivel.replace(" - ", " — ");
  el("dossie-contagem").textContent =
    `${perfil.cenarios_respondidos} tarefa${perfil.cenarios_respondidos === 1 ? "" : "s"} analisada${perfil.cenarios_respondidos === 1 ? "" : "s"}`;
  renderBarrasVulnerabilidade("vuln-barras", perfil.perfil_vulnerabilidade);
}

function abrirFormularioTarefa() {
  el("bloco-boasvindas").classList.add("hidden");
  el("resultado").classList.add("hidden");
  el("tarefa-card").classList.remove("hidden");
  el("tarefa-descrita").value = "";
  el("envio-erro").classList.add("hidden");
  el("btn-gerar").disabled = false;
}

function renderResultado(resultado) {
  el("tarefa-card").classList.add("hidden");
  el("resultado").classList.remove("hidden");

  const stamp = el("stamp");
  stamp.textContent = RISK_LABEL[resultado.risco_da_tarefa_original] || resultado.risco_da_tarefa_original;
  stamp.className = "stamp " + (RISK_CLASS[resultado.risco_da_tarefa_original] || "");

  el("resultado-categoria").textContent = resultado.categoria_identificada;
  el("prompt-seguro").textContent = resultado.prompt_seguro;

  const featuresUl = el("veredito-features");
  featuresUl.innerHTML = "";
  Object.entries(resultado.caracteristicas_identificadas).forEach(([chave, valor]) => {
    const li = document.createElement("li");
    li.className = valor ? "demonstrado" : "nao-demonstrado";
    li.textContent = (FEATURE_LABELS[chave] || chave) + (valor ? " — identificado" : " — não identificado");
    featuresUl.appendChild(li);
  });

  el("dica-personalizada").textContent = resultado.dica_personalizada.texto;

  renderPerfilPessoal(resultado.perfil);
}

/* --------------------------- Painel da empresa --------------------------- */
async function carregarPainelEmpresa() {
  const dados = await api("/api/equipe");
  el("empresa-nome").textContent = dados.nome_empresa;
  el("convite-codigo").textContent = dados.codigo_convite;
  el("empresa-contagem").textContent =
    `${dados.funcionarios_cadastrados} funcionário${dados.funcionarios_cadastrados === 1 ? "" : "s"} cadastrado${dados.funcionarios_cadastrados === 1 ? "" : "s"}`;
  renderAnelSSI("empresa-ssi-anel", "empresa-ssi-valor", dados.ssi_equipe);
  el("empresa-nivel-texto").textContent = dados.nivel_equipe.replace(" - ", " — ");
  el("empresa-respostas").textContent = `${dados.respostas_registradas} decisões registradas no total`;
  renderBarrasVulnerabilidade("empresa-vuln-barras", dados.perfil_vulnerabilidade_equipe);
}

/* --------------------------- Auth: tabs --------------------------- */
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const aba = btn.dataset.tab;
    el("form-entrar").classList.toggle("hidden", aba !== "entrar");
    el("bloco-cadastrar").classList.toggle("hidden", aba !== "cadastrar");
  });
});

document.querySelectorAll(".subtab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const sub = btn.dataset.subtab;
    el("form-cadastro-pessoal").classList.toggle("hidden", sub !== "pessoal");
    el("form-cadastro-funcionario").classList.toggle("hidden", sub !== "funcionario");
    el("form-cadastro-empresa").classList.toggle("hidden", sub !== "empresa");
  });
});

/* --------------------------- Auth: submits --------------------------- */
function limparErro(id) { el(id).classList.add("hidden"); el(id).textContent = ""; }
function mostrarErro(id, msg) { el(id).textContent = msg; el(id).classList.remove("hidden"); }

el("form-entrar").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  limparErro("entrar-erro");
  try {
    state.sessao = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ email: el("entrar-email").value.trim(), senha: el("entrar-senha").value }),
    });
    await pasSessaoParaTela();
  } catch (e) {
    mostrarErro("entrar-erro", e.message);
  }
});

el("form-cadastro-pessoal").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  limparErro("cadastro-erro");
  try {
    state.sessao = await api("/api/cadastro/pessoal", {
      method: "POST",
      body: JSON.stringify({
        nome: el("pessoal-nome").value.trim(),
        email: el("pessoal-email").value.trim(),
        senha: el("pessoal-senha").value,
      }),
    });
    await pasSessaoParaTela();
  } catch (e) {
    mostrarErro("cadastro-erro", e.message);
  }
});

el("form-cadastro-funcionario").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  limparErro("cadastro-erro");
  try {
    state.sessao = await api("/api/cadastro/funcionario", {
      method: "POST",
      body: JSON.stringify({
        codigo_empresa: el("funcionario-codigo").value.trim(),
        nome: el("funcionario-nome").value.trim(),
        email: el("funcionario-email").value.trim(),
        senha: el("funcionario-senha").value,
      }),
    });
    await pasSessaoParaTela();
  } catch (e) {
    mostrarErro("cadastro-erro", e.message);
  }
});

el("form-cadastro-empresa").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  limparErro("cadastro-erro");
  try {
    state.sessao = await api("/api/cadastro/empresa", {
      method: "POST",
      body: JSON.stringify({
        nome: el("empresa-nome-input").value.trim(),
        email: el("empresa-email").value.trim(),
        senha: el("empresa-senha").value,
      }),
    });
    await pasSessaoParaTela();
  } catch (e) {
    mostrarErro("cadastro-erro", e.message);
  }
});

async function pasSessaoParaTela() {
  await atualizarTopbar();
  if (state.sessao.tipo === "empresa") {
    mostrarSoTela("tela-empresa");
    await carregarPainelEmpresa();
  } else {
    mostrarSoTela("tela-dashboard");
    await entrarNoDashboardPessoal();
  }
}

el("btn-sair").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  state.sessao = null;
  mostrarSoTela("tela-landing");
  await atualizarTopbar();
});

el("btn-iniciar-teste").addEventListener("click", () => {
  abrirFormularioTarefa();
});

el("btn-gerar").addEventListener("click", async () => {
  const tarefa_descrita = el("tarefa-descrita").value.trim();
  limparErro("envio-erro");
  if (!tarefa_descrita) {
    mostrarErro("envio-erro", "Descreva a tarefa antes de enviar.");
    return;
  }
  el("btn-gerar").disabled = true;
  el("envio-carregando").classList.remove("hidden");
  try {
    const resultado = await api("/api/gerar-prompt", {
      method: "POST",
      body: JSON.stringify({ tarefa_descrita }),
    });
    renderResultado(resultado);
  } catch (e) {
    mostrarErro("envio-erro", e.message);
  } finally {
    el("btn-gerar").disabled = false;
    el("envio-carregando").classList.add("hidden");
  }
});

el("btn-proximo").addEventListener("click", () => {
  abrirFormularioTarefa();
});

el("btn-copiar").addEventListener("click", async () => {
  const texto = el("prompt-seguro").textContent;
  try {
    await navigator.clipboard.writeText(texto);
    const original = el("btn-copiar").textContent;
    el("btn-copiar").textContent = "Copiado!";
    setTimeout(() => { el("btn-copiar").textContent = original; }, 1500);
  } catch (e) {
    mostrarErro("envio-erro", "Não foi possível copiar automaticamente — selecione o texto manualmente.");
  }
});

carregarSessaoEIrParaTela();
