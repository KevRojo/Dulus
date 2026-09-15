# Dulus FAQ

> Frequently asked questions — in English and Espanol.

---

## General Questions

### What is Dulus?

Dulus is your AI companion — an autonomous Python agent that connects to any language model. It is not a chatbot; it is a friend that flies beside you. Named after the Palmchat (*Dulus dominicus*), the national bird of the Dominican Republic.

### Is Dulus free?

**The engine is.** The open-source REPL is free forever and runs at $0 against a local Ollama model or NVIDIA NIM's free tier. Inference through the hosted Dulus router is metered in Fuel, and `/login claude`, `/login chatgpt`, `/login kimi`, and `/login grok` bill against a subscription you already pay for. Optional extras (voice, MemPalace) are free and open-source.

### What is the $DULUS token?

$DULUS is a utility token on Solana that powers the Dulus business layer (cloud hosting, API credits, subscriptions). The open-source engine stays free regardless of token performance. See the [Token Utility](#token-utility) section below.

### Who built Dulus?

[KevRojo](https://github.com/KevRojo) — a solo developer from Santo Domingo, Dominican Republic. One person, one vision, ~31K lines of Python.

---

## Technical Questions

### Which models does Dulus support?

- **11 native providers:** Anthropic, OpenAI, Gemini, DeepSeek, Qwen, Kimi, Zhipu, MiniMax, Ollama, LM Studio, Custom
- **100+ via LiteLLM:** OpenRouter, Groq, Together, Bedrock, Vertex, Mistral, xAI, Fireworks, Azure, and more
- **No API key:** Dulus router (`/login dulus`), Claude / ChatGPT / Kimi / Grok subscriptions via OAuth, NVIDIA NIM free tier (14 models, 40 RPM), local Ollama

### Does Dulus work offline?

Partially. With Ollama + a local model like `qwen2.5-coder`, the core agent works fully offline. Voice STT (Whisper) also works offline. TTS and cloud providers require internet.

### How do I connect to a remote GPU box?

```
/config custom_base_url=http://your-server:8000/v1
/model custom/your-model-name
```

### Can I pipe input to Dulus?

```bash
echo "explain this" | dulus -p --accept-all
git diff | dulus -p "write a commit message"
cat error.log | dulus -p "what caused this"
```

### Tool calls fail on my local model

Use a model that supports function calling: `qwen2.5-coder`, `llama3.3`, `mistral`, `phi4`. Avoid base models without tool-use training.

### How do I check API cost?

```
/cost
```

### How does subscription sign-in work?

`/login claude`, `/login chatgpt`, `/login kimi`, and `/login grok` each run the provider's official OAuth flow in your browser. Dulus stores the returned token locally and calls the provider's own API with it, so requests bill against the plan you already pay for. No API key is pasted by hand and no session cookie is scraped.

### Is my data safe?

- API keys are encrypted (XOR + base64) before saving to disk
- All processing happens locally (except API calls to providers)
- MemPalace data stays on your machine
- No telemetry, no analytics, no tracking
- Open source — you can audit every line

---

## Comparisons

### Dulus vs Claude Code

| | Claude Code | Dulus |
|---|---|---|
| **Model lock-in** | Claude only | 100+ providers |
| **API key required** | Yes | Optional (OAuth or local models) |
| **Lines of code** | ~100K+ (estimated) | ~31K |
| **License** | Proprietary | GPLv3 |
| **Voice** | No | Yes (offline Whisper) |
| **Memory** | Basic | MemPalace semantic |
| **Sub-agents** | No | Yes (the Flock) |
| **Plugins** | No | Manifest plugins |
| **Cost** | $20+/month | $0 to start |

### Dulus vs AutoGPT

| | AutoGPT | Dulus |
|---|---|---|
| **Complexity** | High (Docker, configs) | Low (pip install) |
| **Setup time** | Hours | 30 seconds |
| **Multi-provider** | Limited | 100+ |
| **Memory** | File-based | Semantic (ChromaDB) |
| **Voice** | No | Yes |

### Dulus vs Continue.dev

| | Continue.dev | Dulus |
|---|---|---|
| **Type** | IDE extension | Standalone agent |
| **Interface** | Editor sidebar | REPL / Web / GUI / Telegram |
| **Sub-agents** | No | Yes |
| **Plugins** | Limited | Manifest plugins (any Python repo) |

---

## Token Utility

### What is $DULUS for?

The token is the fuel layer for the Dulus business layer. The open-source REPL stays free forever.

| Phase | Utility |
|---|---|
| **Now** | Community ownership. Creator-fee rewards locked on-chain |
| **Business v1** | Early access + discounted seats for holders |
| **Credits** | Pay for Dulus Business API credits |
| **Deployments** | Spin up cloud instances with $DULUS |
| **Subscriptions** | Monthly Pro subscription payable in $DULUS |
| **Governance** | Top holders vote on feature priority |

### Is the token required to use Dulus?

**No.** The open-source REPL, all tools, the free model tier — everything stays free forever. $DULUS is only for the optional business layer.

### Contract address?

`9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump` on Solana.

---

## Troubleshooting

### "No matching distribution found for dulus"

Your system Python is older than 3.11. pip hides incompatible packages and prints that useless error instead of saying "need Python 3.11+".

```bash
# Zero-friction fix — installer bootstraps Python for you
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### "No module named 'tkinter'"

```bash
# Linux / WSL
sudo apt install python3-tk
```

### "PortAudio library not found"

```bash
sudo apt install libportaudio2 portaudio19-dev libasound2-dev
pip install sounddevice --upgrade --force-reinstall
```

### MemPalace fails to import

```bash
pip install dulus[memory]   # pulls chromadb
```

### Voice transcribes technical terms wrong

Add domain terms to `~/.dulus/voice_keyterms.txt`, one per line.

### WebBridge not working

```bash
pip install dulus[webbridge]
playwright install
```

### Reset everything

```bash
rm -rf ~/.dulus
# Then run `dulus` again to re-run the welcome wizard
```

---

## Preguntas Frecuentes (Espanol)

### Que es Dulus?

Dulus es tu companero de IA — un agente autonomo en Python que se conecta a cualquier modelo de lenguaje. No es un chatbot; es un amigo que vuela a tu lado. Nombrado en honor a la Cigua Palmera (*Dulus dominicus*), ave nacional de Republica Dominicana.

### Dulus es gratis?

**El motor si.** El REPL open-source es gratis para siempre y corre a $0 con un modelo local de Ollama o con el tier gratuito de NVIDIA NIM. La inferencia por el router alojado de Dulus se mide en Fuel, y `/login claude`, `/login chatgpt`, `/login kimi` y `/login grok` cobran contra una suscripcion que ya pagas.

### Cuales modelos soporta?

- **11 proveedores nativos:** Anthropic, OpenAI, Gemini, DeepSeek, Qwen, Kimi, Zhipu, MiniMax, Ollama, LM Studio, Custom
- **100+ via LiteLLM:** OpenRouter, Groq, Together, Bedrock, Vertex, Mistral, xAI, y mas
- **Sin API key:** router Dulus (`/login dulus`), suscripciones Claude / ChatGPT / Kimi / Grok via OAuth, tier gratuito de NVIDIA NIM (14 modelos), Ollama local

### Como funciona el login por suscripcion?

`/login claude`, `/login chatgpt`, `/login kimi` y `/login grok` ejecutan el flujo OAuth oficial de cada proveedor en tu navegador. Dulus guarda el token localmente y llama a la API del proveedor con el, asi que las solicitudes se cobran contra el plan que ya pagas. No pegas ninguna API key a mano ni se captura ninguna cookie de sesion.

### Mis datos estan seguros?

- Las API keys se encriptan antes de guardarse
- Todo el procesamiento es local (excepto llamadas a proveedores)
- MemPalace permanece en tu maquina
- Sin telemetria, sin analytics, sin tracking
- Codigo abierto — puedes auditar cada linea

### Como conecto a una GPU remota?

```
/config custom_base_url=http://tu-servidor:8000/v1
/model custom/tu-modelo
```

### Las tool calls fallan en mi modelo local

Usa un modelo que soporte function calling: `qwen2.5-coder`, `llama3.3`, `mistral`, `phi4`.

### Como reinicio todo?

```bash
rm -rf ~/.dulus
# Luego corre `dulus` de nuevo para el wizard de bienvenida
```

### "No matching distribution found for dulus" en Ubuntu

Tu Python del sistema es mas viejo que 3.11. pip esconde el paquete y tira ese error basura.

```bash
# Arreglo zero friction — el installer te sube Python solo
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

---

> *Nombrado por el pajaro, no por el cohete. Seguimos volando.*
