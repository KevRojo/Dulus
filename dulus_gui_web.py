"""Launch the Dulus desktop shell without starting a local server."""
from __future__ import annotations

import os
import json
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
GUI_DIST = ROOT / "gui" / "dulus_orchestrator" / "dist" / "standalone.html"
PET_DIST = ROOT / "gui" / "dulus_orchestrator" / "dist" / "desktop-pet.html"
PET_LAUNCHER = ROOT / "dulus_pet.py"
GUI_RUNTIME = GUI_DIST.parent / "runtime-state.js"
DULUS_HOME = Path(os.environ.get("DULUS_HOME", Path.home() / ".dulus"))
GUI_QUESTION = DULUS_HOME / "gui_question.json"
GUI_ANSWER = DULUS_HOME / "gui_answer.json"
GUI_HEARTBEAT = DULUS_HOME / "gui_heartbeat.json"
GUI_CORE_INTAKE = DULUS_HOME / "gui_core_intake.jsonl"


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _profile_names() -> list[str]:
    profiles_dir = DULUS_HOME / "profiles"
    names = []
    if profiles_dir.exists():
        names.extend(p.name for p in profiles_dir.iterdir() if p.is_dir() and not p.name.startswith("."))
    active = _active_profile()
    if active and active not in names:
        names.insert(0, active)
    return sorted(set(names)) or ["default"]


def _active_profile() -> str:
    active = _read_json(DULUS_HOME / "active_profile.json", {})
    return str(active.get("name") or "default")


def _scan_named_dirs(path: Path, limit: int = 80) -> list[dict[str, str]]:
    if not path.exists():
        return []
    items = []
    for entry in sorted(path.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith(".") or entry.name == "__pycache__":
            continue
        if entry.is_dir():
            items.append({"name": entry.name, "path": str(entry)})
        elif entry.suffix.lower() in {".json", ".py", ".js", ".ts", ".md"}:
            items.append({"name": entry.stem, "path": str(entry)})
        if len(items) >= limit:
            break
    return items


def _scan_plugins(profile: str) -> list[dict[str, object]]:
    profile_cfg = DULUS_HOME / "profiles" / profile / "plugins.json"
    base_cfg = DULUS_HOME / "plugins.json"
    plugins: list[dict[str, object]] = []
    seen: set[str] = set()

    for cfg_path in (profile_cfg, base_cfg):
        cfg = _read_json(cfg_path, {"plugins": {}})
        raw_plugins = cfg.get("plugins", {})
        if not isinstance(raw_plugins, dict):
            continue
        for key, data in sorted(raw_plugins.items()):
            if key in seen or not isinstance(data, dict):
                continue
            seen.add(key)
            name = str(data.get("name") or key)
            source = str(data.get("source") or data.get("install_dir") or "")
            plugins.append(
                {
                    "id": key,
                    "name": name,
                    "source": source,
                    "enabled": bool(data.get("enabled", True)),
                    "type": "mcp" if "mcp" in name.lower() else "native",
                    "profile": profile,
                }
            )

    locations = [
        DULUS_HOME / "profiles" / profile / "plugins",
        DULUS_HOME / "plugins",
    ]
    for location in locations:
        for item in _scan_named_dirs(location):
            name = item["name"]
            if name in seen:
                continue
            seen.add(name)
            source = item["path"]
            manifest = Path(source) / "plugin.json"
            if manifest.exists():
                meta = _read_json(manifest, {})
                name = str(meta.get("name") or name)
            plugins.append(
                {
                    "id": name,
                    "name": name,
                    "source": source,
                    "enabled": True,
                    "type": "mcp" if "mcp" in name.lower() else "native",
                    "profile": profile,
                }
            )
    return plugins


def _profile_plugin_cfg(profile: str) -> Path:
    return DULUS_HOME / "profiles" / profile / "plugins.json"


def _scan_skills(profile: str) -> list[dict[str, object]]:
    locations = [
        DULUS_HOME / "profiles" / profile / "skills",
        DULUS_HOME / "skills",
    ]
    seen: set[str] = set()
    skills: list[dict[str, object]] = []
    for location in locations:
        for item in _scan_named_dirs(location):
            name = item["name"]
            if name in seen:
                continue
            seen.add(name)
            skills.append(
                {
                    "id": name,
                    "name": name,
                    "source": item["path"],
                    "enabled": True,
                    "profile": profile,
                }
            )
    return skills


def _models(config: dict[str, object]) -> list[str]:
    preferred = [
        str(config.get("model") or "grok-4"),
        "grok-4",
        "gemini-2.5-flash",
        "claude-3.5-sonnet",
        "nvidia-web/deepseek-r1",
        "deepseek-chat",
        "kimi-k2",
        "ollama/qwen2.5-coder",
    ]
    models: list[str] = []
    for model in preferred:
        if model and model not in models:
            models.append(model)
    return models


def _model_provider(model: str) -> str:
    try:
        from providers import detect_provider

        return detect_provider(model)
    except Exception:
        if "/" in model:
            return model.split("/", 1)[0]
        if model.lower().startswith("grok"):
            return "xai-oauth"
        return "auto"


def _workspaces(current_workspace: str) -> list[str]:
    entries = [current_workspace]
    workspace_dir = DULUS_HOME / "workspaces"
    if workspace_dir.exists():
        entries.extend(str(p) for p in sorted(workspace_dir.iterdir(), key=lambda x: x.name.lower()) if p.is_dir())
    return list(dict.fromkeys(entries))


def _active_workspace(config: dict[str, object]) -> Path:
    workspace_value = os.environ.get("DULUS_WORKSPACE") or str(config.get("workspace_last") or "workspace1")
    candidate = Path(workspace_value).expanduser()
    if not candidate.is_absolute():
        candidate = DULUS_HOME / "workspaces" / workspace_value
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _context_files(current_workspace: Path) -> list[dict[str, str]]:
    names = ("AGENTS.md", "CLAUDE.md", ".codex", ".dulus-context")
    items: list[dict[str, str]] = []
    for name in names:
        path = current_workspace / name
        if path.exists():
            items.append({"id": name, "name": name, "kind": "file", "source": str(path)})
    return items


def _write_runtime_state(workspace: Path | None = None) -> None:
    config = _read_json(DULUS_HOME / "config.json", {})
    workspace = workspace or _active_workspace(config)
    active_profile = _active_profile()
    model = str(config.get("model") or "grok-4")
    models = _models(config)
    state = {
        "workspace": str(workspace),
        "workspaces": _workspaces(str(workspace)),
        "profile": active_profile,
        "profiles": _profile_names(),
        "model": model,
        "modelProvider": _model_provider(model),
        "models": models,
        "modelProviders": {name: _model_provider(name) for name in models},
        "permissionMode": str(config.get("permission_mode") or "auto"),
        "plugins": {profile: _scan_plugins(profile) for profile in _profile_names()},
        "skills": {profile: _scan_skills(profile) for profile in _profile_names()},
        "contextItems": _context_files(workspace),
        "webchatUrl": os.environ.get("DULUS_WEBCHAT_URL", "http://127.0.0.1:5000"),
    }
    GUI_RUNTIME.write_text(
        "window.__DULUS_RUNTIME__ = "
        + json.dumps(state, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )


def _write_pet_html() -> None:
    PET_DIST.parent.mkdir(parents=True, exist_ok=True)
    PET_DIST.write_text(
        r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dulus Pet</title>
  <style>
    :root {
      color-scheme: dark;
      --gold: #fbbf24;
      --orange: #ff6a1a;
      --ink: #09090b;
      --panel: rgba(9, 9, 11, .82);
      --border: rgba(251, 191, 36, .34);
    }
    * { box-sizing: border-box; }
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: transparent;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      user-select: none;
    }
    body { display: grid; place-items: end center; padding: 12px; }
    .shell {
      width: 336px;
      min-height: 190px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: end;
      gap: 8px;
    }
    .bubble {
      width: 100%;
      max-height: 205px;
      display: none;
      flex-direction: column;
      gap: 8px;
      padding: 12px;
      border: 1px solid rgba(255,255,255,.09);
      border-radius: 16px;
      background: var(--panel);
      box-shadow: 0 22px 70px rgba(0,0,0,.55), 0 0 28px rgba(251,191,36,.12);
      backdrop-filter: blur(16px);
    }
    .shell.open .bubble { display: flex; }
    .reply {
      min-height: 38px;
      max-height: 104px;
      overflow-y: auto;
      color: #f8fafc;
      font-size: 13px;
      line-height: 1.4;
      white-space: pre-wrap;
      user-select: text;
    }
    .reply.muted { color: #a1a1aa; }
    .row { display: flex; gap: 8px; align-items: center; }
    input {
      flex: 1;
      min-width: 0;
      height: 38px;
      border: 1px solid rgba(255,255,255,.11);
      border-radius: 12px;
      background: rgba(0,0,0,.5);
      color: white;
      padding: 0 12px;
      outline: none;
      user-select: text;
    }
    input:focus { border-color: rgba(251,191,36,.7); box-shadow: 0 0 0 3px rgba(251,191,36,.12); }
    button {
      border: 0;
      color: #0a0a0a;
      background: var(--gold);
      border-radius: 12px;
      height: 38px;
      padding: 0 12px;
      font-weight: 800;
      cursor: pointer;
    }
    button.icon {
      width: 34px;
      height: 34px;
      padding: 0;
      color: #cbd5e1;
      background: rgba(255,255,255,.08);
    }
    .pet {
      position: relative;
      width: 118px;
      height: 146px;
      cursor: pointer;
      filter: drop-shadow(0 18px 22px rgba(0,0,0,.55));
      animation: bob 2.4s ease-in-out infinite;
    }
    .flame {
      position: absolute;
      left: 39px;
      top: 0;
      width: 40px;
      height: 54px;
      background:
        linear-gradient(45deg, transparent 0 25%, #ff3b00 0 46%, transparent 0),
        linear-gradient(-45deg, transparent 0 19%, #ff8a00 0 58%, transparent 0),
        radial-gradient(circle at 52% 70%, #fff275 0 19%, #ffb000 20% 45%, #ff4d00 46% 72%, transparent 73%);
      clip-path: polygon(48% 0, 67% 22%, 88% 44%, 79% 82%, 50% 100%, 18% 84%, 9% 48%, 28% 28%);
      image-rendering: pixelated;
      animation: flame .38s steps(2) infinite alternate;
      box-shadow: 0 0 18px rgba(255,106,26,.82);
    }
    .head {
      position: absolute;
      left: 16px;
      top: 47px;
      width: 86px;
      height: 72px;
      background: #ffe0a8;
      border: 6px solid #ff7514;
      border-radius: 24px 24px 18px 18px;
      box-shadow: inset 0 -8px 0 rgba(255,166,67,.35), 0 0 0 3px rgba(80,25,0,.22);
    }
    .eye {
      position: absolute;
      top: 24px;
      width: 12px;
      height: 16px;
      background: #171717;
      border-radius: 3px;
    }
    .eye.left { left: 22px; }
    .eye.right { right: 22px; }
    .cheek {
      position: absolute;
      bottom: 18px;
      width: 14px;
      height: 8px;
      border-radius: 50%;
      background: #ff9aa8;
      opacity: .85;
    }
    .cheek.left { left: 10px; }
    .cheek.right { right: 10px; }
    .body {
      position: absolute;
      left: 29px;
      top: 109px;
      width: 60px;
      height: 34px;
      background: #ffe8be;
      border-radius: 14px 14px 18px 18px;
      box-shadow: inset 0 -7px 0 rgba(230,150,70,.3);
    }
    .core {
      position: absolute;
      left: 22px;
      top: 8px;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: repeating-linear-gradient(90deg, #0d0d0d 0 4px, #ff7a00 4px 8px);
      border: 2px solid #3d2100;
      box-shadow: 0 0 11px rgba(255,122,0,.75);
    }
    .arm {
      position: absolute;
      top: 116px;
      width: 18px;
      height: 28px;
      background: #ffdca6;
      border-radius: 14px;
    }
    .arm.left { left: 14px; transform: rotate(16deg); }
    .arm.right { right: 14px; transform: rotate(-16deg); }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      align-self: center;
      padding: 4px 9px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,.58);
      color: var(--gold);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .14em;
      text-transform: uppercase;
    }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 10px #22c55e; }
    @keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
    @keyframes flame { from { transform: translateY(0) scaleX(1); } to { transform: translateY(-2px) scaleX(.92); } }
  </style>
</head>
<body>
  <main class="shell" id="shell">
    <section class="bubble" id="bubble">
      <div class="row">
        <div class="reply muted" id="reply">Klk, soy Dulus. Tócame, escribe, y te respondo aquí mismo.</div>
        <button class="icon" id="close" title="Close">×</button>
      </div>
      <form class="row" id="form">
        <input id="prompt" autocomplete="off" placeholder="Escribe algo..." />
        <button id="send" type="submit">Send</button>
      </form>
    </section>
    <div class="pet" id="pet" title="Dulus pet">
      <div class="flame"></div>
      <div class="head">
        <div class="eye left"></div>
        <div class="eye right"></div>
        <div class="cheek left"></div>
        <div class="cheek right"></div>
      </div>
      <div class="arm left"></div>
      <div class="arm right"></div>
      <div class="body"><div class="core"></div></div>
    </div>
    <div class="status"><span class="dot"></span><span id="status">ready</span></div>
  </main>
  <script>
    const shell = document.getElementById('shell');
    const pet = document.getElementById('pet');
    const closeBtn = document.getElementById('close');
    const form = document.getElementById('form');
    const prompt = document.getElementById('prompt');
    const reply = document.getElementById('reply');
    const status = document.getElementById('status');

    const setOpen = (open) => {
      shell.classList.toggle('open', open);
      if (open) setTimeout(() => prompt.focus(), 50);
    };

    pet.addEventListener('click', () => setOpen(true));
    closeBtn.addEventListener('click', () => setOpen(false));

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const text = prompt.value.trim();
      if (!text) return;
      prompt.value = '';
      reply.classList.remove('muted');
      reply.textContent = `You: ${text}\n\nDulus: pensando...`;
      status.textContent = 'thinking';
      try {
        const api = window.pywebview && window.pywebview.api;
        const result = api && api.send_pet_message
          ? await api.send_pet_message(text)
          : { ok: false, text: 'El puente desktop no está disponible.' };
        reply.textContent = result && result.text ? result.text : 'Dulus no devolvió texto.';
        status.textContent = result && result.ok ? 'answered' : 'error';
      } catch (error) {
        reply.textContent = `No pude hablar con Dulus: ${error && error.message ? error.message : error}`;
        status.textContent = 'error';
      }
    });
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DulusGuiApi:
    def __init__(self) -> None:
        self._agent_state = None
        self._agent_config = None
        self._agent_lock = None

    def _ensure_agent(self):
        if self._agent_state is not None and self._agent_config is not None:
            return self._agent_state, self._agent_config
        import threading
        from agent import AgentState
        from config import load_config

        config = load_config()
        workspace = _active_workspace(config)
        try:
            os.chdir(workspace)
        except Exception:
            pass
        self._agent_state = AgentState()
        self._agent_config = config
        self._agent_lock = threading.Lock()
        return self._agent_state, self._agent_config

    def _event_to_dict(self, event):
        from agent import PermissionRequest, TextChunk, ThinkingChunk, ToolEnd, ToolStart, TurnDone

        if isinstance(event, TextChunk):
            return {"type": "text", "text": event.text}
        if isinstance(event, ThinkingChunk):
            return {"type": "thinking", "text": event.text}
        if isinstance(event, ToolStart):
            return {"type": "tool_start", "name": event.name, "inputs": event.inputs}
        if isinstance(event, ToolEnd):
            return {"type": "tool_end", "name": event.name, "result": event.result, "permitted": event.permitted}
        if isinstance(event, TurnDone):
            return {
                "type": "turn_done",
                "in": event.input_tokens,
                "out": event.output_tokens,
                "cache_read": getattr(event, "cache_read_tokens", 0),
                "cache_write": getattr(event, "cache_creation_tokens", 0),
            }
        if isinstance(event, PermissionRequest):
            return {"type": "permission", "description": event.description}
        return None

    def _touch_heartbeat(self) -> None:
        DULUS_HOME.mkdir(parents=True, exist_ok=True)
        GUI_HEARTBEAT.write_text(json.dumps({"open": True, "ts": _utc_now()}), encoding="utf-8")

    def get_pending_question(self):
        self._touch_heartbeat()
        return _read_json(GUI_QUESTION, None)

    def answer_question(self, question_id: str, answer: str):
        self._touch_heartbeat()
        GUI_ANSWER.write_text(
            json.dumps({"id": question_id, "answer": answer, "answered_at": _utc_now()}, ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            current = _read_json(GUI_QUESTION, {})
            if current.get("id") == question_id:
                GUI_QUESTION.unlink(missing_ok=True)
        except Exception:
            pass
        return {"ok": True}

    def submit_core_intake(self, topic: str, prompt: str, workspace: str, profile: str, model: str):
        self._touch_heartbeat()
        entry = {
            "topic": topic,
            "prompt": prompt,
            "workspace": workspace,
            "profile": profile,
            "model": model,
            "created_at": _utc_now(),
        }
        with GUI_CORE_INTAKE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"ok": True, "prompt": prompt}

    def get_webchat_sessions(self, webchat_url: str = ""):
        self._touch_heartbeat()
        base = (webchat_url or os.environ.get("DULUS_WEBCHAT_URL") or "http://127.0.0.1:5000").rstrip("/")
        try:
            with urlopen(f"{base}/api/sessions", timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return []

    def send_webchat_message(self, message: str, webchat_url: str = ""):
        self._touch_heartbeat()
        base = (webchat_url or os.environ.get("DULUS_WEBCHAT_URL") or "http://127.0.0.1:5000").rstrip("/")
        request = Request(
            f"{base}/chat",
            data=json.dumps({"message": message}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        events: list[dict[str, object]] = []
        try:
            with urlopen(request, timeout=300) as response:
                for raw in response:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data: "):
                        continue
                    try:
                        events.append(json.loads(line[6:]))
                    except Exception:
                        continue
        except Exception as exc:
            return [{"type": "error", "message": str(exc)}]
        return events

    def send_gui_message(self, message: str):
        self._touch_heartbeat()
        try:
            from agent import run as agent_run
            from context import build_system_prompt
            import tools as _tools_init  # noqa: F401

            state, config = self._ensure_agent()
            workspace = _active_workspace(config)
            events: list[dict[str, object]] = []
            lock = self._agent_lock
            if lock is None:
                return [{"type": "error", "message": "GUI agent lock was not initialized."}]

            with lock:
                previous_cwd = Path.cwd()
                try:
                    os.chdir(workspace)
                except Exception:
                    pass
                try:
                    system_prompt = build_system_prompt(config)
                    for event in agent_run(message, state, config, system_prompt):
                        payload = self._event_to_dict(event)
                        if payload:
                            events.append(payload)
                finally:
                    try:
                        os.chdir(previous_cwd)
                    except Exception:
                        pass
            return events
        except Exception as exc:
            return [{"type": "error", "message": str(exc)}]

    def send_pet_message(self, message: str):
        events = self.send_gui_message(message)
        chunks: list[str] = []
        errors: list[str] = []
        for event in events:
            if event.get("type") == "text":
                chunks.append(str(event.get("text") or ""))
            elif event.get("type") == "error":
                errors.append(str(event.get("message") or "Unknown error"))
        text = "".join(chunks).strip()
        if not text and errors:
            text = "\n".join(errors)
        if not text:
            text = "Dulus terminó, pero no devolvió texto."
        return {"ok": not errors, "text": text}

    def set_plugin_enabled(self, profile: str, plugin_id: str, enabled: bool):
        self._touch_heartbeat()
        cfg_path = _profile_plugin_cfg(profile)
        data = _read_json(cfg_path, {"plugins": {}})
        plugins = data.setdefault("plugins", {})
        if plugin_id not in plugins:
            install_dir = DULUS_HOME / "profiles" / profile / "plugins" / plugin_id
            plugins[plugin_id] = {
                "name": plugin_id,
                "scope": "user",
                "source": str(install_dir),
                "install_dir": str(install_dir),
                "enabled": bool(enabled),
            }
        else:
            plugins[plugin_id]["enabled"] = bool(enabled)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"ok": True, "profile": profile, "plugin": plugin_id, "enabled": bool(enabled)}

    def open_pet_window(self):
        self._touch_heartbeat()
        return _start_pet_process()


def _chrome_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env_name)
        if not base:
            continue
        candidates.extend(
            [
                Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ]
        )
    return candidates


def _open_browser_app(url: str) -> bool:
    for browser in _chrome_candidates():
        if browser.exists():
            subprocess.Popen(
                [
                    str(browser),
                    f"--app={url}",
                    "--new-window",
                    "--disable-features=Translate",
                ],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
    webbrowser.open(url)
    return True


def _start_pet_process() -> dict[str, object]:
    _write_pet_html()
    if not PET_LAUNCHER.exists():
        return {"ok": False, "message": f"Pet launcher not found: {PET_LAUNCHER}"}
    log_path = DULUS_HOME / "dulus_pet.log"
    DULUS_HOME.mkdir(parents=True, exist_ok=True)
    try:
        log_file = log_path.open("a", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(PET_LAUNCHER)],
            cwd=str(ROOT),
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {"ok": True, "pid": proc.pid, "log": str(log_path)}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


def _gui_url() -> str:
    _write_runtime_state()
    _write_pet_html()
    return GUI_DIST.resolve().as_uri()


def _pet_url() -> str:
    _write_pet_html()
    return PET_DIST.resolve().as_uri()


def _pet_corner(width: int, height: int) -> tuple[int, int]:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        screen_w = int(user32.GetSystemMetrics(0))
        screen_h = int(user32.GetSystemMetrics(1))
        return max(24, screen_w - width - 28), max(24, screen_h - height - 56)
    except Exception:
        return 1120, 520


def launch_gui(config: dict | None = None, initial_prompt: str | None = None) -> None:
    """Launch the Dulus web GUI (pywebview shell around the React build).

    Args mirror the classic tkinter GUI so `dulus --gui` can call either.
    `config` and `initial_prompt` are accepted for API compatibility;
    the web GUI reads runtime state from ~/.dulus at startup.
    """
    if not GUI_DIST.exists():
        raise FileNotFoundError(
            f"Dulus GUI build not found: {GUI_DIST}\n"
            "Run `npm install` and `npm run build` inside gui/dulus_orchestrator."
        )

    url = _gui_url()
    try:
        import webview  # type: ignore

        api = DulusGuiApi()
        webview.create_window(
            "Dulus",
            url,
            width=1440,
            height=960,
            min_size=(1120, 720),
            background_color="#000000",
            js_api=api,
        )
        # Desktop pet is optional — only start it when the launcher exists.
        if PET_LAUNCHER.exists():
            _start_pet_process()
        webview.start()
    except Exception:
        _open_browser_app(url)


def main() -> None:
    launch_gui()


if __name__ == "__main__":
    main()

