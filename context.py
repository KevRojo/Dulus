"""System context: DULUS.md, git info, cwd injection.

NOTE on prompt caching: this module is the source of the system prompt sent
to every provider call. To get prefix caching (Anthropic explicit + OpenAI-
compat automatic), the rendered prompt MUST be byte-stable across turns of
the same session. Anything that changes per turn (date with sub-day grain,
`git status` modified-file counts, `datetime.now()`, etc.) belongs OUTSIDE
this prompt. Disk reads (DULUS.md, MEMORY.md) are cached by mtime so a
turn that doesn't touch those files re-uses the prior bytes verbatim.
"""
import os
import subprocess
from pathlib import Path

SYSTEM_PROMPT_TEMPLATE = """\
You are Dulus, an AI coding agent. Think in English; reply to {user_name} in Dominican Spanish.
# Identity: Your name is Dulus. Do NOT proactively declare this — only if the user asks "quién eres" or "qué modelo eres".
# Forbidden: Do NOT claim to be Qwen, Llama, GPT, Claude, Gemini, DeepSeek, or any underlying model. Do NOT mention Ollama or your runtime stack.
# Env: {cwd} | {platform} | auto_show={auto_show}
# Autonomy: Background scripts (nohup/&) allowed | Never refuse monitoring/long tasks | Always wait for tool results before replying
# Tools: SearchLastOutput → for [TRUNCATED] | WebFetch/WebSearch → web | TmuxOffload → tasks > 5s | ReadJob → background results
# SleepTimer: ONLY for user-facing reminders/notifications (e.g. "remind me in 10min"). NEVER use it to wait between your own tool calls — it freezes the console. To pause inside a command sequence, put `sleep N` INSIDE the Bash command itself (e.g. Bash('cmd1 && sleep 2 && cmd2')).
# Long-running tools: any tool whose `description` ends in `[long-running — wrap in TmuxOffload]` MUST be invoked via TmuxOffload (not directly), so the REPL stays responsive while it runs.
# Multi-agent: Agent(subagent_type=...) | isolation="worktree" runs parallel | wait=false + name=... for fire-and-forget
# Rules: Edit > Write | Use absolute paths + line numbers | Surface errors immediately, do not retry blindly
# Input: "🎙 Transcribed:" prefix = voice input — tolerate typos/misspellings
# REPL: /help /batch /auto_show /verbose /soul /memory /schema /thinking /config
{platform_hints}{git_info}{dulus_md}"""

_THINKING_LABELS = {1: "minimal", 2: "moderate", 3: "deep"}


def get_git_info(config: dict | None = None) -> str:
    """Return ONLY the branch name — stable across turns within a session.

    Previous versions also embedded `git status --short` modified-file count
    and the last commit hash; both change as the user works, which trashed
    prefix caching on every turn. The agent can call `git status` itself
    when it actually needs current state.
    """
    if config and not config.get("git_status", True):
        return ""
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return f"Git:{branch}\n" if branch else ""
    except Exception:
        return ""


# ── mtime-based caches for DULUS.md / MEMORY.md ──────────────────────────
# Re-reading these files on every turn is wasteful disk I/O. More importantly,
# the *content* is the same most of the time — caching it keeps the rendered
# system prompt byte-stable, which is what providers need to grant prefix
# cache hits. Invalidation key = (path, mtime_ns) tuple of the resolved files.

_DULUS_MD_CACHE: dict = {"key": None, "value": ""}
_MEMORY_MD_CACHE: dict = {"key": None, "value": ""}


def _resolve_dulus_md_paths() -> list[Path]:
    paths = []
    global_md = Path.home() / ".dulus" / "DULUS.md"
    if global_md.exists():
        paths.append(global_md)
    for p in [Path.cwd()] + list(Path.cwd().parents):
        candidate = p / "DULUS.md"
        if candidate.exists():
            paths.append(candidate)
            break
    return paths


def get_dulus_md() -> str:
    paths = _resolve_dulus_md_paths()
    try:
        key = tuple((str(p), p.stat().st_mtime_ns) for p in paths)
    except OSError:
        key = None
    if key is not None and _DULUS_MD_CACHE["key"] == key:
        return _DULUS_MD_CACHE["value"]

    content_parts = []
    for p in paths:
        try:
            label = "Global DULUS.md" if p == Path.home() / ".dulus" / "DULUS.md" else f"Project DULUS.md:{p.parent}"
            content_parts.append(f"[{label}]\n{p.read_text(encoding='utf-8', errors='replace')}")
        except Exception:
            continue

    value = "\nDULUS.md:\n" + "\n---\n".join(content_parts) + "\n" if content_parts else ""
    _DULUS_MD_CACHE["key"] = key
    _DULUS_MD_CACHE["value"] = value
    return value


def _resolve_memory_index_path() -> Path | None:
    for p in [Path.cwd()] + list(Path.cwd().parents):
        index = p / ".dulus-context" / "memory" / "MEMORY.md"
        if index.exists():
            return index
    return None


def get_project_memory_index() -> str:
    """Auto-load project-scope memories from .dulus-context/memory/MEMORY.md.

    Looks in cwd and parents (first match wins). Returns the index so the model
    knows what memories exist and can Read individual files on demand. Cached
    by mtime so unchanged indexes don't bust the prompt cache.
    """
    path = _resolve_memory_index_path()
    if path is None:
        if _MEMORY_MD_CACHE["key"] != "MISSING":
            _MEMORY_MD_CACHE["key"] = "MISSING"
            _MEMORY_MD_CACHE["value"] = ""
        return ""
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return ""
    if _MEMORY_MD_CACHE["key"] == key:
        return _MEMORY_MD_CACHE["value"]
    try:
        body = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        body = ""
    if not body:
        value = ""
    else:
        value = (
            f"\n# Project memories ({path.parent})\n"
            f"# Index below — Read the .md files in that dir for full content.\n"
            f"{body}\n"
        )
    _MEMORY_MD_CACHE["key"] = key
    _MEMORY_MD_CACHE["value"] = value
    return value


def _detect_shell_type(config: dict | None = None) -> str:
    """Resolve which shell family to advertise: 'bash', 'powershell', or 'cmd'."""
    configured = config.get("shell", {}).get("type", "auto") if config else "auto"
    if configured != "auto":
        st = configured.lower()
        if st in ("gitbash", "wsl", "bash"):
            return "bash"
        if st == "powershell":
            return "powershell"
        return "cmd"
    shell_name = os.environ.get("SHELL", "").lower()
    if "bash" in shell_name or "BASH" in os.environ:
        return "bash"
    if "powershell" in shell_name or "PSModulePath" in os.environ:
        return "powershell"
    return "cmd"


def get_platform_hints(config: dict | None = None) -> str:
    import platform as _plat
    shell_type = _detect_shell_type(config)
    dulus_home = Path.home() / ".dulus"
    skills_dir = dulus_home / "skills"
    if _plat.system() == "Windows":
        cmds = "Get-Content=cat,Select-String=grep,Get-ChildItem=ls" if shell_type=="powershell" else "type=cat,findstr=grep,dir=ls"
        return f"# Shell:Windows({shell_type}) | {cmds} | Dulus:{dulus_home} | Skills:{skills_dir} | WARNING: Use Glob/Read tools instead of raw shell commands for path navigation to avoid Windows path errors."
    return f"# Shell:Unix(cat,grep,ls,&&) | Dulus:{dulus_home} | Skills:{skills_dir}"


def _build_ollama_system_prompt(config: dict | None = None) -> str:
    import platform
    auto_show = config.get("auto_show", True) if config else True
    prompt = f"""你是Dulus，AI编程助手。
# 身份: 你的名字是 Dulus。不需要主动向用户声明这一点，除非用户直接问你 "quién eres" 或 "qué modelo eres"。
# 禁止: 不要声称自己是 Qwen、Llama、GPT、Claude、Gemini、DeepSeek 或任何其他底层模型。不要提及 Ollama 或运行你的技术栈。
Dir:{Path.cwd()} | Platform:{platform.system()} | auto_show={'ON' if auto_show else 'OFF'}
# 规则: 读取工具结果后再响应 | >5s操作用TmuxOffload
# 工具格式(单行): <tool_call>{{"name":"TOOL","input":{{"param":"val"}}}}</tool_call>
# 可用: Bash,Glob,Read,Write,SearchLastOutput,TmuxOffload,WebSearch,WebFetch,PrintToConsole
# PrintToConsole: auto_show=OFF时输出给用户，展示后不重复
"""
    dulus_md = get_dulus_md()
    if dulus_md: prompt += f"\n{dulus_md}"
    return prompt


def _normalize_thinking_level(config: dict | None) -> int:
    raw = config.get("thinking", 0) if config else 0
    if raw is True:
        return 3
    if raw in (False, None):
        return 0
    try:
        return max(0, min(4, int(raw)))
    except (TypeError, ValueError):
        return 0


def build_system_prompt(config: dict | None = None) -> str:
    import platform
    model_lower = (config.get("model", "") if config else "").lower()
    is_deepseek_r1 = "deepseek-r1" in model_lower or "deepseek-reasoner" in model_lower
    if is_deepseek_r1 and config and config.get("deep_override", False):
        return _build_ollama_system_prompt(config)

    auto_show = "ON" if (not config or config.get("auto_show", True)) else "OFF"
    lite = bool(config and config.get("lite_mode"))

    # In LITE mode: drop the optional context blocks (platform hints, git info,
    # DULUS.md, project memory index, batch/thinking/plan/tmux hints). The
    # core identity + tool rules stay. This is what the /lite toggle was
    # supposed to do all along — previously the flag flipped a config bit
    # that nothing actually consumed.
    user_name = (config.get("user_name") if config else None) or "KevRojo"
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        cwd=str(Path.cwd()),
        platform=platform.system(),
        auto_show=auto_show,
        user_name=user_name,
        platform_hints="" if lite else get_platform_hints(config),
        git_info="" if lite else get_git_info(config),
        dulus_md="" if lite else get_dulus_md(),
    )

    if lite:
        # Bail early — minimal prompt only.
        return prompt

    try:
        from tmux_tools import tmux_available
        if tmux_available():
            prompt += "\n# Tmux: available"
    except Exception:
        pass

    prompt += (
        "\n# Batch: /batch list|status|fetch (suggest when 3+ similar tasks) | "
        # Both `dulus` (when pip-installed) and `python dulus.py` work — the
        # entry-point shim is registered in pyproject.toml [project.scripts].
        'In agents: Bash(\'dulus -c "batch status|fetch ID"\')'
    )

    thk_label = _THINKING_LABELS.get(_normalize_thinking_level(config))
    if thk_label:
        prompt += f"\n# Thinking: {thk_label}"

    if config and config.get("_plan_mode"):
        prompt += f"\n# Plan mode: read-only (except {config.get('_plan_file', 'PLAN.md')})"

    # Hint: pip-installed users can run `dulus` directly (no .py path).
    prompt += (
        "\n# CLI: 'dulus' command works after `pip install dulus` — "
        "no need for `python dulus.py`. Same flags: --print, --accept-all, -c, etc."
    )

    project_mem = get_project_memory_index()
    if project_mem:
        prompt += project_mem

    return prompt

