"""Dulus Radio: the board every interactive boot prints, and /news.

It is the first screen a new install reads, so it has to fit an 80-column
terminal, keep boot short, and say plainly what the desktop app does that this
open-source CLI doesn't — with the link to get it.
"""
from __future__ import annotations

import re
import unicodedata

import pytest

import dulus

ANSI = re.compile(r"\x1b\[[0-9;]*m")

ENTRIES = [
    "- November 19, 2026 (**🧰 v3.15.4 — tool calls keep their names**): **Bash stays Bash.** "
    + "Some servers resend a tool's full name on every streamed chunk. " * 6,
    "- November 11, 2026 (**🔐 v3.15.3 — sign-in that survives a filtered network, plus a tag "
    "far too long for one line**): **A headline that runs on well past any width a terminal "
    "could give it.** Earlier body.",
    "- October 29, 2026 (**🧠 v6.4.1 — memory that stays with you**): **Memory belongs to the "
    "profile now.** Desktop body.",
]


def _cols(line: str) -> int:
    """Terminal columns: wide and emoji-presentation characters take two."""
    cols = 0
    for i, ch in enumerate(line):
        if ch in "\ufe0f\u200d" or unicodedata.combining(ch):
            continue
        wide = unicodedata.east_asian_width(ch) in "WF" or line[i + 1:i + 2] == "\ufe0f"
        cols += 2 if wide else 1
    return cols


def _board(monkeypatch, capsys, *, boot: bool) -> list[str]:
    monkeypatch.setattr(dulus, "_load_news_entries", lambda: list(ENTRIES))
    assert dulus._print_news_broadcast(3, boot=boot) is True
    return ANSI.sub("", capsys.readouterr().out).splitlines()


@pytest.mark.parametrize("boot", [True, False], ids=["boot", "/news"])
def test_the_board_fits_an_80_column_terminal(monkeypatch, capsys, boot) -> None:
    lines = _board(monkeypatch, capsys, boot=boot)
    assert [line for line in lines if _cols(line) >= 80] == []


def test_boot_airs_a_short_lead_and_earlier_dispatches_as_headlines(monkeypatch, capsys) -> None:
    lines = _board(monkeypatch, capsys, boot=True)
    start = next(i for i, line in enumerate(lines) if "» Bash stays Bash" in line)
    assert 1 <= len(lines[start + 1:lines.index("", start)]) <= 2
    text = "\n".join(lines)
    assert "Earlier body" not in text and "Desktop body" not in text
    assert "v3.15.3" in text and "v6.4.1" in text


def test_desktop_app_dispatches_are_flagged(monkeypatch, capsys) -> None:
    flagged = [line for line in _board(monkeypatch, capsys, boot=True)
               if line.rstrip().endswith("desktop app")]
    assert len(flagged) == 1 and "v6.4.1" in flagged[0]


def test_boot_plays_one_app_spot_and_news_the_whole_lineup(monkeypatch, capsys) -> None:
    titles = [name for name, _, _ in dulus._RADIO_APP_SPOTS]

    boot = "\n".join(_board(monkeypatch, capsys, boot=True))
    assert sum(name in boot for name in titles) == 1
    assert "https://dulus.ai/download/" in boot

    news = "\n".join(_board(monkeypatch, capsys, boot=False))
    assert all(name in news for name in titles)
    assert "https://dulus.ai/download/" in news


@pytest.mark.parametrize("boot", [True, False], ids=["boot", "/news"])
def test_the_board_sends_people_to_app_not_pip(monkeypatch, capsys, boot) -> None:
    # Updates ship in the app now; the board used to sign off with
    # `pip install -U dulus`.
    text = "\n".join(_board(monkeypatch, capsys, boot=boot))
    assert "/app" in text
    assert "pip install" not in text
