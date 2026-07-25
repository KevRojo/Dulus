from __future__ import annotations

import io
from pathlib import Path

from cli_animations import (
    animate_wave,
    animations_enabled,
    print_banner,
    print_creator_signature,
    tool_status,
)


def test_redirected_output_disables_cursor_animation() -> None:
    stream = io.StringIO()

    assert animations_enabled(stream) is False

    animate_wave("DULUS", frames=50, interval=1.0, stream=stream)
    output = stream.getvalue()
    assert "DULUS" in output
    assert "\033[?25l" not in output
    assert "\r" not in output


def test_creator_signature_is_clean_in_logs() -> None:
    stream = io.StringIO()

    print_creator_signature("kevrojo", stream=stream)

    assert stream.getvalue() == "  ◆  kevrojo  ◆\n"


def test_banner_signature_and_tool_status_share_visual_language() -> None:
    stream = io.StringIO()

    print_banner("dulus", stream=stream)
    print_creator_signature("kevrojo", stream=stream)

    output = stream.getvalue()
    assert "Your feathered AI companion" in output
    assert "kevrojo" in output
    assert "✓" in tool_status("Read", "done", "12 lines")


def test_public_cli_wires_animation_showcase_and_signature() -> None:
    source = (Path(__file__).parents[1] / "dulus.py").read_text(encoding="utf-8")

    assert '"animations":  cmd_animations' in source
    # The banner signature is personalized from the welcome wizard's
    # config["user_name"], not a hardcoded name.
    assert "print_creator_signature(_sig)" in source
    assert 'config.get("user_name")' in source
    assert "_cli_thinking_line(i, phrase)" in source
    assert "_cli_tool_status(desc, \"running\")" in source
    assert "Interant" not in source
