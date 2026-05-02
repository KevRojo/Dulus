"""Auto-documentation generator for Falcon.

Scans the codebase and produces docs/api.html with:
- Module index with docstrings
- Class and function listings
- Import dependency graph (raw data + visual)
- Code metrics (LOC, file count, etc.)

Usage:
    python docs/generate.py
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = Path(__file__).parent
API_HTML = DOCS_DIR / "api.html"

EXCLUDE_DIRS = {
    ".git", ".idea", "__pycache__", "venv", ".venv", "node_modules",
    "dist", "build", ".pytest_cache", "htmlcov"
}
EXCLUDE_FILES = {"generate.py"}

# ── AST helpers ──────────────────────────────────────────────────────────────

class ModuleInfo:
    def __init__(self, rel_path: str, abs_path: Path):
        self.rel_path = rel_path
        self.abs_path = abs_path
        self.docstring: str | None = None
        self.classes: List[Dict] = []
        self.functions: List[Dict] = []
        self.imports: List[str] = []
        self.loc = 0


def _get_docstring(node) -> str | None:
    return ast.get_docstring(node)


def _fmt_args(args: ast.arguments) -> str:
    parts: List[str] = []
    # posonlyargs + args + kwonlyargs
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        name = arg.arg
        annot = ""
        if arg.annotation:
            try:
                annot = f": {ast.unparse(arg.annotation)}"
            except Exception:
                annot = ""
        default = ""
        if i >= defaults_offset:
            try:
                default = f" = {ast.unparse(args.defaults[i - defaults_offset])}"
            except Exception:
                default = " = ..."
        parts.append(f"{name}{annot}{default}")
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    return ", ".join(parts)


def parse_file(abs_path: Path, rel_path: str) -> ModuleInfo:
    info = ModuleInfo(rel_path, abs_path)
    try:
        source = abs_path.read_text(encoding="utf-8")
    except Exception as e:
        info.docstring = f"[Error reading file: {e}]"
        return info

    info.loc = len(source.splitlines())
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        info.docstring = f"[Syntax error: {e}]"
        return info

    info.docstring = _get_docstring(tree)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef):
                    methods.append({
                        "name": child.name,
                        "args": _fmt_args(child.args),
                        "docstring": _get_docstring(child),
                        "line": child.lineno,
                    })
            info.classes.append({
                "name": node.name,
                "docstring": _get_docstring(node),
                "line": node.lineno,
                "methods": methods,
            })
        elif isinstance(node, ast.FunctionDef):
            info.functions.append({
                "name": node.name,
                "args": _fmt_args(node.args),
                "docstring": _get_docstring(node),
                "line": node.lineno,
            })
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports.append(alias.name)
            else:
                mod = node.module or ""
                info.imports.append(mod)

    return info


def scan_repo() -> List[ModuleInfo]:
    modules: List[ModuleInfo] = []
    for pyfile in sorted(REPO_ROOT.rglob("*.py")):
        rel = pyfile.relative_to(REPO_ROOT).as_posix()
        if pyfile.name in EXCLUDE_FILES:
            continue
        if any(part in EXCLUDE_DIRS for part in pyfile.parts):
            continue
        info = parse_file(pyfile, rel)
        modules.append(info)
    return modules


# ── HTML generation ──────────────────────────────────────────────────────────

CSS = """
/* ===== RESET + BASE ===== */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0a0a;
  --bg2:#0f0f12;
  --bg3:#15151a;
  --ink:#f0e8df;
  --dim:#6a6470;
  --dim2:#3a3840;
  --accent:#ff6b1f;
  --accent2:#ffb347;
  --green:#7cffb5;
  --red:#ff5a6e;
  --blue:#7ab6ff;
  --yellow:#ffd166;
  --mono:'JetBrains Mono',monospace;
  --radius:4px;
}
html{scroll-behavior:smooth;font-size:16px}
body{background:var(--bg);color:var(--ink);font-family:var(--mono);overflow-x:hidden;line-height:1.6}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--accent);border-radius:3px}

/* ===== LAYOUT ===== */
.container{max-width:1200px;margin:0 auto;padding:0 40px}
header{
  position:sticky;top:0;z-index:50;
  background:rgba(10,10,10,.95);backdrop-filter:blur(16px);
  border-bottom:1px solid rgba(255,107,31,.12);
  padding:20px 0;
}
header .container{display:flex;align-items:center;gap:24px;flex-wrap:wrap}
header h1{font-size:20px;letter-spacing:-.03em}
header .stats{display:flex;gap:20px;margin-left:auto;flex-wrap:wrap}
header .stat{font-size:12px;color:var(--dim)}
header .stat b{color:var(--accent);font-size:14px}
header input{
  background:var(--bg2);border:1px solid var(--dim2);color:var(--ink);
  padding:8px 14px;font-family:var(--mono);font-size:13px;border-radius:var(--radius);
  outline:none;width:260px;
}
header input:focus{border-color:var(--accent)}
header input::placeholder{color:var(--dim)}

/* ===== MODULES ===== */
main{padding:40px 0}
.module{
  background:var(--bg2);border:1px solid var(--dim2);border-radius:var(--radius);
  margin-bottom:16px;overflow:hidden;
}
.module-header{
  display:flex;align-items:center;gap:12px;padding:16px 20px;
  cursor:pointer;user-select:none;transition:background .2s;
}
.module-header:hover{background:rgba(255,107,31,.06)}
.module-header .path{font-size:14px;font-weight:700;color:var(--accent)}
.module-header .loc{font-size:11px;color:var(--dim);margin-left:auto}
.module-body{display:none;padding:0 20px 20px}
.module.open .module-body{display:block}
.module-header .chevron{font-size:12px;color:var(--dim);transition:transform .2s}
.module.open .module-header .chevron{transform:rotate(90deg)}

.docstring{color:var(--dim);font-size:13px;margin-bottom:16px;white-space:pre-wrap}

.section-title{font-size:12px;text-transform:uppercase;letter-spacing:.2em;color:var(--dim);margin:16px 0 8px;border-bottom:1px solid var(--dim2);padding-bottom:4px}
.item{padding:8px 0;border-bottom:1px solid rgba(58,56,64,.4)}
.item:last-child{border-bottom:none}
.item-name{font-size:13px;color:var(--ink);font-weight:700}
.item-sig{font-size:12px;color:var(--blue);margin-left:8px}
.item-doc{font-size:12px;color:var(--dim);margin-top:4px}

.imports{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.import-tag{font-size:11px;background:var(--bg3);color:var(--dim);padding:3px 8px;border-radius:2px}

/* ===== GRAPH ===== */
.graph-container{background:var(--bg2);border:1px solid var(--dim2);border-radius:var(--radius);padding:20px;margin-bottom:40px}
.graph-container h2{font-size:16px;margin-bottom:16px;color:var(--accent)}
#dep-graph{width:100%;height:500px;background:var(--bg3);border-radius:var(--radius)}

.hidden{display:none}
footer{text-align:center;padding:40px 0;font-size:12px;color:var(--dim);border-top:1px solid var(--dim2);margin-top:40px}
"""

JS = """
document.addEventListener('DOMContentLoaded', () => {
  // Toggle modules
  document.querySelectorAll('.module-header').forEach(h => {
    h.addEventListener('click', () => h.parentElement.classList.toggle('open'));
  });

  // Search
  const search = document.getElementById('search');
  search.addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('.module').forEach(mod => {
      const text = mod.innerText.toLowerCase();
      mod.classList.toggle('hidden', q && !text.includes(q));
    });
  });

  // D3 force-directed graph (lightweight inline)
  const data = window.__GRAPH_DATA__;
  if (!data || !data.nodes.length) return;

  const canvas = document.getElementById('dep-graph');
  const ctx = canvas.getContext('2d');
  let w, h;
  const resize = () => {
    const rect = canvas.parentElement.getBoundingClientRect();
    w = canvas.width = rect.width - 40;
    h = canvas.height = 500;
  };
  resize();
  window.addEventListener('resize', resize);

  const nodes = data.nodes.map(n => ({...n, x: Math.random()*w, y: Math.random()*h, vx:0, vy:0}));
  const links = data.links.map(l => ({...l}));
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  function step() {
    // forces
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i+1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        let dist = Math.sqrt(dx*dx + dy*dy) || 1;
        const f = 2000 / (dist * dist);
        const fx = (dx/dist)*f, fy = (dy/dist)*f;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      }
    }
    for (const l of links) {
      const a = nodeMap[l.source], b = nodeMap[l.target];
      if (!a || !b) continue;
      let dx = b.x - a.x, dy = b.y - a.y;
      let dist = Math.sqrt(dx*dx + dy*dy) || 1;
      const f = (dist - 80) * 0.005;
      const fx = (dx/dist)*f, fy = (dy/dist)*f;
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
    }
    for (const n of nodes) {
      n.vx += (w/2 - n.x) * 0.0005;
      n.vy += (h/2 - n.y) * 0.0005;
      n.vx *= 0.92; n.vy *= 0.92;
      n.x += n.vx; n.y += n.vy;
      n.x = Math.max(10, Math.min(w-10, n.x));
      n.y = Math.max(10, Math.min(h-10, n.y));
    }

    ctx.clearRect(0,0,w,h);
    ctx.strokeStyle = 'rgba(255,107,31,.15)';
    ctx.lineWidth = 1;
    for (const l of links) {
      const a = nodeMap[l.source], b = nodeMap[l.target];
      if (!a || !b) continue;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    for (const n of nodes) {
      ctx.fillStyle = n.group === 1 ? '#ff6b1f' : '#3a3840';
      ctx.beginPath(); ctx.arc(n.x, n.y, n.group === 1 ? 6 : 3, 0, Math.PI*2); ctx.fill();
      if (n.group === 1) {
        ctx.fillStyle = '#6a6470';
        ctx.font = '10px JetBrains Mono';
        ctx.fillText(n.id.replace(/^.*\\//,''), n.x + 10, n.y + 3);
      }
    }
    requestAnimationFrame(step);
  }
  step();
});
"""


def build_graph_data(modules: List[ModuleInfo]) -> Tuple[List[Dict], List[Dict]]:
    nodes: Dict[str, Dict] = {}
    links: List[Dict] = []
    for m in modules:
        nid = m.rel_path
        nodes[nid] = {"id": nid, "group": 1}
        for imp in m.imports:
            if imp.startswith(".") or imp == "":
                continue
            # map to local file if possible
            parts = imp.replace(".", "/") + ".py"
            candidates = [m2.rel_path for m2 in modules if m2.rel_path.endswith(parts) or m2.rel_path == parts]
            if candidates:
                target = candidates[0]
                nodes[target] = nodes.get(target, {"id": target, "group": 1})
                links.append({"source": nid, "target": target})
            else:
                # external package
                top = imp.split(".")[0]
                if top not in nodes:
                    nodes[top] = {"id": top, "group": 2}
                links.append({"source": nid, "target": top})
    return list(nodes.values()), links


def escape_html(text: str | None) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def generate_html(modules: List[ModuleInfo]) -> str:
    total_loc = sum(m.loc for m in modules)
    total_classes = sum(len(m.classes) for m in modules)
    total_functions = sum(len(m.functions) for m in modules)
    graph_nodes, graph_links = build_graph_data(modules)

    module_sections = []
    for m in modules:
        classes_html = ""
        if m.classes:
            items = ""
            for c in m.classes:
                methods_html = ""
                if c["methods"]:
                    methods_html = '<div style="margin-left:16px;margin-top:6px;">'
                    for meth in c["methods"]:
                        doc = escape_html(meth["docstring"] or "")[:200]
                        methods_html += f'<div class="item"><span class="item-name">↳ {meth["name"]}</span><span class="item-sig">({meth["args"]})</span>'
                        if doc:
                            methods_html += f'<div class="item-doc">{doc}</div>'
                        methods_html += '</div>'
                    methods_html += '</div>'
                doc = escape_html(c["docstring"] or "")[:300]
                items += f'<div class="item"><span class="item-name">class {c["name"]}</span><div class="item-doc">{doc}</div>{methods_html}</div>'
            classes_html = f'<div class="section-title">Classes ({len(m.classes)})</div>{items}'

        functions_html = ""
        if m.functions:
            items = ""
            for f in m.functions:
                doc = escape_html(f["docstring"] or "")[:300]
                items += f'<div class="item"><span class="item-name">def {f["name"]}</span><span class="item-sig">({f["args"]})</span>'
                if doc:
                    items += f'<div class="item-doc">{doc}</div>'
                items += '</div>'
            functions_html = f'<div class="section-title">Functions ({len(m.functions)})</div>{items}'

        imports_html = ""
        if m.imports:
            tags = "".join(f'<span class="import-tag">{escape_html(imp)}</span>' for imp in sorted(set(m.imports)))
            imports_html = f'<div class="section-title">Imports</div><div class="imports">{tags}</div>'

        doc = escape_html(m.docstring or "")[:500]
        doc_html = f'<div class="docstring">{doc}</div>' if doc else ""

        module_sections.append(
            f'<div class="module">'
            f'<div class="module-header"><span class="chevron">▶</span><span class="path">{m.rel_path}</span><span class="loc">{m.loc} LOC</span></div>'
            f'<div class="module-body">{doc_html}{classes_html}{functions_html}{imports_html}</div>'
            f'</div>'
        )

    graph_data_json = json.dumps({"nodes": graph_nodes, "links": graph_links})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Falcon API Docs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
{CSS}
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>📚 Falcon API Docs</h1>
    <input type="text" id="search" placeholder="Search modules, classes, functions...">
    <div class="stats">
      <div class="stat"><b>{len(modules)}</b> modules</div>
      <div class="stat"><b>{total_classes}</b> classes</div>
      <div class="stat"><b>{total_functions}</b> functions</div>
      <div class="stat"><b>{total_loc:,}</b> LOC</div>
    </div>
  </div>
</header>
<main>
  <div class="container">
    <div class="graph-container">
      <h2>Dependency Graph</h2>
      <canvas id="dep-graph"></canvas>
    </div>
    <div class="modules-list">
      {''.join(module_sections)}
    </div>
  </div>
</main>
<footer>
  <div class="container">
    Auto-generated by <code>docs/generate.py</code> · Falcon Project
  </div>
</footer>
<script>
window.__GRAPH_DATA__ = {graph_data_json};
{JS}
</script>
</body>
</html>
"""


def main() -> int:
    print("[generate] Scanning repository...")
    modules = scan_repo()
    print(f"[generate] Found {len(modules)} modules")

    print("[generate] Building api.html...")
    html = generate_html(modules)
    API_HTML.write_text(html, encoding="utf-8")
    print(f"[generate] Written {API_HTML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
