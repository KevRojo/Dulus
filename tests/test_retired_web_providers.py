"""Upgraded public installs must never route a saved browser session to another provider."""
import json
import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput

import config
import dulus
import providers
from agent import AgentState
from input import SlashCompleter


@pytest.mark.parametrize(("provider", "model"), [
    ("claude-web", "claude-web/claude-sonnet-4-6"),
    ("claude-code", "claude-code/claude-opus-4-6"),
    ("deepseek-web", "deepseek-web/deepseek-r1"),
    ("gemini-web", "gemini-web/gemini-latest"),
    ("kimi-web", "kimi-web/kimi-latest"),
    ("qwen-web", "qwen-web/qwen-plus"),
    ("gemini-web", "GEMINI_WEB:gemini-latest"),
    ("claude-web", "claude-web"),
])
def test_retired_models_stop_before_credentials(provider, model, monkeypatch):
    assert providers.detect_provider(model) == provider
    assert provider not in providers.PROVIDERS
    assert not providers.get_api_key(provider, {f"{provider}_api_key": "old"})
    monkeypatch.setattr(providers, "get_api_key", lambda *_: pytest.fail("looked up credentials"))
    events = list(providers.stream(model, "", [], [], {}))
    assert len(events) == 2
    chunk, turn = events
    assert isinstance(chunk, providers.TextChunk)
    assert isinstance(turn, providers.AssistantTurn) and turn.error
    assert provider in chunk.text
    assert chunk.text == turn.text
    assert "/model" in turn.text


@pytest.mark.parametrize(("model", "provider"), [
    ("nvidia-web/meta/llama-3.3-70b-instruct", "nvidia-web"),
    ("kimi-code/k3", "kimi-code"),
    ("custom/claude-code", "custom"),
])
def test_other_provider_names_remain_selectable(model, provider):
    assert providers.detect_provider(model) == provider


def test_resume_keeps_transcript_and_requires_explicit_model_change(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)
    auth = tmp_path / "gemini_web.json"
    auth.write_text('{"cookies": {"SID": "old-session"}}', encoding="utf-8")
    config_file.write_text(json.dumps({
        "model": "gemini-web/gemini-latest", "gemini_web_auth_path": str(auth),
        "pending_first_run_harvest": "gemini", "gemini_api_key": "own-key",
    }), encoding="utf-8")
    saved = tmp_path / "session_latest.json"
    messages = [{"role": "user", "content": "earlier question"}]
    saved.write_text(json.dumps({"messages": messages, "turn_count": 1}), encoding="utf-8")
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)
    cfg = config.load_config()
    state = AgentState()
    dulus.cmd_resume("", state, cfg)
    assert state.messages == messages

    calls = []

    def record_request(*args):
        calls.append(args)
        return ()

    monkeypatch.setattr(providers, "stream_openai_compat", record_request)
    assert list(providers.stream(cfg["model"], "", state.messages, [], cfg))[-1].error
    assert calls == []

    dulus.cmd_model("gemini/gemini-2.0-flash", state, cfg)
    list(providers.stream(cfg["model"], "", state.messages, [], cfg))
    assert len(calls) == 1
    assert calls[0][:3] == (
        "own-key", providers.PROVIDERS["gemini"]["base_url"], "gemini-2.0-flash",
    )
    assert calls[0][4] == messages


@pytest.mark.parametrize("command", ["/model claude-code:opus", "/config model=claude-web/opus"])
def test_rejected_selection_keeps_current_model(command, monkeypatch, capsys):
    cfg = {"model": "dulus/dulus-b-27b"}
    monkeypatch.setattr(config, "save_config", lambda *_: pytest.fail("saved a removed provider"))
    assert dulus.handle_slash(command, None, cfg)
    assert cfg["model"] == "dulus/dulus-b-27b"
    assert "/login dulus" in capsys.readouterr().err


@pytest.mark.parametrize(("args", "expected"), [
    (["--cmd", "harvest-gemini"], "Unknown command"),
    (["-p", "hello"], "gemini-web"),
    (["--model", "claude-code:opus", "-p", "hello"], "claude-code"),
])
def test_one_shot_reports_error_for_removed_commands_and_saved_models(args, expected, tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({
        "model": "gemini-web/gemini-latest", "telemetry": False,
    }), encoding="utf-8")
    env = dict(os.environ, DULUS_CONFIG_DIR=str(tmp_path), DULUS_HOME=str(tmp_path),
               DULUS_API_KEY="dulus_sk_" + "x" * 32)
    run = subprocess.run(
        [sys.executable, "-m", "dulus", "--output", "json", *args],
        cwd=Path(dulus.__file__).parent, env=env, capture_output=True, encoding="utf-8", timeout=20,
    )
    assert run.returncode == 1
    frame = json.loads(run.stdout)
    assert frame["type"] == "error" and expected in frame["message"]


def test_harvest_commands_are_absent_from_help_dispatch_and_completions(capsys):
    dulus.cmd_help("", None, {})
    help_text = (dulus.__doc__ + capsys.readouterr().out).lower()
    completer = SlashCompleter(lambda: dulus.COMMANDS, lambda: dulus._CMD_META)
    suggestions = {item.text for item in completer.get_completions(Document("/"), CompleteEvent())}
    assert "/model" in suggestions
    assert "harvest" not in help_text
    assert not any("harvest" in name for name in suggestions | dulus.COMMANDS.keys())
    for name in ("claude_chats", "gemini_chats", "kimi_chats"):
        assert name not in dulus.COMMANDS
        assert f"/{name}" not in help_text and f"/{name}" not in suggestions
    assert dulus._model_dynamic_completions("gemini-web/") == []
    assert "gemini/gemini-2.0-flash" in dulus._model_dynamic_completions("gemini/")


def test_old_slash_alias_cannot_fall_through_to_a_saved_skill(monkeypatch, capsys):
    import skill

    monkeypatch.setattr(skill, "find_skill", lambda *_: pytest.fail("looked up a retired command"))
    assert dulus.handle_slash("/gemini_harvest", None, {})
    assert "Unknown command" in capsys.readouterr().err


@pytest.mark.asyncio
@pytest.mark.parametrize("module", ["input", "ui.input"])
async def test_history_suggests_valid_entries_after_upgrade(module, tmp_path):
    path = tmp_path / "input_history_pt.txt"
    history = FileHistory(str(path))
    for entry in ("/help", "/model custom/claude-code", "/harvest-gemini", "/gemini_harvest",
                  "/kimi_chats", "/model claude-code/opus", "/config model=gemini-web:pro"):
        history.append_string(entry)
    with create_app_session(input=DummyInput(), output=DummyOutput()):
        session = import_module(module)._build_session(path)
    buffer = session.default_buffer
    entries = [entry async for entry in buffer.history.load()]
    assert "/harvest-gemini" in entries
    suggest = session.auto_suggest
    for prefix in ("/har", "/gemini_", "/kimi_ch", "/model claude-code", "/config model="):
        assert suggest.get_suggestion(buffer, Document(prefix)) is None
    assert suggest.get_suggestion(buffer, Document("/h")).text == "elp"
    assert suggest.get_suggestion(buffer, Document("/model ")).text == "custom/claude-code"
