"""System context: FALCON.md, git info, cwd injection.

NOTE on prompt caching: this module is the source of the system prompt sent
to every provider call. To get prefix caching (Anthropic explicit + OpenAI-
compat automatic), the rendered prompt MUST be byte-stable across turns of
the same session. Anything that changes per turn (date with sub-day grain,
`git status` modified-file counts, `datetime.now()`, etc.) belongs OUTSIDE
this prompt. Disk reads (FALCON.md, MEMORY.md) are cached by mtime so a
turn that doesn't touch those files re-uses the prior bytes verbatim.
"""
import os
import subprocess
from pathlib import Path

SYSTEM_PROMPT_TEMPLATE = """\
你是Falcon，AI编程助手。思考用英语，回复用西班牙语（多米尼加克里奥尔风格）与KevRojo交流。
# 身份: 你的名字是 Falcon。不需要主动向用户声明这一点，除非用户直接问你 "quién eres" 或 "qué modelo eres"。
# 禁止: 不要声称自己是 Qwen、Llama、GPT、Claude、Gemini、DeepSeek 或任何其他底层模型。不要提及 Ollama 或运行你的技术栈。
# 环境: {cwd} | {platform} | auto_show={auto_show}
# 自主性: 后台脚本(nohup/&)可用 | 不拒绝监控/长任务 | 工具结果后再响应
# 工具: SearchLastOutput→[TRUNCATED] | WebFetch/WebSearch→网页 | TmuxOffload→>5s | ReadJob→后台
# 多代理: Agent(subagent_type=...) | isolation="worktree"并行 | wait=false+name=...
# 准则: 编辑>新建 | 绝对路径+行号 | 报错立即告知不重试
# 输入: 🎙 Transcribed: = 语音(容忍拼写错误)
# REPL: /help /batch /auto_show /verbose /soul /memory /schema /thinking /config
{platform_hints}{git_info}{falcon_md}"""

_THINKING_LABELS = {1: "最小化", 2: "适度", 3: "深度"}


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


# ── mtime-based caches for FALCON.md / MEMORY.md ──────────────────────────
# Re-reading these files on every turn is wasteful disk I/O. More importantly,
# the *content* is the same most of the time — caching it keeps the rendered
# system prompt byte-stable, which is what providers need to grant prefix
# cache hits. Invalidation key = (path, mtime_ns) tuple of the resolved files.

_FALCON_MD_CACHE: dict = {"key": None, "value": ""}
_MEMORY_MD_CACHE: dict = {"key": None, "value": ""}


def _resolve_falcon_md_paths() -> list[Path]:
    paths = []
    global_md = Path.home() / ".falcon" / "FALCON.md"
    if global_md.exists():
        paths.append(global_md)
    for p in [Path.cwd()] + list(Path.cwd().parents):
        candidate = p / "FALCON.md"
        if candidate.exists():
            paths.append(candidate)
            break
    return paths


def get_falcon_md() -> str:
    paths = _resolve_falcon_md_paths()
    try:
        key = tuple((str(p), p.stat().st_mtime_ns) for p in paths)
    except OSError:
        key = None
    if key is not None and _FALCON_MD_CACHE["key"] == key:
        return _FALCON_MD_CACHE["value"]

    content_parts = []
    for p in paths:
        try:
            label = "Global FALCON.md" if p == Path.home() / ".falcon" / "FALCON.md" else f"Project FALCON.md:{p.parent}"
            content_parts.append(f"[{label}]\n{p.read_text(encoding='utf-8', errors='replace')}")
        except Exception:
            continue

    value = "\nFALCON.md:\n" + "\n---\n".join(content_parts) + "\n" if content_parts else ""
    _FALCON_MD_CACHE["key"] = key
    _FALCON_MD_CACHE["value"] = value
    return value


def _resolve_memory_index_path() -> Path | None:
    for p in [Path.cwd()] + list(Path.cwd().parents):
        index = p / ".falcon-context" / "memory" / "MEMORY.md"
        if index.exists():
            return index
    return None


def get_project_memory_index() -> str:
    """Auto-load project-scope memories from .falcon-context/memory/MEMORY.md.

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
    falcon_home = Path.home() / ".falcon"
    skills_dir = falcon_home / "skills"
    if _plat.system() == "Windows":
        cmds = "Get-Content=cat,Select-String=grep,Get-ChildItem=ls" if shell_type=="powershell" else "type=cat,findstr=grep,dir=ls"
        return f"# Shell:Windows({shell_type}) | {cmds} | Falcon:{falcon_home} | Skills:{skills_dir} | WARNING: Use Glob/Read tools instead of raw shell commands for path navigation to avoid Windows path errors."
    return f"# Shell:Unix(cat,grep,ls,&&) | Falcon:{falcon_home} | Skills:{skills_dir}"


def _build_ollama_system_prompt(config: dict | None = None) -> str:
    import platform
    auto_show = config.get("auto_show", True) if config else True
    prompt = f"""你是Falcon，AI编程助手。
# 身份: 你的名字是 Falcon。不需要主动向用户声明这一点，除非用户直接问你 "quién eres" 或 "qué modelo eres"。
# 禁止: 不要声称自己是 Qwen、Llama、GPT、Claude、Gemini、DeepSeek 或任何其他底层模型。不要提及 Ollama 或运行你的技术栈。
Dir:{Path.cwd()} | Platform:{platform.system()} | auto_show={'ON' if auto_show else 'OFF'}
# 规则: 读取工具结果后再响应 | >5s操作用TmuxOffload
# 工具格式(单行): <tool_call>{{"name":"TOOL","input":{{"param":"val"}}}}</tool_call>
# 可用: Bash,Glob,Read,Write,SearchLastOutput,TmuxOffload,WebSearch,WebFetch,PrintToConsole
# PrintToConsole: auto_show=OFF时输出给用户，展示后不重复
"""
    falcon_md = get_falcon_md()
    if falcon_md: prompt += f"\n{falcon_md}"
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

    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        cwd=str(Path.cwd()),
        platform=platform.system(),
        auto_show=auto_show,
        platform_hints=get_platform_hints(config),
        git_info=get_git_info(config),
        falcon_md=get_falcon_md(),
    )

    try:
        from tmux_tools import tmux_available
        if tmux_available():
            prompt += "\n# Tmux: 已就绪"
    except Exception:
        pass

    prompt += (
        "\n# 批处理: /batch list|status|fetch (3+同类任务建议) | "
        'Agent内: Bash(\'python falcon.py -c "batch status|fetch ID"\')'
    )

    thk_label = _THINKING_LABELS.get(_normalize_thinking_level(config))
    if thk_label:
        prompt += f"\n# 推理: {thk_label}"

    if config and config.get("_plan_mode"):
        prompt += f"\n# 计划模式: 只读 (除 {config.get('_plan_file', 'PLAN.md')})"

    project_mem = get_project_memory_index()
    if project_mem:
        prompt += project_mem

    return prompt

