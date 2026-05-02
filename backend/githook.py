"""Git hook management for Falcon."""
import os
import subprocess
import sys
from pathlib import Path

HOOK_TEMPLATE = '''#!/usr/bin/env python3
"""Falcon Pre-Commit Hook — auto-installed by `falcon git-hook install`"""
import subprocess
import sys
from pathlib import Path

BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"
MAX_MB = 10

def log(msg, level="info"):
    colors = {"error": RED, "ok": GREEN, "warn": YELLOW, "info": ""}
    print(f"{colors.get(level, '')}{BOLD}[falcon-hook]{RESET} {msg}")

def get_staged():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True
    )
    return [f for f in r.stdout.strip().split("\\n") if f]

def check_trailing(files):
    issues = []
    for f in files:
        p = Path(f)
        if not p.exists() or p.stat().st_size > 1024*1024:
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if line.rstrip() != line.rstrip(" \\t"):
                        issues.append((f, i, "trailing whitespace"))
        except Exception:
            pass
    return issues

def check_syntax(files):
    issues = []
    for f in files:
        if not f.endswith(".py"):
            continue
        r = subprocess.run([sys.executable, "-m", "py_compile", f],
                          capture_output=True, text=True)
        if r.returncode != 0:
            issues.append((f, 0, f"syntax error: {r.stderr.strip()[:80]}"))
    return issues

def check_size(files):
    return [(f, 0, f"file > {MAX_MB}MB")
            for f in files if Path(f).exists() and Path(f).stat().st_size > MAX_MB*1024*1024]

def check_tasks(files):
    p = Path(".falcon-context/tasks.json")
    if not p.exists():
        return []
    try:
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
        for t in data.get("tasks", []):
            if t.get("status") == "completed" and t.get("blocked_by"):
                return [(str(p), 0, f"Task #{t['id']} completed but has blockers")]
    except Exception:
        pass
    return []

def main():
    log("Running Falcon pre-commit checks...", "info")
    files = get_staged()
    if not files:
        log("No staged files - skipping", "ok")
        sys.exit(0)

    checks = [
        ("trailing whitespace", check_trailing),
        ("Python syntax", check_syntax),
        ("large files", check_size),
        ("task consistency", check_tasks),
    ]
    all_issues = []
    for name, fn in checks:
        issues = fn(files)
        if issues:
            all_issues.extend(issues)
            log(f"{name}: {len(issues)} issue(s)", "warn")

    if all_issues:
        log(f"Found {len(all_issues)} issue(s):", "error")
        for f, line, msg in all_issues[:10]:
            loc = f":{line}" if line else ""
            print(f"  {RED}[X]{RESET} {f}{loc} - {msg}")
        if len(all_issues) > 10:
            print(f"  ... and {len(all_issues)-10} more")
        log("Commit blocked. Fix or use --no-verify to bypass.", "error")
        sys.exit(1)

    log("All checks passed! Falcon out.", "ok")
    sys.exit(0)

if __name__ == "__main__":
    main()
'''


def _hook_path():
    git_dir = Path(".git")
    if not git_dir.exists():
        return None
    return git_dir / "hooks" / "pre-commit"


def is_falcon_hook(path: Path) -> bool:
    return path.exists() and "Falcon Pre-Commit Hook" in path.read_text(encoding="utf-8")


def install():
    hook = _hook_path()
    if hook is None:
        print("[X] Not a git repository.")
        sys.exit(1)

    if hook.exists():
        backup = hook.with_suffix(".backup")
        hook.rename(backup)
        print(f"[BK] Backed up existing hook to {backup.name}")

    hook.write_text(HOOK_TEMPLATE, encoding="utf-8")
    try:
        hook.chmod(0o755)
    except Exception:
        pass
    print("[OK] Falcon pre-commit hook installed!")
    print("     Checks: trailing whitespace / Python syntax / large files / task consistency")


def uninstall():
    hook = _hook_path()
    if hook is None:
        print("[X] Not a git repository.")
        sys.exit(1)

    if is_falcon_hook(hook):
        hook.unlink()
        print("[OK] Falcon pre-commit hook removed.")
    else:
        print("[!] No Falcon hook found.")


def status():
    hook = _hook_path()
    if hook is None:
        print("[X] Not a git repository.")
        sys.exit(1)

    if is_falcon_hook(hook):
        print("[OK] Falcon pre-commit hook is active.")
    else:
        print("[--] Falcon pre-commit hook is NOT installed.")
