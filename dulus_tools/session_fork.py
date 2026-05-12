"""SessionFork - Fork and undo session functionality.

Provides the ability to fork a session at any given turn (creating a new
session branched from that point) and to undo the last turn (forking at
the second-to-last turn).

Inspired by kimi-cli's checkpoint / undo / fork workflow.
"""

import json
import shutil
import re
import os
import time
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Pattern used by kimi-cli to embed checkpoint markers in assistant text.
CHECKPOINT_USER_PATTERN = re.compile(r"^<system>CHECKPOINT \d+</system>$")


@dataclass
class TurnInfo:
    """Lightweight descriptor for a single conversation turn."""

    index: int
    user_text: str


class SessionFork:
    """Session forking and undo functionality.

    Scans the ``wire.jsonl`` file that Dulus uses to persist the raw
    wire-format conversation stream, enumerates turns (defined by
    ``TurnBegin`` / ``TurnEnd`` boundaries), and can create a new session
    directory containing a truncated copy of the wire file.
    """

    def __init__(self, session_dir: str) -> None:
        self._session_dir = Path(session_dir)

    # ------------------------------------------------------------------ #
    #  Turn enumeration
    # ------------------------------------------------------------------ #

    def enumerate_turns(self, wire_path: Optional[Path] = None) -> List[TurnInfo]:
        """Scan session history and return all turns.

        A *turn* begins when a ``TurnBegin`` message is encountered on
        the wire.  The user text is extracted from the ``user_input``
        payload (first line, max 80 chars) so that the caller can
        present a human-readable menu of turns to fork/undo to.
        """
        if wire_path is None:
            wire_path = self._session_dir / "wire.jsonl"
        if not wire_path.exists():
            return []

        turns: List[TurnInfo] = []
        current_turn = -1

        with open(wire_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                # Skip metadata envelope records
                if record.get("type") == "metadata":
                    continue

                message = record.get("message", {})
                msg_type = message.get("type")

                if msg_type == "TurnBegin":
                    current_turn += 1
                    user_input = message.get("payload", {}).get("user_input", "")
                    text = self._extract_user_text(user_input)
                    turns.append(TurnInfo(index=current_turn, user_text=text))

        return turns

    def _extract_user_text(self, user_input) -> str:
        """Extract a short preview of the user input.

        * ``str``   – take the first line, max 80 chars.
        * ``list``  – concatenate text parts, max 80 chars.
        * other     – empty string.
        """
        if isinstance(user_input, str):
            return user_input.split("\n")[0][:80]

        parts: List[str] = []
        for part in user_input if isinstance(user_input, list) else []:
            if isinstance(part, dict):
                text = part.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts)[:80]

    # ------------------------------------------------------------------ #
    #  Truncation
    # ------------------------------------------------------------------ #

    def truncate_at_turn(self, wire_path: Path, turn_index: int) -> List[str]:
        """Return every wire line up to and including the given turn.

        The walk is stateful: metadata lines are always included,
        ``TurnBegin`` increments the turn counter, and we stop as
        soon as we have passed the requested *turn_index*.

        Raises:
            ValueError: if *wire_path* does not exist.
        """
        if not wire_path.exists():
            raise ValueError("wire file not found")

        lines: List[str] = []
        current_turn = -1

        with open(wire_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                # Always carry metadata forward
                if record.get("type") == "metadata":
                    lines.append(stripped)
                    continue

                message = record.get("message", {})
                msg_type = message.get("type")

                if msg_type == "TurnBegin":
                    current_turn += 1
                    if current_turn > turn_index:
                        break

                if current_turn <= turn_index:
                    lines.append(stripped)

                # Stop precisely at the end of the target turn
                if msg_type == "TurnEnd" and current_turn == turn_index:
                    break

        return lines

    # ------------------------------------------------------------------ #
    #  Fork
    # ------------------------------------------------------------------ #

    async def fork(
        self,
        turn_index: Optional[int] = None,
        title_prefix: str = "Fork",
    ) -> str:
        """Fork session at the given turn.

        A new session directory is created next to the current one with
        a truncated ``wire.jsonl`` containing everything up to
        *turn_index* (inclusive).  When *turn_index* is ``None`` the
        entire wire file is copied (full fork).

        Returns:
            The new session ID (directory name).
        """
        new_session_id = f"{title_prefix.lower()}-{int(time.time())}"
        new_dir = self._session_dir.parent / new_session_id
        new_dir.mkdir(parents=True, exist_ok=True)

        wire_path = self._session_dir / "wire.jsonl"

        if turn_index is not None:
            lines = self.truncate_at_turn(wire_path, turn_index)
        else:
            lines = self._read_all_lines(wire_path)

        new_wire = new_dir / "wire.jsonl"
        with open(new_wire, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line + "\n")

        return new_session_id

    # ------------------------------------------------------------------ #
    #  Undo
    # ------------------------------------------------------------------ #

    async def undo(self) -> str:
        """Undo the last turn by forking at the second-to-last turn.

        Returns:
            The new session ID (directory name).

        Raises:
            ValueError: if the session has fewer than 2 turns.
        """
        turns = self.enumerate_turns()
        if len(turns) < 2:
            raise ValueError("Cannot undo: fewer than 2 turns in session")
        return await self.fork(turn_index=len(turns) - 2, title_prefix="Undo")

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _read_all_lines(self, path: Path) -> List[str]:
        """Return every non-empty stripped line in *path*."""
        if not path.exists():
            return []
        lines: List[str] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
        return lines
