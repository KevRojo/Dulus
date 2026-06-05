<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — La Cigua Palmera" width="280">

<h1>DULUS</h1>

<h3>Tu Compa de IA. No un Chatbot. Un Amigo que Vuela a Tu Lado.</h3>

<p>
  <strong>Usa IA de frontera sin API key. $0. Sin tarjeta. Sin suscripcion.</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="Descargas"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/licencia-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="Licencia"/>
  <img src="https://img.shields.io/badge/proveedores-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Proveedores"/>
  <img src="https://img.shields.io/badge/herramientas-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Herramientas"/>
  <img src="https://img.shields.io/badge/tests-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Tests"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#inicio-rapido"><b>Inicio Rapido</b></a> ·
  <a href="#caracteristicas"><b>Caracteristicas</b></a> ·
  <a href="#proveedores"><b>Proveedores</b></a> ·
  <a href="#arquitectura"><b>Arquitectura</b></a> ·
  <a href="#token"><b>$DULUS</b></a> ·
  <a href="https://dulus.ai/"><b>Sitio Web</b></a>
</p>

</div>

---

> Nombrado en honor a la **Cigua Palmera** (*Dulus dominicus*), ave nacional de la Republica Dominicana — simbolo de libertad, resiliencia y volar juntos. Dulus no es un chatbot. Es tu companero, tu amigo, tu socio de IA que vuela a tu lado.

---

## Por que Dulus?

| | Ecosistemas Cerrados | Frameworks Complejos | **Dulus** |
|---|---|---|---|
| **Tiempo de setup** | Horas + aprobaciones | Dias de config | **30 segundos** |
| **Costo inicial** | $$$ + API keys | $$$ + infra | **$0** |
| **Proveedor** | Unico | Unico | **100+ proveedores** |
| **Codigo** | Caja negra | 100K+ lineas | **~12K lineas legibles** |
| **Voz** | Solo nube | No incluido | **Whisper offline** |
| **Memoria** | Solo contexto | Manual | **MemPalace semantica** |

**El problema:** Los agentes de IA hoy estan bloqueados a un solo proveedor (solo Claude, solo GPT) o requieren un doctorado en ingenieria ML para configurarlos. Y todos quieren tu tarjeta de credito antes de que puedas probarlos.

**La solucion:** Dulus. Un agente autonomo en Python que se conecta a cualquier modelo — desde sesiones gratuitas en el navegador (Gemini guest, Claude.ai, Kimi, Qwen, DeepSeek) hasta 100+ proveedores pagos via LiteLLM, hasta modelos locales en tu Mac M2. ~12K lineas de Python legible. Sin build step. Sin gatekeeping. Solo garras.

---

## Inicio Rapido

### Instalacion en 30 Segundos

```bash
pip install dulus && dulus
```

Eso es todo. En el primer arranque, Dulus abre un navegador, captura una **sesion guest de Gemini** (sin login, sin API key, sin tarjeta), y ya estas chateando con IA de frontera en menos de 30 segundos.

### Instalador One-liner (recomendado)

**Linux / macOS / WSL:**
```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/KevRojo/Dulus/main/install.ps1 | iex
```

### Docker (sin setup local)

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## Caracteristicas

| Caracteristica | Descripcion |
|---|---|
| Multi-Proveedor | 11 proveedores nativos + 100+ via LiteLLM |
| Sin API Key | Captura sesiones gratuitas del navegador |
| 30+ Herramientas | Archivos, shell, web, OCR, voz, y mas |
| Auto-Adapter | Instala cualquier repo Python como plugin |
| MemPalace | Memoria semantica con ChromaDB |
| Voz I/O | STT offline via Whisper. TTS multi-engine |
| Sub-Agentes | Agentes tipados en git worktrees aislados |
| Mesa Redonda | Debate multi-modelo |
| Sandbox OS | Mini-OS en el navegador con 58 apps |
| Telegram Bridge | Corre Dulus desde tu telefono |
| MCP | Model Context Protocol |
| Brainstorm | Consejo de expertos IA |
| SSJ Mode | 10 atajos de workflow encadenados |
| Checkpoints | Snapshot y rewind de cualquier turno |
| Compresion | Auto-compacta sesiones largas |
| OCR Local | Extrae texto de imagenes sin tokens de vision |
| Multi-Idioma | `/lang` — 34 codigos ISO |
| Composio | 1,000+ integraciones SaaS |
| WebBridge | Automatizacion de navegador via Playwright |

---

## Proveedores

### Gratuitos (Sin API Key)

| Proveedor | Modelos | Setup |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | Abre navegador → escribe "hola" → listo |
| **Claude.ai** | claude-sonnet-4-6 | Tu sesion de claude.ai existente |
| **Kimi.com** | kimi-k2.5 | Tu sesion de kimi.com existente |
| **Qwen** | qwen-max, qwen-plus | Tu sesion de qwen.ai existente |
| **DeepSeek** | deepseek-chat, deepseek-reasoner | Tu sesion de deepseek existente |
| **NVIDIA NIM** | 14 modelos, 40 RPM cada uno | Registro gratis en build.nvidia.com |
| **Ollama** | Cualquier modelo local | `ollama pull qwen2.5-coder` |

### Cloud APIs (Requieren API Key)

| Proveedor | Modelos | Variable de Entorno |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 100+ backends via un gateway | Key del backend especifico |

---

## Arquitectura

```
Input del Usuario
    |
    v
dulus.py  ── REPL, comandos slash, voz, Telegram, GUI
    |
    ├── agent.py  ── Loop multi-turn, gates de permiso, gobernanza
    |       |
    |       ├── providers.py  ── Streaming multi-proveedor
    |       ├── tool_registry.py ── Sistema de plugins
    |       ├── tools.py  ── 30+ herramientas integradas
    |       ├── compaction.py  ── Gestion de ventana de contexto
    |       ├── governance.py  ── Gobernanza de presupuesto/permisos
    |       └── multi_agent/  ── Sub-agentes (la Parvada)
    |
    ├── context.py  ── Constructor de system prompt
    |       └── memory/  ── MemPalace memoria semantica
    |
    ├── skill/  ── Sistema de skills
    ├── checkpoint/  ── Snapshots + rewind
    ├── plugin/  ── Sistema Auto-Adapter
    ├── voice/  ── STT (Whisper) + TTS (multi-engine)
    ├── task/  ── Gestion de tareas
    ├── webbridge/  ── Automatizacion Playwright
    └── dulus_mcp/  ── Cliente MCP
```

---

## La Parvada (Sub-Agentes)

Dulus puede generar agentes tipados que trabajan en **git worktrees aislados**. Envia una feature mientras un reviewer revisa la anterior. Un tester corre en paralelo.

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## Permisos

| Modo | Comportamiento |
|---|---|
| `auto` *(default)* | Lecturas permitidas. Pregunta antes de escrituras/shell. |
| `accept-all` | Sin prompts. Todo auto-aprobado. **YOLO.** |
| `manual` | Pregunta por cada operacion. |
| `plan` | Solo lectura. Solo el plan file es escribible. |

---

## Comandos Slash

`/` + Tab en el REPL muestra todo. Destacados:

| Comando | Descripcion |
|---|---|
| `/model [nombre]` | Mostrar o cambiar modelo |
| `/memory [query]` | Memoria semantica persistente |
| `/voice` | Entrada de voz (Whisper offline) |
| `/brainstorm [tema]` | Consejo de fantasmas |
| `/ssj` | Menu de poder (10 atajos) |
| `/telegram [token] [id]` | Puente Telegram |
| `/checkpoint [id]` | Listar / rebobinar checkpoints |
| `/plan [desc]` | Entrar / salir modo plan |
| `/lang [codigo]` | Cambiar idioma (34 codigos) |
| `/cost` | Tokens y USD gastados |
| `/help` | Todos los comandos |

---

## $DULUS Token

**Contrato:** `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`

El token $DULUS es la capa de combustible del ecosistema Dulus. El REPL open-source sigue gratis para siempre — $DULUS es la llave a la capa de negocios.

| Fase | Utilidad |
|---|---|
| **Ahora** | Propiedad comunitaria. Recompensas bloqueadas on-chain |
| **Business v1** | Acceso temprano + descuentos para holders |
| **Creditos** | Paga creditos API con $DULUS |
| **Deployments** | Lanza instancias cloud pagando con $DULUS |
| **Subscripciones** | Suscripcion mensual payable en $DULUS |
| **Gobernanza** | Top holders votan prioridad de features |

---

## Licencia

GPLv3. Forkealo, modificalo, redistribuilo — pero mantenlo abierto.

> *Nombrado por el pajaro, no por el cohete. Seguimos volando.*

---

<div align="center">

**[Primeros Pasos](GETTING_STARTED.md)** · **[Arquitectura](ARCHITECTURE.md)** · **[API](API.md)** · **[Contribuir](CONTRIBUTING.md)** · **[FAQ](FAQ.md)**

<p><sub>Construido con garras por <a href="https://github.com/KevRojo">KevRojo</a> · Santo Domingo, Republica Dominicana · 2026</sub></p>

</div>
