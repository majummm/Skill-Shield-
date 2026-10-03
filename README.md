# SkillShield — Site

Site completo do SkillShield: landing page, login/cadastro (pessoal, funcionário
de empresa ou empresa) e um gerador de **prompt seguro**. A pessoa descreve uma
tarefa real que quer fazer com uma IA, o Google Gemini identifica os riscos
dessa tarefa e já devolve um prompt pronto pra colar na ferramenta de IA —
enquanto, por trás, um modelo de Machine Learning treinado no próprio servidor
classifica o risco da tarefa original e atualiza o perfil de vulnerabilidade
e o SSI da pessoa.

```
Navegador (front-end)  --descreve a tarefa-->  Servidor Flask
                                                    |
                                                    |-- Gemini identifica categoria + 9 caracteristicas
                                                    |-- Gemini gera o prompt seguro
                                                    |-- modelo de ML ja treinado preve o risco da tarefa
                                                    |-- SQLite guarda contas, historico, perfil e SSI
Navegador (front-end)  <--prompt seguro, risco, dica, perfil--
```

A chave de API do Google **fica só no servidor** (variável de ambiente) —
o navegador nunca tem acesso a ela.

## 1. Contas: pessoal, funcionário e empresa

* **Pessoal** — qualquer pessoa cria uma conta e vê só o próprio perfil de
  vulnerabilidade e SSI.
* **Empresa** — cria uma conta e recebe um **código de convite** único.
  Ao entrar, vê o painel da equipe: SSI médio, nível médio e perfil de
  vulnerabilidade médio de todos os funcionários vinculados — não vê
  ninguém individualmente.
* **Funcionário** — se cadastra sozinho informando o código da empresa. A
  experiência dele é igual à de uma conta pessoal (só vê o próprio
  progresso); o que muda é que as tarefas dele entram na média da
  empresa à qual está vinculado.

Login é feito por e-mail + senha (senhas guardadas com hash, nunca em texto
puro) usando sessão de cookie assinada pelo Flask (`SECRET_KEY`).

## 2. Pré-requisitos

* Python 3.10 ou mais recente
* Uma chave de API gratuita do Google Gemini: https://aistudio.google.com/apikey

## 3. Instalação (rodando localmente)

```bash
cd skillshield_site
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite o arquivo .env e cole sua GOOGLE_API_KEY e defina uma SECRET_KEY

python app.py
```

Abra **http://localhost:5000** no navegador.

## 4. Como funciona por dentro

* `ml_core.py` — banco de 50 cenários, geração do dataset sintético de
  treinamento, treinamento/comparação dos modelos, Perfil de
  Vulnerabilidade, SSI, níveis e motor de treinamento adaptativo.
* `llm_gemini.py` — chama o Gemini uma vez por tarefa para: identificar a
  categoria de risco, extrair o vetor de 9 características, e gerar o
  prompt seguro (tudo com `response_schema` forçando JSON estruturado).
* `db.py` — persistência em SQLite: tabelas `empresas`, `usuarios`
  (pessoais ou vinculados a uma empresa via `empresa_id`) e `respostas`.
  Senhas com `werkzeug.security.generate_password_hash`.
* `app.py` — servidor Flask: autenticação por sessão (`/api/cadastro/*`,
  `/api/login`, `/api/logout`, `/api/me`), gerador de prompt seguro
  (`/api/gerar-prompt`, `/api/perfil`) e painel agregado da empresa
  (`/api/equipe`).
* `templates/index.html`, `static/style.css`, `static/app.js` — front-end
  (HTML/CSS/JS puro), com a landing page, os formulários de login/cadastro
  e os dois painéis (pessoal e empresa).
* `static/img/` — logo do SkillShield (ícone e versão com o nome), usada
  no topo do site e como favicon.

## 5. Importante — transparência científica

O modelo preditivo é treinado, a cada início do servidor, com um **dataset
sintético** gerado por regras — não há respostas de usuários reais nesses
dados de treino. Veja `ml_core.generate_dataset()` para a metodologia
completa. As métricas do modelo ficam em `GET /api/status`.

Quando houver volume suficiente de tarefas reais (tabela `respostas` do
`skillshield.db`, que agora guarda `tarefa_texto` e `prompt_gerado`), o
ideal é: (1) definir como obter um "risco verdadeiro" confiável pra essas
tarefas — ex. avaliação humana de uma amostra — (2) substituir
`generate_dataset()` por esses dados reais rotulados, e (3) retreinar e
comparar os modelos de novo antes de confiar neles em produção. O banco de
50 cenários fictícios em `ml_core.py` continua existindo só para gerar
esse dataset sintético inicial de treino — ele não é mais mostrado ao
usuário final.

## 6. Colocando o site no ar (deploy)

Qualquer serviço que rode aplicações Python/Flask funciona (Render,
Railway, Replit, PythonAnywhere, Google Cloud Run...). Em qualquer um
deles:

1. Suba os arquivos deste projeto (sem o `.env`!).
2. Configure as variáveis de ambiente `GOOGLE_API_KEY` e `SECRET_KEY` no
   painel do serviço.
3. Garanta que o disco onde fica `skillshield.db` seja persistente — em
   alguns serviços gratuitos ele reseta a cada novo deploy. Para uso com
   um número real de participantes, considere trocar o SQLite por um
   banco gerenciado (Postgres, por exemplo).

## 7. Rodando em modo debug (opcional, só em desenvolvimento)

```bash
FLASK_DEBUG=1 python app.py
```

Nunca use `FLASK_DEBUG=1` em produção.
