"""Tests for SessionExporter and SessionImporter — Feature 13.

Covers:
* export_markdown (basic, with session_id/token_count, structured content)
* export_json (basic, round-trip)
* export_text (basic)
* import_from_file (missing file, JSON, Markdown, text, max_context_size)
* import_from_session_id (missing session, valid session)
"""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path

# Ensure dulus modules are importable
import sys

_PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_DIR))

from dulus_tools.export_import import SessionExporter, SessionImporter


# --------------------------------------------------------------------------- #
#  Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def sample_history() -> list[dict]:
    """A small conversation history for export tests."""
    return [
        {"role": "user", "content": "Hello, what is 2+2?"},
        {"role": "assistant", "content": "The answer is 4."},
        {"role": "user", "content": "And 3*3?"},
        {"role": "assistant", "content": "That would be 9."},
    ]


@pytest.fixture
def exporter() -> SessionExporter:
    return SessionExporter()


@pytest.fixture
def importer() -> SessionImporter:
    return SessionImporter()


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """A temporary file path for writing exports."""
    return tmp_path / "output"


# --------------------------------------------------------------------------- #
#  SessionExporter.export_markdown
# --------------------------------------------------------------------------- #


def test_export_markdown_basic(exporter: SessionExporter, sample_history: list, tmp_output: Path):
    path, count = exporter.export_markdown(sample_history, tmp_output.with_suffix(".md"))
    assert path.exists()
    assert count == 4
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Session Export:")
    assert "## USER" in text
    assert "## ASSISTANT" in text
    assert "Hello, what is 2+2?" in text
    assert "The answer is 4." in text


def test_export_markdown_with_metadata(exporter: SessionExporter, sample_history: list, tmp_output: Path):
    path, count = exporter.export_markdown(
        sample_history,
        tmp_output.with_suffix(".md"),
        session_id="abc-123",
        token_count=150,
    )
    text = path.read_text(encoding="utf-8")
    assert "abc-123" in text
    assert "150" in text
    assert "4" in text  # message count


def test_export_markdown_structured_content(exporter: SessionExporter, tmp_output: Path):
    history = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
    ]
    path, count = exporter.export_markdown(history, tmp_output.with_suffix(".md"))
    text = path.read_text(encoding="utf-8")
    # Structured content should be JSON-serialized
    assert '"type": "text"' in text


def test_export_markdown_creates_directories(exporter: SessionExporter, sample_history: list, tmp_path: Path):
    nested = tmp_path / "a" / "b" / "c" / "out.md"
    path, count = exporter.export_markdown(sample_history, nested)
    assert path.exists()


def test_export_markdown_empty_history(exporter: SessionExporter, tmp_output: Path):
    path, count = exporter.export_markdown([], tmp_output.with_suffix(".md"))
    assert count == 0
    text = path.read_text(encoding="utf-8")
    assert "Messages**: 0" in text


# --------------------------------------------------------------------------- #
#  SessionExporter.export_json
# --------------------------------------------------------------------------- #


def test_export_json_basic(exporter: SessionExporter, sample_history: list, tmp_output: Path):
    path, count = exporter.export_json(sample_history, tmp_output.with_suffix(".json"))
    assert path.exists()
    assert count == 4
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["message_count"] == 4
    assert data["session_id"] == ""
    assert len(data["messages"]) == 4
    assert "exported_at" in data


def test_export_json_with_metadata(exporter: SessionExporter, sample_history: list, tmp_output: Path):
    path, count = exporter.export_json(
        sample_history,
        tmp_output.with_suffix(".json"),
        session_id="sess-99",
        token_count=2048,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["session_id"] == "sess-99"
    assert data["token_count"] == 2048


def test_export_json_round_trip(exporter: SessionExporter, sample_history: list, tmp_output: Path):
    """Exported JSON should be importable and contain identical messages."""
    path, _ = exporter.export_json(sample_history, tmp_output.with_suffix(".json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["messages"] == sample_history


def test_export_json_empty(exporter: SessionExporter, tmp_output: Path):
    path, count = exporter.export_json([], tmp_output.with_suffix(".json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["messages"] == []
    assert data["message_count"] == 0


# --------------------------------------------------------------------------- #
#  SessionExporter.export_text
# --------------------------------------------------------------------------- #


def test_export_text_basic(exporter: SessionExporter, sample_history: list, tmp_output: Path):
    path, count = exporter.export_text(sample_history, tmp_output.with_suffix(".txt"))
    assert path.exists()
    assert count == 4
    text = path.read_text(encoding="utf-8")
    assert text.startswith("[user]")
    assert "[assistant]" in text
    assert "Hello, what is 2+2?" in text


def test_export_text_structured_content(exporter: SessionExporter, tmp_output: Path):
    history = [
        {"role": "user", "content": {"type": "image", "url": "http://example.com/img.png"}},
    ]
    path, count = exporter.export_text(history, tmp_output.with_suffix(".txt"))
    text = path.read_text(encoding="utf-8")
    assert "[user]" in text
    assert "http://example.com/img.png" in text


def test_export_text_empty(exporter: SessionExporter, tmp_output: Path):
    path, count = exporter.export_text([], tmp_output.with_suffix(".txt"))
    assert count == 0
    assert path.read_text(encoding="utf-8") == ""


# --------------------------------------------------------------------------- #
#  SessionImporter.import_from_file
# --------------------------------------------------------------------------- #


def test_import_missing_file(importer: SessionImporter):
    desc, length = importer.import_from_file("/nonexistent/path/file.json")
    assert desc.startswith("Error:")
    assert length == 0


def test_import_json_file(importer: SessionImporter, tmp_path: Path):
    data = {
        "session_id": "test",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    }
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    desc, length = importer.import_from_file(str(path))
    assert "JSON" in desc
    assert "2 messages" in desc
    assert length > 0


def test_import_invalid_json_file(importer: SessionImporter, tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{ not valid json", encoding="utf-8")
    desc, length = importer.import_from_file(str(path))
    assert desc.startswith("Error:")
    assert length == 0


def test_import_markdown_file(importer: SessionImporter, tmp_path: Path):
    path = tmp_path / "test.md"
    path.write_text("# Hello\n\nSome content here.\n", encoding="utf-8")
    desc, length = importer.import_from_file(str(path))
    assert "Markdown" in desc
    assert length == len(path.read_text(encoding="utf-8"))


def test_import_text_file(importer: SessionImporter, tmp_path: Path):
    path = tmp_path / "notes.txt"
    path.write_text("Plain text content", encoding="utf-8")
    desc, length = importer.import_from_file(str(path))
    assert "Text" in desc
    assert length == len("Plain text content")


def test_import_with_max_context_size(importer: SessionImporter, tmp_path: Path):
    path = tmp_path / "long.txt"
    path.write_text("A" * 10000, encoding="utf-8")
    desc, length = importer.import_from_file(str(path), max_context_size=100)
    assert length == 100


def test_import_unknown_extension(importer: SessionImporter, tmp_path: Path):
    """Files with unknown extensions are treated as plain text."""
    path = tmp_path / "data.xyz"
    path.write_text("some data", encoding="utf-8")
    desc, length = importer.import_from_file(str(path))
    assert "Text" in desc


# --------------------------------------------------------------------------- #
#  SessionImporter.import_from_session_id
# --------------------------------------------------------------------------- #


def test_import_missing_session(importer: SessionImporter, tmp_path: Path):
    desc, length = importer.import_from_session_id(
        "nonexistent_session",
        sessions_root=str(tmp_path),
    )
    assert desc.startswith("Error:")
    assert length == 0


def test_import_valid_session(importer: SessionImporter, tmp_path: Path):
    session_dir = tmp_path / "my-session"
    session_dir.mkdir()
    wire = session_dir / "wire.jsonl"
    wire.write_text(
        json.dumps({"type": "TurnBegin"}) + "\n"
        + json.dumps({"type": "TurnEnd"}) + "\n",
        encoding="utf-8",
    )
    desc, length = importer.import_from_session_id(
        "my-session",
        sessions_root=str(tmp_path),
    )
    assert "my-session" in desc
    assert "2 lines" in desc
    assert length > 0


def test_import_session_empty_wire(importer: SessionImporter, tmp_path: Path):
    session_dir = tmp_path / "empty-session"
    session_dir.mkdir()
    wire = session_dir / "wire.jsonl"
    wire.write_text("\n\n  \n", encoding="utf-8")
    desc, length = importer.import_from_session_id(
        "empty-session",
        sessions_root=str(tmp_path),
    )
    assert "empty-session" in desc
    assert "0 lines" in desc


def test_import_session_default_root(importer: SessionImporter):
    """When sessions_root is None, it should default to ~/.dulus/sessions."""
    desc, length = importer.import_from_session_id("nonexistent")
    assert desc.startswith("Error:")
