"""Tests for TreeLs directory tree rendering."""
import os
import tempfile
from pathlib import Path

import pytest

from dulus_tools.tree_ls import build_tree


def test_build_tree_basic():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a_dir").mkdir()
        (root / "a_file.txt").write_text("hello")

        tree = build_tree(root, depth=1)
        assert str(root) in tree or root.name in tree
        assert "a_dir/" in tree
        assert "a_file.txt" in tree


def test_build_tree_respects_depth():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "level1" / "level2" / "level3").mkdir(parents=True)

        tree = build_tree(root, depth=2)
        assert "level1/" in tree
        assert "level2/" in tree
        assert "level3/" not in tree


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


def test_build_tree_not_a_directory():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "a_file.txt"
        f.write_text("hello")
        tree = build_tree(f, depth=2)
        assert "Not a directory" in tree


def test_build_tree_default_depth():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "level1").mkdir()
        tree = build_tree(root)
        assert "level1/" in tree


def test_build_tree_limits_depth():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a").mkdir()
        # depth higher than 5 should be clamped
        tree = build_tree(root, depth=10)
        assert "(depth=5)" in tree


def test_build_tree_relative_path():
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            root = Path(tmp)
            (root / "rel_dir").mkdir()
            tree = build_tree(".", depth=1)
            assert "rel_dir/" in tree
        finally:
            os.chdir(original)
