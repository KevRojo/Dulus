# -*- coding: utf-8 -*-
"""Algolia-first /mcp search (2026-08-09).

hub.search() queries our dulus_mcps Algolia index first (~1ms, typo-tolerant)
and only falls back to the live registry/awesome crawl (list_all — thousands
of entries, 10s+) when Algolia is down or DULUS_ALGOLIA=0 is set.
"""
from __future__ import annotations

import algolia_search
from dulus_mcp import hub


def test_search_mcp_algolia_first(monkeypatch):
    """Algolia hits map to MCPServerEntry and the live crawl is NOT touched."""
    captured: dict = {}

    def fake_search(index, query, *, page, hits_per_page, filters=None, facets=None):
        captured.update(index=index, query=query, hits_per_page=hits_per_page)
        return {
            "hits": [{
                "name": "github",
                "description": "GitHub MCP server",
                "source": "official-registry",
                "url": "https://example.com/github",
                "transport": "stdio",
            }],
            "total": 1, "page": 0, "pages": 1, "has_more": False,
            "hits_per_page": hits_per_page, "facets": {},
        }

    monkeypatch.setattr(algolia_search, "search_index", fake_search)
    monkeypatch.setattr(hub, "list_installed", lambda *a, **kw: [])

    def _boom(*_a, **_kw):
        raise AssertionError("live list_all must not run: Algolia answered first")

    monkeypatch.setattr(hub, "list_all", _boom)

    result = hub.search("github")

    assert captured["index"] == algolia_search.INDEX_MCPS
    assert captured["query"] == "github"
    assert len(result) == 1
    entry = result[0]
    assert entry.name == "github"
    assert entry.description == "GitHub MCP server"
    assert entry.source == "registry"  # official-registry -> registry
    assert entry.installed is False


def test_search_mcp_kill_switch_falls_back_to_live(monkeypatch):
    """DULUS_ALGOLIA=0 → the original live list_all() path runs untouched."""
    monkeypatch.setenv("DULUS_ALGOLIA", "0")

    sentinel = ["<<live-crawl-result>>"]
    monkeypatch.setattr(hub, "list_all", lambda query=None, **kw: sentinel)

    def _boom(*_a, **_kw):
        raise AssertionError("search_index must not be called when disabled")

    monkeypatch.setattr(algolia_search, "search_index", _boom)

    assert hub.search("github") is sentinel


def test_search_mcp_algolia_down_falls_back_to_live(monkeypatch):
    """Algolia returning None (timeout/5xx) → live fallback still works."""
    monkeypatch.setattr(algolia_search, "search_index", lambda *a, **kw: None)

    sentinel = ["<<live-crawl-result>>"]
    monkeypatch.setattr(hub, "list_all", lambda query=None, **kw: sentinel)

    assert hub.search("github") is sentinel
