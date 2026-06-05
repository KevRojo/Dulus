# Contributing to Dulus

> Thank you for considering contributing to Dulus! This document will get you started.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Code Structure](#code-structure)
- [Adding Tools](#adding-tools)
- [Adding Providers](#adding-providers)
- [Adding Skills](#adding-skills)
- [Testing](#testing)
- [Style Guide](#style-guide)
- [Code of Conduct](#code-of-conduct)

---

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/Dulus && cd Dulus
```
3. Install in editable mode:
```bash
pip install -e .
pip install -e ".[full]"   # with all extras
```
4. Run the tests to make sure everything works:
```bash
python -m pytest tests/ -v
```
5. Create a branch for your changes:
```bash
git checkout -b feature/my-awesome-feature
```

---

## Code Structure

```
dulus/
  dulus.py              # Entry point (~11,800 lines)
  agent.py              # Core agent loop (~420 lines)
  providers.py          # Multi-provider streaming (~4,500 lines)
  tools.py              # Built-in tools (~2,940 lines)
  tool_registry.py      # Tool plugin system (~215 lines)
  compaction.py         # Context management (~375 lines)
  context.py            # System prompt builder (~360 lines)
  config.py             # Configuration (~185 lines)
  governance.py         # Budget/permission governance (~275 lines)
  soul.py               # Personality system (~120 lines)
  welcome.py            # First-run wizard (~290 lines)
  webchat.py            # WebChat server (~430 lines)
  webchat_server.py     # Production webchat (~4,300 lines)
  dulus_gui.py          # Desktop GUI (~385 lines)
  batch_api.py          # Batch processor (~470 lines)
  common.py             # Shared utilities (~210 lines)
  input.py              # Input handling (~1,150 lines)
  memory/               # MemPalace semantic memory
  skill/                # Skill system
  multi_agent/          # Sub-agent system
  plugin/               # Auto-Adapter plugin system
  voice/                # STT (Whisper) + TTS
  checkpoint/           # Session snapshots
  task/                 # Task management
  webbridge/            # Playwright browser automation
  dulus_mcp/            # MCP client
  tests/                # 263+ tests
```

**Key invariant:** Dependencies flow downward. `dulus.py` imports `agent.py`, which imports `providers.py`, `tool_registry.py`, `compaction.py`, etc. No circular imports at the module level.

---

## Adding Tools

Tools are the primary way to extend Dulus's capabilities. Here's how to add one:

### 1. Define Your Tool

```python
from tool_registry import ToolDef, register_tool

def my_awesome_tool(params: dict, config: dict) -> str:
    """Your tool implementation."""
    name = params.get("name", "world")
    return f"Hello, {name}! This tool is awesome."

register_tool(ToolDef(
    name="MyAwesomeTool",
    schema={
        "name": "MyAwesomeTool",
        "description": "Does something awesome. Use when the user wants awesomeness.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to greet"
                }
            },
            "required": ["name"]
        }
    },
    func=my_awesome_tool,
    read_only=True,          # auto-approve in 'auto' mode
    concurrent_safe=True,    # safe for parallel sub-agents
))
```

### 2. Place Your Tool

- **Built-in tool:** Add to `tools.py` (imports at top ensure registration)
- **Plugin tool:** Create a plugin that registers on import
- **MCP tool:** Configure an MCP server in `.mcp.json`

### 3. Test Your Tool

```python
# tests/test_my_tool.py
from tool_registry import get_tool, execute_tool

def test_my_awesome_tool():
    tool = get_tool("MyAwesomeTool")
    assert tool is not None
    result = execute_tool("MyAwesomeTool", {"name": "Dulus"}, {})
    assert "Hello, Dulus!" in result
```

### Tool Design Guidelines

- **Name:** Use PascalCase, descriptive. Examples: `Read`, `WebFetch`, `ExtractTextFromImage`
- **Description:** Be specific about when the LLM should use this tool
- **Read-only:** Mark `True` if the tool only reads data (safe to auto-approve)
- **Concurrent-safe:** Mark `True` if the tool has no side effects (safe for parallel agents)
- **Output:** Return a string. Keep it under 32K characters (auto-truncated beyond that)
- **Errors:** Return strings starting with `Error: ` — the model knows to handle them

---

## Adding Providers

Dulus supports any OpenAI-compatible API out of the box via the `custom` provider. For native support:

### 1. Add Provider Config

In `providers.py`, add to the `PROVIDERS` dict:

```python
PROVIDERS = {
    # ... existing providers ...
    "myprovider": {
        "base_url": "https://api.myprovider.com/v1",
        "api_key_env": "MYPROVIDER_API_KEY",
        "models": ["myprovider-model-1", "myprovider-model-2"],
        "default_model": "myprovider-model-1",
    },
}
```

### 2. Add Model Detection

In the `detect_provider()` function:

```python
def detect_provider(model: str) -> str:
    # ... existing detection ...
    if model.startswith("myprovider-"):
        return "myprovider"
    # ...
```

### 3. Add Cost Calculation

In the `calc_cost()` function:

```python
def calc_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    rates = {
        # ... existing rates ...
        "myprovider-model-1": (0.50, 1.50),   # ($/1M input, $/1M output)
    }
    # ...
```

### 4. Test

```bash
export MYPROVIDER_API_KEY=sk-...
dulus --model myprovider/model-1
```

---

## Adding Skills

Skills are markdown files with frontmatter that define reusable prompt templates.

### Skill File Format

Create a file at `~/.dulus/skills/my-skill.md`:

```markdown
---
name: my-skill
description: Does something useful
triggers: ["/mytrigger"]
tools: [Read, Write, Bash]
---

You are an expert at doing this thing. Follow these steps:

1. Read the relevant files
2. Analyze the code
3. Make the necessary changes
4. Run tests to verify

Always explain your reasoning before making changes.
```

### Skill Discovery

Skills are discovered from:
- Project: `./.dulus/skills/`
- User: `~/.dulus/skills/`

Project-level overrides user-level when names collide.

### Testing Skills

```python
# tests/test_skills.py
from skills import load_skill, execute_skill

def test_my_skill():
    skill = load_skill("my-skill")
    assert skill is not None
    assert "mytrigger" in skill.triggers
```

---

## Testing

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific module
python -m pytest tests/test_tool_registry.py -v
python -m pytest tests/test_compaction.py -v
python -m pytest tests/test_memory.py -v
python -m pytest tests/test_subagent.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Writing Tests

- Use `monkeypatch` to mock external APIs
- Use `tmp_path` for filesystem operations
- Mock `_agent_run` for sub-agent tests to avoid real API calls
- Each test should be independent (no shared state)

```python
def test_read_tool(tmp_path, monkeypatch):
    # Create a temp file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    # Mock cwd
    monkeypatch.chdir(tmp_path)

    # Execute tool
    result = execute_tool("Read", {"file_path": str(test_file)}, {})
    assert "Hello, World!" in result
```

---

## Style Guide

### Python

- **Line length:** 100 characters (not 79, not 120)
- **Quotes:** Double quotes for strings, single quotes for dict keys
- **Imports:** Standard lib first, third-party second, local third
- **Type hints:** Use them for function signatures
- **Docstrings:** Google style

```python
"""Module docstring."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests
from rich import print

from config import load_config


def my_function(param: str, optional: Optional[int] = None) -> str:
    """Short description.

    Longer description if needed.

    Args:
        param: Required parameter description.
        optional: Optional parameter description.

    Returns:
        Description of return value.
    """
    return f"Result: {param}"
```

### Commit Messages

Follow conventional commits:

```
feat: add new WebBridge screenshot tool
fix: handle empty tool responses gracefully
docs: update architecture diagram
test: add tests for MemPalace search
refactor: simplify permission checking logic
```

---

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

**Unacceptable behavior:**
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project team at [@KevRojo](https://x.com/KevRojo). All complaints will be reviewed and investigated promptly.

---

## Questions?

- Join the conversation on [X / @KevRojo](https://x.com/KevRojo)
- Open an issue on [GitHub](https://github.com/KevRojo/Dulus/issues)

---

> *Named after the bird, not the rocket. We keep flying.*
