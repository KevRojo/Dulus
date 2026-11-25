"""Prompt history suggestions shared by the terminal input layouts."""
from __future__ import annotations

from prompt_toolkit.auto_suggest import AutoSuggestFromHistory, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document

from retired_web import retired_command_error


class DulusHistorySuggest(AutoSuggestFromHistory):
    """Skip retired slash commands while keeping the original history available for recall."""

    def get_suggestion(self, buffer: Buffer, document: Document) -> Suggestion | None:
        prefix = document.text.rsplit("\n", 1)[-1]
        if not prefix.lstrip().startswith("/"):
            return super().get_suggestion(buffer, document)

        for entry in reversed(buffer.history.get_strings()):
            for line in reversed(entry.splitlines()):
                if line.startswith(prefix) and not retired_command_error(line):
                    return Suggestion(line[len(prefix):])
        return None
