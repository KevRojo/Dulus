"""Dulus WebChat — standalone or in-process mirror of the terminal agent.

When launched via /webchat from backend.py, the in-process server in
webchat_server.py is used instead. This file remains usable as a
standalone fallback.
"""
from __future__ import annotations

import argparse
import json
import queue
import threading
import time
import uuid
import webbrowser
from typing import Generator

from flask import Flask, request, jsonify, Response, stream_with_context

from agent import (
    run as agent_run,
    AgentState,
    TextChunk,
    ThinkingChunk,
    ToolStart,
    ToolEnd,
    TurnDone,
    PermissionRequest,
)
from context import build_system_prompt
from common import sanitize_text
from config import load_config

# Ensure tools are registered
import tools as _tools_init
import memory.tools as _mem_tools_init
import multi_agent.tools as _ma_tools_init
import skill.tools as _sk_tools_init
import dulus_mcp.tools as _mcp_tools_init
import task.tools as _task_tools_init

try:
    import tmux_tools as _tmux_tools_init
except Exception:
    pass

try:
    from plugin.loader import register_plugin_tools
    register_plugin_tools()
except Exception:
    pass

# ── shared state for standalone mode ───────────────────────────────────────
HISTORY_LOCK = threading.Lock()
CONFIG = load_config()
STATE = AgentState()
_PENDING_PERMISSIONS: dict[str, tuple[PermissionRequest, threading.Event]] = {}


def _run_agent_standalone(user_message: str) -> Generator:
    """Run agent loop with local state/config, yielding all events."""
    cfg = CONFIG
    state = STATE
    user_input = sanitize_text(user_message)

    # Skill inject
    _skill_body = cfg.pop("_skill_inject", "")
    if _skill_body:
        user_input = (
            "[SKILL CONTEXT — follow these instructions for this turn]\n\n"
            + _skill_body
            + "\n\n---\n\n[USER MESSAGE]\n"
            + user_input
        )

    # MemPalace
    if cfg.get("mem_palace", True) and user_input and len(user_input.strip()) >= 12:
        _trivial = {
            "hola", "klk", "gracias", "ok", "si", "no", "dale",
            "exit", "quit", "help", "thanks", "bien",
        }
        _first = user_input.strip().lower().split()[0]
        if _first not in _trivial:
            try:
                from memory import find_relevant_memories

                _q = user_input.strip()[:200]
                _raw_hits = find_relevant_memories(_q, max_results=3)
                if _raw_hits:
                    _parts = []
                    for _i, _h in enumerate(_raw_hits, 1):
                        _name = _h.get("name", f"hit_{_i}")
                        _desc = _h.get("description", "")
                        _body = _h.get("content", "").strip()
                        _snip = _body[:300] + ("..." if len(_body) > 300 else "")
                        if _desc:
                            _parts.append(f"### {_name}\n_{_desc}_\n{_snip}")
                        else:
                            _parts.append(f"### {_name}\n{_snip}")
                    _hits_str = "\n\n".join(_parts)
                    if len(_hits_str) > 2000:
                        _hits_str = _hits_str[:2000] + "\n[...truncated]"
                    _inject = (
                        "[MemPalace — relevant memories pre-loaded for this turn. "
                        "Do NOT re-query unless the user explicitly asks for more.]\n\n"
                        + _hits_str
                    )
                    user_input = (
                        _inject + "\n\n---\n\n[USER MESSAGE]\n" + user_input
                    )
            except Exception:
                pass

    system_prompt = build_system_prompt(cfg)
    cfg["_last_interaction_time"] = time.time()

    yield from agent_run(user_input, state, cfg, system_prompt)


def create_app() -> Flask:
    app = Flask(__name__)

    PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Dulus WebChat</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0a0a0c;color:#e6e6e6;font:14px/1.5 Consolas,monospace;height:100vh;display:flex;flex-direction:column}
  header{padding:10px 18px;background:#111;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
  header h1{font-size:14px;color:#00ffa3;font-weight:600}
  header .model{font-size:11px;color:#666}
  header button{background:#222;color:#888;border:1px solid #333;padding:4px 10px;border-radius:3px;cursor:pointer;font:inherit}
  header button:hover{color:#fff}
  #log{flex:1;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:14px}
  .msg{max-width:780px;padding:10px 14px;border-radius:6px;white-space:pre-wrap;word-wrap:break-word}
  .user{align-self:flex-end;background:#1a3a2a;border:1px solid #2a5a40}
  .assistant{align-self:flex-start;background:#15151a;border:1px solid #2a2a30}
  .meta{font-size:10px;color:#555;margin-top:4px}
  .err{color:#ff6b6b}
  form{display:flex;gap:8px;padding:12px 18px;background:#111;border-top:1px solid #222}
  textarea{flex:1;background:#000;color:#e6e6e6;border:1px solid #333;padding:10px;border-radius:4px;font:inherit;resize:none;height:60px;outline:none}
  textarea:focus{border-color:#00ffa3}
  button.send{background:#00ffa3;color:#000;border:none;padding:0 22px;border-radius:4px;font-weight:600;cursor:pointer}
  button.send:disabled{opacity:.4;cursor:wait}
  .think{font-size:10px;color:#888;margin-top:6px;padding:6px;border-left:2px solid #444;background:#0d0d10;white-space:pre-wrap}
  .tool{font-size:11px;color:#aaa;margin-top:6px;padding:8px;border-left:2px solid #00ffa3;background:#0d1a14;white-space:pre-wrap}
  .tool-result{font-size:11px;color:#ccc;margin-top:4px;padding:6px;border-left:2px solid #444;background:#111;white-space:pre-wrap;max-height:200px;overflow-y:auto}
  .perm{font-size:12px;color:#ffcc00;margin-top:6px;padding:8px;border:1px solid #443300;background:#1a1500;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .perm button{background:#333;color:#fff;border:1px solid #555;padding:4px 12px;border-radius:3px;cursor:pointer}
  .perm button.approve{background:#00ffa3;color:#000;border-color:#00ffa3}
</style></head><body>
<header><h1>DULUS WEBCHAT</h1><span class="model" id="modelTag">…</span><button onclick="clearChat()">clear</button></header>
<div id="log"></div>
<form id="f" onsubmit="return send(event)">
  <textarea id="inp" placeholder="Mensaje a Dulus... (Enter envía, Shift+Enter nueva línea)" autofocus></textarea>
  <button class="send" id="sendBtn">SEND</button>
</form>
<script>
const log=document.getElementById('log'),inp=document.getElementById('inp'),btn=document.getElementById('sendBtn'),modelTag=document.getElementById('modelTag');

function add(role,text,extra){
  const d=document.createElement('div');d.className='msg '+role;
  if(typeof text==='string') d.textContent=text; else d.appendChild(text);
  if(extra){const m=document.createElement('div');m.className='meta';m.textContent=extra;d.appendChild(m);}
  log.appendChild(d);log.scrollTop=log.scrollHeight;return d;
}

let currentAssistant=null, currentText='';

function ensureAssistant(){
  if(!currentAssistant){currentAssistant=add('assistant','');}
  return currentAssistant;
}

function appendText(text){
  ensureAssistant();
  currentText+=text;
  currentAssistant.textContent=currentText;
  log.scrollTop=log.scrollHeight;
}

function appendThinking(text){
  ensureAssistant();
  let th=currentAssistant.querySelector('.think');
  if(!th){th=document.createElement('div');th.className='think';th.textContent='[thinking]\n';currentAssistant.appendChild(th);}
  th.textContent+=text;
  log.scrollTop=log.scrollHeight;
}

function startTool(name,inputs){
  ensureAssistant();
  const t=document.createElement('div');t.className='tool';
  t.textContent='🔧 '+name+'\n'+JSON.stringify(inputs,null,2);
  currentAssistant.appendChild(t);
  log.scrollTop=log.scrollHeight;
}

function endTool(name,result,permitted){
  ensureAssistant();
  const r=document.createElement('div');r.className='tool-result';
  r.textContent=(permitted?'✅':'❌')+' '+result;
  currentAssistant.appendChild(r);
  log.scrollTop=log.scrollHeight;
}

function showPermission(id,desc){
  ensureAssistant();
  const p=document.createElement('div');p.className='perm';
  p.innerHTML='<span>⛔ '+desc+'</span>';
  const yes=document.createElement('button');yes.textContent='Approve';yes.className='approve';
  yes.onclick=()=>{sendPermission(id,true);p.remove();};
  const no=document.createElement('button');no.textContent='Deny';
  no.onclick=()=>{sendPermission(id,false);p.remove();};
  p.appendChild(yes);p.appendChild(no);
  currentAssistant.appendChild(p);
  log.scrollTop=log.scrollHeight;
}

async function sendPermission(id,granted){
  await fetch('/permission',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,granted})});
}

async function send(e){
  if(e)e.preventDefault();
  const t=inp.value.trim();if(!t)return false;
  add('user',t);inp.value='';btn.disabled=true;
  currentAssistant=null;currentText='';
  try{
    const resp=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:t})});
    const reader=resp.body.getReader();
    const decoder=new TextDecoder();
    let buf='';
    while(true){
      const {done,value}=await reader.read();
      if(done) break;
      buf+=decoder.decode(value,{stream:true});
      const lines=buf.split('\n');
      buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: ')) continue;
        let d;
        try{d=JSON.parse(line.slice(6));}catch(_){continue;}
        if(d.type==='text') appendText(d.text);
        else if(d.type==='thinking') appendThinking(d.text);
        else if(d.type==='tool_start') startTool(d.name,d.inputs);
        else if(d.type==='tool_end') endTool(d.name,d.result,d.permitted);
        else if(d.type==='permission') showPermission(d.id,d.description);
        else if(d.type==='turn_done'){
          const meta=document.createElement('div');meta.className='meta';
          meta.textContent='in:'+d.in+' out:'+d.out;
          ensureAssistant().appendChild(meta);
        }
        else if(d.type==='error') appendText('\n[error] '+d.message);
        else if(d.type==='done'){}
      }
    }
  }catch(err){
    add('assistant','[network] '+err,'').classList.add('err');
  }finally{
    btn.disabled=false;inp.focus();
  }
  return false;
}

async function clearChat(){
  await fetch('/clear',{method:'POST'});
  log.innerHTML='';currentAssistant=null;currentText='';
}

async function syncChat(){
  if(btn.disabled) return;
  const r=await fetch('/state');const j=await r.json();
  modelTag.textContent=j.model;
  const currentMsgs = log.querySelectorAll('.msg').length;
  if(j.history.length !== currentMsgs){
    const wasNearBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 50;
    log.innerHTML='';
    currentAssistant=null;
    currentText='';
    for(const m of j.history){
      if(m.role==='user') add('user',m.content||'');
      else if(m.role==='assistant'){
        const d=add('assistant',m.content||'');
        if(m.thinking){const th=document.createElement('div');th.className='think';th.textContent='[thinking]\n'+m.thinking;d.appendChild(th);}
      }
      else if(m.role==='tool'){
        const d=add('assistant','');
        const t=document.createElement('div');t.className='tool-result';t.textContent='🔧 tool result:\n'+(m.content||'');d.appendChild(t);
      }
    }
    if(wasNearBottom) log.scrollTop=log.scrollHeight;
  }
}

async function loadHist(){ return syncChat(); }

inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
loadHist();
setInterval(syncChat, 5000);
</script>
</body></html>"""

    @app.route("/")
    def home() -> Response:
        return Response(PAGE, mimetype="text/html")

    @app.route("/state")
    def state_endpoint() -> Response:
        with HISTORY_LOCK:
            hist = [dict(m) for m in STATE.messages]
            model = CONFIG.get("model", "?")
        return jsonify(model=model, history=hist)

    @app.route("/clear", methods=["POST"])
    def clear() -> Response:
        with HISTORY_LOCK:
            STATE.messages.clear()
        return jsonify(ok=True)

    @app.route("/permission", methods=["POST"])
    def permission() -> Response:
        body = request.get_json(silent=True) or {}
        pid = body.get("id")
        granted = body.get("granted", False)
        with HISTORY_LOCK:
            item = _PENDING_PERMISSIONS.get(pid)
        if item is None:
            return jsonify(error="not found"), 404
        req, evt = item
        req.granted = bool(granted)
        evt.set()
        return jsonify(ok=True)

    @app.route("/chat", methods=["POST"])
    def chat() -> Response:
        body = request.get_json(silent=True) or {}
        msg = (body.get("message") or "").strip()
        if not msg:
            return jsonify(error="empty message"), 400

        def generate():
            q: queue.Queue = queue.Queue(maxsize=512)
            exc_holder = [None]

            def producer():
                try:
                    for ev in _run_agent_standalone(msg):
                        q.put(ev)
                except Exception as e:
                    exc_holder[0] = e
                finally:
                    q.put(None)

            t = threading.Thread(target=producer, daemon=True)
            t.start()

            yield 'data: {"type":"start"}\n\n'

            while True:
                item = q.get()
                if item is None:
                    break

                payload = None
                if isinstance(item, TextChunk):
                    payload = {"type": "text", "text": item.text}
                elif isinstance(item, ThinkingChunk):
                    payload = {"type": "thinking", "text": item.text}
                elif isinstance(item, ToolStart):
                    payload = {"type": "tool_start", "name": item.name, "inputs": item.inputs}
                elif isinstance(item, ToolEnd):
                    payload = {
                        "type": "tool_end",
                        "name": item.name,
                        "result": item.result,
                        "permitted": item.permitted,
                    }
                elif isinstance(item, TurnDone):
                    payload = {
                        "type": "turn_done",
                        "in": item.input_tokens,
                        "out": item.output_tokens,
                    }
                elif isinstance(item, PermissionRequest):
                    pid = str(uuid.uuid4())
                    evt = threading.Event()
                    _PENDING_PERMISSIONS[pid] = (item, evt)
                    payload = {
                        "type": "permission",
                        "id": pid,
                        "description": item.description,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    evt.wait(timeout=300)
                    _PENDING_PERMISSIONS.pop(pid, None)
                    continue
                else:
                    continue

                yield f"data: {json.dumps(payload)}\n\n"

            if exc_holder[0]:
                err = exc_holder[0]
                yield f'data: {json.dumps({"type":"error","message":f"{type(err).__name__}: {err}"})}\n\n'

            yield 'data: {"type":"done"}\n\n'

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
        )

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--model", default="", help="Override model from config.json")
    ap.add_argument("--open", action="store_true", help="open browser on start")
    args = ap.parse_args()
    if args.model:
        CONFIG["model"] = args.model
    app = create_app()
    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{args.host}:{args.port}/")).start()
    print(f"[webchat] model={CONFIG.get('model')} -> http://{args.host}:{args.port}/")
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
