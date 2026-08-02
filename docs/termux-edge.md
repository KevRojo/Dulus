# Run Dulus with a model *on your phone* — Termux + `edge` 📱🦅

No cloud. No API key. No per-token bill. Just your Android phone, a small model
running **on the device**, and Dulus driving it. This is the `edge` provider, and
here is the whole install — copy-paste, top to bottom.

> **What you get:** a real agent (tools, memory, MCP, everything) talking to a
> model whose weights never leave your phone. Works offline once it's set up.

---

## The shape of it

```
┌─────────────────────────── your Android phone ───────────────────────────┐
│                                                                           │
│   Termux                                                                  │
│   ┌───────────────────────┐        OpenAI /v1        ┌──────────────────┐ │
│   │  llama-server (:8080) │  ◄───────────────────►   │  dulus           │ │
│   │  gemma-3-1b (GGUF)    │   127.0.0.1, on-device   │  --model edge/…  │ │
│   └───────────────────────┘                          └──────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

Dulus's `edge` provider is just an OpenAI client pointed at `127.0.0.1:8080`. It
does not care *what* serves that port — so we serve it with **llama.cpp**, which
runs anywhere, including Termux.

---

## 1. Install Termux (the right one)

Install Termux from **F-Droid** or **GitHub**, *not* the Play Store version
(it's outdated and breaks package installs).

- F-Droid: <https://f-droid.org/en/packages/com.termux/>

Open it and update:

```bash
pkg update && pkg upgrade -y
```

## 2. Install the basics

```bash
pkg install -y python git curl tmux
```

## 3. Get a local model server (llama.cpp)

Termux ships llama.cpp as a package — this is the easy path:

```bash
pkg install -y llama-cpp
```

That gives you `llama-server`, `llama-cli`, etc. (If the package isn't available
on your arch, build from source: `git clone https://github.com/ggml-org/llama.cpp
&& cd llama.cpp && cmake -B build && cmake --build build -j`.)

## 4. Download a small model (GGUF)

A 1B model in Q4 is ~700 MB and runs comfortably on a modern phone. Grab any
small **instruct** GGUF from Hugging Face — for example a Gemma 3 1B:

```bash
curl -L -o gemma-3-1b-it-Q4_K_M.gguf \
  "https://huggingface.co/<org>/<repo>/resolve/main/gemma-3-1b-it-Q4_K_M.gguf"
```

> Pick the biggest one that fits your RAM. 1B–2B in Q4 is the sweet spot for a
> phone; 3B+ works on flagships. The file is the only thing you download — after
> this you can go fully offline.

## 5. Start the server

Run it in its own `tmux` window so it keeps serving while you use Dulus:

```bash
tmux new -d -s llama \
  "llama-server -m gemma-3-1b-it-Q4_K_M.gguf --port 8080 --ctx-size 8192"
```

Give it a few seconds to load, then confirm it's up:

```bash
curl -s http://127.0.0.1:8080/v1/models
```

## 6. Install Dulus

```bash
pip install dulus
```

## 7. Talk to your on-device model

```bash
dulus --model edge/gemma-3-1b
```

That's it. The `edge/` prefix routes to the local server; the model name after it
is just a label (llama-server serves whatever you loaded with `-m`). Everything —
tools, memory, `/model`, tasks — works exactly like the cloud providers, except
nothing leaves the phone.

---

## Already running Ollama?

If you have Ollama going instead of raw llama.cpp, point `edge` at it:

```bash
dulus --config edge_base_url=http://127.0.0.1:11434/v1
dulus --model edge/gemma3
```

## Model on the phone, keyboard on your laptop

`edge`'s host/port is overridable, so the model can run on your phone while you
drive Dulus from your laptop on the same Wi-Fi:

```bash
# on the phone: bind llama-server to the LAN
llama-server -m model.gguf --host 0.0.0.0 --port 8080

# on the laptop:
export DULUS_EDGE_BASE_URL=http://<phone-lan-ip>:8080/v1
dulus --model edge/gemma-3-1b
```

## Tips

- **Battery / heat:** on-device inference is CPU-heavy. Keep it to small models,
  and cap context (`--ctx-size`) to what you actually need.
- **Keep it alive:** `termux-wake-lock` stops Android from killing the server
  when the screen sleeps.
- **It's free:** on-device models are priced at `$0` in Dulus — `/cost` will
  show zeros, because there's nothing to bill.

---

### What about Gemma Nano / the on-device APK?

A native Android bridge that runs **Gemma Nano directly on the phone's NPU via
AICore** — zero download, hardware-accelerated — is still being built. That APK
takes time. Until it ships, the Termux + llama.cpp path above already gets you a
**fully local model on the same phone**, today, no APK required. Same `edge/*`
route; when the APK lands it just becomes another backend behind the same
provider.

---

Run it → `pip install dulus` · [dulus.ai](https://dulus.ai)
Hosted agents + dashboard, zero setup → [dulus.online](https://dulus.online)

Same brain either way. 🦅🇩🇴
