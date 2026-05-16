"""
Multi-provider support for Dulus.

Supported providers:
  anthropic  — Claude (claude-opus-4-6, claude-sonnet-4-6, ...)
  openai     — GPT (gpt-4o, o3-mini, ...)
  gemini     — Google Gemini (gemini-2.0-flash, gemini-1.5-pro, ...)
  kimi       — Moonshot AI (kimi-k2.5, moonshot-v1-8k/32k/128k)
  kimi-code  — Kimi Code (kimi-for-coding, membership API from kimi.com/code)
  qwen       — Alibaba DashScope (qwen-max, qwen-plus, ...)
  zhipu      — Zhipu GLM (glm-4, glm-4-plus, ...)
  deepseek   — DeepSeek (deepseek-chat, deepseek-reasoner, ...)
  minimax    — MiniMax (MiniMax-Text-01, abab6.5s-chat, ...)
  ollama     — Local Ollama (llama3.3, qwen2.5-coder, ...)
  lmstudio   — Local LM Studio (any loaded model)
  custom     — Any OpenAI-compatible endpoint

Model string formats:
  "claude-opus-4-6"          auto-detected → anthropic
  "gpt-4o"                   auto-detected → openai
  "ollama/qwen2.5-coder"     explicit provider prefix
  "custom/my-model"          uses CUSTOM_BASE_URL from config
"""
from __future__ import annotations
import json
import urllib.request
import urllib.parse
import requests
import re
import time
import random
import functools
import subprocess
import platform
from typing import Generator, Any, Callable


# ── Provider resilience: retry with exponential backoff + jitter ─────────

class _ProviderRetry:
    """Lightweight retry wrapper for provider streaming calls.

    Retries on: timeout, connection errors, 429 (rate limit), 5xx.
    Does NOT retry on: 4xx (client errors), auth failures.
    """
    MAX_RETRIES: int = 3
    BASE_DELAY: float = 1.0
    MAX_DELAY: float = 30.0

    @classmethod
    def is_retryable(cls, exc: Exception) -> bool:
        """Return True if the exception is worth retrying."""
        msg = str(exc).lower()
        # Rate limit / server overload
        if "429" in msg or "rate limit" in msg or "too many requests" in msg:
            return True
        # Server errors
        if "500" in msg or "502" in msg or "503" in msg or "504" in msg:
            return True
        # Timeouts / connection issues
        if "timeout" in msg or "connection" in msg or "timed out" in msg:
            return True
        if "chunked encoding" in msg or "broken pipe" in msg:
            return True
        return False

    @classmethod
    def sleep_for_attempt(cls, attempt: int) -> float:
        """Exponential backoff with full jitter."""
        exp = cls.BASE_DELAY * (2 ** attempt)
        jitter = random.random() * exp
        return min(jitter, cls.MAX_DELAY)

    @classmethod
    def wrap_generator(cls, fn: Callable, *args, **kwargs) -> Generator:
        """Wrap a generator function with retry logic.

        Yields through the generator; if it raises a retryable exception,
        waits and retries up to MAX_RETRIES times.
        """
        last_exc: Exception | None = None
        for attempt in range(cls.MAX_RETRIES + 1):
            try:
                yield from fn(*args, **kwargs)
                return
            except Exception as exc:
                last_exc = exc
                if attempt >= cls.MAX_RETRIES or not cls.is_retryable(exc):
                    raise
                delay = cls.sleep_for_attempt(attempt)
                time.sleep(delay)
        # Should never reach here, but just in case
        if last_exc:
            raise last_exc


_ANTHROPIC_PARAM_RE = re.compile(
    r'<parameter\s+name="(?P<key>[^"]+)"\s*>(?P<val>.*?)</parameter>',
    re.DOTALL,
)
_TOOLCALL_NAME_RE = re.compile(r'"name"\s*:\s*"(?P<name>[^"]+)"')


def _parse_tool_call_payload(payload: str):
    """Best-effort extraction of (tool_name, input_dict) from the body of a
    `<tool_call>...</tool_call>` block.

    Why this exists: models sometimes leak Anthropic's `<function_calls>` /
    `<parameter>` syntax INSIDE our `<tool_call>` block, which corrupts the
    JSON. Without a recovery path the call is silently dropped by
    `try: json.loads(...); except: pass` and the user sees their request
    vanish into thin air. We try three strategies, easiest first.

    Returns (name, input_dict) or None.
    """
    payload = (payload or "").strip()
    if not payload:
        return None

    # Strategy 1 — clean JSON ("name" + "input"). Vast majority of calls.
    try:
        data = json.loads(payload)
        if isinstance(data, dict):
            name = data.get("name") or (
                data.get("function", {}).get("name")
                if isinstance(data.get("function"), dict) else None
            )
            if name:
                inp = data.get("input") or (
                    data.get("function", {}).get("arguments")
                    if isinstance(data.get("function"), dict) else None
                ) or {}
                if isinstance(inp, str):
                    try:
                        inp = json.loads(inp)
                    except Exception:
                        inp = {}
                return name, (inp if isinstance(inp, dict) else {})
    except Exception:
        pass

    # Strategy 2 — Anthropic-syntax leak: `{"name": "X">  <parameter ...>` etc.
    # Pull the tool name from the leading JSON-ish prefix and the params from
    # all `<parameter name="K">V</parameter>` blocks. Coerce numeric/bool
    # strings into proper JSON types where obvious.
    if "<parameter" in payload and "</parameter>" in payload:
        m = _TOOLCALL_NAME_RE.search(payload)
        if m:
            name = m.group("name")
            inp: dict = {}
            for pm in _ANTHROPIC_PARAM_RE.finditer(payload):
                key = pm.group("key")
                val = pm.group("val")
                # Coerce common scalar forms; leave everything else as string.
                sval = val.strip()
                if sval.lower() == "true":
                    inp[key] = True
                elif sval.lower() == "false":
                    inp[key] = False
                elif sval.lower() == "null":
                    inp[key] = None
                else:
                    try:
                        if sval.isdigit() or (sval.startswith("-") and sval[1:].isdigit()):
                            inp[key] = int(sval)
                        elif sval.replace(".", "", 1).lstrip("-").isdigit():
                            inp[key] = float(sval)
                        elif sval.startswith("[") or sval.startswith("{"):
                            inp[key] = json.loads(sval)
                        else:
                            inp[key] = val
                    except Exception:
                        inp[key] = val
            if inp:
                return name, inp

    # Strategy 3 — last-ditch: maybe the JSON is just unterminated. Try to
    # find balanced braces from the first `{` and parse that.
    first = payload.find("{")
    if first != -1:
        depth = 0
        end = -1
        in_str = False
        esc = False
        for i in range(first, len(payload)):
            c = payload[i]
            if esc:
                esc = False; continue
            if c == "\\":
                esc = True; continue
            if c == '"':
                in_str = not in_str; continue
            if in_str:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end != -1:
            try:
                data = json.loads(payload[first:end])
                if isinstance(data, dict):
                    name = data.get("name")
                    if name:
                        return name, (data.get("input") or {})
            except Exception:
                pass

    return None


class WebToolParser:
    """Shared parser for prompt-based tool calls in XML format.
    Also supports auto-wrapping raw JSON tool calls if auto_wrap_json=True.
    """
    def __init__(self, auto_wrap_json: bool = False):
        self._in_call = False
        self._call_buf = ""
        self._raw_buf = ""
        self._auto_wrap_json = auto_wrap_json
        self.tool_calls = []

    def parse_chunk(self, chunk: str) -> str:
        """Parse chunk, return display text and accumulate tool calls."""
        if not chunk: return ""
        self._raw_buf += chunk
        display = ""

        while True:
            if not self._in_call:
                # Look for start tag
                pos = self._raw_buf.find("<tool_call>")
                if pos == -1:
                    # No start tag. Check for partial start tag at the very end
                    last_lt = self._raw_buf.rfind("<")
                    if last_lt != -1 and "<tool_call>".startswith(self._raw_buf[last_lt:]):
                        display += self._raw_buf[:last_lt]
                        self._raw_buf = self._raw_buf[last_lt:]
                    else:
                        display += self._raw_buf
                        self._raw_buf = ""
                    break
                else:
                    # Found start tag: everything before is text
                    display += self._raw_buf[:pos]
                    self._in_call = True
                    self._raw_buf = self._raw_buf[pos + len("<tool_call>"):]
                    continue # Look for end tag in the rest of buffer
            else:
                # Inside a tag: look for end tag
                pos = self._raw_buf.find("</tool_call>")
                if pos == -1:
                    # End tag not found yet. BUT: if we already buffered a full
                    # Anthropic-style `<function_calls>` block leak (i.e. JSON
                    # opener + at least one `</parameter>`), the model is never
                    # going to close with `</tool_call>` — recover now instead
                    # of waiting forever and dumping as text on flush().
                    self._call_buf += self._raw_buf
                    self._raw_buf = ""
                    if "</parameter>" in self._call_buf and "<parameter" in self._call_buf:
                        parsed = _parse_tool_call_payload(self._call_buf.strip())
                        if parsed:
                            name, inp = parsed
                            self.tool_calls.append({
                                "id": f"call_pt_{len(self.tool_calls)}",
                                "name": name,
                                "input": inp,
                            })
                            self._call_buf = ""
                            self._in_call = False
                            continue
                    break
                else:
                    # Found end tag: extract JSON and continue
                    self._call_buf += self._raw_buf[:pos]
                    self._raw_buf = self._raw_buf[pos + len("</tool_call>"):]
                    parsed = _parse_tool_call_payload(self._call_buf.strip())
                    if parsed:
                        name, inp = parsed
                        self.tool_calls.append({
                            "id": f"call_pt_{len(self.tool_calls)}",
                            "name": name,
                            "input": inp,
                        })
                    self._call_buf = ""
                    self._in_call = False
                    continue # Look for more tags in the rest of buffer

        # 2. Raw JSON Fallback (only if enabled and NOT inside a tag)
        if self._auto_wrap_json and not self._in_call and "{" in display:
            search_pos = 0
            while True:
                start = display.find("{", search_pos)
                if start == -1: break
                
                snippet = display[start:start+500]
                if '"name"' in snippet and ('"input"' in snippet or '"arguments"' in snippet):
                    brace_count = 0
                    end_pos = -1
                    for j in range(start, len(display)):
                        if display[j] == "{": brace_count += 1
                        elif display[j] == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = j + 1
                                break
                    if end_pos != -1:
                        try:
                            json_str = display[start:end_pos]
                            data = json.loads(json_str)
                            name = data.get("name") or (data.get("function", {}).get("name") if isinstance(data.get("function"), dict) else None)
                            if name:
                                self.tool_calls.append({
                                    "id": f"call_pt_{len(self.tool_calls)}",
                                    "name": name,
                                    "input": data.get("input") or data.get("function", {}).get("arguments") or {},
                                })
                                display = display[:start] + display[end_pos:]
                                search_pos = start
                                continue
                        except: pass
                search_pos = start + 1
        
        return display

    def flush(self) -> str:
        """Return any remaining text in the buffer."""
        res = self._raw_buf
        self._raw_buf = ""
        # If we were in a call but it never ended, we should probably output the partial call?
        # But for now, just the raw text.
        if self._in_call:
            res = "<tool_call>" + self._call_buf + res
            self._call_buf = ""
            self._in_call = False
        return res


def _format_web_tool_manifest(tool_schemas: list, config: dict, messages: list) -> str:
    """Format tools as a prompt hint for web models.
    First turn → full manifest with strong instructions + tool list.
    Continuation turns → short format reminder (always injected, cheap).
    Disable entirely with config["no_tools"] = True.
    """
    if not tool_schemas or config.get("no_tools"):
        return ""

    is_first_turn = len([m for m in messages if m.get("role") == "user"]) <= 1

    # Web providers (claude.ai, qwen.ai, etc.) keep the conversation server-side,
    # so the turn-1 manifest is still in the model's context on every later turn.
    # Re-injecting wastes tokens. Skip unless the user explicitly opted in.
    if not is_first_turn and not config.get("always_inject_tools"):
        return ""

    manifest = [
        "\n\n[TOOL USE — READ CAREFULLY]",
        "You are running inside an agent harness that can EXECUTE tools for you.",
        "When you need information, file contents, or to run an action — DO NOT describe what you would do; CALL the tool.",
        "",
        "EXACT format (any deviation = the call is ignored):",
        '  <tool_call>{"name": "ToolName", "input": {"key": "value"}}</tool_call>',
        "",
        "Rules:",
        "1. The <tool_call> tag MUST be on its own line, with valid JSON inside.",
        "2. Use ONLY tool names from the list below. Do NOT invent tools (no `SleepTimer`, no `WaitFor`, no fake names — `Reminder` is the real one if you need a delayed wake-up).",
        "3. To call multiple tools, emit multiple <tool_call> blocks in the SAME response — do not wait for results between them.",
        "4. After tool results come back, you may call more tools or give a final answer.",
        "5. If no tool is needed, just answer normally — no tool_call tag.",
        "",
        "Example (correct):",
        '  <tool_call>{"name": "Read", "input": {"file_path": "/tmp/foo.txt"}}</tool_call>',
        "",
        "Available Tools:",
    ]
    for s in tool_schemas:
        manifest.append(f"- {s['name']}: {s.get('description', '')}")
        manifest.append(f"  Inputs: {json.dumps(s.get('parameters', {}).get('properties', {}), separators=(',', ':'))}")

    return "\n".join(manifest)


def _consolidate_web_history(messages: list, manifest: str = "") -> str:
    """Consolidate history since last assistant turn into one prompt string.
    This ensures tool results and system notifications are correctly perceived
    by web-based models that take a single prompt string.
    """
    if not messages:
        return manifest
    
    # Find last assistant message that actually has text or was saved
    last_ast = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            last_ast = i
            break
    
    parts = []
    relevant = messages[last_ast + 1:] if last_ast != -1 else messages
    
    for m in relevant:
        role = m.get("role", "user")
        content = m.get("content", "")
        
        # We only skip empty content if it's NOT a tool result.
        # Tool results must be sent even if empty so the model knows they ran.
        if role != "tool" and not content:
            continue
            
        header = f"--- [{role.upper()}] ---"
        if role == "tool":
            header = f"--- [Tool Result: {m.get('name', 'Unknown')}] ---"
            if not content:
                content = "(No output / Empty result)"
        
        parts.append(f"{header}\n{content}")
    
    prompt = "\n\n".join(parts).strip()
    if manifest:
        prompt = manifest + "\n\n" + prompt
        
    return prompt.strip()

# ── Provider registry ──────────────────────────────────────────────────────

PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "type":       "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "context_limit": 200000,
        "models": [
            "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
            "claude-opus-4-5", "claude-sonnet-4-5",
            "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
        ],
    },
    "openai": {
        "type":       "openai",
        "api_key_env": "OPENAI_API_KEY",
        "base_url":   "https://api.openai.com/v1",
        "context_limit": 128000,
        "max_completion_tokens": 16384,  # safe cap across gpt-4o/gpt-4.1 family
        "models": [
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4.1", "gpt-4.1-mini",
            "o3-mini", "o1", "o1-mini",
        ],
    },
    "gemini": {
        "type":       "openai",
        "api_key_env": "GEMINI_API_KEY",
        "base_url":   "https://generativelanguage.googleapis.com/v1beta/openai/",
        "context_limit": 1000000,
        "max_completion_tokens": 65536,  # Gemini 2.x supports up to 65k output tokens
        "models": [
            "gemini-2.5-pro-preview-03-25",
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
            "gemini-1.5-pro", "gemini-1.5-flash",
        ],
    },
    "gemini-web": {
        "type":       "gemini-web",
        "context_limit": 1000000,
        "models": [
            "gemini-latest", "gemini-flash", "gemini-pro",
        ],
    },
    "kimi": {
        "type":       "openai",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url":   "https://api.moonshot.ai/v1",
        "context_limit": 250000,
        "models": [
            "kimi-k2.5", "kimi-latest",
            "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k",
        ],
    },
    "kimi-code": {
        "type":       "openai",
        "api_key_env": "KIMI_CODE_API_KEY",
        "base_url":   "https://api.kimi.com/coding/v1",
        "context_limit": 256000,
        "models": [
            "kimi-for-coding", "kimi-k2.6", "kimi-k2.5", "kimi-latest",
        ],
    },
    "kimi-code2": {
        "type":       "openai",
        "api_key_env": "KIMI_CODE2_API_KEY",
        "base_url":   "https://api.kimi.com/coding/v1",
        "context_limit": 256000,
        "models": [
            "kimi-for-coding", "kimi-k2.6", "kimi-k2.5", "kimi-latest",
        ],
    },
    "kimi-code3": {
        "type":       "openai",
        "api_key_env": "KIMI_CODE3_API_KEY",
        "base_url":   "https://api.kimi.com/coding/v1",
        "context_limit": 256000,
        "models": [
            "kimi-for-coding", "kimi-k2.6", "kimi-k2.5", "kimi-latest",
        ],
    },
    "moonshot": {
        "type":       "openai",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url":   "https://api.moonshot.ai/v1",
        "context_limit": 250000,
        "models": [
            "kimi-k2.5", "kimi-latest",
            "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k",
        ],
    },
    "qwen": {
        "type":       "openai",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url":   "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "context_limit": 1000000,
        "models": [
            "qwen-max", "qwen-plus", "qwen-turbo", "qwen-long",
            "qwen2.5-72b-instruct", "qwen2.5-coder-32b-instruct",
            "qwq-32b",
        ],
    },
    "zhipu": {
        "type":       "openai",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url":   "https://api.z.ai/api/coding/paas/v4",
        "context_limit": 128000,
        "models": [
            "glm-4-plus", "glm-4", "glm-4-flash", "glm-4-air",
            "glm-z1-flash", "GLM-4.7", "GLM-4.5-AIR",
        ],
    },
    "deepseek": {
        "type":       "openai",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url":   "https://api.deepseek.com/v1",
        "context_limit": 64000,
        "models": [
            "deepseek-chat", "deepseek-coder", "deepseek-reasoner",
            "deepseek-v3", "deepseek-r1",
        ],
    },
    # LiteLLM unified gateway. ONE provider entry that fans out to 100+
    # underlying backends via prefixed model strings:
    #     openrouter/anthropic/claude-3-5-sonnet
    #     groq/llama-3.3-70b-versatile
    #     together_ai/meta-llama/Llama-3-70b-chat-hf
    #     bedrock/anthropic.claude-3-sonnet-20240229-v1:0
    #     vertex_ai/gemini-1.5-pro
    #     cohere/command-r-plus
    #     perplexity/sonar-large-online
    #     xai/grok-2-latest
    #     mistral/mistral-large-latest
    #     fireworks_ai/...   anyscale/...   replicate/...   azure/...
    # LiteLLM auto-reads per-backend env vars (OPENROUTER_API_KEY,
    # GROQ_API_KEY, TOGETHER_API_KEY, …). User picks the model string in
    # the welcome wizard; the right env var must exist for that backend.
    "litellm": {
        "type":       "litellm",
        "api_key_env": None,   # backend-specific; LiteLLM resolves the right one
        "context_limit": 200000,   # safe default; LiteLLM has accurate per-model values
        "models": [
            # A curated, useful slice — LiteLLM supports ~1000 model strings.
            # The user can type any of them; these are just suggestions for /model picker.
            "openrouter/anthropic/claude-3-5-sonnet",
            "openrouter/openai/gpt-4o",
            "openrouter/google/gemini-pro-1.5",
            "openrouter/meta-llama/llama-3.3-70b-instruct",
            "openrouter/x-ai/grok-2-1212",
            "groq/llama-3.3-70b-versatile",
            "groq/mixtral-8x7b-32768",
            "together_ai/meta-llama/Llama-3-70b-chat-hf",
            "perplexity/sonar-large-online",
            "cohere/command-r-plus",
            "mistral/mistral-large-latest",
            "fireworks_ai/accounts/fireworks/models/llama-v3p3-70b-instruct",
        ],
    },
    "minimax": {
        "type":       "openai",
        "api_key_env": "MINIMAX_API_KEY",
        "base_url":   "https://api.minimaxi.chat/v1",
        "context_limit": 1000000,
        "models": [
            "MiniMax-Text-01", "MiniMax-VL-01",
            "abab6.5s-chat", "abab6.5-chat",
            "abab5.5s-chat", "abab5.5-chat",
        ],
    },
    "ollama": {
        "type":       "ollama",
        "api_key_env": None,
        "base_url":   "http://localhost:11434",
        "api_key":    "ollama",
        "context_limit": 250000,
        "models": [
            "llama3.3", "llama3.2", "phi4", "mistral", "mixtral",
            "qwen2.5-coder", "deepseek-r1", "gemma3",
        ],
    },
    "lmstudio": {
        "type":       "openai",
        "api_key_env": None,
        "base_url":   "http://localhost:1234/v1",
        "api_key":    "lm-studio",
        "context_limit": 128000,
        "models": [],   # dynamic, depends on loaded model
    },
    "custom22": {
        "type":       "openai",
        "api_key_env": "MIMO_API_KEY",
        "base_url":   "https://api.xiaomimimo.com/v1",   # read from config["custom_base_url"]
        "context_limit": 128000,
        "models": ["MiMo-V2-Pro"],
    },
    "claude-web": {
        "type":       "claude_web",
        "api_key_env": None,
        "context_limit": 200000,
        "models": [
            "claude-sonnet-4-6", "claude-haiku-4-5",
            "claude-opus-4-6", "claude-opus-4-5",
        ],
    },
    "claude-code": {
        "type":        "claude_code",
        "api_key_env": None,
        "context_limit": 200000,
        "models": [
            "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6",
        ],
    },
    "kimi-web": {
        "type":       "kimi_web",
        "api_key_env": None,
        "context_limit": 128000,
        "models": [
            "kimi-latest", "kimi-v1",
        ],
    },
    "deepseek-web": {
        "type":       "deepseek_web",
        "api_key_env": None,
        "context_limit": 64000,
        "models": [
            "deepseek-v3", "deepseek-r1", "deepseek-latest",
        ],
    },
    "qwen-web": {
        "type":       "qwen_web",
        "api_key_env": None,
        "context_limit": 1_000_000,
        "models": [
            "qwen3.6-plus", "qwen-max", "qwen-turbo", "qwen-plus",
        ],
    },
    "nvidia-web": {
        "type":       "openai",
        "api_key_env": "NVIDIA_API_KEY",
        "base_url":   "https://integrate.api.nvidia.com/v1",
        "context_limit": 128000,
        "max_completion_tokens": 16384,
        "models": [
            "deepseek-ai/deepseek-v4-flash",
            "deepseek-ai/deepseek-r1",
            "meta/llama-3.3-70b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "mistralai/mixtral-8x22b-instruct-v0.1",
            "microsoft/phi-3-medium-128k-instruct",
            "stepfun-ai/step-3.5-flash",
            "qwen/qwen2.5-72b-instruct",
            "google/gemma-2-27b-it",
        ],
    },
    "gcloud": {
        "type":       "gcloud",
        "api_key_env": None,
        "context_limit": 1000000,
        "max_completion_tokens": 65536,
        "models": [
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
        ],
    },
}

# Cost per million tokens (approximate, fallback to 0 for unknown)
COSTS = {
    "claude-opus-4-6":          (15.0, 75.0),
    "claude-sonnet-4-6":        (3.0,  15.0),
    "claude-haiku-4-5-20251001": (0.8,  4.0),
    "gpt-4o":                   (2.5,  10.0),
    "gpt-4o-mini":              (0.15,  0.6),
    "o3-mini":                  (1.1,   4.4),
    "gemini-2.0-flash":         (0.075, 0.3),
    "gemini-1.5-pro":           (1.25,  5.0),
    "gemini-2.5-pro-preview-03-25": (1.25, 10.0),
    "moonshot-v1-8k":           (1.0,   3.0),
    "moonshot-v1-32k":          (2.4,   7.0),
    "moonshot-v1-128k":         (8.0,  24.0),
    "qwen-max":                 (2.4,   9.6),
    "qwen-plus":                (0.4,   1.2),
    "deepseek-chat":            (0.27,  1.1),
    "deepseek-reasoner":        (0.55,  2.19),
    "glm-4-plus":               (0.7,   0.7),
    "GLM-4.7":                  (0.7,   0.7),
    "GLM-4.5-AIR":              (0.5,   0.5),
    "MiniMax-Text-01":          (0.7,   2.1),
    "abab6.5s-chat":            (0.1,   0.1),
    "abab6.5-chat":             (0.5,   0.5),
    "gcloud/gemini-2.5-pro":    (1.25, 10.0),
    "gcloud/gemini-2.0-flash":  (0.075, 0.3),
    "gcloud/gemini-1.5-pro":    (1.25, 5.0),
}

# Auto-detection: prefix → provider name
_PREFIXES = [
    ("claude-",       "anthropic"),
    ("gpt-",          "openai"),
    ("o1",            "openai"),
    ("o3",            "openai"),
    ("gemini-",       "gemini"),
    ("kimi-code/",    "kimi-code"),
    ("kimi-code2/",   "kimi-code2"),
    ("kimi-code3/",   "kimi-code3"),
    ("kimi-for-coding", "kimi-code"),
    ("kimi",          "kimi"),  # matches 'kimi-' and 'kimi'
    ("moonshot-",     "kimi"),
    ("moonshot",       "kimi"), 
    ("qwen",          "qwen"),  # qwen-max, qwen2.5-...
    ("qwq-",          "qwen"),
    ("glm-",          "zhipu"),
    ("GLM-",          "zhipu"),
    ("deepseek-",     "deepseek"),
    ("minimax-",      "minimax"),
    ("MiniMax-",      "minimax"),
    ("abab",          "minimax"),
    ("llama",         "ollama"),
    ("mistral",       "ollama"),
    ("phi",           "ollama"),
    ("gemma",         "ollama"),
    ("gcloud/",       "gcloud"),
    ("gcloud-",       "gcloud"),
]

# Models available under claude-web/ prefix
_CLAUDE_WEB_MODELS = {
    "claude-sonnet-4-6", "claude-haiku-4-5",
    "claude-opus-4-6", "claude-opus-4-5",
    "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
}


def detect_provider(model: str) -> str:
    """Return provider name for a model string.
    Supports 'provider/model' explicit format, or auto-detect by prefix."""
    if "/" in model:
        p = model.split("/", 1)[0]
        if p in PROVIDERS:
            return p
    for prefix, pname in _PREFIXES:
        if model.lower().startswith(prefix):
            return pname
    return "openai"   # fallback


def _claude_web_cookies_path(config: dict) -> str:
    """Return path to claude.ai cookies JSON file."""
    import os, pathlib
    p = config.get("claude_web_cookies") or str(
        pathlib.Path.home() / ".dulus" / "claude_cookies.json"
    )
    return p


def _kimi_web_auth_path(config: dict) -> str:
    """Return path to kimi.com consumer auth JSON file."""
    import os, pathlib
    p = config.get("kimi_web_auth_path") or str(
        pathlib.Path.home() / ".dulus" / "kimi_consumer.json"
    )
    return p


def _kimi_web_list_chats(auth_data: dict, page_size: int = 50,
                         page_token: str = "", query: str = "") -> dict:
    """List recent chats from kimi.com using harvested cookies/headers.

    Reuses the auth blob saved by /harvest (cookies + x-msh-* + Bearer).
    Endpoint is kimi.chat.v1.ChatService/ListChats (NOT the gateway /Chat one).
    Returns the parsed JSON from the API or raises on HTTP error.
    """
    import requests as _req

    s = _req.Session()
    for c in auth_data.get("cookies", []):
        s.cookies.set(c["name"], c["value"],
                      domain=c.get("domain", ".kimi.com"),
                      path=c.get("path", "/"))

    # Reuse harvested headers, but override content-type for plain JSON
    # (the harvested one is connect+json for the streaming /Chat endpoint).
    base = auth_data.get("headers", {})
    headers = {k: v for k, v in base.items() if k.lower() not in ("content-type",)}
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "*/*"
    headers["Origin"] = "https://www.kimi.com"
    headers.setdefault("Referer", "https://www.kimi.com/chat/history")

    body = {
        "project_id": "",
        "page_size":  page_size,
        "page_token": page_token,
        "query":      query,
    }
    url = "https://www.kimi.com/apiv2/kimi.chat.v1.ChatService/ListChats"
    resp = s.post(url, headers=headers, json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _gemini_web_auth_path(config: dict) -> str:
    """Return path to gemini.google.com consumer auth JSON file."""
    import os, pathlib
    p = config.get("gemini_web_auth_path") or str(
        pathlib.Path.home() / ".dulus" / "gemini_web.json"
    )
    return p


def _deepseek_web_auth_path(config: dict) -> str:
    """Return path to chat.deepseek.com consumer auth JSON file."""
    import pathlib
    p = config.get("deepseek_web_auth_path") or str(
        pathlib.Path.home() / ".dulus" / "deepseek_web.json"
    )
    return p


def _qwen_web_auth_path(config: dict) -> str:
    """Return path to chat.qwen.ai consumer auth JSON file."""
    import pathlib
    p = config.get("qwen_web_auth_path") or str(
        pathlib.Path.home() / ".dulus" / "qwen_web.json"
    )
    return p


def _claude_web_org_id(cookies_data: dict, config: dict) -> str:
    """Extract org ID: try cookies → try API → fallback from config → hardcoded."""
    # 1. Cached in config
    if config.get("claude_web_org_id"):
        return config["claude_web_org_id"]

    # 2. Scan cookies for lastActiveOrg
    for c in cookies_data.get("cookies", []):
        name = c.get("name", "")
        val  = c.get("value", "")
        if name == "lastActiveOrg" and val:
            config["claude_web_org_id"] = val
            return val

    # 3. Try /api/organizations with harvested cookies
    org_id = _claude_web_fetch_org_id(cookies_data)
    if org_id:
        config["claude_web_org_id"] = org_id
        return org_id

    # 4. Fallback from config or hardcoded
    return config.get("claude_web_org_id", "022b6d58-7355-4e97-bfab-c4fc047674bb")


def _claude_web_headers(cookies_data: dict, referer: str = "https://claude.ai/new") -> dict:
    """Build HTTP headers for claude.ai requests."""
    cookie_str = "; ".join(
        f"{c['name']}={c['value']}"
        for c in cookies_data.get("cookies", [])
        if "claude.ai" in c.get("domain", "") or "anthropic.com" in c.get("domain", "")
    )
    ua = cookies_data.get(
        "user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    h = {
        "Content-Type":                "application/json",
        "Accept":                      "text/event-stream",
        "Accept-Language":             "en-US,en;q=0.9",
        "anthropic-client-platform":   "web_claude_ai",
        "Origin":                      "https://claude.ai",
        "Referer":                     referer,
        "User-Agent":                  ua,
        "Cookie":                      cookie_str,
    }
    # Merge harvested request headers (skip Cookie/Host/Content-Length)
    for k, v in cookies_data.get("headers", {}).items():
        if k.lower() not in ("cookie", "host", "content-length", "content-type"):
            h[k] = v
    return h


def _claude_web_fetch_org_id(cookies_data: dict) -> str | None:
    """Call /api/organizations using requests.Session with harvested cookies."""
    try:
        import requests as _req
        s = _req.Session()
        for c in cookies_data.get("cookies", []):
            s.cookies.set(c["name"], c["value"],
                          domain=c.get("domain", "claude.ai"),
                          path=c.get("path", "/"))
        ua = cookies_data.get("user_agent", "Mozilla/5.0")
        s.headers.update({
            "User-Agent": ua,
            "Accept": "application/json",
            "anthropic-client-platform": "web_claude_ai",
            "Origin": "https://claude.ai",
            "Referer": "https://claude.ai/new",
        })
        resp = s.get("https://claude.ai/api/organizations", timeout=10)
        if resp.status_code == 200:
            orgs = resp.json()
            if isinstance(orgs, list) and orgs:
                return orgs[0].get("uuid") or orgs[0].get("id")
            if isinstance(orgs, dict):
                return orgs.get("uuid") or orgs.get("id")
    except Exception:
        pass
    return None


def _claude_web_create_conversation(cookies_data: dict, org_id: str) -> str | None:
    """Create a new claude.ai chat conversation using requests.Session."""
    from datetime import datetime as _dt
    try:
        import requests as _req
        s = _req.Session()
        for c in cookies_data.get("cookies", []):
            s.cookies.set(c["name"], c["value"],
                          domain=c.get("domain", "claude.ai"),
                          path=c.get("path", "/"))
        ua = cookies_data.get("user_agent", "Mozilla/5.0")
        s.headers.update({
            "User-Agent": ua,
            "Accept": "application/json",
            "anthropic-client-platform": "web_claude_ai",
            "Origin": "https://claude.ai",
            "Referer": "https://claude.ai/new",
        })
        url = f"https://claude.ai/api/organizations/{org_id}/chat_conversations"
        resp = s.post(url, json={"name": f"Dulus — {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}"}, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("uuid")
    except Exception:
        pass
    return None


def stream_claude_web(
    cookies_file: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from claude.ai web using harvested browser cookies.

    Tool calling is prompt-based: tool manifest injected into the user
    message; <tool_call>...</tool_call> tags parsed from the response.
    Conversation context is maintained server-side via conversation_id.
    """
    import pathlib

    # ── Load cookies ─────────────────────────────────────────────────────────
    cpath = pathlib.Path(cookies_file)
    if not cpath.exists():
        msg = f"[claude-web] Cookie file not found: {cookies_file}  →  run /harvest"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    with open(cpath, encoding="utf-8") as f:
        cookies_data = json.load(f)

    # ── Org ID ───────────────────────────────────────────────────────────────
    org_id = _claude_web_org_id(cookies_data, config)
    if not org_id:
        msg = "[claude-web] Could not get org ID — cookies may be expired. Run /harvest."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    # ── Conversation ID (persists for the Dulus session) ───────────────────
    conv_id = config.get("claude_web_conv_id")
    if not conv_id:
        # Use existing conv_id from harvest first (like CODE5.PY)
        conv_ids = cookies_data.get("conversation_ids", [])
        if conv_ids:
            conv_id = conv_ids[0]
        else:
            conv_id = _claude_web_create_conversation(cookies_data, org_id)
        if conv_id:
            config["claude_web_conv_id"] = conv_id
        else:
            msg = "[claude-web] Could not get conversation ID. Run /harvest."
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

    # ── Build prompt from history ──────────────────────────────────────────
    manifest = _format_web_tool_manifest(tool_schemas, config, messages)
    prompt = _consolidate_web_history(messages, manifest)

    # ── HTTP request ─────────────────────────────────────────────────────────
    url = (
        f"https://claude.ai/api/organizations/{org_id}"
        f"/chat_conversations/{conv_id}/completion"
    )
    payload = {
        "prompt":          prompt,
        "timezone":        config.get("timezone", "America/Santo_Domingo"),
        "model":           model,
        "attachments":     [],
        "files":           [],
        "rendering_mode":  "messages",
    }
    # ── Build requests.Session with cookies (same as CODE5.PY) ─────────────
    import requests as _req
    session = _req.Session()
    for c in cookies_data.get("cookies", []):
        session.cookies.set(c["name"], c["value"],
                            domain=c.get("domain", "claude.ai"),
                            path=c.get("path", "/"))
    ua = cookies_data.get("user_agent", "Mozilla/5.0")
    session.headers.update({
        "User-Agent":                  ua,
        "Accept":                      "text/event-stream",
        "Accept-Language":             "en-US,en;q=0.9",
        "anthropic-client-platform":   "web_claude_ai",
        "Origin":                      "https://claude.ai",
        "Referer":                     f"https://claude.ai/chat/{conv_id}",
    })
    # Merge any harvested headers
    for k, v in cookies_data.get("headers", {}).items():
        if k.lower() not in ("cookie", "host", "content-length", "content-type"):
            session.headers[k] = v

    # Unified parser for <tool_call> tags
    parser = WebToolParser()

    # ── Stream ───────────────────────────────────────────────────────────────
    text = ""
    _debug_events: list = []
    try:
        resp_cm = session.post(url, json=payload, stream=True, timeout=120)
        if resp_cm.status_code != 200:
            if resp_cm.status_code in (401, 403):
                msg = f"[claude-web] Auth error {resp_cm.status_code} — cookies expired. Run /harvest."
            elif resp_cm.status_code == 404:
                config.pop("claude_web_conv_id", None)
                msg = "[claude-web] Conversation not found (404). New one will be created next message."
            else:
                msg = f"[claude-web] HTTP {resp_cm.status_code}: {resp_cm.text[:300]}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return
    except Exception as e:
        msg = f"[claude-web] Connection error: {e}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    for raw_line in resp_cm.iter_lines():
        if not raw_line:
            continue
        line_str = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        line_str = line_str.strip()
        if not line_str or not line_str.startswith("data: "):
            continue
        data_str = line_str[6:]
        if data_str == "[DONE]":
            break
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        # OLD format: {"completion": "delta", "stop_reason": null}
        # NEW format: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "..."}}
        completion = data.get("completion", "")
        if not completion:
            evt_type = data.get("type", "")
            if evt_type == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    completion = delta.get("text", "")

        if completion:
            display = parser.parse_chunk(completion)
            if display:
                text += display
                yield TextChunk(display)

        # Stop only when stop_reason is explicitly set
        stop_reason = data.get("stop_reason")
        if stop_reason and stop_reason != "null":
            break

    remaining = parser.flush()
    if remaining:
        text += remaining
        yield TextChunk(remaining)

    yield AssistantTurn(text, parser.tool_calls, 0, 0)


def stream_claude_code(
    cookies_file: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from claude.ai/code remote-control session using harvested cookies.

    Endpoint: POST https://claude.ai/v1/sessions/{session_id}/events
    Payload:  {"events": [{"type":"user","uuid":"...","session_id":"...","parent_tool_use_id":null,"message":{"role":"user","content":"..."}}]}
    Auth:     same claude_cookies.json as claude-web + anthropic-beta: ccr-byoc-2025-07-29
    """
    import pathlib
    import uuid as _uuid
    import requests as _req

    # ── Load cookies ──────────────────────────────────────────────────────────
    cpath = pathlib.Path(cookies_file)
    if not cpath.exists():
        msg = f"[claude-code] Cookie file not found: {cookies_file}  →  run /harvest"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    with open(cpath, encoding="utf-8") as f:
        cookies_data = json.load(f)

    # ── Session ID ────────────────────────────────────────────────────────────
    session_id = config.get("claude_code_session_id", "")
    if not session_id:
        msg = (
            "[claude-code] No session ID set.\n"
            "Run `claude remote-control` in a terminal, then:\n"
            "  /config claude_code_session_id=session_01VP9K..."
        )
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    # Accept full URL or bare session ID
    if "/" in session_id:
        session_id = session_id.rstrip("/").split("/")[-1]

    # ── Org ID + activity session from cookies data ───────────────────────────
    org_id = _claude_web_org_id(cookies_data, config)
    # activity_session_id lives in cookies
    activity_session_id = ""
    for c in cookies_data.get("cookies", []):
        if c.get("name") == "activitySessionId":
            activity_session_id = c.get("value", "")
            break

    # ── Build prompt — same as claude-web (handles list content blocks) ─────────
    prompt = _consolidate_web_history(messages)

    # ── HTTP session ──────────────────────────────────────────────────────────
    req_session = _req.Session()
    for c in cookies_data.get("cookies", []):
        req_session.cookies.set(
            c["name"], c["value"],
            domain=c.get("domain", "claude.ai"),
            path=c.get("path", "/"),
        )
    ua = cookies_data.get("user_agent", "Mozilla/5.0")
    req_session.headers.update({
        "User-Agent":                  ua,
        "Accept":                      "*/*",
        "Accept-Language":             "en-US,en;q=0.9",
        "anthropic-beta":              "ccr-byoc-2025-07-29",
        "anthropic-client-feature":    "ccr",
        "anthropic-client-platform":   "web_claude_ai",
        "anthropic-client-version":    "1.0.0",
        "anthropic-version":           "2023-06-01",
        "content-type":                "application/json",
        "Origin":                      "https://claude.ai",
        "Referer":                     f"https://claude.ai/code/{session_id}",
    })
    if org_id:
        req_session.headers["x-organization-uuid"] = org_id
    if activity_session_id:
        req_session.headers["x-activity-session-id"] = activity_session_id
    # Merge harvested device-id etc
    for k, v in cookies_data.get("headers", {}).items():
        kl = k.lower()
        if kl not in ("cookie", "host", "content-length", "content-type",
                      "anthropic-beta", "anthropic-version"):
            req_session.headers[k] = v

    # ── Payload ───────────────────────────────────────────────────────────────
    event_uuid = str(_uuid.uuid4())
    url = f"https://claude.ai/v1/sessions/{session_id}/events"
    payload = {
        "events": [
            {
                "type": "user",
                "uuid": event_uuid,
                "session_id": session_id,
                "parent_tool_use_id": None,
                "message": {
                    "role": "user",
                    "content": prompt,
                },
            }
        ]
    }

    # ── Seed existing JSONL entries BEFORE sending (to detect new ones after) ──
    import subprocess as _sp
    from pathlib import Path as _Path

    _project_override = config.get("claude_code_project_dir", "").strip()
    if _project_override:
        _slug = _project_override.replace(":", "-").replace("\\", "-").replace("/", "-")
    else:
        _slug = str(_Path.cwd()).replace(":", "-").replace("\\", "-").replace("/", "-")
    _session_dir = _Path.home() / ".claude" / "projects" / _slug
    _jsonl_files = sorted(_session_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    _jsonl_path = _jsonl_files[0] if _jsonl_files else None

    _seen_uuids: set = set()
    if _jsonl_path and _jsonl_path.exists():
        try:
            with open(_jsonl_path, "r", encoding="utf-8", errors="ignore") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _e = json.loads(_line)
                        _uid = _e.get("uuid") or _e.get("id")
                        if _uid:
                            _seen_uuids.add(_uid)
                    except Exception:
                        pass
        except Exception:
            pass

    parser = WebToolParser()
    text = ""

    try:
        resp = req_session.post(url, json=payload, stream=True, timeout=120)
        if resp.status_code == 404:
            msg = (
                "[claude-code] Session not found (404). May have expired.\n"
                "Run `claude remote-control` and update:\n"
                "  /config claude_code_session_id=<new_id>"
            )
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return
        if resp.status_code in (401, 403):
            msg = f"[claude-code] Auth error {resp.status_code} — run /harvest."
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return
        if resp.status_code != 200:
            msg = f"[claude-code] HTTP {resp.status_code}: {resp.text[:400]}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return
    except Exception as e:
        msg = f"[claude-code] Connection error: {e}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    # POST sent — close response (fire-and-forget, response comes via JSONL)
    try:
        resp.close()
    except Exception:
        pass

    # ── Poll JSONL for new assistant entry ────────────────────────────────────
    if not _jsonl_path:
        msg = f"[claude-code] No JSONL session file found in {_session_dir}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    import time as _time
    _deadline = _time.time() + 90
    _poll = 0.3
    _silence = 2.5  # wait this long after last new entry before yielding

    _accumulated: list[str] = []
    _last_new_entry_time: float = 0.0

    def _extract_text(entry: dict) -> str:
        _m = entry.get("message", {})
        if _m.get("role") != "assistant":
            return ""
        _c = _m.get("content", "")
        if isinstance(_c, str):
            return _c.strip()
        if isinstance(_c, list):
            _parts = []
            for _b in _c:
                if isinstance(_b, dict) and _b.get("type") == "text":
                    _parts.append(_b.get("text", "").strip())
            return "\n".join(_parts).strip()
        return ""

    while _time.time() < _deadline:
        # Scan for new entries
        try:
            with open(_jsonl_path, "r", encoding="utf-8", errors="ignore") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _e = json.loads(_line)
                    except Exception:
                        continue
                    _uid = _e.get("uuid") or _e.get("id")
                    if _uid in _seen_uuids:
                        continue
                    _seen_uuids.add(_uid)
                    _t = _extract_text(_e)
                    if _t:
                        _accumulated.append(_t)
                        _last_new_entry_time = _time.time()
        except Exception:
            pass

        # If we have text and silence window passed — flush
        if _accumulated and (_time.time() - _last_new_entry_time) >= _silence:
            text = "\n\n".join(_accumulated)
            _parser = WebToolParser(auto_wrap_json=True)
            _display = _parser.parse_chunk(text) + _parser.flush()
            yield TextChunk(_display)
            yield AssistantTurn(_display, _parser.tool_calls, 0, 0)
            return

        _time.sleep(_poll)

    if _accumulated:
        text = "\n\n".join(_accumulated)
        _parser = WebToolParser(auto_wrap_json=True)
        _display = _parser.parse_chunk(text) + _parser.flush()
        yield TextChunk(_display)
        yield AssistantTurn(_display, _parser.tool_calls, 0, 0)
        return

    msg = "[claude-code] Timeout waiting for assistant response (90s)."
    yield TextChunk(msg)
    yield AssistantTurn(msg, [], 0, 0, error=True)


def stream_kimi_web(
    auth_file: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from kimi.com consumer web using harvested gRPC-Web tokens."""
    import json
    import struct
    import os
    from pathlib import Path

    # 1. Load harvested auth
    if not os.path.exists(auth_file):
        msg = f"[kimi-web] Auth file not found: {auth_file}. Run harvester first."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    with open(auth_file, "r", encoding="utf-8") as f:
        auth_data = json.load(f)

    session = urllib.request.build_opener()
    
    # Set cookies
    cookies = []
    for c in auth_data.get("cookies", []):
        cookies.append(f"{c['name']}={c['value']}")
    
    headers = auth_data.get("headers", {}).copy()
    headers["Cookie"] = "; ".join(cookies)
    # Ensure Connect protocol
    headers["Content-Type"] = "application/connect+json"
    
    # 2. Maintain state (chat_id, parent_id)
    last_payload = auth_data.get("last_payload", {})
    harvested_chat_id = last_payload.get("chat_id")
    chat_id = config.get("kimi_web_chat_id") or harvested_chat_id

    # parent_id priority: use config value ONLY if it belongs to the current chat
    # (config may hold a stale parent_id from a previous session with a different chat_id)
    harvested_parent_id = last_payload.get("message", {}).get("parent_id")
    config_parent_id = config.get("kimi_web_parent_id")
    config_chat_id = config.get("kimi_web_chat_id")
    if config_parent_id and config_chat_id == harvested_chat_id:
        _kimi_web_parent_id = config_parent_id
    elif harvested_parent_id:
        _kimi_web_parent_id = harvested_parent_id
    else:
        _kimi_web_parent_id = None  # explicit fallback — new chat will be created

    # ── Build prompt from history ──────────────────────────────────────────
    manifest = _format_web_tool_manifest(tool_schemas, config, messages)
    last_user_msg = _consolidate_web_history(messages, manifest)

    payload = last_payload.copy()
    payload["chat_id"] = chat_id
    payload["message"] = {
        "parent_id": _kimi_web_parent_id,
        "role":      "user",
        "blocks":    [{"message_id": "", "text": {"content": last_user_msg}}],
        "scenario":  last_payload.get("message", {}).get("scenario", "SCENARIO_K2D5")
    }

    # ... (binary framing) ...
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    header_frame = struct.pack(">B I", 0, len(payload_bytes))
    data_to_send = header_frame + payload_bytes

    url = auth_data.get("url")
    req = urllib.request.Request(url, data=data_to_send, headers=headers, method="POST")

    # ── Streaming with Retries ──────────────────────────────────────────────
    text = ""
    raw_content = ""   # accumulate full response before parsing
    parser = WebToolParser(auto_wrap_json=True)

    for attempt in range(2):
        # attempt 0: original try
        # attempt 1: retry fresh thread if attempt 0 empty
        
        if attempt == 1:
            config.pop("kimi_web_chat_id", None)
            config.pop("kimi_web_parent_id", None)
            yield TextChunk("[kimi-web] Empty response — retrying with fresh thread...\n")
            
            # Rebuild payload for fresh thread
            payload["chat_id"] = None
            payload["message"]["parent_id"] = None
            payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            header_frame = struct.pack(">B I", 0, len(payload_bytes))
            data_to_send = header_frame + payload_bytes
            req = urllib.request.Request(url, data=data_to_send, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                while True:
                    h_bytes = resp.read(5)
                    if not h_bytes or len(h_bytes) < 5: break
                    flags, length = struct.unpack(">B I", h_bytes)
                    body = resp.read(length)
                    if not body: break
                    
                    try:
                        data = json.loads(body.decode("utf-8", errors="ignore"))
                        
                        # Capture state
                        if data.get("op") == "set":
                            if data.get("mask") == "chat":
                                config["kimi_web_chat_id"] = data.get("chat", {}).get("id")
                            elif data.get("mask") == "message":
                                msg_info = data.get("message", {})
                                if msg_info.get("role") == "user":
                                    if not config.get("kimi_web_parent_id"):
                                        config["kimi_web_parent_id"] = msg_info.get("id")
                                elif msg_info.get("role") == "assistant":
                                    config["kimi_web_parent_id"] = msg_info.get("id")
                        
                        content = ""
                        if data.get("op") == "set" and data.get("mask") == "block.text":
                            content = data.get("block", {}).get("text", {}).get("content", "")
                        elif data.get("op") == "append" and data.get("mask") == "block.text.content":
                            content = data.get("block", {}).get("text", {}).get("content", "")
                        
                        if content:
                            raw_content += content
                    except:
                        continue

            # If we got output, we are done
            if raw_content or parser.tool_calls:
                break

        except Exception as e:
            if attempt == 0: continue
            msg = f"[kimi-web] Error: {e}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

    # Parse the full response once — avoids tool_call tags split across chunks
    if raw_content:
        text = parser.parse_chunk(raw_content)
        text += parser.flush()
        if text:
            yield TextChunk(text)

    yield AssistantTurn(text, parser.tool_calls, 0, 0)



def stream_gemini_web(
    auth_file: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from gemini.google.com using the fast REST API with user-provided headers.

    Uses the 'requests' library with the exact cookies and headers captured from
    the user's browser. The harvester requires the user to type 'DULUS' as the
    message so we can locate and replace it in the f.req payload.
    """
    import requests
    import os
    import re
    import urllib.parse

    if not os.path.exists(auth_file):
        msg = f"[gemini-web] Error: Auth file {auth_file} not found. Run /harvest-gemini."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    with open(auth_file, "r", encoding="utf-8") as f:
        auth_data = json.load(f)

    # ── State / Prompt Extraction ──────────────────────────────────────────
    manifest = _format_web_tool_manifest(tool_schemas, config, messages)
    last_user_msg = _consolidate_web_history(messages, manifest)

    # ── Payload Building ───────────────────────────────────────────────────
    last_req = auth_data.get("intercepted_requests", [{}])[-1]
    url = last_req.get("url")
    if not url:
        msg = "[gemini-web] Error: Intercepted URL not found. Re-harvest."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    pd_raw = last_req.get("post_data", "")
    pd_parsed = urllib.parse.parse_qs(pd_raw)

    # Extract URL params for requests.post
    parsed_url = urllib.parse.urlparse(url)
    params_qs = urllib.parse.parse_qs(parsed_url.query)
    requests_params = {k: v[0] for k, v in params_qs.items()}

    def find_and_replace(obj, target1, replacement):
        if isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, str) and target1 in v:
                    if v == target1:
                        obj[i] = replacement
                    else:
                        try:
                            inner = json.loads(v)
                            find_and_replace(inner, target1, replacement)
                            obj[i] = json.dumps(inner, separators=(',', ':'))
                        except Exception:
                            pass
                elif isinstance(v, (list, dict)):
                    find_and_replace(v, target1, replacement)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and target1 in v:
                    if v == target1:
                        obj[k] = replacement
                elif isinstance(v, (list, dict)):
                    find_and_replace(v, target1, replacement)

    f_req = []
    f_req_source = None
    if "f.req" in pd_parsed:
        f_req = json.loads(pd_parsed["f.req"][0])
        f_req_source = "post_data"
    elif "f.req" in requests_params:
        f_req = json.loads(requests_params["f.req"])
        f_req_source = "params"

    if f_req_source:
        find_and_replace(f_req, "DULUS", last_user_msg)
        
        # Inject IDs to maintain conversation thread
        try:
            # f.req structure for Gemini usually has IDs at specific positions
            # We try to inject them if they exist in config
            c_id = config.get("gemini_web_c_id")
            r_id = config.get("gemini_web_r_id")
            if c_id and r_id:
                # Typically [null, "[[\"message\",0,null,null,null,null,0],[\"es\"],[\"c_id\",\"r_id\"]...]"]
                # The inner string is what we need to modify
                for i, val in enumerate(f_req):
                    if isinstance(val, str) and val.startswith("["):
                        try:
                            inner_req = json.loads(val)
                            # inner_req[1] is usually the language ["es"]
                            # inner_req[2] is usually [conv_id, reply_to_id]
                            if len(inner_req) > 2:
                                if not inner_req[2] or (isinstance(inner_req[2], list) and not inner_req[2][0]):
                                    inner_req[2] = [c_id, r_id]
                                    f_req[i] = json.dumps(inner_req, separators=(',', ':'))
                        except:
                            pass
        except:
            pass

    pd_new_dict = {}
    for k, v in pd_parsed.items():
        if k == "f.req" and f_req_source == "post_data":
            pd_new_dict[k] = json.dumps(f_req, separators=(',', ':'))
        else:
            pd_new_dict[k] = v[0] if isinstance(v, list) else v
    
    if f_req_source == "params":
        requests_params["f.req"] = json.dumps(f_req, separators=(',', ':'))

    # Ensure 'at' token is present
    if "at" not in pd_new_dict and auth_data.get("snlm0e"):
        pd_new_dict["at"] = auth_data["snlm0e"]

    # ── Headers / Cookies ──────────────────────────────────────────────────
    cookies = {c['name']: c['value'] for c in auth_data.get('cookies', [])}

    headers = last_req.get("headers", {}).copy()
    for h in ["Content-Length", "Accept-Encoding", "Content-Type"]:
        headers.pop(h, None)
        headers.pop(h.lower(), None)
    headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"

    # ── Streaming with Retries ──────────────────────────────────────────────
    # Accumulate the FULL raw response per attempt and parse <tool_call> tags
    # ONCE at the very end (same pattern as stream_kimi_web / stream_qwen_web).
    # Per-chunk parsing is fragile in gemini-web: tags can arrive split across
    # frames or come in a single blob, so end-of-response parsing is more robust.
    raw_content = ""
    text = ""
    parser = WebToolParser(auto_wrap_json=True)

    for attempt in range(3):
        raw_content = ""  # reset per attempt; previous attempt may have been incomplete
        # attempt 0: original try
        # attempt 1: same-thread retry (if attempt 0 was empty)
        # attempt 2: fresh-thread retry (clear IDs if attempt 1 was empty)
        
        if attempt == 1:
            yield TextChunk("[gemini-web] Empty response — retrying same thread...\n")
        elif attempt == 2:
            config.pop("gemini_web_c_id", None)
            config.pop("gemini_web_r_id", None)
            config.pop("gemini_web_rc_id", None)
            yield TextChunk("[gemini-web] Empty response — IDs cleared, retrying with new thread...\n")

        # Build/Re-build payload
        curr_f_req = []
        f_req_source = None
        if "f.req" in pd_parsed:
            curr_f_req = json.loads(pd_parsed["f.req"][0])
            f_req_source = "post_data"
        elif "f.req" in requests_params:
            curr_f_req = json.loads(requests_params["f.req"])
            f_req_source = "params"

        if f_req_source:
            find_and_replace(curr_f_req, "DULUS", last_user_msg)
            # Inject IDs if not on attempt 2 (fresh thread)
            if attempt < 2:
                try:
                    c_id = config.get("gemini_web_c_id")
                    r_id = config.get("gemini_web_r_id")
                    if c_id and r_id:
                        for i, val in enumerate(curr_f_req):
                            if isinstance(val, str) and val.startswith("["):
                                try:
                                    inner_req = json.loads(val)
                                    if len(inner_req) > 2:
                                        if not inner_req[2] or (isinstance(inner_req[2], list) and not inner_req[2][0]):
                                            inner_req[2] = [c_id, r_id]
                                            curr_f_req[i] = json.dumps(inner_req, separators=(',', ':'))
                                except: pass
                except: pass

        pd_curr_dict = {}
        curr_requests_params = requests_params.copy()
        for k, v in pd_parsed.items():
            if k == "f.req" and f_req_source == "post_data":
                pd_curr_dict[k] = json.dumps(curr_f_req, separators=(',', ':'))
            else:
                pd_curr_dict[k] = v[0] if isinstance(v, list) else v
        
        if f_req_source == "params":
            curr_requests_params["f.req"] = json.dumps(curr_f_req, separators=(',', ':'))
        if "at" not in pd_curr_dict and auth_data.get("snlm0e"):
            pd_curr_dict["at"] = auth_data["snlm0e"]

        raw_text_len = 0
        try:
            response = requests.post(
                url.split('?')[0],
                params=curr_requests_params,
                cookies=cookies,
                headers=headers,
                data=pd_curr_dict,
                stream=True,
                timeout=120,
            )

            if response.status_code != 200:
                if attempt < 2: continue # Retry on HTTP error too? maybe only on 429/500
                msg = f"[gemini-web] HTTP {response.status_code}: {response.text[:200]}"
                yield TextChunk(msg)
                yield AssistantTurn(msg, [], 0, 0, error=True)
                return

            for raw_line in response.iter_lines():
                if not raw_line: continue
                try:
                    line = raw_line.decode('utf-8').strip()
                except: continue
                if not line.startswith('[["wrb.fr"'): continue

                try:
                    envelope = json.loads(line)
                    for item in envelope:
                        if len(item) > 2 and item[0] == "wrb.fr" and isinstance(item[2], str) and item[2].startswith("["):
                            try:
                                inner = json.loads(item[2])
                                # Capture IDs
                                if isinstance(inner, list) and len(inner) > 1:
                                    ids = inner[1]
                                    if isinstance(ids, list) and len(ids) >= 2:
                                        if ids[0]: config["gemini_web_c_id"] = ids[0]
                                        if ids[1]: config["gemini_web_r_id"] = ids[1]
                                
                                # Text Extraction
                                candidate = None
                                try:
                                    if (isinstance(inner, list) and len(inner) > 4 
                                            and isinstance(inner[4], list) and inner[4]
                                            and isinstance(inner[4][0], list) and len(inner[4][0]) > 1
                                            and isinstance(inner[4][0][1], list) and inner[4][0][1]):
                                        candidate = inner[4][0][1][0]
                                except: pass
                                if not candidate:
                                    try:
                                        if (isinstance(inner, list) and len(inner) > 0 
                                                and isinstance(inner[0], list) and len(inner[0]) > 0
                                                and isinstance(inner[0][0], str) and inner[0][0]):
                                            candidate = inner[0][0]
                                    except: pass
                                
                                if candidate and isinstance(candidate, str) and len(candidate) > raw_text_len:
                                    diff = candidate[raw_text_len:]
                                    raw_text_len = len(candidate)
                                    raw_content += diff
                                    try:
                                        if len(inner) > 4 and inner[4][0][0]:
                                            config["gemini_web_rc_id"] = inner[4][0][0]
                                    except: pass
                            except: pass
                except: continue
        except Exception as e:
            if attempt < 2: continue
            msg = f"[gemini-web] Protocol Error: {e}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

        # Check if we got something
        if raw_content:
            break

    # Parse the full response once — avoids tool_call tags split across chunks
    if raw_content:
        text = parser.parse_chunk(raw_content)
        text += parser.flush()
        if text:
            yield TextChunk(text)

    if not text and not parser.tool_calls:
        yield AssistantTurn("[gemini-web: no response after retries]", [], 0, 0)
    else:
        yield AssistantTurn(text, parser.tool_calls, 0, 0)



class _DeepSeekPoWSolver:
    """Lazy-initialized WASM PoW solver for DeepSeek web (sha3_wasm_bg)."""
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        import os
        import wasmtime
        import ctypes
        wasm_path = os.path.join(os.path.dirname(__file__), "sha3_wasm_bg.7b9ca65ddd.wasm")
        if not os.path.exists(wasm_path):
            raise FileNotFoundError(f"WASM not found: {wasm_path}")
        self._engine = wasmtime.Engine()
        self._store = wasmtime.Store(self._engine)
        self._module = wasmtime.Module.from_file(self._engine, wasm_path)
        self._instance = wasmtime.Instance(self._store, self._module, [])
        self._mem = self._instance.exports(self._store)["memory"]
        self._sp = self._instance.exports(self._store)["__wbindgen_add_to_stack_pointer"]
        self._malloc = self._instance.exports(self._store)["__wbindgen_export_0"]
        self._solve = self._instance.exports(self._store)["wasm_solve"]

    def _get_mem_array(self):
        import ctypes
        ptr = self._mem.data_ptr(self._store)
        return ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ubyte * self._mem.data_len(self._store))).contents

    def _alloc_string(self, s: str):
        data = s.encode("utf-8")
        ptr = self._malloc(self._store, len(data), 1)
        arr = self._get_mem_array()
        for i, b in enumerate(data):
            arr[ptr + i] = b
        return ptr, len(data)

    def solve(self, challenge: str, salt: str, expire_at: int, difficulty: int):
        import struct
        prefix = f"{salt}_{expire_at}_"
        retptr = self._sp(self._store, -16)
        try:
            ch_ptr, ch_len = self._alloc_string(challenge)
            prefix_ptr, prefix_len = self._alloc_string(prefix)
            self._solve(self._store, retptr, ch_ptr, ch_len, prefix_ptr, prefix_len, float(difficulty))
            arr = self._get_mem_array()
            status = struct.unpack("<i", bytes(arr[retptr:retptr + 4]))[0]
            value = struct.unpack("<d", bytes(arr[retptr + 8:retptr + 16]))[0]
            if status == 0:
                return None
            return int(value)
        finally:
            self._sp(self._store, 16)


def stream_deepseek_web(
    auth_file: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from chat.deepseek.com web using harvested browser session.

    DeepSeek's web UI uses a simple SSE (text/event-stream) API:
      POST https://chat.deepseek.com/api/v0/chat/completion
      Headers: Authorization: Bearer <token>
      Body: { model, messages, stream: true, chat_session_id? }

    The harvester captures: Authorization token, cookies, and optionally a
    chat_session_id so the conversation continues in the same thread.

    Harvester writes JSON: {
        "token": "...",
        "cookies": [...],
        "headers": {...},
        "chat_session_id": "...",   // optional, for session continuity
        "model": "deepseek_v3"      // internal model name used by the web UI
    }
    """
    import requests
    import os

    if not os.path.exists(auth_file):
        msg = f"[deepseek-web] Auth file not found: {auth_file}. Run /harvest-deepseek."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    with open(auth_file, "r", encoding="utf-8") as f:
        auth_data = json.load(f)

    # ── Load persisted chat state (session + parent message) ─────────────────
    import pathlib as _pl
    _ds_state_path = _pl.Path.home() / ".dulus" / "deepseek_chat_state.json"
    _ds_state = {}
    if _ds_state_path.exists():
        try:
            with open(_ds_state_path, "r", encoding="utf-8") as _f:
                _ds_state = json.load(_f)
        except Exception:
            _ds_state = {}

    def _save_ds_state(st: dict):
        try:
            _ds_state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(_ds_state_path, "w", encoding="utf-8") as _f:
                json.dump(st, _f, indent=2)
        except Exception:
            pass

    token = auth_data.get("token") or auth_data.get("authorization", "")
    if token and not token.startswith("Bearer "):
        token = f"Bearer {token}"

    cookies = {c["name"]: c["value"] for c in auth_data.get("cookies", [])}

    # Build conversation history
    manifest = _format_web_tool_manifest(tool_schemas, config, messages)
    last_user_msg = _consolidate_web_history(messages, manifest)

    # Build messages list (system + history + new user message)
    ds_messages = []
    if system:
        ds_messages.append({"role": "system", "content": system})

    # Include prior turns for context (last N to stay within limits)
    for m in messages[:-1][-20:]:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        if role in ("user", "assistant") and content:
            ds_messages.append({"role": role, "content": content})

    ds_messages.append({"role": "user", "content": last_user_msg})

    # Internal model name (DeepSeek web uses "deepseek_v3" / "deepseek_r1" not "deepseek-v3")
    internal_model = auth_data.get("model", "deepseek_v3")
    if "r1" in model.lower():
        internal_model = "deepseek_r1"
    elif "v3" in model.lower() or "chat" in model.lower():
        internal_model = "deepseek_v3"

    # Session continuity — state file has highest priority, then config, then auth_data
    chat_session_id = (
        _ds_state.get("chat_session_id")
        or config.get("deepseek_web_session_id")
        or auth_data.get("chat_session_id")
    )
    parent_message_id = (
        _ds_state.get("parent_message_id")
        or config.get("deepseek_web_parent_id")
    )

    # ── Headers ──────────────────────────────────────────────────────────
    headers = auth_data.get("headers", {}).copy()
    for h in ["Content-Length", "Accept-Encoding", "Content-Type", "content-length"]:
        headers.pop(h, None)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "text/event-stream"
    if token:
        headers["Authorization"] = token

    url = auth_data.get("url") or "https://chat.deepseek.com/api/v0/chat/completion"

    # DeepSeek web API uses `prompt` (string) not `messages` (array).
    # Conversation history is maintained server-side via chat_session_id.
    if chat_session_id:
        # Server has history — just send the new user message as prompt
        prompt_text = last_user_msg
    else:
        # No session — flatten everything into a single prompt string
        parts = []
        if system:
            parts.append(f"[System]: {system}")
        for m in ds_messages[:-1]:  # exclude last user msg, already in last_user_msg
            role = m.get("role", "user").capitalize()
            parts.append(f"[{role}]: {m.get('content', '')}")
        parts.append(last_user_msg)
        prompt_text = "\n\n".join(parts)

    payload = {
        "model": internal_model,
        "prompt": prompt_text,
        "ref_file_ids": [],
        "thinking_enabled": internal_model == "deepseek_r1",
        "search_enabled": False,
        "stream": True,
    }
    if chat_session_id:
        payload["chat_session_id"] = chat_session_id
    if parent_message_id is not None:
        payload["parent_message_id"] = parent_message_id

    text = ""
    thinking = ""
    raw_content = ""   # accumulate full response before parsing
    parser = WebToolParser(auto_wrap_json=True)
    in_thinking = False

    try:
        # Fetch and solve PoW challenge
        try:
            pow_resp = requests.post(
                "https://chat.deepseek.com/api/v0/chat/create_pow_challenge",
                cookies=cookies,
                headers={k: v for k, v in headers.items() if k.lower() != "x-ds-pow-response"},
                json={"target_path": "/api/v0/chat/completion"},
                timeout=10,
            )
            if pow_resp.status_code == 200:
                ch = pow_resp.json()["data"]["biz_data"]["challenge"]
                solver = _DeepSeekPoWSolver.get()
                ans = solver.solve(ch["challenge"], ch["salt"], ch["expire_at"], ch["difficulty"])
                if ans is not None:
                    import base64 as _b64
                    pow_obj = {
                        "algorithm": ch["algorithm"],
                        "challenge": ch["challenge"],
                        "salt": ch["salt"],
                        "answer": ans,
                        "signature": ch["signature"],
                        "target_path": ch["target_path"],
                    }
                    headers["x-ds-pow-response"] = _b64.b64encode(
                        json.dumps(pow_obj, separators=(",", ":")).encode()
                    ).decode()
        except Exception: pass

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            cookies=cookies,
            stream=True,
            timeout=120,
        )

        if response.status_code == 401:
            msg = "[deepseek-web] Auth error (401) — token expired. Run /harvest-deepseek."
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

        if response.status_code != 200:
            msg = f"[deepseek-web] HTTP {response.status_code}: {response.text[:200]}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

        for raw_line in response.iter_lines():
            if not raw_line:
                continue
            try:
                line = raw_line.decode("utf-8").strip()
            except Exception:
                continue

            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break

            try:
                data = json.loads(data_str)
            except Exception:
                continue

            content_chunk = ""
            thinking_chunk = ""

            if isinstance(data, dict):
                # Capture message IDs
                if "response_message_id" in data:
                    config["deepseek_web_parent_id"] = data["response_message_id"]
                    _save_ds_state({
                        "chat_session_id": chat_session_id or data.get("id"),
                        "parent_message_id": data["response_message_id"],
                    })
                if data.get("id"):
                    config["deepseek_web_session_id"] = data["id"]

                # Native protocol
                p, o, v = data.get("p", ""), data.get("o", ""), data.get("v")
                if p == "response/fragments/-1/content" and o == "APPEND" and isinstance(v, str):
                    content_chunk = v
                elif "p" not in data and "o" not in data and isinstance(v, str):
                    content_chunk = v
                elif isinstance(v, dict):
                    response_obj = v.get("response", {})
                    if isinstance(response_obj, dict):
                        fragments = response_obj.get("fragments", [])
                        for frag in fragments:
                            if isinstance(frag, dict) and frag.get("type") == "RESPONSE":
                                content_chunk += frag.get("content", "")

            # Fallback: SSE format
            if not content_chunk and not thinking_chunk:
                choices = data.get("choices", [])
                for choice in choices:
                    delta = choice.get("delta", {})
                    thinking_chunk = delta.get("reasoning_content") or delta.get("thinking_content", "")
                    content_chunk = delta.get("content", "")

            if thinking_chunk:
                thinking += thinking_chunk
                if not in_thinking:
                    in_thinking = True
                yield TextChunk(thinking_chunk)

            if content_chunk:
                in_thinking = False
                raw_content += content_chunk

    except Exception as e:
        msg = f"[deepseek-web] Error: {e}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    # Parse the full response once — avoids tool_call tags split across chunks
    if raw_content:
        text = parser.parse_chunk(raw_content)
        text += parser.flush()
        if text:
            yield TextChunk(text)

    yield AssistantTurn(text or "[deepseek-web: no response]", parser.tool_calls, 0, 0)


def stream_qwen_web(
    auth_file: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from chat.qwen.ai web using harvested browser session.

    Qwen web uses a JSON-stream API:
      POST https://chat.qwen.ai/api/v2/chat/completions?chat_id=<uuid>
      Cookies: token=<JWT>, plus anti-bot cookies (cna/isg/tfstk/...)
      Body: {stream:true, version:"2.1", incremental_output:true, chat_id,
             chat_mode:"normal", model, parent_id, messages:[...]}

    Harvester writes JSON: {
        "token": "<JWT>",
        "cookies": [...],
        "headers": {...},
        "chat_id": "...",
        "parent_id": "...",
        "model": "qwen3.6-plus"
    }
    """
    import requests
    import os
    import time
    import uuid

    if not os.path.exists(auth_file):
        msg = f"[qwen-web] Auth file not found: {auth_file}. Run /harvest-qwen."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    with open(auth_file, "r", encoding="utf-8") as f:
        auth_data = json.load(f)

    # ── Load persisted chat state (chat_id + parent_id across restarts) ──
    import pathlib as _pl
    _qw_state_path = _pl.Path.home() / ".dulus" / "qwen_chat_state.json"
    _qw_state = {}
    if _qw_state_path.exists():
        try:
            with open(_qw_state_path, "r", encoding="utf-8") as _f:
                _qw_state = json.load(_f)
        except Exception:
            _qw_state = {}

    def _save_qw_state(st: dict):
        try:
            _qw_state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(_qw_state_path, "w", encoding="utf-8") as _f:
                json.dump(st, _f, indent=2)
        except Exception:
            pass

    cookies = {c["name"]: c["value"] for c in auth_data.get("cookies", [])}
    if auth_data.get("token") and "token" not in cookies:
        cookies["token"] = auth_data["token"]

    # Session continuity — state file (most fresh) > config > auth_data > new
    chat_id = (
        _qw_state.get("chat_id")
        or config.get("qwen_web_chat_id")
        or auth_data.get("chat_id")
        or str(uuid.uuid4())
    )
    parent_id = (
        _qw_state.get("parent_id")
        or config.get("qwen_web_parent_id")
        or auth_data.get("parent_id")
    )

    # Build conversation history. Qwen's server keeps the thread (chat_id +
    # parent_id), so on continuation turns we send ONLY the new user content
    # + tool results — re-sending the system prompt and tool manifest every
    # turn wastes 1-2K tokens per call.
    is_first_turn = not parent_id
    if is_first_turn:
        manifest = _format_web_tool_manifest(tool_schemas, config, messages)
        last_user_msg = _consolidate_web_history(messages, manifest)
        if system:
            last_user_msg = f"[System]: {system}\n\n{last_user_msg}"
    else:
        last_user_msg = _consolidate_web_history(messages, "")

    fid = str(uuid.uuid4())
    next_child_id = str(uuid.uuid4())
    ts = int(time.time())

    # Internal model name — strip provider prefix if any
    internal_model = model
    if "/" in internal_model:
        internal_model = internal_model.split("/", 1)[1]
    if not internal_model or internal_model == "qwen-latest":
        internal_model = auth_data.get("model") or "qwen3.6-plus"

    # ── Headers ──────────────────────────────────────────────────────────
    headers = auth_data.get("headers", {}).copy()
    for h in ["Content-Length", "Accept-Encoding", "Content-Type",
              "content-length", "Cookie", "cookie"]:
        headers.pop(h, None)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    headers.setdefault("Origin", "https://chat.qwen.ai")
    headers.setdefault("Referer", f"https://chat.qwen.ai/c/{chat_id}")
    headers.setdefault("source", "web")
    headers.setdefault("Version", "0.2.45")
    headers["X-Request-Id"] = str(uuid.uuid4())

    user_message = {
        "fid": fid,
        "parentId": parent_id,
        "childrenIds": [next_child_id],
        "role": "user",
        "content": last_user_msg,
        "user_action": "chat",
        "files": [],
        "timestamp": ts,
        "models": [internal_model],
        "chat_type": "t2t",
        "feature_config": {
            "thinking_enabled": False,
            "output_schema": "phase",
            "research_mode": "normal",
            "auto_thinking": False,
            "thinking_mode": "Auto",
            "thinking_format": "summary",
            "auto_search": False,
        },
        "extra": {"meta": {"subChatType": "t2t"}},
        "sub_chat_type": "t2t",
        "parent_id": parent_id,
    }

    payload = {
        "stream": True,
        "version": "2.1",
        "incremental_output": True,
        "chat_id": chat_id,
        "chat_mode": "normal",
        "model": internal_model,
        "parent_id": parent_id,
        "messages": [user_message],
        "timestamp": ts,
    }

    url = "https://chat.qwen.ai/api/v2/chat/completions"
    params = {"chat_id": chat_id}

    raw_content = ""
    text = ""
    parser = WebToolParser(auto_wrap_json=True)

    # ── 2-attempt loop: if chat was deleted server-side (404 / 400 / empty
    # stream) regenerate chat_id+parent_id once and retry as a fresh thread.
    for attempt in range(2):
        if attempt == 1:
            config.pop("qwen_web_chat_id", None)
            config.pop("qwen_web_parent_id", None)
            _save_qw_state({})
            chat_id = str(uuid.uuid4())
            parent_id = None
            params["chat_id"] = chat_id
            payload["chat_id"] = chat_id
            payload["parent_id"] = None
            user_message["parentId"] = None
            user_message["parent_id"] = None
            payload["messages"] = [user_message]
            yield TextChunk("[qwen-web] Chat unavailable — retrying with fresh thread...\n")
            raw_content = ""

        try:
            response = requests.post(
                url, params=params, json=payload,
                headers=headers, cookies=cookies,
                stream=True, timeout=120,
            )
        except Exception as e:
            msg = f"[qwen-web] Error: {e}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

        if response.status_code == 401:
            msg = "[qwen-web] Auth error (401) — token expired. Run /harvest-qwen."
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

        if response.status_code in (400, 404) and attempt == 0:
            continue  # likely chat deleted — retry with fresh thread

        if response.status_code != 200:
            msg = f"[qwen-web] HTTP {response.status_code}: {response.text[:300]}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

        try:
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                try:
                    line = raw_line.decode("utf-8").strip()
                except Exception:
                    continue

                # Qwen uses SSE-style "data: {...}" lines
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                else:
                    data_str = line
                if not data_str or data_str == "[DONE]":
                    if data_str == "[DONE]":
                        break
                    continue

                try:
                    data = json.loads(data_str)
                except Exception:
                    continue

                if not isinstance(data, dict):
                    continue

                content_chunk = ""

                # ── Capture assistant message ID for thread continuity ──
                # Qwen response shapes vary; scan many likely keys. Whatever
                # ID we land on becomes the next turn's parent_id (mirrors
                # kimi-web / deepseek-web — without this, every turn looks
                # like a fresh chat to Qwen's server).
                captured_id = (
                    data.get("response.message_id")
                    or data.get("response_message_id")
                    or data.get("message_id")
                    or (data.get("message", {}) or {}).get("id")
                    or data.get("response_id")
                )
                if not captured_id:
                    for ch in data.get("choices", []) or []:
                        msg_obj = ch.get("message") if isinstance(ch, dict) else None
                        if isinstance(msg_obj, dict) and msg_obj.get("id"):
                            captured_id = msg_obj["id"]
                            break
                if not captured_id:
                    resp_obj = data.get("response", {})
                    if isinstance(resp_obj, dict):
                        captured_id = resp_obj.get("id") or resp_obj.get("message_id")
                if not captured_id and data.get("id") and data.get("id") != chat_id:
                    captured_id = data["id"]
                if captured_id:
                    config["qwen_web_parent_id"] = captured_id
                    _save_qw_state({
                        "chat_id":   config.get("qwen_web_chat_id") or chat_id,
                        "parent_id": captured_id,
                    })

                if data.get("chat_id") and not config.get("qwen_web_chat_id"):
                    config["qwen_web_chat_id"] = data["chat_id"]

                # Try multiple shapes the Qwen API has been seen using:
                # 1) {"choices":[{"delta":{"content":"..."}}]}
                choices = data.get("choices", [])
                for choice in choices:
                    delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
                    if isinstance(delta, dict):
                        c = delta.get("content")
                        if isinstance(c, str):
                            content_chunk += c
                        rc = delta.get("reasoning_content") or delta.get("thinking_content")
                        if isinstance(rc, str) and rc:
                            yield TextChunk(rc)

                # 2) {"output":{"text":"...", "finish_reason":...}}
                if not content_chunk:
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        t = output.get("text") or output.get("content")
                        if isinstance(t, str):
                            content_chunk = t

                # 3) {"content":"..."}  (rare flat form)
                if not content_chunk and isinstance(data.get("content"), str):
                    content_chunk = data["content"]

                if content_chunk:
                    raw_content += content_chunk
        except Exception as e:
            msg = f"[qwen-web] Error: {e}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return

        # If first attempt produced nothing, retry with a fresh thread once
        if not raw_content and attempt == 0:
            continue

        break  # success — exit retry loop

    # Parse the full response once — avoids tool_call tags split across chunks
    if raw_content:
        text = parser.parse_chunk(raw_content)
        text += parser.flush()
        if text:
            yield TextChunk(text)

    # Persist next-turn state in config + disk (covers the case where the
    # chat_id was generated client-side and never echoed back in the stream).
    if not config.get("qwen_web_chat_id"):
        config["qwen_web_chat_id"] = chat_id
    _save_qw_state({
        "chat_id":   config.get("qwen_web_chat_id") or chat_id,
        "parent_id": config.get("qwen_web_parent_id"),
    })

    yield AssistantTurn(text or "[qwen-web: no response]", parser.tool_calls, 0, 0)


def bare_model(model: str) -> str:
    """Strip 'provider/' prefix if present."""
    return model.split("/", 1)[1] if "/" in model else model


def get_api_key(provider_name: str, config: dict) -> str:
    prov = PROVIDERS.get(provider_name, {})
    # 1. Check config dict (e.g. config["kimi_api_key"])
    cfg_key = config.get(f"{provider_name}_api_key", "")
    if cfg_key:
        return cfg_key
    
    # Alias fallback: moonshot <-> kimi
    if provider_name == "moonshot":
        cfg_key = config.get("kimi_api_key", "")
        if cfg_key: return cfg_key
    elif provider_name == "kimi":
        cfg_key = config.get("moonshot_api_key", "")
        if cfg_key: return cfg_key
    elif provider_name == "kimi-code":
        cfg_key = config.get("kimi_code_api_key", "")
        if cfg_key: return cfg_key
    elif provider_name == "kimi-code2":
        cfg_key = config.get("kimi_code2_api_key", "")
        if cfg_key: return cfg_key
    elif provider_name == "kimi-code3":
        cfg_key = config.get("kimi_code3_api_key", "")
        if cfg_key: return cfg_key

    # 2. Check env var
    env_var = prov.get("api_key_env")
    if env_var:
        import os
        return os.environ.get(env_var, "")
    # 3. Hardcoded (for local providers)
    return prov.get("api_key", "")


def calc_cost(model: str, in_tok: int, out_tok: int) -> float:
    ic, oc = COSTS.get(bare_model(model), (0.0, 0.0))
    return (in_tok * ic + out_tok * oc) / 1_000_000


# ── Native tool-call format interceptors ──────────────────────────────────
# Some models (Gemma 3/4, Mistral, ...) emit their NATIVE tool-call format
# inside `delta.content` even when the API has been told to use OpenAI-style
# tool schemas. Without interception the user sees raw markers like
# `<|tool_call>call:Foo{"x":1}<tool_call|>` streamed as text, and the
# intended tool call never fires — and on Ollama Cloud / vLLM the broken
# format can also trip a 502 from the upstream proxy. The helpers below let
# stream_ollama / stream_openai_compat detect these markers, switch into
# buffer mode, and parse the buffered tail into proper tool_calls.
_NATIVE_TOOL_OPENERS = (
    "<|tool_call|>",   # Gemma official
    "<|tool_call>",    # Gemma 4 asymmetric variant seen in the wild
    "<tool_call>",     # Hermes / Qwen
    "[TOOL_CALLS]",    # Mistral
)

_GEMMA_QUOTE_TOKEN_FIXES = (
    ("<|\"|>", '"'),
    ("<|'|>", "'"),
)

_NATIVE_FMT_V2 = re.compile(
    r"<\|?tool_call\|?>\s*call:\s*(\w+)\s*(\{.*?\})\s*<\|?(?:end_)?(?:/)?tool_call\|?>",
    re.DOTALL,
)
_NATIVE_FMT_V1 = re.compile(
    r"<\|?tool_call\|?>\s*(\{.*?\})\s*<\|?(?:end_)?(?:/)?tool_call\|?>",
    re.DOTALL,
)
_NATIVE_FMT_MISTRAL = re.compile(r"\[TOOL_CALLS\]\s*(\[.*?\])", re.DOTALL)


def _find_native_tool_marker(text: str) -> "int | None":
    earliest = None
    for opener in _NATIVE_TOOL_OPENERS:
        idx = text.find(opener)
        if idx != -1 and (earliest is None or idx < earliest):
            earliest = idx
    return earliest


def _extract_native_tool_calls(buf: str) -> list:
    """Parse buffered native-format tool calls. Returns [] on any failure."""
    if not buf:
        return []
    for tok, repl in _GEMMA_QUOTE_TOKEN_FIXES:
        buf = buf.replace(tok, repl)

    out: list = []

    # Format 2 first (more specific — explicit `call:NAME` outside the JSON)
    for m in _NATIVE_FMT_V2.finditer(buf):
        name, body = m.group(1), m.group(2)
        try:
            args = json.loads(body)
            if not isinstance(args, dict):
                args = {"_raw": body}
        except json.JSONDecodeError:
            args = {"_raw": body}
        out.append({"id": f"native_call_{len(out)}", "name": name, "input": args})

    # Format 1: JSON envelope with `name` + `arguments`
    if not out:
        for m in _NATIVE_FMT_V1.finditer(buf):
            try:
                parsed = json.loads(m.group(1))
                if isinstance(parsed, dict):
                    name = parsed.get("name") or parsed.get("function") or ""
                    args = parsed.get("arguments") or parsed.get("args") or {}
                    if name:
                        if not isinstance(args, dict):
                            args = {"_raw": str(args)}
                        out.append({
                            "id": f"native_call_{len(out)}",
                            "name": name, "input": args,
                        })
            except json.JSONDecodeError:
                continue

    # Mistral [TOOL_CALLS] [{...}, {...}]
    if not out:
        for m in _NATIVE_FMT_MISTRAL.finditer(buf):
            try:
                arr = json.loads(m.group(1))
                if isinstance(arr, list):
                    for item in arr:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name") or (item.get("function") or {}).get("name") or ""
                        args = item.get("arguments") or (item.get("function") or {}).get("arguments") or {}
                        if name:
                            if not isinstance(args, dict):
                                args = {"_raw": str(args)}
                            out.append({
                                "id": f"native_call_{len(out)}",
                                "name": name, "input": args,
                            })
            except json.JSONDecodeError:
                continue

    return out


def estimate_tokens_kimi(api_key: str, model: str, messages: list) -> int | None:
    """Estimate token count using Kimi's native API endpoint.
    
    Args:
        api_key: Moonshot API key
        model: Model name (e.g., "kimi-k2.5")
        messages: List of message dicts with "role" and "content"
    Returns:
        Estimated token count, or None if the request fails
    """
    if not api_key:
        return None
    
    url = "https://api.moonshot.ai/v1/tokenizers/estimate-token-count"
    
    # Convert messages to Kimi format (similar to OpenAI format)
    kimi_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, str):
            kimi_messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            # Multimodal content - extract text parts
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            if text_parts:
                kimi_messages.append({"role": role, "content": " ".join(text_parts)})
    
    payload = {
        "model": model,
        "messages": kimi_messages
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Response: {"data": {"total_tokens": 123}}
            if "data" in data and "total_tokens" in data["data"]:
                return data["data"]["total_tokens"]
            return None
    except Exception:
        # Silently fail - caller will fall back to character-based estimation
        return None


# ── Tool schema conversion ─────────────────────────────────────────────────

def scrub_any_type(obj: Any) -> Any:
    """Recursively remove 'type': 'any' from schema dictionaries as it's not valid JSON Schema."""
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k == "type" and v == "any":
                continue
            new_obj[k] = scrub_any_type(v)
        return new_obj
    elif isinstance(obj, list):
        return [scrub_any_type(item) for item in obj]
    return obj


def tools_to_openai(tool_schemas: list) -> list:
    """Convert Anthropic-style tool schemas to OpenAI function-calling format."""
    out = []
    for t in tool_schemas:
        if not isinstance(t, dict) or "name" not in t:
            continue
        
        # Handle different schema names (Anthropic input_schema vs OpenAI parameters)
        params = t.get("input_schema") or t.get("parameters")
        if params is None:
            # Fallback to empty object if missing, better than crashing
            params = {"type": "object", "properties": {}}
        
        # Scrub invalid 'any' types that some models hallucinate
        params = scrub_any_type(params)
            
        out.append({
            "type": "function",
            "function": {
                "name":        t["name"],
                "description": t.get("description", ""),
                "parameters":  params,
            },
        })
    return out


# ── Message format conversion ──────────────────────────────────────────────
#
# Internal "neutral" message format:
#   {"role": "user",      "content": "text"}
#   {"role": "assistant", "content": "text", "tool_calls": [
#       {"id": "...", "name": "...", "input": {...}}
#   ]}
#   {"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}

def messages_to_anthropic(messages: list) -> list:
    """Convert neutral messages → Anthropic API format."""
    result = []
    i = 0
    while i < len(messages):
        m = messages[i]
        role = m["role"]

        if role == "user":
            result.append({"role": "user", "content": m["content"]})
            i += 1

        elif role == "assistant":
            blocks = []
            thinking = m.get("thinking", "")
            if thinking:
                blocks.append({"type": "thinking", "thinking": thinking})
            
            text = m.get("content", "")
            if text:
                blocks.append({"type": "text", "text": text})
            for tc in m.get("tool_calls", []):
                blocks.append({
                    "type":  "tool_use",
                    "id":    tc["id"],
                    "name":  tc["name"],
                    "input": tc["input"],
                })
            result.append({"role": "assistant", "content": blocks})
            i += 1

        elif role == "tool":
            # Collect consecutive tool results into one user message
            tool_blocks = []
            while i < len(messages) and messages[i]["role"] == "tool":
                t = messages[i]
                tool_blocks.append({
                    "type":        "tool_result",
                    "tool_use_id": t["tool_call_id"],
                    "content":     t["content"],
                })
                i += 1
            result.append({"role": "user", "content": tool_blocks})

        else:
            i += 1

    return result


def messages_to_openai(messages: list, ollama_native_images: bool = False) -> list:
    """Convert neutral messages → OpenAI API format.

    Also sanitizes orphan tool_calls — if an assistant message has tool_calls
    but the matching tool responses are missing (e.g. user interrupted mid-call),
    the tool_calls are stripped to avoid API rejection.
    """
    # ── Sanitize orphan tool_calls ────────────────────────────────────────
    # Collect all tool_call_ids that have a matching tool response
    answered_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    sanitized = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            # Keep only tool_calls that have a matching response
            valid_tcs = [tc for tc in m["tool_calls"] if tc.get("id") in answered_ids]
            if valid_tcs:
                sanitized.append({**m, "tool_calls": valid_tcs})
            else:
                # All tool_calls are orphans — strip them, keep text content only
                sanitized.append({"role": "assistant", "content": m.get("content") or "(interrupted)"})
        else:
            sanitized.append(m)
    messages = sanitized

    result = []
    for m in messages:
        role = m["role"]

        if role == "user":
            content = m["content"]
            if ollama_native_images and m.get("images"):
                # Ollama /api/chat native: bare base64 list on the message
                msg_out = {"role": "user", "content": content, "images": m["images"]}
            elif not ollama_native_images and m.get("images"):
                # OpenAI / Gemini multipart vision format
                parts = [{"type": "text", "text": content}]
                for img_b64 in m["images"]:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    })
                msg_out = {"role": "user", "content": parts}
            else:
                msg_out = {"role": "user", "content": content}
            result.append(msg_out)

        elif role == "assistant":
            msg: dict = {"role": "assistant", "content": m.get("content") or None}
            if "thinking" in m and m["thinking"]:
                msg["reasoning_content"] = m["thinking"]
            
            tcs = m.get("tool_calls", [])
            if tcs:
                msg["tool_calls"] = []
                for tc in tcs:
                    tc_msg = {
                        "id":   tc["id"],
                        "type": "function",
                        "function": {
                            "name":      tc["name"],
                            "arguments": json.dumps(tc["input"], ensure_ascii=False),
                        },
                    }
                    # Pass through provider-specific fields (e.g. Gemini thought_signature)
                    if tc.get("extra_content"):
                        tc_msg["extra_content"] = tc["extra_content"]
                    msg["tool_calls"].append(tc_msg)
            result.append(msg)

        elif role == "tool":
            result.append({
                "role":         "tool",
                "tool_call_id": m["tool_call_id"],
                "content":      m["content"],
            })

    return result


# ── Streaming adapters ─────────────────────────────────────────────────────

class TextChunk:
    def __init__(self, text): self.text = text

class ThinkingChunk:
    def __init__(self, text): self.text = text

class AssistantTurn:
    """Completed assistant turn with text + tool_calls + thinking."""
    def __init__(self, text, tool_calls, in_tokens, out_tokens, thinking="", error=False,
                 cache_creation_tokens=0, cache_read_tokens=0):
        self.text        = text
        self.tool_calls  = tool_calls   # list of {id, name, input}
        self.in_tokens   = in_tokens
        self.out_tokens  = out_tokens
        self.thinking    = thinking
        self.error       = error
        # Anthropic explicit caching + OpenAI prompt-cached tokens.
        # 0 when the provider doesn't report it.
        self.cache_creation_tokens = cache_creation_tokens
        self.cache_read_tokens     = cache_read_tokens


def friendly_api_error(exc: Exception) -> str:
    """Map common API exceptions to short, actionable hints for the user.

    Returns a single-line string suitable for streaming back to the REPL.
    Falls back to the raw exception message when no pattern matches.
    """
    s = str(exc).lower()
    etype = type(exc).__name__

    # Auth / key problems
    if "authentication" in s or "invalid_api_key" in s or "401" in s or etype == "AuthenticationError":
        return "API key is missing or invalid. Run /config <provider>_api_key=... or set the env var."
    # Rate limit
    if "rate limit" in s or "rate_limit" in s or "429" in s or etype == "RateLimitError":
        return "Rate limit hit. Wait a bit and retry, or switch model with /model."
    # Overload / capacity
    if "overloaded" in s or "capacity" in s or "503" in s or "502" in s:
        return "Provider is overloaded right now. Retry in a few seconds or switch model."
    # Context / token limit
    if "context_length" in s or "maximum context" in s or "too many tokens" in s or "context_window" in s:
        return "Context window exceeded. Try /compact to shrink history or /clear to reset."
    # Bad request / tool schema
    if "invalid_request" in s or "400" in s or etype == "BadRequestError":
        return f"API rejected the request: {exc}. Check tool schemas, message format, or model name."
    # Network / DNS
    if "connection" in s or "timeout" in s or "dns" in s or etype in ("APIConnectionError", "ConnectTimeout"):
        return "Network problem reaching the API. Check connection, VPN, or provider status."
    # Permission / model access
    if "permission" in s or "model_not_found" in s or "404" in s:
        return "Model not found or not enabled for your account. Check model name or billing."
    return f"API error: {exc}"


def _thinking_level_from(value) -> int:
    """Coerce legacy bool/int thinking config into an int 0-4."""
    if value is True:  return 3
    if value is False or value is None: return 0
    try:
        lvl = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(4, lvl))


def stream_anthropic(
    api_key: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from Anthropic API. Yields TextChunk/ThinkingChunk, then AssistantTurn.

    Prompt caching: marks up to 3 cache breakpoints — system prompt, tools
    block, and the latest user message. Anthropic caches everything BEFORE
    each breakpoint, so the conversation history up to the latest user turn
    rides the same cache as long as it's appended (not edited). 4-breakpoint
    cap is the API limit; 3 is the practical sweet spot for an agent loop.
    """
    import anthropic as _ant
    client = _ant.Anthropic(api_key=api_key)

    # 1) System prompt as a single text block with cache_control.
    if isinstance(system, str) and system:
        system_blocks = [{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }]
    else:
        system_blocks = system  # already structured, leave as-is

    # 2) Tools: cache the last tool's schema. Caches the whole tools array.
    cached_tools = list(tool_schemas) if tool_schemas else tool_schemas
    if cached_tools:
        last_tool = dict(cached_tools[-1])
        last_tool["cache_control"] = {"type": "ephemeral"}
        cached_tools[-1] = last_tool

    # 3) Latest user message: marker on the last content block. Caches the
    #    full prior conversation so multi-turn sessions hit the cache.
    ant_messages = messages_to_anthropic(messages)
    for i in range(len(ant_messages) - 1, -1, -1):
        m = ant_messages[i]
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            m["content"] = [{
                "type": "text",
                "text": c,
                "cache_control": {"type": "ephemeral"},
            }]
        elif isinstance(c, list) and c:
            last = c[-1]
            if isinstance(last, dict):
                # Don't double-mark if caller already set it.
                last.setdefault("cache_control", {"type": "ephemeral"})
        break

    kwargs = {
        "model":      model,
        "max_tokens": config.get("max_tokens", 8192),
        "system":     system_blocks,
        "messages":   ant_messages,
        "tools":      cached_tools,
    }
    _thk_raw = config.get("thinking", 0)
    _thk_level = _thinking_level_from(_thk_raw)
    if _thk_level > 0:
        # Budget scales with level: 1=low, 2=medium, 3=high, 4=normal (mid). Explicit
        # thinking_budget in config still wins when provided.
        _level_budgets = {1: 2048, 2: 6000, 3: 16000, 4: 8192}
        budget = config.get("thinking_budget") or _level_budgets[_thk_level]
        kwargs["thinking"] = {
            "type":          "enabled",
            "budget_tokens": budget,
        }

    tool_calls = []
    text       = ""
    thinking   = ""

    try:
        with client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", None)
                    if dtype == "text_delta":
                        text += delta.text
                        yield TextChunk(delta.text)
                    elif dtype == "thinking_delta":
                        thinking += delta.thinking
                        yield ThinkingChunk(delta.thinking)

            final = stream.get_final_message()
            for block in final.content:
                if block.type == "tool_use":
                    tool_calls.append({
                        "id":    block.id,
                        "name":  block.name,
                        "input": block.input,
                    })

            _cc = getattr(final.usage, "cache_creation_input_tokens", 0) or 0
            _cr = getattr(final.usage, "cache_read_input_tokens", 0) or 0
            yield AssistantTurn(
                text, tool_calls,
                final.usage.input_tokens,
                final.usage.output_tokens,
                thinking=thinking,
                cache_creation_tokens=_cc,
                cache_read_tokens=_cr,
            )
    except Exception as _e:
        msg = friendly_api_error(_e)
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return


def stream_kimi(
    api_key: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from Kimi API using native HTTP requests. Yields TextChunk, then AssistantTurn.
    
    This is a native implementation using urllib.request instead of the OpenAI SDK,
    allowing direct comparison with the OpenAI-compatible version.
    
    Token estimation:
    1. Input tokens: Estimados ANTES usando estimate_tokens_kimi() (endpoint nativo de Kimi)
    2. Output tokens: Capturados del campo usage de la respuesta streaming
    """
    url = "https://api.moonshot.ai/v1/chat/completions"

    # Build messages
    kimi_messages = [{"role": "system", "content": system}] + messages_to_openai(messages)

    # Kimi rejects assistant messages with null/empty content and no tool_calls
    # (happens when a prior turn was thinking-only or interrupted).
    # Replace empty content with a placeholder so the conversation chain stays valid.
    for _m in kimi_messages:
        if _m.get("role") == "assistant" and not _m.get("tool_calls"):
            if not _m.get("content"):
                _m["content"] = "..."

    # === CONTADOR DE TOKENS ===
    # Input: Estimación por caracteres (fallback simple y confiable)
    # Output: Capturado del usage del stream
    in_tok = 0
    
    # Build request payload
    payload: dict = {
        "model": model,
        "messages": kimi_messages,
        "stream": True,
        "stream_options": {"include_usage": True},  # ensure token usage in stream
    }

    # Kimi thinking control
    thinking_mode = "enabled" if config.get("thinking", False) else "disabled"
    payload["thinking"] = {"type": thinking_mode}

    # Tools
    if tool_schemas and not config.get("no_tools"):
        payload["tools"] = tools_to_openai(tool_schemas)
        if not config.get("disable_tool_choice"):
            payload["tool_choice"] = "auto"

    # Max tokens (Kimi prefers max_completion_tokens like OpenAI new API)
    if config.get("max_tokens"):
        prov_cap = PROVIDERS.get("kimi", {}).get("max_completion_tokens")
        mt = config["max_tokens"]
        payload["max_completion_tokens"] = min(mt, prov_cap) if prov_cap else mt
    
    # Extra options
    if config.get("temperature") is not None:
        payload["temperature"] = config["temperature"]
    if config.get("top_p") is not None:
        payload["top_p"] = config["top_p"]
    
    # Make request
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )
    
    text = ""
    thinking = ""
    tool_buf: dict = {}
    out_tok = 0
    cached_tok = 0
    
    # Estimación simple de tokens de entrada (caracteres / 4)
    # Esto es aproximado pero confiable
    total_chars = len(system) + sum(len(str(m.get("content", ""))) for m in messages)
    in_tok = max(1, total_chars // 4)
    
    try:
        resp = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_data = json.loads(err_body)
            err_msg = err_data.get("error", {}).get("message", str(e))
        except:
            err_msg = str(e)
        msg = f"Error: Kimi API error: {err_msg}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return
    except Exception as e:
        msg = f"Error: Failed to connect to Kimi API: {e}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return
    
    # Parse SSE stream
    for line in resp:
        line = line.decode("utf-8").strip()
        if not line or not line.startswith("data: "):
            continue
        
        data_str = line[6:]  # Remove "data: " prefix
        if data_str == "[DONE]":
            break
        
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        
        # Extract usage if present
        if "usage" in data and data["usage"]:
            u = data["usage"]
            in_tok = u.get("prompt_tokens", 0) or in_tok
            out_tok = u.get("completion_tokens", 0) or out_tok
            # Kimi exposes cached prompt tokens at top-level usage.cached_tokens
            # (some accounts also report prompt_tokens_details.cached_tokens).
            cached_tok = (
                u.get("cached_tokens", 0)
                or (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                or cached_tok
            )
        
        # Extract choices
        choices = data.get("choices", [])
        if not choices:
            continue
        
        delta = choices[0].get("delta", {})
        
        # Content
        content = delta.get("content")
        if content:
            text += content
            yield TextChunk(content)
        
        # Reasoning content
        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
        if reasoning:
            thinking += reasoning
            yield ThinkingChunk(reasoning)
        
        # Tool calls
        tool_calls = delta.get("tool_calls", [])
        for tc in tool_calls:
            idx = tc.get("index", 0)
            if idx not in tool_buf:
                tool_buf[idx] = {"id": "", "name": "", "args": ""}
            if tc.get("id"):
                tool_buf[idx]["id"] = tc["id"]
            fn = tc.get("function", {})
            if fn.get("name"):
                tool_buf[idx]["name"] += fn["name"]
            if fn.get("arguments"):
                tool_buf[idx]["args"] += fn["arguments"]
    
    # Build final tool calls
    final_tool_calls = []
    for idx in sorted(tool_buf):
        v = tool_buf[idx]
        try:
            inp = json.loads(v["args"]) if v["args"] else {}
        except json.JSONDecodeError:
            inp = {"_raw": v["args"]}
        final_tool_calls.append({
            "id": v["id"] or f"call_{idx}",
            "name": v["name"],
            "input": inp
        })
    
    yield AssistantTurn(text, final_tool_calls, in_tok, out_tok, thinking=thinking,
                        cache_read_tokens=cached_tok)


def stream_litellm(
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream via LiteLLM — one entry point routing to 100+ backends.

    `model` arrives WITHOUT the leading "litellm/" prefix (bare_model strips
    one level). So for `litellm/openrouter/anthropic/claude-3-5-sonnet`,
    `model` here is `openrouter/anthropic/claude-3-5-sonnet` — exactly the
    format LiteLLM's `completion()` expects.

    LiteLLM auto-resolves the underlying API key from env (OPENROUTER_API_KEY,
    GROQ_API_KEY, TOGETHER_API_KEY, …). For Dulus we also mirror the relevant
    config-stored key into the env before dispatching, so users who put their
    keys under `/config openrouter_api_key=...` Just Work without `export`.
    """
    # Robust detection: ImportError covers "not installed at all", but a
    # phantom `litellm` namespace (stale stub, name collision with a local
    # litellm.py, partial pip install) can let the import succeed while
    # `.completion` is missing — that surfaces as a confusing AttributeError
    # mid-call. Check both, and treat missing-completion the same as
    # missing-package so the user gets the same friendly install hint.
    try:
        import litellm  # type: ignore
    except ImportError:
        litellm = None  # type: ignore
    if litellm is None or not hasattr(litellm, "completion"):
        where = ""
        try:
            if litellm is not None and getattr(litellm, "__file__", None):
                where = f"\n  (found a partial 'litellm' module at: {litellm.__file__})"
        except Exception:
            pass
        msg = (
            "[litellm] Not installed (or installed module is missing .completion). Run:\n"
            "  pip install 'dulus[litellm]'\n"
            "or directly:\n"
            "  pip install -U litellm" + where
        )
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    # Mirror config-stored API keys into the env so LiteLLM finds them.
    # LiteLLM reads ~30 env vars depending on the backend prefix; we surface
    # the most common ones from config.
    import os as _os
    _env_map = {
        "openrouter":   "OPENROUTER_API_KEY",
        "groq":         "GROQ_API_KEY",
        "together_ai":  "TOGETHER_API_KEY",
        "perplexity":   "PERPLEXITYAI_API_KEY",
        "cohere":       "COHERE_API_KEY",
        "mistral":      "MISTRAL_API_KEY",
        "fireworks_ai": "FIREWORKS_API_KEY",
        "xai":          "XAI_API_KEY",
        "anyscale":     "ANYSCALE_API_KEY",
        "deepinfra":    "DEEPINFRA_API_KEY",
        "replicate":    "REPLICATE_API_KEY",
        "azure":        "AZURE_API_KEY",
        "bedrock":      "AWS_ACCESS_KEY_ID",     # bedrock needs AWS creds, not single key
        "vertex_ai":    "GOOGLE_APPLICATION_CREDENTIALS",
        "openai":       "OPENAI_API_KEY",
        "anthropic":    "ANTHROPIC_API_KEY",
        "gemini":       "GEMINI_API_KEY",
    }
    backend = model.split("/", 1)[0] if "/" in model else ""
    env_name = _env_map.get(backend)
    if env_name:
        cfg_key = (
            config.get(f"{backend}_api_key", "")
            or config.get(f"litellm_{backend}_api_key", "")
            or config.get("litellm_api_key", "")
        )
        if cfg_key and not _os.environ.get(env_name):
            _os.environ[env_name] = cfg_key

    oai_messages = [{"role": "system", "content": system}] + messages_to_openai(messages)

    kwargs: dict = {
        "model":    model,
        "messages": oai_messages,
        "stream":   True,
    }
    if tool_schemas and not config.get("no_tools"):
        kwargs["tools"] = tools_to_openai(tool_schemas)
        if not config.get("disable_tool_choice"):
            kwargs["tool_choice"] = "auto"
    if config.get("max_tokens"):
        kwargs["max_tokens"] = config["max_tokens"]

    text     = ""
    thinking = ""
    tool_buf: dict = {}
    in_tok = out_tok = 0

    try:
        response = litellm.completion(**kwargs)
    except Exception as e:
        msg = f"[litellm] {type(e).__name__}: {e}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    try:
        for chunk in response:
            # LiteLLM normalises every backend into OpenAI ChunkChoice format.
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                # Usage block sometimes arrives in a separate trailing chunk.
                u = getattr(chunk, "usage", None)
                if u is not None:
                    in_tok = getattr(u, "prompt_tokens", 0) or 0
                    out_tok = getattr(u, "completion_tokens", 0) or 0
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            piece = getattr(delta, "content", None) or ""
            if piece:
                text += piece
                yield TextChunk(piece)
            tc_list = getattr(delta, "tool_calls", None) or []
            for tc in tc_list:
                idx = getattr(tc, "index", 0) or 0
                slot = tool_buf.setdefault(idx, {"id": "", "name": "", "args": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    args_piece = getattr(fn, "arguments", "") or ""
                    if args_piece:
                        slot["args"] += args_piece
    except Exception as e:
        msg = f"[litellm stream] {type(e).__name__}: {e}"
        yield TextChunk(msg)
        yield AssistantTurn(text or msg, [], in_tok, out_tok, error=True)
        return

    # Flatten tool_buf into AssistantTurn tool_calls.
    tool_calls = []
    for idx in sorted(tool_buf.keys()):
        slot = tool_buf[idx]
        if not slot["name"]:
            continue
        try:
            args = json.loads(slot["args"] or "{}")
        except Exception:
            args = {}
        tool_calls.append({"id": slot["id"] or f"call_{idx}", "name": slot["name"], "input": args})

    yield AssistantTurn(text, tool_calls, in_tok, out_tok, thinking=thinking)


def stream_openai_compat(
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from any OpenAI-compatible API. Yields TextChunk, then AssistantTurn."""
    from openai import OpenAI
    # Detect kimi-code by base_url, NOT by model name. Reason: when invoked as
    # `kimi-code/kimi-k2.5` (or k2.6, kimi-latest, etc.), `model` arrives here
    # already stripped to the bare name, and detect_provider("kimi-k2.5") falls
    # through to the generic "kimi" prefix → header omitted → 403.
    # The /coding/v1 endpoint is unique to kimi-code regardless of model.
    _is_kimi_code = (
        "api.kimi.com/coding" in (base_url or "")
        or detect_provider(model) in ("kimi-code", "kimi-code2", "kimi-code3")
    )
    client_kwargs: dict = {"api_key": api_key or "dummy", "base_url": base_url}
    if _is_kimi_code:
        # Kimi Code API whitelists only known Coding Agents by User-Agent.
        # Without this header the API returns 403.
        client_kwargs["default_headers"] = {"User-Agent": "KimiCLI/1.30.0"}
    client = OpenAI(**client_kwargs)

    oai_messages = [{"role": "system", "content": system}] + messages_to_openai(messages)

    _is_nvidia = detect_provider(model) == "nvidia-web"

    kwargs: dict = {
        "model":    model,
        "messages": oai_messages,
        "stream":   True,
        "stream_options": {"include_usage": True},
    }

    # Pass num_ctx for known Ollama/LM Studio ports only — avoids matching other local servers (e.g. vLLM on :8000)
    _is_local_ollama = "11434" in base_url
    _is_lmstudio     = "1234" in base_url and ("lmstudio" in base_url or "localhost" in base_url or "127.0.0.1" in base_url)
    if _is_local_ollama or _is_lmstudio:
        prov = detect_provider(model)
        ctx_limit = PROVIDERS.get(prov if prov in ("ollama", "lmstudio") else "ollama", {}).get("context_limit", 128000)
        kwargs["extra_body"] = {"options": {"num_ctx": ctx_limit}}

    # Kimi thinking control (v1.0.1.20+)
    if detect_provider(model) in ("kimi", "moonshot", "kimi-code", "kimi-code2", "kimi-code3"):
        if not kwargs.get("extra_body"): kwargs["extra_body"] = {}
        # Kimi expects an object: {"type": "enabled" | "disabled"}
        mode = "enabled" if config.get("thinking", False) else "disabled"
        kwargs["extra_body"]["thinking"] = {"type": mode}
    
    # DeepSeek reasoning control (reasoning_effort for thinking models)
    if detect_provider(model) == "deepseek":
        if config.get("thinking", False):
            # Map thinking mode to reasoning_effort
            kwargs["reasoning_effort"] = "medium"  # default
        else:
            kwargs["reasoning_effort"] = "none"

    # NVIDIA NIM thinking control (chat_template_kwargs)
    if _is_nvidia and config.get("thinking", False):
        if not kwargs.get("extra_body"):
            kwargs["extra_body"] = {}
        kwargs["extra_body"]["chat_template_kwargs"] = {
            "thinking": True,
            "reasoning_effort": "high",
        }

    if tool_schemas and not config.get("no_tools"):
        kwargs["tools"] = tools_to_openai(tool_schemas)
        # "auto" requires vLLM --enable-auto-tool-choice; omit if server doesn't support it
        if not config.get("disable_tool_choice"):
            kwargs["tool_choice"] = "auto"
    if config.get("max_tokens"):
        prov_cap = PROVIDERS.get(detect_provider(model), {}).get("max_completion_tokens")
        mt = config["max_tokens"]
        kwargs["max_tokens"] = min(mt, prov_cap) if prov_cap else mt

    text          = ""
    thinking      = ""
    tool_buf: dict = {}   # index → {id, name, args_str}
    in_tok = out_tok = 0
    cached_tok = 0  # OpenAI-compat prefix-cached prompt tokens (when reported)

    try:
        from openai import AuthenticationError, RateLimitError, APIConnectionError, APIStatusError
        stream = client.chat.completions.create(**kwargs)
    except (AuthenticationError, RateLimitError, APIConnectionError, APIStatusError) as e:
        if _is_nvidia:
            import sys; print(f"[nvidia-web RAW ERROR] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        msg = friendly_api_error(e)
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return
    except Exception as e:
        if _is_nvidia:
            import sys; print(f"[nvidia-web RAW ERROR] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        msg = friendly_api_error(e)
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    in_thought = False
    def _extract_cached(u) -> int:
        # Cached prompt tokens come in different shapes depending on provider:
        #   OpenAI:    usage.prompt_tokens_details.cached_tokens
        #   Kimi/code: usage.cached_tokens (top-level) or same as OpenAI
        #   DeepSeek:  usage.prompt_cache_hit_tokens
        #   Anthropic-style proxy: usage.cache_read_input_tokens
        c = 0
        details = getattr(u, "prompt_tokens_details", None)
        if details:
            c = (
                getattr(details, "cached_tokens", 0)
                or (details.get("cached_tokens", 0) if isinstance(details, dict) else 0)
                or 0
            )
        return (
            c
            or getattr(u, "cached_tokens", 0)
            or getattr(u, "prompt_cache_hit_tokens", 0)
            or getattr(u, "cache_read_input_tokens", 0)
            or 0
        )

    for chunk in stream:
        if not chunk.choices:
            # usage-only chunk (some providers send this last)
            if hasattr(chunk, "usage") and chunk.usage:
                u = chunk.usage
                in_tok  = getattr(u, "prompt_tokens", 0) or in_tok
                out_tok = getattr(u, "completion_tokens", 0) or out_tok
                cached_tok = _extract_cached(u) or cached_tok
            continue

        choice = chunk.choices[0]
        delta  = choice.delta

        content = delta.content
        if content:
            # Heuristic: detect reasoning tags in the content stream
            lower_c = content.lower()
            if "<thought" in lower_c or "<reasoning" in lower_c:
                in_thought = True
            
            # If we are inside a thought block, check for closing tags
            if in_thought:
                if "</thought" in lower_c or "</reasoning" in lower_c:
                    # Closing tag found: yield current chunk as thinking, then flip
                    yield ThinkingChunk(content)
                    in_thought = False
                else:
                    yield ThinkingChunk(content)
            else:
                text += content
                yield TextChunk(content)

        # Capture native reasoning content (DeepSeek/Gemini/OpenAI/Custom)
        reasoning = (
            getattr(delta, "reasoning_content", None)
            or getattr(delta, "reasoning", None)
            or getattr(delta, "thought", None)
        )
        if reasoning:
            thinking += reasoning
            yield ThinkingChunk(reasoning)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_buf:
                    tool_buf[idx] = {"id": "", "name": "", "args": "", "extra_content": None}
                if tc.id:
                    tool_buf[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        tool_buf[idx]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_buf[idx]["args"] += tc.function.arguments
                # Capture extra_content (e.g. Gemini thought_signature)
                extra = getattr(tc, "extra_content", None)
                if extra:
                    tool_buf[idx]["extra_content"] = extra

        # Some providers include usage in the last chunk
        if hasattr(chunk, "usage") and chunk.usage:
            u = chunk.usage
            in_tok  = (getattr(u, "prompt_tokens", 0) or getattr(u, "prompt_token_count", 0) or in_tok)
            out_tok = (getattr(u, "completion_tokens", 0) or getattr(u, "candidate_token_count", 0) or out_tok)
            cached_tok = _extract_cached(u) or cached_tok
        elif hasattr(chunk, "x_groq") and chunk.x_groq and "usage" in chunk.x_groq:
            # Groq-specific usage
            u = chunk.x_groq["usage"]
            in_tok = u.get("prompt_tokens", 0) or in_tok
            out_tok = u.get("completion_tokens", 0) or out_tok
        elif hasattr(chunk, "model_extra") and chunk.model_extra and "usage" in chunk.model_extra:
            # Pydantic v2 / Gemini proxy fallback
            u = chunk.model_extra["usage"]
            if u:
                if isinstance(u, dict):
                    in_tok = u.get("prompt_tokens", 0) or in_tok
                    out_tok = u.get("completion_tokens", 0) or out_tok
                else:
                    in_tok = getattr(u, "prompt_tokens", 0) or in_tok
                    out_tok = getattr(u, "completion_tokens", 0) or out_tok

    tool_calls = []
    for idx in sorted(tool_buf):
        v = tool_buf[idx]
        try:
            inp = json.loads(v["args"]) if v["args"] else {}
        except json.JSONDecodeError:
            inp = {"_raw": v["args"]}
        tc_entry = {"id": v["id"] or f"call_{idx}", "name": v["name"], "input": inp}
        if v.get("extra_content"):
            tc_entry["extra_content"] = v["extra_content"]
        tool_calls.append(tc_entry)

    yield AssistantTurn(
        text, tool_calls, in_tok, out_tok,
        thinking=thinking,
        cache_read_tokens=cached_tok,
    )


def _flatten_tool_messages(messages: list) -> list:
    """Convert tool-call history to plain text for models without native tool support.

    Transforms:
      - assistant messages with tool_calls → text + inline <tool_call> representation
      - role:tool messages → role:user with [Tool Result] prefix
    This lets the model see the full conversation without needing the tools API.
    """
    out = []
    for m in messages:
        role = m.get("role", "")

        if role == "assistant":
            text = m.get("content") or ""
            tcs = m.get("tool_calls", [])
            if tcs:
                # Append inline <tool_call> tags so the model sees what it called
                parts = [text] if text else []
                for tc in tcs:
                    fn = tc.get("function", {})
                    name = fn.get("name", tc.get("name", ""))
                    args = fn.get("arguments", tc.get("input", {}))
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            pass
                    parts.append(
                        f'<tool_call>{json.dumps({"name": name, "input": args}, ensure_ascii=False)}</tool_call>'
                    )
                out.append({"role": "assistant", "content": "\n".join(parts)})
            else:
                out.append({"role": "assistant", "content": text})

        elif role == "tool":
            # Convert tool result to a user message the model can read
            name = m.get("name", m.get("tool_call_id", "unknown"))
            content = m.get("content", "")
            # Make format more explicit for DeepSeek-R1
            tool_result_msg = f"[Tool Result: {name}]\n{content}\n\n[INSTRUCTION: Use this data to respond. Do not ask what to do next.]"
            out.append({
                "role": "user",
                "content": tool_result_msg,
            })

        else:
            # system / user — pass through as-is
            out.append(m)

    return out


def _build_prompt_tool_manifest(tool_schemas: list) -> str:
    """Build the text block injected into the system prompt for prompt-based tool calling."""
    oai_tools = tools_to_openai(tool_schemas)
    tool_lines = []
    for t in oai_tools:
        fn = t.get("function", t)
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = json.dumps(fn.get("parameters", {}))
        tool_lines.append(f"  - {name}: {desc}\n    Parameters: {params}")

    return (
        "\n\n[TOOL USE]\nYou have access to these tools. "
        "When you need to use a tool, you MUST output EXACTLY this format (no extra text):\n"
        '<tool_call>{"name": "tool_name", "input": {"param": "value"}}</tool_call>\n\n'
        "EXAMPLE - If you need to search, output ONLY this exact line:\n"
        '<tool_call>{"name": "web_search", "input": {"query": "search term"}}</tool_call>\n\n'
        "CRITICAL RULES:\n"
        "1. ALWAYS wrap the JSON in <tool_call>...</tool_call> tags\n"
        "2. The <tool_call> tag must be on its own line with NO extra text before or after\n"
        "3. Use ONLY the exact JSON format: {\"name\": \"tool_name\", \"input\": {...}}\n"
        "4. Output the tool call IMMEDIATELY - do not explain first\n"
        "5. Wait for the tool result before continuing\n"
        "6. After your thinking is done, output ONLY the <tool_call> line\n"
        "7. AFTER calling a tool, WAIT for [Tool Result] and READ it before responding\n"
        "8. DO NOT call multiple tools at once - wait for each result\n\n"
        "WORKFLOW EXAMPLE:\n"
        "User: 'List files'\n"
        "Assistant: <tool_call>{\"name\": \"Glob\", \"input\": {\"pattern\": \"*\"}}</tool_call>\n"
        "[Tool Result: Glob]\n"
        "file1.txt\nfile2.txt\n"
        "Assistant: 'Found files: file1.txt, file2.txt'\n\n"
        "Available tools:\n" + "\n".join(tool_lines)
    )


def _get_gcloud_token() -> str:
    """Obtain OAuth2 access token from gcloud CLI."""
    use_shell = platform.system() == "Windows"
    result = subprocess.run(
        "gcloud auth print-access-token",
        capture_output=True,
        text=True,
        check=True,
        shell=use_shell,
    )
    return result.stdout.strip()


def _openai_messages_to_vertex_contents(messages: list) -> list:
    """Convert OpenAI-format messages to Vertex AI generateContent 'contents'."""
    contents = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")

        if role == "system":
            continue  # handled separately as systemInstruction

        if role == "user":
            parts = []
            if content:
                parts.append({"text": content})
            contents.append({"role": "user", "parts": parts})

        elif role == "assistant":
            parts = []
            if content:
                parts.append({"text": content})
            # Native tool calls from OpenAI format
            for tc in m.get("tool_calls", []):
                fn = tc.get("function", {})
                name = fn.get("name", tc.get("name", ""))
                args = fn.get("arguments", tc.get("input", {}))
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                if name:
                    parts.append({
                        "functionCall": {"name": name, "args": args}
                    })
            contents.append({"role": "model", "parts": parts})

        elif role == "tool":
            name = m.get("name", m.get("tool_call_id", "unknown"))
            parts = [{
                "functionResponse": {
                    "name": name,
                    "response": {"result": content},
                }
            }]
            contents.append({"role": "user", "parts": parts})

    return contents


def _openai_tools_to_vertex_tools(tool_schemas: list) -> list:
    """Convert OpenAI-format tools to Vertex AI functionDeclarations."""
    declarations = []
    for t in tool_schemas:
        if not isinstance(t, dict):
            continue
        fn = t.get("function", t)
        name = fn.get("name", t.get("name", ""))
        if not name:
            continue
        declarations.append({
            "name": name,
            "description": fn.get("description", t.get("description", "")),
            "parameters": fn.get("parameters", t.get("input_schema", {"type": "object", "properties": {}})),
        })
    return [{"functionDeclarations": declarations}] if declarations else []


def stream_gcloud(
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """Stream from Google Cloud Vertex AI using gcloud OAuth2 authentication.

    Uses the generateContent REST API directly with Bearer tokens from
    `gcloud auth print-access-token`. Supports native function calling.
    """
    # ── Auth ────────────────────────────────────────────────────────────────
    try:
        token = _get_gcloud_token()
    except Exception as e:
        msg = f"[gcloud] Failed to get gcloud token: {e}. Run `gcloud auth login`."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    # ── Configurable project/location (fallback to hardcoded) ─────────────
    project_id = config.get("gcloud_project_id", "gen-lang-client-0108363942")
    location   = config.get("gcloud_location", "us-west1")
    bare = model.split("/")[-1] if "/" in model else model

    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/"
        f"publishers/google/models/{bare}:generateContent"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # ── Convert messages ────────────────────────────────────────────────────
    oai_messages = messages_to_openai(messages)
    contents = _openai_messages_to_vertex_contents(oai_messages)

    # Cap maxOutputTokens to Vertex AI limit (65536)
    prov_cap = PROVIDERS.get("gcloud", {}).get("max_completion_tokens", 65536)
    req_max = config.get("max_tokens", 2048)
    safe_max = min(req_max, prov_cap) if prov_cap else req_max

    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": config.get("temperature", 0.7),
            "maxOutputTokens": safe_max,
        },
    }

    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    # ── Tools ───────────────────────────────────────────────────────────────
    if tool_schemas and not config.get("no_tools"):
        vertex_tools = _openai_tools_to_vertex_tools(tools_to_openai(tool_schemas))
        if vertex_tools:
            payload["tools"] = vertex_tools
            payload["toolConfig"] = {
                "functionCallingConfig": {"mode": "AUTO"}
            }

    # ── Request ─────────────────────────────────────────────────────────────
    text = ""
    thinking = ""
    tool_calls: list = []
    in_tok = out_tok = 0

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code != 200:
            msg = f"[gcloud] HTTP {resp.status_code}: {resp.text[:400]}"
            yield TextChunk(msg)
            yield AssistantTurn(msg, [], 0, 0, error=True)
            return
        data = resp.json()
    except Exception as e:
        msg = f"[gcloud] Request error: {e}"
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    # ── Parse response ──────────────────────────────────────────────────────
    candidates = data.get("candidates", [])
    if not candidates:
        msg = "[gcloud] No candidates in response."
        yield TextChunk(msg)
        yield AssistantTurn(msg, [], 0, 0, error=True)
        return

    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])

    for part in parts:
        if "text" in part:
            chunk_text = part["text"]
            text += chunk_text
            yield TextChunk(chunk_text)

        if "functionCall" in part:
            fc = part["functionCall"]
            tool_calls.append({
                "id": f"call_gc_{len(tool_calls)}",
                "name": fc.get("name", ""),
                "input": fc.get("args", {}),
            })

    # Token usage (Vertex AI sometimes includes usageMetadata)
    usage = data.get("usageMetadata", {})
    in_tok = usage.get("promptTokenCount", 0)
    out_tok = usage.get("candidatesTokenCount", 0)

    yield AssistantTurn(text, tool_calls, in_tok, out_tok, thinking=thinking)


def stream_ollama(
    base_url: str,
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    # pass_images=True: Ollama /api/chat accepts base64 images natively in the message
    oai_messages = [{"role": "system", "content": system}] + messages_to_openai(messages, ollama_native_images=True)
    
    # Ollama requires tool arguments as dict objects, not strings. OpenAI uses strings.
    for m in oai_messages:
        if m.get("content") is None:
            m["content"] = ""
        if "tool_calls" in m and m["tool_calls"]:
            for tc in m["tool_calls"]:
                fn = tc.get("function", {})
                if isinstance(fn.get("arguments"), str):
                    try:
                        fn["arguments"] = json.loads(fn["arguments"])
                    except Exception:
                        pass

    # ── DeepSeek-R1 Specific Fix ─────────────────────────────────────────
    # Simplified instructions for smaller models
    is_deepseek_r1 = "deepseek-r1" in model.lower()
    if is_deepseek_r1:
        deepseek_fix = (
            '\n\nRules: Reply directly. Use tools ONLY when needed. Format: <tool_call>{"name": "...", "input": {}}</tool_call>\n'
        )
        for msg in oai_messages:
            if msg.get("role") == "system":
                msg["content"] += deepseek_fix
                break

    # ── Check if a previous turn already detected no native tool support ──
    # Use model-specific key to persist across sessions
    _no_native_tools_key = f"_no_native_tools_{model}"
    _prompt_tool_mode = False
    
    # Check both the old generic flag and the new model-specific flag
    if (config.get("_prompt_tool_mode") or config.get(_no_native_tools_key)) and tool_schemas and not config.get("no_tools"):
        _prompt_tool_mode = True
        # Flatten tool messages in history so the model can read them as plain text
        oai_messages = _flatten_tool_messages(oai_messages)
        # Inject tool manifest into system prompt
        tool_manifest = _build_prompt_tool_manifest(tool_schemas)
        for msg in oai_messages:
            if msg.get("role") == "system":
                msg["content"] += tool_manifest
                break

    payload = {
        "model": model,
        "messages": oai_messages,
        "stream": True,
        "options": {
            "num_ctx": config.get("context_limit", 32768)
        }
    }

    if tool_schemas and not config.get("no_tools") and not _prompt_tool_mode:
        payload["tools"] = tools_to_openai(tool_schemas)
    
    def _make_request(p):
        return urllib.request.Request(
            f"{base_url.rstrip('/')}/api/chat",
            data=json.dumps(p).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

    req = _make_request(payload)

    text = ""
    thinking = ""
    tool_buf: dict = {}

    # Native tool-call interceptor state. When the model emits its native
    # `<|tool_call|>...` envelope inside `content` (Gemma 3/4 in particular
    # do this even when given OpenAI-style tool schemas), we stop yielding
    # text and accumulate everything from the marker onward. At end-of-stream
    # we parse the buffer into proper tool_calls. Without this the user sees
    # `<|tool_call>call:Foo{...}<tool_call|>` as raw text, the tool never
    # fires, and on Ollama Cloud the malformed exchange can trip a 502.
    _native_buf = ""           # text accumulated after a native marker
    _native_intercept = False  # True once we've seen any native marker

    # State for prompt-based tool call parsing across streamed chunks
    use_deep_tools = config.get("deep_tools", False) if config else False
    _auto_wrap_json = is_deepseek_r1 and use_deep_tools
    parser = WebToolParser(auto_wrap_json=_auto_wrap_json)

    # Cloud-routed Ollama models (e.g. minimax-m2.7:cloud) need a moment before
    # the proxy starts streaming real content — without this, the first response
    # can come back empty.
    import time as _time
    if ":cloud" in model.lower():
        _time.sleep(1)

    try:
        resp_cm = urllib.request.urlopen(req)
    except urllib.error.HTTPError:
        raise

    # Buffer for accumulating thinking content to reduce word-by-word chunks
    _thinking_buffer = ""
    
    with resp_cm as resp:
        for line in resp:
            if not line.strip(): continue
            try:
                data = json.loads(line)
            except Exception: continue

            msg = data.get("message", {})
            reasoning = None
            for r_key in ["thinking", "reasoning", "thought", "reasoning_content"]:
                if r_key in msg and msg[r_key]:
                    reasoning = msg[r_key]
                    break

            if reasoning:
                thinking += reasoning
                _thinking_buffer += reasoning
                if len(_thinking_buffer) >= 20 or (_thinking_buffer and reasoning and reasoning[0] in " \n\t.,;:!?"):
                    yield ThinkingChunk(_thinking_buffer)
                    _thinking_buffer = ""

            content = msg.get("content", "") if "content" in msg else ""
            content = msg.get("content", "") if "content" in msg else ""
            if content:
                # Flush thinking buffer before content
                if _thinking_buffer:
                    yield ThinkingChunk(_thinking_buffer)
                    _thinking_buffer = ""
                
                if _prompt_tool_mode:
                    display = parser.parse_chunk(content)
                    if display:
                        text += display
                        yield TextChunk(display)
                elif _native_intercept:
                    # Already inside a native tool-call envelope — buffer silently.
                    _native_buf += content
                else:
                    marker = _find_native_tool_marker(content)
                    if marker is not None:
                        # Yield clean prefix, then start buffering from the marker.
                        prefix = content[:marker]
                        if prefix:
                            text += prefix
                            yield TextChunk(prefix)
                        _native_buf += content[marker:]
                        _native_intercept = True
                    else:
                        text += content
                        yield TextChunk(content)

            # Handle native ollama tools format
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                idx = len(tool_buf) # Ollama sends complete tool calls, not delta
                tool_buf[idx] = {
                    "id": "call_ollama" + str(idx),
                    "name": fn.get("name", ""),
                    "input": fn.get("arguments", {})
                }

    # Flush any remaining thinking buffer at end of stream
    if _thinking_buffer:
        yield ThinkingChunk(_thinking_buffer)

    if _prompt_tool_mode:
        remaining = parser.flush()
        if remaining:
            text += remaining
            yield TextChunk(remaining)

    tool_calls = []
    # Merge native Ollama tools
    for idx in sorted(tool_buf):
        v = tool_buf[idx]
        tool_calls.append({"id": v["id"], "name": v["name"], "input": v["input"]})

    # Merge native-format tool calls intercepted from `content` (Gemma 3/4 etc.)
    if _native_intercept:
        intercepted = _extract_native_tool_calls(_native_buf)
        if intercepted:
            tool_calls.extend(intercepted)
        else:
            # Parser couldn't make sense of it — surface the raw buffer so the
            # user sees something instead of a silent stall.
            text += _native_buf
            yield TextChunk(_native_buf)

    # Merge prompt-based tools from parser
    if _prompt_tool_mode:
        for tc in parser.tool_calls:
            tool_calls.append(tc)

    # NOTE: Sanitizer temporarily disabled due to space issues
    # if is_deepseek_r1:
    #     text = _sanitize_deepseek_output(text)
    #     thinking = _sanitize_deepseek_output(thinking)

    # Ollama doesn't return exact token counts via livestream easily until "done",
    # but we can do a rough estimate or 0, dulus handles zero gracefully

    # For cloud-routed models: if text is empty (timing issue), retry once with longer wait
    if not text and not tool_calls and ":cloud" in model.lower():
        _time.sleep(2)
        try:
            req2 = _make_request(payload)
            text2 = ""
            thinking2 = ""
            with urllib.request.urlopen(req2) as resp2:
                for line in resp2:
                    if not line.strip(): continue
                    try:
                        data2 = json.loads(line)
                    except Exception: continue
                    msg2 = data2.get("message", {})
                    c2 = msg2.get("content", "") if "content" in msg2 else ""
                    if c2:
                        text2 += c2
                        yield TextChunk(c2)
                    for r_key in ["thinking", "reasoning", "thought", "reasoning_content"]:
                        if r_key in msg2 and msg2[r_key]:
                            thinking2 += msg2[r_key]
                            break
            yield AssistantTurn(text2 or "[ollama-cloud: no response]", [], 0, 0, thinking=thinking2)
        except Exception as _e:
            msg_err = f"[ollama-cloud] Retry failed: {_e}"
            yield TextChunk(msg_err)
            yield AssistantTurn(msg_err, [], 0, 0, error=True)
        return

    yield AssistantTurn(text, tool_calls, 0, 0, thinking=thinking)


def stream(
    model: str,
    system: str,
    messages: list,
    tool_schemas: list,
    config: dict,
) -> Generator:
    """
    Unified streaming entry point.
    Auto-detects provider from model string.
    Yields: TextChunk | ThinkingChunk | AssistantTurn

    All provider calls are wrapped with automatic retry on transient
    failures (timeouts, 429 rate-limit, 5xx server errors).
    """
    provider_name = detect_provider(model)
    model_name    = bare_model(model)
    prov          = PROVIDERS.get(provider_name, PROVIDERS["openai"])
    api_key       = get_api_key(provider_name, config)

    def _inner_stream() -> Generator:
        if prov["type"] == "claude_web":
            cookies_file = _claude_web_cookies_path(config)
            yield from stream_claude_web(cookies_file, model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "claude_code":
            cookies_file = _claude_web_cookies_path(config)
            yield from stream_claude_code(cookies_file, model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "kimi_web":
            auth_file = _kimi_web_auth_path(config)
            yield from stream_kimi_web(auth_file, model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "gemini-web":
            auth_file = _gemini_web_auth_path(config)
            yield from stream_gemini_web(auth_file, model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "deepseek_web":
            auth_file = _deepseek_web_auth_path(config)
            yield from stream_deepseek_web(auth_file, model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "qwen_web":
            auth_file = _qwen_web_auth_path(config)
            yield from stream_qwen_web(auth_file, model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "gcloud":
            yield from stream_gcloud(model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "litellm":
            yield from stream_litellm(model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "anthropic":
            yield from stream_anthropic(api_key, model_name, system, messages, tool_schemas, config)
        elif prov["type"] == "ollama":
            base_url = prov.get("base_url", "http://localhost:11434")
            yield from stream_ollama(base_url, model_name, system, messages, tool_schemas, config)
        elif provider_name in ("kimi", "moonshot"):
            # Use native Kimi HTTP implementation for testing/comparison
            yield from stream_kimi(api_key, model_name, system, messages, tool_schemas, config)
        else:
            import os as _os
            if provider_name == "custom":
                base_url = (config.get("custom_base_url")
                            or _os.environ.get("CUSTOM_BASE_URL", ""))
                if not base_url:
                    raise ValueError(
                        "custom provider requires a base_url. "
                        "Set CUSTOM_BASE_URL env var or run: /config custom_base_url=http://..."
                    )
            else:
                base_url = prov.get("base_url", "https://api.openai.com/v1")
            yield from stream_openai_compat(
                api_key, base_url, model_name, system, messages, tool_schemas, config
            )

    # Wrap with retry on transient failures
    yield from _ProviderRetry.wrap_generator(_inner_stream)


def list_ollama_models(base_url: str) -> list[str]:
    """Fetch locally available model tags from Ollama server."""
    try:
        url = f"{base_url.rstrip('/')}/api/tags"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Ollama returns {"models": [{"name": "llama3:latest", ...}, ...]}
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []
