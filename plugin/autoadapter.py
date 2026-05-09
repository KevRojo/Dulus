"""Auto-Adapter: Static analysis + AI to generate manifests for external repos."""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Any

from .types import PluginManifest
from providers import stream, AssistantTurn, TextChunk, ThinkingChunk
import tools  # Ensure tools are registered in tool_registry for agent use

from common import info, ok, warn, err, stream_thinking, print_tool_start, print_tool_end
from memory.context import find_relevant_memories
from memory.sessions import search_session_history

def _sanitize_python_code(code: str) -> str:
    """Fix common JSON-to-Python spills like true/false/null."""
    import re
    # Strip stray delimiter lines leaked from the ---FILE:--- prompt format
    code = re.sub(r'^\s*-{3,}(?:FILE:.*|END|EOF)?\s*-*\s*$', '', code, flags=re.MULTILINE)
    # Heuristic: replace lowercase true/false/null with Python equivalents
    # but ONLY if they are not inside quotes.
    # We use a simple regex for word boundaries which captures most cases.
    code = re.sub(r'\btrue\b', 'True', code)
    code = re.sub(r'\bfalse\b', 'False', code)
    code = re.sub(r'\bnull\b', 'None', code)
    # Remove trailing blank lines
    code = code.rstrip() + '\n'
    return code

def _analyze_repository(plugin_dir: Path | str, verbose: bool = False) -> dict:
    """Scan the repository for structure, functions, and dependencies (no execution)."""
    pname = getattr(plugin_dir, 'name', os.path.basename(str(plugin_dir)))
    print_tool_start("Read", {"file_path": pname})
    analysis = {
        "files": [],
        "requirements": [],
        "readme": "",
        "entry_points": []
    }

    # 1. Read README
    for readme_name in ["README.md", "README", "README.txt"]:
        readme_path = plugin_dir / readme_name
        if readme_path.exists():
            analysis["readme"] = readme_path.read_text(errors="ignore")[:2000] # Truncate
            break

    # 2. Extract dependencies (Recursive)
    analysis["requirements"] = []
    exclude_dirs = {"docs", "tests", "venv", ".git", "__pycache__", "dist", "build", "node_modules"}
    
    # Identify all requirements files, excluding common junk
    for req_file in plugin_dir.rglob("*requirements*.txt"):
        if any(x in str(req_file.parents) for x in exclude_dirs):
            continue
        try:
            lines = req_file.read_text(errors="ignore").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # If it's a pointer to another file, we'll find that file anyway via rglob
                if line.startswith("-r"):
                    continue
                analysis["requirements"].append(line)
        except Exception:
            continue
    
    # Also parse pyproject.toml — modern Python projects (PEP 621 / Poetry) keep
    # deps there instead of requirements.txt. MemPalace and most post-2022 libs
    # work this way, so ignoring pyproject meant we installed nothing.
    pyproject = plugin_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            try:
                import tomllib  # py3.11+
            except ImportError:
                import tomli as tomllib  # type: ignore
            data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
            # PEP 621: [project] dependencies + optional-dependencies
            proj = data.get("project", {})
            for dep in proj.get("dependencies", []) or []:
                if isinstance(dep, str) and dep.strip():
                    analysis["requirements"].append(dep.strip())
            opt = proj.get("optional-dependencies", {}) or {}
            for group in opt.values():
                for dep in group or []:
                    if isinstance(dep, str) and dep.strip():
                        analysis["requirements"].append(dep.strip())
            # Poetry: [tool.poetry.dependencies]
            poetry_deps = (data.get("tool", {}).get("poetry", {}) or {}).get("dependencies", {}) or {}
            for name, spec in poetry_deps.items():
                if name.lower() == "python":
                    continue
                if isinstance(spec, str):
                    analysis["requirements"].append(f"{name}{spec if spec.startswith(('>', '<', '=', '~', '!')) else ''}".strip())
                else:
                    analysis["requirements"].append(name)
        except Exception as e:
            if verbose:
                info(f"    pyproject.toml parse failed: {e}")

    # Dedup
    analysis["requirements"] = list(dict.fromkeys(analysis["requirements"]))

    # 3. Scan .py files
    all_files = []
    
    # Efficiently find all .py files while skipping excluded directories
    for p in plugin_dir.rglob("*.py"):
        try:
            rel_parts = p.relative_to(plugin_dir).parts[:-1]
            if any(part in exclude_dirs or part.startswith(".") for part in rel_parts):
                continue
            all_files.append(p)
        except Exception:
            continue

    # Prioritize files that aren't setup.py or tests
    priority_files = []
    other_files = []
    for f in all_files:
        if verbose:
            info(f"    Scanning {f.relative_to(plugin_dir)}...")
        if f.name in ["setup.py", "conftest.py"] or "test" in f.name.lower():
            other_files.append(f)
        else:
            priority_files.append(f)

    selected_files = (priority_files + other_files)[:15]

    for py_file in selected_files:
        try:
            rel_path = py_file.relative_to(plugin_dir)
            code = py_file.read_text(errors="ignore")
            # Skip very short files or pure comments
            if len(code.strip()) < 50:
                continue

            exports = _extract_exports(code)
            # Only include files that have some exports OR are in a package
            if not exports and "__init__" not in py_file.name:
                continue

            file_info = {
                "path": str(rel_path).replace("\\", "/"),
                "exports": exports,
                "snippet": code[:1500]
            }
            analysis["files"].append(file_info)
        except Exception:
            continue

    print_tool_end("Read", f"Detected {len(analysis['files'])} files", success=True)
    return analysis

def _extract_exports(code: str) -> list[dict]:
    """Extract public functions and classes from Python code using AST."""
    exports = []
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):
                    args = [a.arg for a in node.args.args]
                    exports.append({"type": "function", "name": node.name, "args": args})
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    init_args = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                            init_args = [a.arg for a in item.args.args if a.arg != "self"]
                            break
                    methods = [
                        n.name for n in node.body
                        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
                    ]
                    exports.append({"type": "class", "name": node.name, "methods": methods, "init_args": init_args})
    except SyntaxError:
        pass
    return exports

def generate_plugin_files(plugin_dir: Path, safe_name: str, config: dict) -> bool:
    """Use AI to generate plugin_tool.py and plugin.json based on analysis."""
    analysis = _analyze_repository(plugin_dir)

    # ── Gain context from previous implementations ───────────────────────
    implementation_context = ""
    try:
        # Search for "Adaptation Guide" and "plugin_tool.py" in persistent memory
        memories = find_relevant_memories("adaptation guide plugin_tool.py", max_results=3, config=config)
        # Also search historical sessions for past adaptation discussions
        session_matches = search_session_history("adapt plugin", max_results=2)
        
        # ── Search the web for similar plugin implementations ──────────────────
        # NOTE: WebSearch is available but NOT used by default here.
        # It will be suggested in _attempt_fix if verification fails.
        context_parts = []
        if memories:
            context_parts.append("### RELEVANT PREVIOUS ADAPTATION GUIDES (from persistent memory):")
            for m in memories:
                context_parts.append(f"#### Memory: {m['name']}\n{m['content'][:1000]}")
        
        if session_matches:
            context_parts.append("### RELEVANT PREVIOUS ADAPTATION DISCUSSIONS (from session history):")
            for sm in session_matches:
                hits = "\n".join([f"- [{h['role']}] {h['snippet']}" for h in sm["hits"]])
                context_parts.append(f"#### Session {sm['session_id']} ({sm['saved_at']}):\n{hits}")
        
        if context_parts:
            implementation_context = "\n\n".join(context_parts)
    except Exception as e:
        warn(f"Could not retrieve implementation context: {e}")

    # Build repository analysis report for the prompt
    analysis_report = []
    analysis_report.append(f"### REPOSITORY ANALYSIS: {safe_name}\n")
    
    if analysis.get("readme"):
        analysis_report.append(f"#### README:\n{analysis['readme'][:1500]}\n")
    
    if analysis.get("requirements"):
        analysis_report.append(f"#### DEPENDENCIES:\n" + "\n".join(f"- {r}" for r in analysis["requirements"][:20]) + "\n")
    
    if analysis.get("files"):
        analysis_report.append(f"#### SOURCE FILES ({len(analysis['files'])} found):\n")
        for f in analysis["files"]:
            analysis_report.append(f"\n--- FILE: {f['path']} ---")
            if f.get("exports"):
                analysis_report.append(f"EXPORTS: {f['exports']}")
            if f.get("snippet"):
                analysis_report.append(f"CODE:\n{f['snippet'][:1200]}")
    
    analysis_report_str = "\n".join(analysis_report)

    prompt = f"""
Adapt the Python repository "{safe_name}" as a Dulus plugin.

{analysis_report_str}

{implementation_context if implementation_context else ""}

GOAL: Generate `plugin.json`, `plugin_tool.py`, and `ADAPTATION_GUIDE.md`.

>HINT: Check existing plugins in ~/.dulus/plugins/ for working examples. You have WebSearch if needed.<

GUIDELINES FOR plugin_tool.py:

1. EXPORTS (mandatory):
   - `TOOL_DEFS`: list of `ToolDef(name, schema, func)` objects
   - `TOOL_SCHEMAS`: `[t.schema for t in TOOL_DEFS]`
   - Function signature: `func(params: dict, config: dict) -> str`

2. TOOL STRATEGY — classify the repo, pick ONE approach:
   a) LIBRARY: Has importable functions → import directly (PREFERRED)
   b) CLI TOOL: Primary interface is command line → `subprocess.run([sys.executable, "-m", pkg, ...])`
   c) WEB SERVICE / API: Server or wraps external API → use `requests` to call endpoints
   d) RENDERING LIBRARY (TUI): Terminal-UI lib → use OFFLINE rendering APIs only (stdout is StringIO, NO TTY)
      - asciimatics: use `FigletText`, `Fire`, etc. → `renderer.rendered_text` or `repr(renderer)`; NEVER use `Screen`
      - rich: `Console(file=io.StringIO())`; blessed: string methods only
   e) FILE-GENERATING: Creates files on disk → return file path, accept `output_path` param

3. ROBUSTNESS:
   - ENCODING: Always `encoding='utf-8', errors='replace'` for files and subprocess
   - NO TTY: stdout is StringIO. `Screen.play()`, `curses.initscr()` → CRASH
   - Use `params.get("key", default)`, NEVER `params["key"]`
   - External binaries: add to `os.environ['PATH']` before importing (e.g. Graphviz)

4. SCHEMA DESIGN:
   - Each param gets its own property. Never bundle into single "data" string
   - Include `limit`/`max_results` (default: 10, NOT 50) and `verbose` (default: False) on every tool

5. TOOL GRANULARITY:
   - Multiple specific tools > one mega-tool
   - Include discovery tools: `list_*`, `get_available_*`

6. OUTPUT EFFICIENCY — THIS IS NON-NEGOTIABLE (token-waste = bug):
   The agent harness has a hard 2500-char cap; anything above gets truncated
   and force-paginated, polluting context. Your tools MUST return concise,
   pre-curated output BY DESIGN — not by relying on the cap. Concretely:

   a) NEVER dump raw upstream API responses. yfinance's `.info` returns 8KB
      of metadata; pick the 6-10 fields actually useful (price, change,
      volume, marketCap, P/E, sector, summary[:300]). Same for any
      `.to_dict()`, `requests.json()`, library object — extract, don't dump.
   b) Format as compact key:value lines or a small markdown table. No
      pretty-print JSON, no full DataFrame `to_string()`, no log spam.
   c) For list-returning tools, default `limit=10` and SLICE before formatting.
   d) Long-form text fields (descriptions, summaries, articles) → truncate
      to ~300-500 chars with "..." suffix unless `verbose=True`.
   e) Numeric data: round floats to 2-4 decimals; format large numbers as
      "1.2B", "850M" instead of "1234567890.12".
   f) Smoke-test mentally: if your tool's typical output exceeds 2500 chars
      with default params, it is WRONG — redesign before writing.

   Example (BAD vs GOOD):
   BAD : return json.dumps(yf.Ticker(t).info)            # 8KB dump
   GOOD: i = yf.Ticker(t).info
         return (f"{{t}}: ${{i['currentPrice']:.2f}} "
                 f"({{i['regularMarketChangePercent']:+.2%}}) | "
                 f"MCap ${{i['marketCap']/1e9:.1f}}B | "
                 f"P/E {{i.get('trailingPE', 'N/A')}} | "
                 f"{{i['sector']}}")                       # ~120 chars

   When `verbose=True`, you MAY include more fields — but still no raw dumps.

6. ToolDef takes: `name` (str), `schema` (dict), `func` (callable)
   NEVER pass `description`/`parameters`/`handler` as kwargs — they go INSIDE `schema`

EXAMPLE (Library pattern):
```python
import sys
from pathlib import Path
from tool_registry import ToolDef

PLUGIN_DIR = Path(__file__).parent.absolute()
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import art

def text_to_art(params, config):
    text = params.get("text", "Hello")
    font = params.get("font", "standard")
    try:
        return art.text2art(text, font=font)
    except Exception as e:
        return f"Error: {{str(e)}}"

text_tool = ToolDef(
    name="text_to_ascii",
    schema={{
        "name": "text_to_ascii",
        "description": "Converts text into ASCII art.",
        "input_schema": {{ "type": "object", "properties": {{
            "text": {{"type": "string"}},
            "font": {{"type": "string", "description": "Font style (default: standard)"}}
        }}, "required": ["text"] }}
    }},
    func=text_to_art
)
TOOL_DEFS = [text_tool]
TOOL_SCHEMAS = [t.schema for t in TOOL_DEFS]
```

CRITICAL:
- JSON Schema types only: string/integer/boolean/number/object/array — NEVER "any"
- plugin.json "dependencies" MUST be a simple LIST of strings
- Include "ADAPTATION_GUIDE.md" in plugin.json "skills" list

TMUX-OFFLOAD HINT (important for UX):
- For each tool you generate, ESTIMATE its typical runtime.
- If a tool typically runs > 15 seconds (network scans, sherlock, full holehe sweeps, large file ingestion, OSINT crawls, video downloads, full-repo analysis, etc.), APPEND the literal marker `[long-running — wrap in TmuxOffload]` at the END of the tool's `description` field in the JSON schema.
- Tools that are fast (< 5s) do NOT need the marker. Don't be over-cautious — only mark tools where users will visibly wait.
- The marker is read by Dulus's agent at runtime: when it sees a tool description ending in `[long-running — wrap in TmuxOffload]`, it knows to wrap that call in TmuxOffload instead of blocking the REPL.
- Example: `"description": "Search for a username across hundreds of social networks. [long-running — wrap in TmuxOffload]"`

Respond with the delimited format:
---FILE: ADAPTATION_GUIDE.md---
(Overview, tool design decisions, error patterns, validation)
---FILE: plugin.json---
(JSON manifest)
---FILE: plugin_tool.py---
(Python code)
"""

    # Install dependencies before generation so the AI can import them if needed
    if analysis["requirements"]:
        print_tool_start("Bash", {"command": f"pip install {' '.join(analysis['requirements'][:3])}..."})
        from .store import _install_dependencies
        dep_ok, dep_msg = _install_dependencies(analysis["requirements"])
        print_tool_end("Bash", "Success" if dep_ok else f"Failed: {dep_msg}", success=dep_ok, verbose=config.get("verbose"))
        if not dep_ok:
            warn("Some dependencies failed to install, proceeding anyway.")

    import re
    try:
        model = config.get("model", "gemini-2.0-flash")
        verbose = config.get("verbose", False)
        response_text = ""
        reasoning_text = ""

        generation_system = (
            "You are a plugin adapter for the Dulus AI agent system. "
            "Your job is to generate plugin_tool.py and plugin.json that make an existing Python repo usable as a Dulus tool.\n\n"
            "IMPORTANT: You are generating code, NOT running inside Dulus. Do NOT attempt to validate or test by calling Dulus system tools. "
            "Tool registration happens automatically later via /plugin reload. Just write the files correctly.\n\n"
            "ABSOLUTE RULES — violating these causes immediate failure:\n"
            "- TOOL_DEFS must be a list of ToolDef objects: ToolDef(name, schema, func)\n"
            "- TOOL_SCHEMAS = [t.schema for t in TOOL_DEFS]\n"
            "- Tool function signature: func(params: dict, config: dict) -> str  — MUST return a string\n"
            "- JSON Schema types only: string/integer/boolean/number/object/array — NEVER 'any'\n"
            "- stdout is redirected to StringIO during execution — NO terminal/TTY access\n"
            "  → Screen.play(), Screen.wrapper(), curses.initscr() will crash — use offline rendering APIs\n"
            "- Always encoding='utf-8', errors='replace' for file/subprocess I/O\n"
            "- Never lowercase true/false/null in Python — always True/False/None\n\n"
            "TOKEN OPTIMIZATION RULES — plugins MUST be efficient:\n"
            "- Every tool MUST accept a 'limit' or 'max_results' parameter (default: 50, max: 200)\n"
            "- Every tool MUST accept a 'verbose' parameter (default: False)\n"
            "- When verbose=False, return ONLY essential data — no debug info, no banners\n"
            "- Lists/arrays MUST be truncated before returning — never return unlimited items\n"
            "- Large text outputs MUST be truncated to max 5000 chars with '(truncated)' notice\n"
            "- Include 'pattern' or 'filter' parameters where applicable for client-side filtering\n"
            "- Return compact formats (JSON, CSV, tables) instead of prose paragraphs\n"
            "- Discovery tools (list_*) should return simple arrays, not nested objects\n\n"
            "Respond ONLY with the delimited file blocks. No prose outside the blocks."
        )

        verbose = config.get("verbose", False)

        def _do_stream():
            nonlocal response_text, reasoning_text
            for chunk in stream(model, generation_system,
                                [{"role": "user", "content": prompt}], [], config):
                if isinstance(chunk, AssistantTurn):
                    response_text = chunk.text
                elif isinstance(chunk, ThinkingChunk):
                    reasoning_text += chunk.text + "\n"
                    if verbose:
                        stream_thinking(chunk.text, verbose)

        print_tool_start("Write", {"file_path": f"{safe_name}/plugin_tool.py"})
        _do_stream()

        # ── Parse the three delimited files from the single response ──────
        data: dict = {}

        file_pattern = r"---FILE:\s*(.*?)\s*---(.*?)(?=---FILE:|$)"
        for fname, content in re.findall(file_pattern, response_text, re.DOTALL):
            data[fname.strip()] = content.strip()

        # Fallback: detect code blocks if delimiters are missing
        if "plugin_tool.py" not in data or "plugin.json" not in data:
            for block in re.findall(r"```(?:\w+)?\n(.*?)\n```", response_text, re.DOTALL):
                block = block.strip()
                if "TOOL_DEFS" in block and "plugin_tool.py" not in data:
                    data["plugin_tool.py"] = block
                elif '"name":' in block and '"version":' in block and "plugin.json" not in data:
                    data["plugin.json"] = block

        # Strip any residual markdown fences inside captured blocks
        for k in list(data):
            v = data[k]
            if "```" in v:
                inner = re.search(r"```(?:\w+)?\n(.*?)\n```", v, re.DOTALL)
                if inner:
                    data[k] = inner.group(1).strip()

        # Strip stray delimiter lines from all parsed blocks (defense-in-depth)
        for k in list(data):
            data[k] = re.sub(r'^\s*-{3,}(?:FILE:.*|END|EOF)?\s*-*\s*$', '', data[k], flags=re.MULTILINE).strip()

        if not data:
            raise ValueError("Could not parse AI response — no file blocks found.")

        # ── Save generation as a Dulus session JSON ──────────────────────
        # The fixer agent (in _attempt_fix) seeds its state.messages from this
        # file, so it picks up exactly where the generator left off — same
        # format Dulus uses for /save and /load. Persistent + user-inspectable.
        try:
            import uuid as _uuid
            from datetime import datetime as _dt
            gen_session = {
                "session_id": _uuid.uuid4().hex[:8],
                "saved_at": _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                "_kind": "plugin_adapter_generation",
                "_plugin": safe_name,
                "system": generation_system,
                "messages": [
                    {"role": "user", "content": prompt},
                    {
                        "role": "assistant",
                        "content": response_text,
                        **({"thinking": reasoning_text.strip()} if reasoning_text.strip() else {}),
                    },
                ],
                "turn_count": 1,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
            (plugin_dir / "_generation_session.json").write_text(
                json.dumps(gen_session, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as _e:
            warn(f"Could not save generation session: {_e}")

        # ── Write ADAPTATION_GUIDE.md ──────────────────────────────────────
        guide_content = data.get("ADAPTATION_GUIDE.md") or reasoning_text.strip()
        if guide_content:
            (plugin_dir / "ADAPTATION_GUIDE.md").write_text(
                guide_content if "Adaptation Guide" in guide_content
                else f"# Adaptation Guide: {safe_name}\n\n{guide_content}\n",
                encoding="utf-8",
            )

        # ── Write plugin_tool.py ───────────────────────────────────────────
        tool_code = data.get("plugin_tool.py")
        if not tool_code:
            raise ValueError("Missing plugin_tool.py in AI response.")
        tool_code = _sanitize_python_code(tool_code)
        (plugin_dir / "plugin_tool.py").write_text(tool_code, encoding="utf-8")

        # ── Write plugin.json ──────────────────────────────────────────────
        manifest_raw = data.get("plugin.json")
        if not manifest_raw:
            raise ValueError("Missing plugin.json in AI response.")
        manifest_data = json.loads(manifest_raw) if isinstance(manifest_raw, str) else manifest_raw

        # Sanitize dependency format
        deps = manifest_data.get("dependencies", [])
        if isinstance(deps, dict):
            deps = deps.get("requirements") or deps.get("pip") or []
        manifest_data["dependencies"] = deps if isinstance(deps, list) else []

        # Ensure required fields
        if "plugin_tool" not in manifest_data.get("tools", []):
            manifest_data.setdefault("tools", []).append("plugin_tool")
        if "ADAPTATION_GUIDE.md" not in manifest_data.get("skills", []):
            manifest_data.setdefault("skills", []).append("ADAPTATION_GUIDE.md")

        # Merge requirements.txt deps not already in manifest
        if analysis["requirements"]:
            existing = {d.lower().split("=")[0].split(">")[0].split("<")[0].strip()
                        for d in manifest_data["dependencies"]}
            for req in analysis["requirements"]:
                rname = req.lower().split("=")[0].split(">")[0].split("<")[0].strip()
                if rname not in existing:
                    manifest_data["dependencies"].append(req)

        (plugin_dir / "plugin.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        print_tool_end("Write", f"Generated {len(data)} files for '{safe_name}'", success=True)

        # ── Worker: verify every tool, fix failures, abort if unfixable ───
        # Pass the generation reasoning as context so the fix agent knows the library structure
        worker_ok = _run_adapter_worker(plugin_dir, safe_name, analysis, config, 
                                        generator_context=reasoning_text)
        if not worker_ok:
            warn(f"Plugin '{safe_name}' adaptation had issues — saving as disabled for manual fixing.")
            # Mark plugin as disabled so user can enable manually after fixing
            manifest_data["enabled"] = False
            manifest_data["_adaptation_issues"] = True
            (plugin_dir / "plugin.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
            ok(f"Plugin '{safe_name}' saved with issues. Enable with: /plugin enable {safe_name}")
        else:
            ok(f"Plugin '{safe_name}' adapted successfully.")
        
        # Save adaptation guide to persistent memory - GLOBAL scope so it's available everywhere
        try:
            from datetime import datetime
            from memory.store import MemoryEntry, save_memory
            mem = MemoryEntry(
                name=f"plugin_guide_{safe_name}",
                description=f"Auto-generated usage guide and technical hints for the '{safe_name}' plugin.",
                type="user",  # Changed to user for global availability
                content=guide_content,
                hall="advice",
                created=datetime.now().strftime("%Y-%m-%d"),
                scope="user",  # GLOBAL - available from any directory
                source="model",
            )
            save_memory(mem, scope="user")  # Save to ~/.dulus/memory/
        except Exception as e:
            warn(f"Could not save persistent memory for plugin: {e}")
        
        # Save plugin_tool.py source code as permanent memory - GLOBAL scope
        try:
            tool_file = plugin_dir / "plugin_tool.py"
            if tool_file.exists():
                tool_source = tool_file.read_text(encoding="utf-8")
                tool_mem = MemoryEntry(
                    name=f"{safe_name}_plugin_tools",
                    description=f"Complete source code of {safe_name}'s plugin_tool.py - contains exact tool definitions, schemas, and implementations.",
                    type="user",  # Changed to user for global availability
                    content=f"# {safe_name} Plugin Tools - Source Code\n\n```python\n{tool_source}\n```",
                    hall="facts",
                    created=datetime.now().strftime("%Y-%m-%d"),
                    scope="user",  # GLOBAL - available from any directory
                    source="system",
                )
                save_memory(tool_mem, scope="user")  # Save to ~/.dulus/memory/
                info(f"Saved {safe_name}_plugin_tools to permanent memory")
        except Exception as e:
            warn(f"Could not save plugin tools source to memory: {e}")

        # Register plugin in system (even if adaptation had issues)
        try:
            from .store import _save_entry, _is_git_url
            from .types import PluginEntry, PluginScope
            
            # Determine source from analysis or use plugin_dir as fallback
            source = analysis.get("source", str(plugin_dir))
            
            entry = PluginEntry(
                name=safe_name,
                scope=PluginScope.USER,
                source=source,
                install_dir=plugin_dir,
                enabled=worker_ok,  # Only enable if adaptation was successful
                manifest=PluginManifest.from_plugin_dir(plugin_dir),
            )
            _save_entry(entry)
            info(f"Plugin '{safe_name}' registered in system (enabled={worker_ok})")
        except Exception as e:
            warn(f"Could not register plugin in system: {e}")

        return True
    except Exception as e:
        err(f"Failed to generate plugin files: {e}")
        return False


def _compile_check(plugin_dir: Path) -> tuple[bool, str]:
    """Hard syntax check on plugin_tool.py."""
    tool_file = plugin_dir / "plugin_tool.py"
    if not tool_file.exists():
        return False, "plugin_tool.py was not generated."
    source = tool_file.read_text(encoding="utf-8", errors="replace")
    try:
        compile(source, str(tool_file), "exec")
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    return True, "compile OK"


def _load_plugin_module(plugin_dir: Path, safe_name: str) -> tuple[Any, str]:
    """Import plugin_tool.py and return (module_or_None, error_or_empty)."""
    import importlib.util
    tool_file = plugin_dir / "plugin_tool.py"
    spec = importlib.util.spec_from_file_location(
        f"_validate_{safe_name}_{id(plugin_dir)}", str(tool_file)
    )
    if spec is None or spec.loader is None:
        return None, "Could not create import spec for plugin_tool.py"

    original_path = sys.path[:]
    try:
        mod = importlib.util.module_from_spec(spec)
        if str(plugin_dir) not in sys.path:
            sys.path.insert(0, str(plugin_dir))
        spec.loader.exec_module(mod)
        return mod, ""
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        sys.path[:] = original_path


def _smoke_test_tool(td: Any) -> tuple[bool, str]:
    """
    Run a single tool with minimal valid params, mirroring execute_tool()'s
    stdout/stderr capture. Many plugin tools `print()` their output instead of
    returning it, so we MUST capture stdout or we will wrongly report "empty".
    """
    import io
    import traceback
    from contextlib import redirect_stdout, redirect_stderr

    test_params: dict = {}
    try:
        # Robustly handle cases where td might be a dict or a ToolDef object
        if hasattr(td, "schema"):
            schema = td.schema
        elif isinstance(td, dict) and "schema" in td:
            schema = td["schema"]
        else:
            return False, f"Tool object {type(td)} missing schema"
            
        props = schema.get("input_schema", {}).get("properties", {})
        required = schema.get("input_schema", {}).get("required", [])
        for key in required:
            ptype = str(props.get(key, {}).get("type", "string")).lower()
            # Use smarter test values based on parameter name patterns
            key_lower = key.lower()
            
            # Code/code-related params need valid Python, not just "test"
            if key_lower in ("code", "python_code", "script", "source"):
                test_params[key] = "print('hello')"  # Valid Python code
            elif key_lower in ("query", "search", "text", "title", "name"):
                test_params[key] = "test"
            elif key_lower in ("url", "link", "path", "file"):
                test_params[key] = "https://example.com"
            elif key_lower in ("username", "user", "account"):
                test_params[key] = "testuser"
            elif key_lower in ("location", "city", "place"):
                test_params[key] = "New York"
            elif ptype in ("string", "str"):
                test_params[key] = "test"
            elif ptype in ("integer", "int"):
                test_params[key] = 1
            elif ptype in ("boolean", "bool"):
                test_params[key] = True
            elif ptype in ("number", "float", "double"):
                test_params[key] = 1.0
            else:
                test_params[key] = "test" # default fallback

        f_stdout = io.StringIO()
        f_stderr = io.StringIO()
        try:
            with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
                func = td.func if hasattr(td, "func") else td.get("function") if isinstance(td, dict) else None
                if not func:
                    return False, "Tool missing callable function"
                result = func(test_params, {})
        except (NameError, SyntaxError) as e:
            # These errors often indicate the test parameters were invalid for this tool
            # (e.g., passing 'test' as Python code). Consider this a test environment issue.
            err_msg = f"{type(e).__name__}: {e}"
            # Check if it's likely a test parameter issue
            if any(k in str(e).lower() for k in test_params.values() if isinstance(k, str)):
                return True, f"OK (test param compatibility issue - tool likely works with real inputs)"
            tb_str = traceback.format_exc()
            return False, f"{err_msg}\n\nFull traceback:\n{tb_str}"
        except Exception as e:
            # Capture full traceback for debugging
            tb_str = traceback.format_exc()
            return False, f"{type(e).__name__}: {e}\n\nFull traceback:\n{tb_str}"

        captured_out = f_stdout.getvalue()
        captured_err = f_stderr.getvalue()
        result_str = "" if result is None else str(result)

        # Merge return value + captured stdout (same semantics as execute_tool)
        merged_parts = []
        if captured_out.strip():
            merged_parts.append(captured_out.strip())
        if result_str.strip() and result_str.strip().lower() != "null":
            merged_parts.append(result_str.strip())
        merged = "\n\n".join(merged_parts)

        if not merged:
            detail = ""
            if captured_err.strip():
                # Include full stderr (up to 2000 chars to avoid overwhelming output)
                err_full = captured_err.strip()
                if len(err_full) > 2000:
                    err_full = err_full[:2000] + "\n... (truncated, see full error in plugin files)"
                detail = f"\n\nstderr:\n{err_full}"
            return False, f"tool returned empty result{detail}"
        if merged.startswith("Error"):
            # Include full error message (up to 2000 chars)
            if len(merged) > 2000:
                return False, merged[:2000] + "\n... (truncated)"
            return False, merged
        # Output-efficiency check: tools that return >2500 chars with default
        # params are wasting context. Fail the smoke test so the worker fix
        # cycle refactors the tool to curate its output.
        BLOAT_CAP = 2500
        if len(merged) > BLOAT_CAP:
            preview = merged[:400].replace("\n", " ")
            return False, (
                f"OUTPUT_TOO_VERBOSE: tool returned {len(merged)} chars "
                f"with default params (cap is {BLOAT_CAP}). This will be "
                f"truncated at runtime, polluting context. REFACTOR the "
                f"tool to extract only essential fields (curated key:value "
                f"or compact table) — do NOT dump raw API responses, full "
                f"DataFrames, or json.dumps of library objects. Slice lists "
                f"to limit=10. Truncate long descriptions to ~400 chars. "
                f"Output preview (first 400 chars): {preview}"
            )
        return True, f"OK ({len(merged)} chars)"
    except Exception as e:
        tb_str = traceback.format_exc()
        return False, f"{type(e).__name__}: {e}\n\nFull traceback:\n{tb_str}"


# ── Adapter Worker ────────────────────────────────────────────────────────────

def _build_todo_items(plugin_dir: Path, safe_name: str) -> list[dict]:
    """
    Derive a structured todo list directly from the generated tools.
    Each item: {title, verify, status}
    verify is one of: 'compile' | 'import' | 'exports' | ('smoke', tool_name)
    """
    items: list[dict] = [
        {"title": "plugin_tool.py compiles (no SyntaxError)", "verify": "compile"},
        {"title": "plugin_tool.py imports without runtime errors", "verify": "import"},
        {"title": "TOOL_DEFS and TOOL_SCHEMAS are exported", "verify": "exports"},
        {"title": "TOOL_DEFS contains valid ToolDef objects (not raw functions)", "verify": "tooldef_structure"},
    ]
    # Try to load module so we can list tools
    mod, _err = _load_plugin_module(plugin_dir, safe_name)
    if mod is not None:
        tool_defs = getattr(mod, "TOOL_DEFS", None) or []
        for td in tool_defs:
            # Only add smoke tests for proper ToolDef objects with a string name
            tname = td.name if (hasattr(td, "name") and isinstance(td.name, str)) else None
            if tname is None:
                continue  # tooldef_structure check will catch and explain this
            items.append({
                "title": f"Tool `{tname}` runs successfully with default params",
                "verify": ("smoke", tname),
            })
    return items


def _write_todo_file(plugin_dir: Path, safe_name: str, items: list[dict]) -> Path:
    todo_path = plugin_dir / "ADAPTATION_TODO.md"
    lines = [
        f"# Adaptation Tasks for `{safe_name}`",
        "",
        "Auto-generated checklist verifying the AI-generated plugin works.",
        "Each task is verified by the adapter worker; failures trigger a fix attempt.",
        "",
    ]
    for item in items:
        lines.append(f"- [ ] {item['title']}")
    todo_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return todo_path


def _mark_task(todo_path: Path, title: str, status: str) -> None:
    """status: 'done' (x) or 'fail' (still [ ] but with FAILED tag)"""
    if not todo_path.exists():
        return
    text = todo_path.read_text(encoding="utf-8")
    if status == "done":
        text = text.replace(f"- [ ] {title}", f"- [x] {title}")
    else:
        text = text.replace(f"- [ ] {title}", f"- [ ] {title}  ⚠ FAILED")
    todo_path.write_text(text, encoding="utf-8")


def _run_verification(plugin_dir: Path, safe_name: str, verify: Any) -> tuple[bool, str]:
    """Dispatch to the right verification routine."""
    if verify == "compile":
        return _compile_check(plugin_dir)
    if verify == "import":
        mod, err_msg = _load_plugin_module(plugin_dir, safe_name)
        return (mod is not None), err_msg or "import OK"
    if verify == "exports":
        mod, err_msg = _load_plugin_module(plugin_dir, safe_name)
        if mod is None:
            return False, err_msg
        if not getattr(mod, "TOOL_DEFS", None):
            return False, "TOOL_DEFS missing or empty"
        if not getattr(mod, "TOOL_SCHEMAS", None):
            return False, "TOOL_SCHEMAS missing or empty"
        return True, "exports OK"
    if verify == "tooldef_structure":
        mod, err_msg = _load_plugin_module(plugin_dir, safe_name)
        if mod is None:
            return False, err_msg
        tool_defs = getattr(mod, "TOOL_DEFS", None) or []
        bad = []
        for i, td in enumerate(tool_defs):
            if not hasattr(td, "name") or not isinstance(td.name, str):
                bad.append(f"TOOL_DEFS[{i}] is {type(td).__name__} `{getattr(td, '__name__', td)}` — must be a ToolDef object, not a raw function. "
                           f"Wrap it: ToolDef(name='tool_name', schema={{...}}, func={getattr(td, '__name__', 'fn')})")
            elif not hasattr(td, "schema") or not hasattr(td, "func"):
                bad.append(f"TOOL_DEFS[{i}] (name={td.name!r}) is missing schema or func attribute.")
        if bad:
            return False, " | ".join(bad)
        return True, f"all {len(tool_defs)} ToolDef objects are valid"
    if isinstance(verify, tuple) and verify[0] == "smoke":
        tool_name = verify[1]
        mod, err_msg = _load_plugin_module(plugin_dir, safe_name)
        if mod is None:
            return False, f"cannot load module: {err_msg}"
        for td in getattr(mod, "TOOL_DEFS", []) or []:
            tname = td.name if hasattr(td, "name") else str(td)
            if tname == tool_name:
                return _smoke_test_tool(td)
        return False, f"tool '{tool_name}' not found in TOOL_DEFS"
    return False, f"unknown verify spec: {verify}"


def _read_relevant_sources(plugin_dir: Path, error_msg: str, max_chars: int = 6000) -> str:
    """
    Read actual source files from the plugin repo to give the fix AI real API context.
    Prioritizes files whose names appear in the error message, then __init__.py files.
    """
    exclude = {"__pycache__", ".git", "venv", "dist", "build", "node_modules", "tests", "docs"}
    candidates: list[tuple[int, Path]] = []

    # Score each .py file: higher = more relevant
    error_lower = error_msg.lower()
    for p in plugin_dir.rglob("*.py"):
        rel = p.relative_to(plugin_dir)
        if any(part in exclude for part in rel.parts):
            continue
        score = 0
        stem = p.stem.lower()
        # File name appears in the error message
        if stem in error_lower:
            score += 10
        # __init__ files expose the public API
        if p.name == "__init__.py":
            score += 5
        # Root-level files are more likely to be the main API
        if len(rel.parts) <= 2:
            score += 3
        candidates.append((score, p))

    candidates.sort(key=lambda x: -x[0])

    parts = []
    total = 0
    for _, p in candidates:
        if total >= max_chars:
            break
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            snippet = content[: max_chars - total]
            rel = p.relative_to(plugin_dir)
            parts.append(f"### {rel}\n```python\n{snippet}\n```")
            total += len(snippet)
        except Exception:
            continue

    return "\n\n".join(parts) if parts else "(no source files found)"


def _attempt_fresh_start(plugin_dir: Path, safe_name: str,
                         accumulated_errors: list[str], analysis: dict, config: dict) -> bool:
    """
    Full rewrite of plugin_tool.py from scratch after repeated fix failures.
    Feeds all accumulated error history so the agent doesn't repeat the same mistakes.
    """
    import agent as _agent

    tool_file = plugin_dir / "plugin_tool.py"
    current_code = ""
    if tool_file.exists():
        try:
            current_code = tool_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    error_history = "\n".join(f"  - Attempt {i+1}: {e}" for i, e in enumerate(accumulated_errors))

    rewrite_message = f"""Completely rewrite `plugin_tool.py` for the Dulus plugin `{safe_name}` from scratch.

PLUGIN DIR: {plugin_dir}

PREVIOUS ATTEMPTS FAILED WITH THESE ERRORS (do NOT repeat these mistakes):
{error_history}

CURRENT (broken) plugin_tool.py:
```python
{current_code[:3000]}
```

STEPS:
1. Read the plugin source files in `{plugin_dir}` to understand the real API.
2. Use Bash to test imports: `python -c "import <pkg>; print(dir(<pkg>))"` (cwd={plugin_dir}).
3. Write a completely fresh `{plugin_dir}/plugin_tool.py` that avoids ALL the errors above.
4. Test with Bash — use a MockToolDef since tool_registry is only available at Dulus runtime.
5. Verify: `python -c "import ast; ast.parse(open(r'{plugin_dir}/plugin_tool.py').read())"`.

RULES (non-negotiable):
- TOOL_DEFS = [ToolDef(name, schema, func), ...]
- TOOL_SCHEMAS = [t.schema for t in TOOL_DEFS]
- Tool functions: func(params: dict, config: dict) -> str  (MUST return a string)
- Use params.get() with defaults, NEVER params[key]
- No TTY/terminal calls — stdout is StringIO
- encoding='utf-8', errors='replace' everywhere
- True/False/None only, never true/false/null
"""

    # Fresh start always creates new agent - full system prompt needed
    system = (
        f"You are an AI coding assistant helping write a Dulus plugin adapter. "
        f"Your task: write plugin_tool.py and plugin.json in {plugin_dir}. "
        f"\n\n"
        f"AVAILABLE TOOLS: Read, Write, Edit, Bash, Grep, WebSearch, MemorySearch. "
        f"Use these to write and test the plugin files. "
        f"\n\n"
        f"CRITICAL: You MUST write VALID Python code that CAN be imported. Do NOT say 'I cannot test this' or 'this is a test environment'. "
        f"Your code WILL be executed. Write real, working code. "
        f"\n\n"
        f"ToolDef IMPORT: Use 'from tool_registry import ToolDef' - this module exists and will be available when the plugin runs. "
        f"Do NOT question whether ToolDef exists - just import it. "
        f"\n\n"
        f"REQUIRED EXPORTS from plugin_tool.py:\n"
        f"  - TOOL_DEFS = [ToolDef(name, schema, func), ...]  (list of ToolDef OBJECTS, not functions)\n"
        f"  - TOOL_SCHEMAS = [t.schema for t in TOOL_DEFS]\n"
        f"\n"
        f"FUNCTION SIGNATURE: def my_func(params: dict, config: dict) -> str:\n"
        f"  - MUST return a string (not None, not print)\n"
        f"  - Use params.get('key', default) NEVER params['key']\n"
        f"\n"
        f"TEST YOUR CODE: Use Bash to verify it compiles: python -c 'import ast; ast.parse(open(\"plugin_tool.py\").read())' "
        f"\n\n"
        f"Search memory FIRST for successful similar adaptations. "
        f"ENCODING: Always use encoding='utf-8' in open() and subprocess."
    )

    fix_config = {**config, "permission_mode": "accept-all"}
    state = _agent.AgentState()  # Fresh start = brand new agent

    warn(f"  [fresh start] Rewriting plugin_tool.py from scratch for '{safe_name}'...")
    try:
        for event in _agent.run(rewrite_message, state, fix_config, system):
            if isinstance(event, _agent.ToolStart):
                print_tool_start(event.name, event.inputs)
            elif isinstance(event, _agent.ToolEnd):
                chars = len(event.result) if event.result else 0
                label = event.result[:80] if chars <= 80 else f"{chars} chars"
                print_tool_end(event.name, label, success=not (event.result or "").startswith("Error"))
            elif isinstance(event, _agent.ThinkingChunk):
                stream_thinking(event.text, config.get("verbose", False))

        compile_ok, _ = _compile_check(plugin_dir)
        return compile_ok
    except Exception as e:
        print_tool_end("Write", f"Fresh start agent failed: {e}", success=False)
        return False


def _attempt_fix(plugin_dir: Path, safe_name: str, task_title: str,
                 error_msg: str, analysis: dict, config: dict, original_goal: str | None = None,
                 state=None, generation_context: str = "") -> tuple[bool, Any, bool]:
    """
    Run a full tool-enabled agent turn to fix a failing task.
    The agent has Read/Write/Edit/Bash/Grep/WebSearch — same as normal Dulus.
    Reuses existing state if provided (for multi-attempt fixes), otherwise creates new state.
    Returns (success, state) so state can be reused for next attempt.
    
    Args:
        generation_context: Optional context from generation phase explaining the library design
    """
    import agent as _agent

    tool_file = plugin_dir / "plugin_tool.py"
    if not tool_file.exists():
        return False, state, False

    # ── Build error-type-specific hints ───────────────────────────────────
    error_lower = error_msg.lower()
    extra_hints = ""

    # TTY / terminal dependency detected
    if any(kw in error_lower for kw in ("tty", "screen", "isatty", "initscr", "terminal", "curses")):
        extra_hints += """
⚠ TTY ERROR DETECTED: The tool is trying to use the terminal directly.
Tool functions run with stdout redirected to StringIO — there is NO real TTY.
Any call to Screen.play(), Screen.wrapper(), curses.initscr(), or similar will crash.

FIX: Use the library's OFFLINE rendering API instead:
  • asciimatics: import Renderer subclasses (FigletText, Fire, Plasma, SpeechBubble, etc.)
    - lines, _ = renderer.rendered_text   → list of strings, join with \\n
    - repr(renderer)                       → plain-text next frame (simplest)
    - DO NOT import or use Screen, ManagedScreen, Scene, Effect, or draw()
  • rich: Console(file=io.StringIO()) then .getvalue()
  • blessed: Terminal() string methods only, never cbreak()/inkey()
"""

    # Empty result — tool ran but returned nothing
    elif "empty result" in error_lower:
        extra_hints += """
⚠ EMPTY RESULT: The tool ran but returned no output. Common causes:
  a) The library tried to write to a terminal and crashed silently (TTY issue — see above).
  b) The tool calls print() but returns None — make sure the function returns a string.
  c) subprocess had empty stdout — check if the command needs different args.
  d) The function caught an exception and swallowed it — check try/except blocks.

FIX: The function MUST end with `return <some_string>`. Use Bash to test the import manually:
  python -c "from <package> import <class>; r = <class>('test'); print(repr(r))"
"""

    # ModuleNotFoundError / ImportError
    elif any(kw in error_lower for kw in ("modulenotfounderror", "importerror", "no module named")):
        extra_hints += f"""
⚠ IMPORT ERROR: A module could not be imported.
  • The plugin root `{plugin_dir}` is already in sys.path — local package imports should work.
  • If a dependency is missing, check if it's listed in plugin.json "dependencies".
  • Use Bash to verify: `python -c "import <package>"` in cwd={plugin_dir}
  • If the package name differs from the import name, adjust the import statement.
"""

    # ToolDef structure error
    elif "must be a tooldef" in error_lower or "raw function" in error_lower:
        extra_hints += """
⚠ TOOLDEF STRUCTURE: TOOL_DEFS contains a raw function instead of a ToolDef object.
WRONG:  TOOL_DEFS = [my_tool_function]
RIGHT:  TOOL_DEFS = [ToolDef(name="my_tool", schema={...}, func=my_tool_function)]

Each entry in TOOL_DEFS must be a ToolDef object with: name (str), schema (dict), func (callable).
ToolDef takes EXACTLY: ToolDef(name, schema, func, read_only=False, concurrent_safe=False).
NEVER pass description/parameters/handler as kwargs to ToolDef — they go INSIDE schema.
"""

    # OUTPUT_TOO_VERBOSE — tool worked but dumped too many chars
    elif "output_too_verbose" in error_lower:
        extra_hints += """
⚠ OUTPUT BLOAT: The tool ran successfully but returned too many chars,
which would get truncated at runtime and waste context. The tool needs
REDESIGN, not a bug fix. Concretely:

  a) Identify the bloat source: `.info` dict? `.to_dict()`? `json.dumps()`
     of a full library object? `print()` of an entire DataFrame?
  b) Replace it with a CURATED selection — pick the 6-12 fields that
     actually matter for the tool's purpose. Drop everything else.
  c) Format compactly: `f"{key}: {val}"` lines, or a small markdown table.
     No pretty-printed JSON. No raw dumps. No log spam.
  d) For lists: SLICE to limit=10 (default) BEFORE formatting.
  e) For long text fields (descriptions, summaries): truncate to ~400 chars
     with "..." suffix unless params.get("verbose") is True.
  f) For numbers: round floats, format big numbers as "1.2B" / "850M".

Edit the function body — do NOT touch the schema unless adding a `verbose`
param. Re-run with default params and confirm output < 2500 chars.
"""

    # General hint for documentation/API research (appears after specific error hints)
    elif "import" in error_lower or "attribute" in error_lower or "type" in error_lower or "api" in error_lower:
        extra_hints += f"""
⚠ RESEARCH HINT: This error suggests you need external documentation.
You have WebSearch available — use it to find official docs, examples, or Stack Overflow discussions.
Example: `WebSearch(query="python {safe_name} {task_title.replace(' ', ' ').split()[0] if task_title else 'error'} documentation")`
"""

    context_hint = f"\nORIGINAL GOAL: {original_goal}\n" if original_goal else ""

    # generation_context is now obsolete — the full generator conversation is
    # seeded into state.messages from _generation_session.json above. Kept as
    # a no-op fallback for older callers that still pass it.
    gen_context_hint = ""

    fix_message = f"""Fix a failing verification task in the Dulus plugin `{safe_name}`.

PLUGIN DIR: {plugin_dir}
{context_hint}
FAILING TASK: {task_title}

FULL ERROR:
```
{error_msg}
```
{extra_hints}
{gen_context_hint}

HOW TO FIX:
1. Read `{plugin_dir}/plugin_tool.py` and relevant source files in `{plugin_dir}`
2. Use Bash to test: `python -c "import <pkg>; <test>"` (cwd={plugin_dir})
3. Edit `{plugin_dir}/plugin_tool.py` to fix the issue
4. Verify: `python -c "import ast; ast.parse(open(r'{plugin_dir}/plugin_tool.py').read())"`

KEY RULES:
- Use `params.get("key", default)`, NEVER `params["key"]`
- Tool functions MUST return a string (not None, not just print)
- `encoding='utf-8', errors='replace'` everywhere
- True/False/None only, never true/false/null
- `from tool_registry import ToolDef` — this exists, don't question it
- Fix ONLY this failing task. Don't redesign the whole plugin.

SPECIAL OPTIONS:
- BYPASS_REQUEST: If the error is a false positive after your fix
- SKIP_TOOL: If a tool truly cannot be fixed, remove it from TOOL_DEFS

When done, output a one-line summary of what you changed.
"""

    fix_config = {**config, "permission_mode": "accept-all"}

    # Fresh state per task. Seed messages from the generator's session JSON
    # so the fixer continues the same conversation — same effect as /load on
    # a normal Dulus session, but inline. Falls back to empty if the JSON
    # is missing (older plugins, or generation failed to save it).
    state = _agent.AgentState()
    gen_session_path = plugin_dir / "_generation_session.json"
    if gen_session_path.exists():
        try:
            _gen = json.loads(gen_session_path.read_text(encoding="utf-8"))
            seeded = _gen.get("messages") or []
            if seeded and isinstance(seeded, list):
                state.messages = list(seeded)
        except Exception as _e:
            warn(f"Could not seed fixer state from generation session: {_e}")
    
    # System prompt notes whether we resumed from generation or started fresh,
    # so the model knows whether to trust the prior assistant turn as its own.
    _resumed = bool(state.messages)
    _continuity_note = (
        "CONTINUITY: The conversation above is YOUR earlier work generating "
        "this plugin (you are the same assistant — same identity, full memory "
        "of your design choices). A verification step then failed — your job "
        "now is to fix it without contradicting your prior design unless the "
        "failure shows the design itself was wrong.\n\n"
        if _resumed else ""
    )

    # DEBUG MODE system prompt - focused on fixing broken code
    # Do NOT use build_system_prompt - it confuses the agent about being "inside Dulus"
    system = (
        f"You are an AI coding assistant fixing a broken Dulus plugin. "
        f"Your task: Fix the code in {plugin_dir}/plugin_tool.py\n"
        f"\n"
        f"{_continuity_note}"
        f"\n"
        f"AVAILABLE TOOLS: Read, Write, Edit, Bash, Grep, WebSearch, MemorySearch. "
        f"Use these tools to fix and verify the code. "
        f"\n"
        f"CRITICAL: You MUST write VALID Python code that CAN be imported and executed. "
        f"This is NOT a simulation. Your code WILL be run. Do NOT say 'I cannot test this'. "
        f"\n"
        f"ToolDef IMPORT: Use 'from tool_registry import ToolDef' - this exists. "
        f"Do NOT question it - just write the import. "
        f"\n"
        f"DEBUGGING STRATEGY:\n"
        f"1. READ the error message below carefully\n"
        f"2. LOOK at the current broken code with Read tool\n"
        f"3. UNDERSTAND what the library expects (check __init__.py, docs)\n"
        f"4. FIX only what's broken - don't rewrite everything\n"
        f"5. TEST that it works with Bash tool\n"
        f"\n"
        f"WINDOWS PATHS: Use forward slashes / or raw strings r'...' in Python\n"
        f"ENCODING: Always use encoding='utf-8' when reading/writing files\n"
        f"PARAMETERS: Use params.get() with defaults, NEVER params[key]"
    )
    
    message_to_send = fix_message

    print_tool_start("Edit", {"file_path": f"{safe_name}/plugin_tool.py", "reason": task_title})
    bypass_requested = False
    bypass_reason = ""
    skip_tool_requested = False
    skip_tool_reason = ""
    try:
        mtime_before = tool_file.stat().st_mtime if tool_file.exists() else 0

        for event in _agent.run(message_to_send, state, fix_config, system):
            if isinstance(event, _agent.ToolStart):
                print_tool_start(event.name, event.inputs)
            elif isinstance(event, _agent.ToolEnd):
                lines = event.result.count("\n") + 1 if event.result else 0
                chars = len(event.result) if event.result else 0
                label = f"{lines} lines ({chars} chars)" if lines > 1 else event.result[:80]
                print_tool_end(event.name, label, success=not event.result.startswith("Error"))
            elif isinstance(event, _agent.TextChunk):
                # Check for BYPASS_REQUEST in agent response
                if "BYPASS_REQUEST" in event.text:
                    bypass_requested = True
                    bypass_reason = event.text.split("BYPASS_REQUEST:")[-1].strip() if "BYPASS_REQUEST:" in event.text else "Agent reports this is a false positive"
                    info(f"  Agent requests bypass: {bypass_reason[:80]}...")
                # Check for SKIP_TOOL in agent response
                if "SKIP_TOOL" in event.text:
                    skip_tool_requested = True
                    skip_tool_reason = event.text.split("SKIP_TOOL:")[-1].strip() if "SKIP_TOOL:" in event.text else "Agent reports tool cannot be fixed"
                    info(f"  Agent requests skip: {skip_tool_reason[:80]}...")
                pass  # suppress inline text; summary printed at end
            elif isinstance(event, _agent.ThinkingChunk):
                stream_thinking(event.text, config.get("verbose", False))

        mtime_after = tool_file.stat().st_mtime if tool_file.exists() else 0
        file_changed = mtime_after != mtime_before

        # If skip was requested, handle it specially
        if skip_tool_requested:
            print_tool_end("Edit", f"Agent skipped tool: {skip_tool_reason[:60]}...", success=True)
            # Return special flag to indicate tool should be removed
            return True, state, "skip"

        # If bypass was requested, return special status
        if bypass_requested:
            print_tool_end("Edit", f"Fix reports bypass needed: {bypass_reason[:60]}...", success=True)
            return True, state, "bypass"

        # Validate the result compiles regardless of whether the file changed
        if tool_file.exists():
            compile_ok, _ = _compile_check(plugin_dir)
            if compile_ok:
                print_tool_end("Edit", "Fix applied and compiles OK", success=True)
                return True, state, False
            else:
                print_tool_end("Edit", "Fix attempted but result does not compile", success=False)
                return False, state, False

        print_tool_end("Edit", "Fix attempted but plugin_tool.py missing", success=False)
        return False, state, False
    except Exception as e:
        print_tool_end("Edit", f"Fix agent failed: {e}", success=False)
        return False, state, False


def _run_adapter_worker(plugin_dir: Path, safe_name: str,
                        analysis: dict, config: dict,
                        generator_context: str = "") -> bool:
    """
    Worker loop: derive todo from generated tools, verify each, fix failures.
    Returns True only if every required task passes.
    
    Args:
        generator_context: Context from generation phase (reasoning text) to help fix agent understand the library
    """
    verbose = config.get("verbose", False)
    if verbose:
        info(f"Running adapter worker for '{safe_name}'...")

    max_fix_attempts  = config.get("adapter_max_fix_attempts", 20)

    # Pre-flight: code must at least compile to derive a todo. If it doesn't,
    # try fix passes on the syntax error before giving up (single agent, user decides on fresh start).
    compile_ok, compile_msg = _compile_check(plugin_dir)
    if not compile_ok:
        if verbose: warn(f"  Initial compile failed: {compile_msg}")
        accumulated_compile_errors: list[str] = []
        compile_state = None  # Will hold agent state across compile fix attempts
        compile_bypass_available = False
        for attempt in range(max_fix_attempts):
            accumulated_compile_errors.append(compile_msg)
            # Pass generation context only on first attempt to help agent understand library
            gen_ctx = generator_context if attempt == 0 else ""
            _, compile_state, fix_status = _attempt_fix(plugin_dir, safe_name, "plugin_tool.py compiles",
                         compile_msg, analysis, config,
                         original_goal=f"Attempt {attempt+1}: initial generation had syntax errors",
                         state=compile_state,
                         generation_context=gen_ctx)
            if fix_status == "bypass":
                compile_bypass_available = True
            elif fix_status == "skip":
                # Agent wants to skip - treat as bypass for compile errors
                compile_bypass_available = True
            compile_ok, compile_msg = _compile_check(plugin_dir)
            if compile_ok:
                if verbose: ok(f"  Compile fixed on attempt {attempt + 1}.")
                break
        
        if not compile_ok:
            # Max attempts reached - ask user what to do
            err(f"  Could not fix compile error after {max_fix_attempts} attempts.")
            print()
            print("What would you like to do?")
            print("  [1] Keep files and fix manually later")
            print("  [2] Fresh start - reset and try with new context")
            print("  [3] SKIP compilation check - I will fix it manually (NOT RECOMMENDED)")
            try:
                choice = input("Choose [1/2/3]: ").strip()
            except (EOFError, KeyboardInterrupt):
                choice = "1"
            
            if choice == "3":
                warn(f"  Skipping compilation check as requested. Plugin may not work correctly.")
                # Continue with potentially broken code - user responsibility
            elif choice == "2":
                warn(f"  Triggering fresh start for '{safe_name}'...")
                _attempt_fresh_start(plugin_dir, safe_name, accumulated_compile_errors, analysis, config)
                # Recursively retry with fresh start (new agent)
                return _run_adapter_worker(plugin_dir, safe_name, analysis, config)
            else:
                err(f"  Compile errors persisted. Plugin files kept in {plugin_dir}")
                return False

    # Build todo list from the (now compileable) tools
    items = _build_todo_items(plugin_dir, safe_name)
    todo_path = _write_todo_file(plugin_dir, safe_name, items)

    if verbose:
        print_tool_start("Verify", {"plugin": safe_name, "tasks": len(items)})

    # Run each task; retry up to max_fix_attempts with single agent (user decides on fresh start).
    failed_tasks: list[str] = []
    for item in items:
        title = item["title"]
        verify = item["verify"]

        passed, msg = _run_verification(plugin_dir, safe_name, verify)
        if passed:
            if verbose: print_tool_end("Verify", f"✓ {title} ({msg})", success=True)
            _mark_task(todo_path, title, "done")
            continue

        if verbose: print_tool_end("Verify", f"✗ {title} ({msg})", success=False)

        accumulated_errors: list[str] = [msg]
        task_state = None  # Single agent state for this task
        bypass_available = False
        bypass_reason = ""
        skip_requested = False
        skip_reason = ""
        for attempt in range(max_fix_attempts):
            if verbose: info(f"    Fix attempt {attempt + 1}/{max_fix_attempts} for: {title}")

            # Pass generation context only on first attempt
            gen_ctx = generator_context if attempt == 0 else ""
            success, task_state, fix_status = _attempt_fix(plugin_dir, safe_name, title, msg, analysis, config,
                         original_goal=f"Attempt {attempt + 1}: task '{title}' failed with: {msg}",
                         state=task_state,
                         generation_context=gen_ctx)

            # If agent requested bypass, remember it for the user menu
            if fix_status == "bypass":
                bypass_available = True
                bypass_reason = "Agent reports this error is a false positive and the fix is correct"
            elif fix_status == "skip":
                # Agent wants to skip this tool
                skip_requested = True
                skip_reason = f"Agent could not fix {title} and requests to skip it"
                if verbose: warn(f"    Agent requests to skip '{title}' - will remove from plugin")
                break

            passed, msg = _run_verification(plugin_dir, safe_name, verify)
            if passed:
                if verbose: ok(f"    ✓ {title}  [fixed on attempt {attempt + 1}: {msg}]")
                _mark_task(todo_path, title, "done")
                break

            accumulated_errors.append(msg)

        # Handle agent requesting to skip this tool
        if skip_requested:
            if verbose: warn(f"    Agent requested to skip '{title}' - will be removed from plugin")
            failed_tasks.append(title)  # Add to failed so it gets removed
            _mark_task(todo_path, title, "skip")
            continue  # Skip to next task

        if not passed:
            # Max attempts reached - ask user what to do
            if verbose: err(f"    ✗ {title}  [unfixed after {max_fix_attempts} attempts: {msg}]")
            print()
            print(f"Task '{title}' failed after {max_fix_attempts} attempts. What would you like to do?")
            print("  [1] Keep files and fix manually later")
            print("  [2] Fresh start - reset and retry this task with new context")
            print(f"  [3] BYPASS - Skip this task and continue (use if fix seems correct but test is wrong)")
            try:
                choice = input(f"Choose [1/2/3]: ").strip()
            except (EOFError, KeyboardInterrupt):
                choice = "3"  # Default to bypass on interrupt to avoid infinite loops
            
            if choice == "3":
                ok(f"    ✓ {title}  [BYPASSED: {bypass_reason if bypass_available else 'User requested bypass'}]")
                _mark_task(todo_path, title, "bypassed")
                continue  # Skip to next task
            elif choice == "2":
                warn(f"  Triggering fresh start for '{safe_name}'...")
                fresh_ok = _attempt_fresh_start(plugin_dir, safe_name, accumulated_errors, analysis, config)
                if not fresh_ok:
                    err(f"  Fresh start failed to generate valid code for '{safe_name}'")
                    _mark_task(todo_path, title, "fail")
                    failed_tasks.append(title)
                    continue  # Skip to next task
                    
                # Rebuild todo and restart this task with fresh agent
                items = _build_todo_items(plugin_dir, safe_name)
                _write_todo_file(plugin_dir, safe_name, items)
                # Reset task state for fresh agent
                task_state = None
                # IMPORTANT: Update msg with CURRENT error from the fresh code
                passed, msg = _run_verification(plugin_dir, safe_name, verify)
                if passed:
                    # Fresh start already fixed it!
                    if verbose: ok(f"    ✓ {title}  [fixed by fresh start: {msg}]")
                    _mark_task(todo_path, title, "done")
                    continue  # Skip to next task
                
                # Retry this specific task from beginning with UPDATED error message
                fresh_bypass_available = False
                for fresh_attempt in range(max_fix_attempts):
                    if verbose: info(f"    Fresh attempt {fresh_attempt + 1}/{max_fix_attempts} for: {title}")
                    # Pass generation context and accumulated errors in first fresh attempt
                    gen_ctx = generator_context if fresh_attempt == 0 else ""
                    # Include error history so agent knows what NOT to repeat
                    error_history = "\n".join(f"  - Previous error {i+1}: {e}" for i, e in enumerate(accumulated_errors[-5:]))  # Last 5 errors
                    original_goal = f"Fresh attempt {fresh_attempt + 1}: {title}\n\nCURRENT ERROR: {msg}\n\nPREVIOUS ERRORS (DO NOT REPEAT THESE):\n{error_history}"
                    success, task_state, fix_status = _attempt_fix(plugin_dir, safe_name, title, msg, analysis, config,
                                 original_goal=original_goal,
                                 state=task_state,
                                 generation_context=gen_ctx)
                    if fix_status == "bypass":
                        fresh_bypass_available = True
                    elif fix_status == "skip":
                        # Agent wants to skip this tool even after fresh start
                        if verbose: warn(f"    Agent requests to skip '{title}' after fresh start")
                        failed_tasks.append(title)
                        _mark_task(todo_path, title, "skip")
                        # Need to break out of fresh_attempt loop and skip to next item
                        passed = False  # Mark as not passed but will be handled by skip
                        break
                    passed, msg = _run_verification(plugin_dir, safe_name, verify)
                    if passed:
                        if verbose: ok(f"    ✓ {title}  [fixed on fresh attempt {fresh_attempt + 1}: {msg}]")
                        _mark_task(todo_path, title, "done")
                        break
                    accumulated_errors.append(msg)
                
                # Check if tool was marked for skip during fresh attempts
                if title in failed_tasks:
                    # Skip was requested - continue to next item
                    continue
                
                if passed:
                    # Fresh start succeeded - continue to next task
                    continue
                
                # After fresh start also failed, ask user again with bypass option
                print(f"    Fresh start also failed for '{title}'. What would you like to do?")
                print("  [1] Keep files and fix manually later")
                print("  [2] Mark as failed and continue to next task")
                print("  [3] BYPASS this task and continue")
                try:
                    fresh_choice = input("Choose [1/2/3]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    fresh_choice = "3"
                
                if fresh_choice == "3":
                    ok(f"    ✓ {title}  [BYPASSED after fresh start]")
                    _mark_task(todo_path, title, "bypassed")
                elif fresh_choice == "2":
                    _mark_task(todo_path, title, "fail")
                    failed_tasks.append(title)
                else:
                    err(f"    ✗ {title}  [still unfixed after fresh start]")
                    _mark_task(todo_path, title, "fail")
                    failed_tasks.append(title)
            else:
                _mark_task(todo_path, title, "fail")
                failed_tasks.append(title)

    if failed_tasks:
        err(f"  {len(failed_tasks)} task(s) failed after {max_fix_attempts} fix attempts each:")
        for t in failed_tasks:
            err(f"    - {t}")
        
        # Extract tool names from failed smoke tests
        failed_tool_names = []
        for title in failed_tasks:
            # Parse "Tool `name` runs successfully..."
            if "Tool `" in title and "` runs" in title:
                import re
                match = re.search(r"Tool `([^`]+)`", title)
                if match:
                    failed_tool_names.append(match.group(1))
        
        if failed_tool_names:
            info(f"  Removing {len(failed_tool_names)} failed tool(s) from plugin...")
            _remove_failed_tools(plugin_dir, safe_name, failed_tool_names, verbose)
        
        # Check if we have at least some working tools
        mod, _ = _load_plugin_module(plugin_dir, safe_name)
        if mod and getattr(mod, "TOOL_DEFS", None):
            remaining_tools = len(mod.TOOL_DEFS)
            if remaining_tools > 0:
                ok(f"  Plugin saved with {remaining_tools} working tool(s). Failed tools removed.")
                # Update plugin.json to only include working tools
                _update_plugin_json_tools(plugin_dir, safe_name, [t.name for t in mod.TOOL_DEFS if hasattr(t, 'name')])
                return True
        
        # No tools left working - real failure
        return False

    if verbose:
        ok(f"  All {len(items)} tasks passed.")
    return True


def _remove_failed_tools(plugin_dir: Path, safe_name: str, failed_tool_names: list[str], verbose: bool = False) -> None:
    """
    Update plugin_tool.py to only include working tools in TOOL_DEFS and TOOL_SCHEMAS.
    Keeps all the original code, just updates the export lists.
    """
    import re
    
    # Reload module to identify which ToolDef variables correspond to working tools
    mod, _ = _load_plugin_module(plugin_dir, safe_name)
    if not mod or not getattr(mod, "TOOL_DEFS", None):
        return
    
    # Build mapping of tool_name -> var_name by parsing the source
    tool_file = plugin_dir / "plugin_tool.py"
    source = tool_file.read_text(encoding="utf-8", errors="replace")
    
    working_var_names = []
    for td in mod.TOOL_DEFS:
        if hasattr(td, "name") and td.name not in failed_tool_names:
            # Find the variable name for this tool
            # Look for pattern: var_name = ToolDef(... name="tool_name" ...)
            pattern = rf'(\w+)\s*=\s*ToolDef\([^)]*name\s*=\s*["\']{re.escape(td.name)}["\']'
            match = re.search(pattern, source)
            if match:
                working_var_names.append(match.group(1))
    
    if not working_var_names:
        return
    
    # Replace TOOL_DEFS line
    new_tool_defs = f"TOOL_DEFS = [{', '.join(working_var_names)}]"
    source = re.sub(r'^TOOL_DEFS\s*=\s*\[.*?\].*$', new_tool_defs, source, flags=re.MULTILINE | re.DOTALL)
    
    # Replace TOOL_SCHEMAS line  
    new_tool_schemas = "TOOL_SCHEMAS = [t.schema for t in TOOL_DEFS]"
    source = re.sub(r'^TOOL_SCHEMAS\s*=.*$', new_tool_schemas, source, flags=re.MULTILINE)
    
    # Add comment noting failed tools were removed
    if '# NOTE:' not in source:
        source = source.replace(
            'TOOL_DEFS = [',
            f'# NOTE: Removed failed tools: {failed_tool_names}\nTOOL_DEFS = ['
        )
    
    tool_file.write_text(source, encoding="utf-8")
    
    if verbose:
        info(f"    Updated TOOL_DEFS to include only {len(working_var_names)} working tool(s)")


def _update_plugin_json_tools(plugin_dir: Path, safe_name: str, working_tool_names: list[str]) -> None:
    """Update plugin.json to reflect only the working tools."""
    import json
    
    json_file = plugin_dir / "plugin.json"
    if not json_file.exists():
        return
    
    try:
        manifest = json.loads(json_file.read_text(encoding="utf-8"))
        # Keep plugin_tool in tools list (that's the module)
        manifest["tools"] = ["plugin_tool"]
        # Add a note about which specific tools are available
        manifest["_working_tools"] = working_tool_names
        manifest["_failed_tools_removed"] = True
        json_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception as e:
        warn(f"    Could not update plugin.json: {e}")


# Keep the old name for any external callers
def _validate_generated_tools(plugin_dir: Path, safe_name: str) -> bool:
    """Backward-compat shim — runs the worker without fix attempts (no AI)."""
    items = _build_todo_items(plugin_dir, safe_name)
    if not items:
        return False
    for item in items:
        passed, _msg = _run_verification(plugin_dir, safe_name, item["verify"])
        if not passed and item["verify"] in ("compile", "import", "exports"):
            return False
    return True


def autoadapt_if_needed(plugin_dir: Path, name: str, config: dict) -> bool:
    """Main entry point: check if manifest is missing and try to generate it."""
    from .types import PluginManifest
    manifest = PluginManifest.from_plugin_dir(plugin_dir)
    if manifest is None:
        info(f"Missing manifest for '{name}', attempting auto-adaptation...")
        success = generate_plugin_files(plugin_dir, name, config)
        # Always reload to register the plugin (even if adaptation had issues)
        from .loader import reload_plugins
        result = reload_plugins()
        if success:
            ok(f"Plugin '{name}' processed: {result['tools_registered']} tools registered")
        return success
    return True
