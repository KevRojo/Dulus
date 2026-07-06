"""Tests for fs_compass path resolution and tree rendering."""
import os
import tempfile
from pathlib import Path

import pytest

from dulus_tools.fs_compass import build_tree, resolve_path


def test_resolve_home():
    result = resolve_path("home")
    assert result is not None
    assert result.resolve() == Path.home().resolve()


def test_resolve_absolute_path():
    with tempfile.TemporaryDirectory() as tmp:
        result = resolve_path(tmp)
        assert result is not None
        assert result.resolve() == Path(tmp).resolve()


def test_resolve_relative_path_from_cwd():
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            result = resolve_path(".")
            assert result is not None
            assert result.resolve() == Path(tmp).resolve()
        finally:
            os.chdir(original)


def test_resolve_unknown_returns_none():
    result = resolve_path("this-definitely-does-not-exist-12345")
    assert result is None


def test_build_tree_depth_one():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a_dir").mkdir()
        (root / "a_file.txt").write_text("hello")

        tree = build_tree(root, depth=1)
        assert root.name in tree or str(root) in tree
        assert "a_dir/" in tree
        assert "a_file.txt" in tree


def test_build_tree_prunes_noise_dirs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "visible").mkdir()
        (root / "node_modules").mkdir()
        (root / "node_modules" / "junk.js").write_text("x")

        tree = build_tree(root, depth=2)
        assert "visible/" in tree
        assert "node_modules" not in tree


def test_build_tree_missing_path():
    tree = build_tree("/__nonexistent_path_12345__/xyz", depth=2)
    assert "Path not found" in tree


def test_build_tree_respects_max_depth():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "level1" / "level2" / "level3").mkdir(parents=True)

        tree = build_tree(root, depth=2)
        assert "level1/" in tree
        assert "level2/" in tree
        assert "level3/" not in tree
