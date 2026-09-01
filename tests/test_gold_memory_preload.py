"""Gold memory (incl. short_memory) must survive `/mem_palace off`.

`/mem_palace` is a cost knob for per-turn *semantic search*. It was silently
also starving the model of the curated `short_memory` scratchpad, and the
GUI/WebChat surfaces never loaded gold memories at all — only the CLI REPL
did. These tests lock the contract:

1. `gold_context_messages()` returns gold entries regardless of any config.
2. WebChat's `_preload_gold_memories` seeds a fresh session even when
   `mem_palace=False` (GUI *display* copies).
3. The preload is idempotent (re-entry must not double-inject).
4. Model source of truth is the system prompt via `gold_system_fragment` /
   `soul_system_fragment` — always present, even under lite mode.
5. API path strips baseline display blobs (soul/gold/welcome).
6. MemPalace per-turn inject skips short_memory / soul (no dual-path noise).
"""
from __future__ import annotations

from agent import AgentState


def test_gold_context_messages_includes_short_memory() -> None:
    from memory import gold_context_messages
    from memory.store import is_short_memory_name

    msgs = gold_context_messages()
    assert msgs, "gold_context_messages returned nothing — short_memory missing?"
    for m in msgs:
        assert m["role"] == "assistant"  # GUI display copy
        assert m["content"].startswith("[Golden Memory Loaded:")
    assert any(
        is_short_memory_name(
            m["content"].split("]", 1)[0].removeprefix("[Golden Memory Loaded: ").strip()
        )
        for m in msgs
    ), "short_memory must always be among the gold preload"


def test_gold_system_fragment_is_model_source_of_truth() -> None:
    """System prompt fragment carries short_memory — not chat turns."""
    from memory import gold_system_fragment

    frag = gold_system_fragment()
    assert frag, "gold_system_fragment empty — short_memory not in system baseline"
    assert "short_memory" in frag or "Short Memory" in frag
    assert "[Golden Memory Loaded:" in frag
    assert "always-on baseline" in frag.lower() or "Golden Memory" in frag


def test_build_system_prompt_embeds_gold_and_soul() -> None:
    from context import build_system_prompt

    prompt = build_system_prompt({"model": "test-model", "lite_mode": True})
    assert "[Golden Memory Loaded:" in prompt or "short_memory" in prompt.lower()
    # Soul may or may not exist on a fresh machine; gold short_memory is forced.


def test_preload_runs_with_mem_palace_off() -> None:
    """The bug this guards: `/mem_palace off` used to also blind the model to gold."""
    import webchat_server as ws

    state = AgentState()
    cfg = {"mem_palace": False}

    ws._preload_gold_memories(state, cfg)

    assert state.messages, "gold preload skipped while mem_palace was off"
    assert any(
        m["content"].startswith(ws._GOLD_MARKER) for m in state.messages
    )


def test_preload_is_idempotent() -> None:
    import webchat_server as ws

    state = AgentState()
    cfg: dict = {"mem_palace": True}

    ws._preload_gold_memories(state, cfg)
    first = len(state.messages)
    assert first >= 1

    ws._preload_gold_memories(state, cfg)
    assert len(state.messages) == first, "gold preload double-injected"


def test_baseline_display_message_detector() -> None:
    from memory import is_baseline_display_message, is_baseline_memory_name

    assert is_baseline_display_message({
        "role": "assistant",
        "content": "[Golden Memory Loaded: short_memory]\n\nhello",
    })
    assert is_baseline_display_message({
        "role": "assistant",
        "content": "[Identity Essence Loaded: soul]\n\nI am Dulus",
    })
    assert is_baseline_display_message({
        "role": "assistant",
        "content": "<!-- dulus:welcome -->\nWelcome",
    })
    assert not is_baseline_display_message({
        "role": "assistant",
        "content": "Normal reply about OVH",
    })
    assert is_baseline_memory_name("short_memory")
    assert is_baseline_memory_name("short-memory")
    assert is_baseline_memory_name("soul")
    assert not is_baseline_memory_name("ovh_le_beast")


def test_lookback_strips_baseline_from_api_window() -> None:
    from lookback import apply_lookback_window

    msgs = [
        {"role": "assistant", "content": "[Golden Memory Loaded: short_memory]\n\nOVH stuck"},
        {"role": "assistant", "content": "[Identity Essence Loaded: soul]\n\nI am Dulus"},
        {"role": "user", "content": "klk"},
        {"role": "assistant", "content": "Klk papi"},
    ]
    window, meta = apply_lookback_window(msgs, {"lookback": False})
    assert all(
        not (m.get("content") or "").startswith("[Golden Memory Loaded:")
        for m in window
    )
    assert all(
        not (m.get("content") or "").startswith("[Identity Essence Loaded:")
        for m in window
    )
    assert any(m.get("content") == "klk" for m in window)
    assert meta.get("baseline_stripped", 0) >= 2 or len(window) == 2


def test_is_baseline_memory_name_filters_mempalace_hits() -> None:
    from memory import is_baseline_memory_name

    hits = [
        {"name": "short_memory", "content": "OVH", "keyword_score": 0.9},
        {"name": "palace", "content": "# Short Memory (gold)\n...", "keyword_score": 0.8},
        {"name": "ovh_notes", "content": "le-beast IP", "keyword_score": 0.7},
        {"name": "soul", "content": "I am Dulus", "keyword_score": 0.6},
    ]
    kept = [
        h for h in hits
        if not is_baseline_memory_name(h.get("name"))
    ]
    names = {h["name"] for h in kept}
    assert "short_memory" not in names
    assert "soul" not in names
    assert "ovh_notes" in names
    assert "palace" in names  # generic palace name stays; content filter is separate
