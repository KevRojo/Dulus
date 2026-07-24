<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — O Guacpanche" width="280">

<h1>DULUS</h1>

<h3>Seu Companheiro de IA. Nao um Chatbot. Um Amigo que Voa ao Seu Lado.</h3>

<p>
  <strong>Use IA de ponta sem uma chave API. $0. Sem cartao. Sem assinatura.</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="Downloads"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/licenca-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="Licenca"/>
  <img src="https://img.shields.io/badge/provedores-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Provedores"/>
  <img src="https://img.shields.io/badge/ferramentas-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Ferramentas"/>
  <img src="https://img.shields.io/badge/tests-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Tests"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#inicio-rapido"><b>Inicio Rapido</b></a> ·
  <a href="#recursos"><b>Recursos</b></a> ·
  <a href="#provedores"><b>Provedores</b></a> ·
  <a href="#arquitetura"><b>Arquitetura</b></a> ·
</p>

</div>

---

> Nomeado em homenagem ao **Guacpanche** (*Dulus dominicus*), ave nacional da Republica Dominicana — simbolo de liberdade, resiliencia e voar juntos. Dulus nao e um chatbot. E seu companheiro, seu amigo, seu parceiro de IA que voa ao seu lado.

---

## Por que Dulus?

| | Ecossistemas Fechados | Frameworks Complexos | **Dulus** |
|---|---|---|---|
| **Tempo de setup** | Horas + aprovacoes | Dias de config | **30 segundos** |
| **Custo inicial** | $$$ + chaves API | $$$ + infra | **$0** |
| **Lock-in** | Provedor unico | Provedor unico | **100+ provedores** |
| **Codebase** | Caixa preta | 100K+ linhas | **~56K linhas Python proprias** |
| **Voz** | Apenas nuvem | Nao incluido | **Whisper offline** |
| **Memoria** | Apenas contexto | Manual | **MemPalace semantica** |

**O problema:** Agentes de IA hoje estao bloqueados em um unico provedor ou exigem um doutorado em engenharia ML para configurar. E todos querem seu cartao de credito antes que voce possa experimenta-los.

**A solucao:** Dulus. Um agente autonomo Python que se conecta a qualquer modelo — de sessoes de navegador gratuitas a 100+ provedores pagos via LiteLLM e modelos locais no seu proprio hardware. ~56K linhas Python proprias. Sem build step. Sem gatekeeping.

---

## Inicio Rapido

### Instalacao em 30 Segundos

```bash
pip install dulus && dulus
```

E isso. Na primeira execucao, o Dulus abre um navegador, captura uma **sessao guest do Gemini** (sem login, sem chave API, sem cartao), e voce ja esta conversando com IA de ponta em menos de 30 segundos.

### Instalador One-liner (recomendado)

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### Docker (zero setup local)

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## Recursos

| Recurso | Descricao |
|---|---|
| Multi-Provedor | 11 nativos + 100+ via LiteLLM |
| Zero Chave API | Captura sessoes de navegador gratuitas |
| 30+ Ferramentas | Arquivos, shell, web, OCR, voz, e mais |
| Auto-Adapter | Instala qualquer repo Python como plugin |
| MemPalace | Memoria semantica com ChromaDB |
| Voz I/O | STT offline via Whisper. TTS multi-motor |
| Sub-Agentes | Agentes tipados em git worktrees isolados —— o Bando |
| Mesa Redonda | Debate multi-modelo |
| Sandbox OS | Mini-OS baseado em navegador com 58 apps |
| Ponte Telegram | Execute Dulus do seu celular |
| MCP | Model Context Protocol |
| Brainstorm | Conselho de especialistas IA |
| Modo SSJ | 10 atalhos de workflow encadeados |
| Checkpoints | Snapshot e rewind de qualquer turno |
| Compressao | Auto-compacta sessoes longas |
| OCR Local | Extrai texto de imagens sem tokens de visao |
| Multi-Idioma | `/lang` —— 34 codigos ISO |
| Composio | 1,000+ integracoes SaaS |
| WebBridge | Automacao de navegador via Playwright |

---

## Provedores

### Gratuitos (Sem Chave API)

| Provedor | Modelos | Configuracao |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | Abrir navegador → digitar "ola" → pronto |
| **Claude.ai** | claude-sonnet-4-6 | Sua sessao claude.ai existente |
| **Kimi.com** | kimi-k2.5 | Sua sessao kimi.com existente |
| **Qwen** | qwen-max, qwen-plus | Sua sessao qwen.ai existente |
| **DeepSeek** | deepseek-chat | Sua sessao deepseek existente |
| **NVIDIA NIM** | 14 modelos, 40 RPM cada | Registro gratis em build.nvidia.com |
| **Ollama** | Qualquer modelo local | `ollama pull qwen2.5-coder` |

### Cloud APIs (Chave API Necessaria)

| Provedor | Modelos | Variavel de Ambiente |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 100+ backends via um gateway | Chave do backend especifico |

---

## Arquitetura

```
Entrada do Usuario
    |
    v
dulus.py —— REPL, comandos slash, voz, Telegram, GUI
    |
    ├── agent.py —— Loop multi-turn, gates de permissao, governanca
    |       |
    |       ├── providers.py —— Streaming multi-provedor
    |       ├── tool_registry.py —— Sistema de plugins
    |       ├── tools.py —— 30+ ferramentas integradas
    |       ├── compaction.py —— Gerenciamento de janela de contexto
    |       ├── governance.py —— Governanca de orcamento/permissao
    |       └── multi_agent/ —— Sub-agentes (o Bando)
    |
    ├── context.py —— Construtor de system prompt
    |       └── memory/ —— MemPalace memoria semantica
    |
    ├── skill/ —— Sistema de skills
    ├── checkpoint/ —— Snapshots + rewind
    ├── plugin/ —— Sistema Auto-Adapter
    ├── voice/ —— STT (Whisper) + TTS (multi-motor)
    ├── task/ —— Gerenciamento de tarefas
    ├── webbridge/ —— Automacao Playwright
    └── dulus_mcp/ —— Cliente MCP
```

---

## O Bando (Sub-Agentes)

Dulus pode gerar agentes tipados que trabalham em **git worktrees isolados**.

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## Permissoes

| Modo | Comportamento |
|---|---|
| `auto` *(padrao)* | Leituras sempre permitidas. Pergunta antes de escritas/shell. |
| `accept-all` | Sem prompts. Tudo auto-aprovado. **YOLO.** |
| `manual` | Pergunta para cada operacao. |
| `plan` | Somente leitura. Apenas o plan file e gravavel. |

---

## Comandos Slash

| Comando | Descricao |
|---|---|
| `/model [nome]` | Mostrar ou trocar modelo |
| `/memory [consulta]` | Memoria semantica persistente |
| `/voice` | Entrada de voz (Whisper offline) |
| `/brainstorm [topico]` | Conselho de fantasmas |
| `/ssj` | Menu de poder (10 atalhos) |
| `/telegram [token] [id]` | Ponte Telegram |
| `/checkpoint [id]` | Listar / rebobinar checkpoints |
| `/plan [desc]` | Entrar / sair modo plan |
| `/lang [codigo]` | Trocar idioma (34 codigos) |
| `/cost` | Tokens e USD gastos |
| `/help` | Todos os comandos |

---

## Licenca

GPLv3. Faça fork, modifique, redistribua —— mas mantenha aberto.

> *Nomeado em homenagem ao passaro, nao ao foguete. Continuamos voando.*

---

<div align="center">

<p><sub>Construido com garras por <a href="https://github.com/KevRojo">KevRojo</a> · Santo Domingo, Republica Dominicana · 2026</sub></p>

</div>
