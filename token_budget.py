from __future__ import annotations
from typing import NamedTuple
CONTEXT_SAFETY_MARGIN = 2048
MIN_COMPLETION = 512
MIN_ANSWER = 1024
MIN_THINKING = 1024
DEFAULT_CONTEXT = 128000
DEFAULT_OUTPUT = 8192
LOCAL_PROVIDERS = ('ollama', 'lmstudio')
LOCAL_CONTEXT_AUTO = 32768
_LEVEL_BUDGETS = {1: 2048, 2: 6000, 3: 16000, 4: 16000}
_FAMILIES: list[tuple[str, int, int]] = [('claude-3-5', 200000, 8192), ('claude-3-7', 200000, 64000), ('claude-3', 200000, 4096), ('claude-haiku', 200000, 64000), ('claude-sonnet', 200000, 64000), ('claude-opus', 200000, 64000), ('claude', 200000, 32000), ('gpt-5', 400000, 128000), ('gpt-4.1', 1000000, 32768), ('gpt-4o', 128000, 16384), ('gpt-oss', 128000, 32768), ('o1', 200000, 100000), ('o3', 200000, 100000), ('o4', 200000, 100000), ('gemini-2.0', 1000000, 8192), ('gemini', 1000000, 65536), ('k3-256k', 262144, 32768), ('k3', 1000000, 32768), ('kimi', 262144, 32768), ('moonshot', 131072, 32768), ('deepseek', 128000, 8192), ('glm', 200000, 32768), ('qwen', 262144, 32768), ('grok', 131072, 32768), ('llama', 131072, 8192), ('mistral', 131072, 8192), ('mixtral', 32768, 8192), ('gemma', 131072, 8192), ('phi', 131072, 8192)]

class Budget(NamedTuple):
    context: int
    output: int
    thinking: int

    def as_dict(self) -> dict:
        return {'context': self.context, 'output': self.output, 'thinking': self.thinking}

def _wire(model) -> str:
    w = str(model or '').strip().lower()
    if '/' in w:
        w = w.rsplit('/', 1)[-1]
    for prefix in ('chatgpt-', 'codex-'):
        if w.startswith(prefix):
            w = w[len(prefix):]
            break
    return w

def _family_limits(model) -> tuple[int, int] | None:
    w = _wire(model)
    if not w:
        return None
    for prefix, ctx, out in _FAMILIES:
        if w.startswith(prefix):
            return (ctx, out)
    return None

def _provider_entry(model, provider: str='') -> tuple[str, dict]:
    try:
        import providers as _p
    except Exception:
        return (provider or '', {})
    name = provider or _p.detect_provider(model)
    return (name, _p.PROVIDERS.get(name, {}) or {})

def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def context_window(model, config: dict | None=None, provider: str='') -> int:
    name, prov = _provider_entry(model, provider)
    real = _int(prov.get('model_context_limits', {}).get(_bare(model)))
    if not real:
        real = _int(prov.get('context_limit'))
    if not real:
        fam = _family_limits(model)
        real = fam[0] if fam else 0
    if not real:
        real = DEFAULT_CONTEXT
    want = _int((config or {}).get('context_limit'))
    return min(want, real) if want > 0 else real

def is_local(model, provider: str='') -> bool:
    return _provider_entry(model, provider)[0] in LOCAL_PROVIDERS

def local_num_ctx(model, config: dict | None=None, provider: str='') -> int:
    window = context_window(model, config, provider)
    if _int((config or {}).get('context_limit')) > 0:
        return window
    return min(window, LOCAL_CONTEXT_AUTO)

def output_cap(model, config: dict | None=None, provider: str='', prompt_tokens: int=0) -> int:
    name, prov = _provider_entry(model, provider)
    fam = _family_limits(model)
    limit = fam[1] if fam else 0
    prov_cap = _int(prov.get('max_completion_tokens'))
    if prov_cap:
        limit = min(limit, prov_cap) if limit else prov_cap
    if not limit:
        limit = DEFAULT_OUTPUT
    want = _int((config or {}).get('max_tokens'))
    cap = min(want, limit) if want > 0 else limit
    window = local_num_ctx(model, config, name) if name in LOCAL_PROVIDERS else context_window(model, config, name)
    room = window - max(prompt_tokens, 0) - CONTEXT_SAFETY_MARGIN
    cap = min(cap, max(room, MIN_COMPLETION))
    floor = min(want, MIN_COMPLETION) if want > 0 else MIN_COMPLETION
    return max(cap, floor)

def thinking_budget(model, config: dict | None=None, provider: str='', level: int | None=None, out_cap: int | None=None) -> int:
    if level is None:
        level = _thinking_level((config or {}).get('thinking', 0))
    if level <= 0:
        return 0
    cap = out_cap if out_cap is not None else output_cap(model, config, provider)
    if cap - MIN_ANSWER < MIN_THINKING:
        return 0
    want = _int((config or {}).get('thinking_budget'))
    budget = want if want > 0 else _LEVEL_BUDGETS.get(level, _LEVEL_BUDGETS[3])
    return max(min(budget, cap - MIN_ANSWER), MIN_THINKING)

def resolve(model, config: dict | None=None, provider: str='', prompt_tokens: int=0, level: int | None=None) -> Budget:
    name, _prov = _provider_entry(model, provider)
    ctx = context_window(model, config, name)
    out = output_cap(model, config, name, prompt_tokens)
    if level is None:
        level = _thinking_level((config or {}).get('thinking', 0))
    think = 0
    if level > 0:
        headroom = output_cap(model, {**(config or {}), 'max_tokens': 0}, name, prompt_tokens)
        want = _int((config or {}).get('thinking_budget')) or _LEVEL_BUDGETS.get(level, _LEVEL_BUDGETS[3])
        if _int((config or {}).get('max_tokens')) > 0:
            out = min(max(out, MIN_THINKING + MIN_ANSWER), headroom)
        else:
            out = min(max(out, min(want + MIN_ANSWER, headroom)), headroom)
        think = thinking_budget(model, config, name, level, out)
    return Budget(context=ctx, output=out, thinking=think)

def describe(model, config: dict | None=None, provider: str='') -> str:
    b = resolve(model, config, provider)
    think = f'{b.thinking:,}' if b.thinking else 'off'
    return f"context {b.context:,} · output {b.output:,} · thinking {think}  (model: {_wire(model) or 'unknown'})"

def _bare(model) -> str:
    m = str(model or '').strip()
    return m.rsplit('/', 1)[-1] if '/' in m else m

def _thinking_level(value) -> int:
    if isinstance(value, bool):
        return 4 if value else 0
    if isinstance(value, (int, float)):
        return max(0, min(4, int(value)))
    s = str(value or '').strip().lower()
    if s in ('off', 'false', 'no', '0', ''):
        return 0
    if s in ('low', '1'):
        return 1
    if s in ('medium', 'med', '2'):
        return 2
    if s in ('high', '3'):
        return 3
    if s in ('on', 'true', 'yes', '4', 'max', 'ultra'):
        return 4
    return 0
