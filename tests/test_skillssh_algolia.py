# -*- coding: utf-8 -*-
"""Algolia-first /skill search (2026-08-09).

search_skillssh queries our dulus_skills Algolia index first (~1ms,
typo-tolerant) and only touches the throttled live APIs (skills.sh →
skillsdirectory) when Algolia is down or DULUS_ALGOLIA=0 is set.
"""
from __future__ import annotations

import io
import json

import algolia_search
from skill import clawhub


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_search_skillssh_algolia_first(monkeypatch):
    """Default path: Algolia hits map to the CLI shape and ZERO live network
    calls happen (skills.sh / skillsdirectory untouched)."""
    captured: dict = {}

    def fake_search(index, query, *, page, hits_per_page, filters=None, facets=None):
        captured.update(index=index, query=query, page=page, hits_per_page=hits_per_page)
        return {
            "hits": [{
                "name": "React Helper",
                "slug": "octo-react-helper",
                "description": "Helps with React hooks",
                "repository": "octo/skills",
                "category": "development",
                "author": "octo",
                "stars": 42,
                "verified": True,
                "tags": ["react"],
                "source": "skillsdirectory",
            }],
            "total": 1,
            "page": 0,
            "pages": 1,
            "has_more": False,
            "hits_per_page": hits_per_page,
            "facets": {},
        }

    monkeypatch.setattr(algolia_search, "search_index", fake_search)

    def _boom(*_a, **_kw):
        raise AssertionError("must not call urlopen: Algolia answered first")

    monkeypatch.setattr("urllib.request.urlopen", _boom)

    result = clawhub.search_skillssh("react", limit=5)

    assert captured["index"] == algolia_search.INDEX_SKILLS
    assert captured["query"] == "react"
    assert captured["page"] == 0
    assert captured["hits_per_page"] == 5
    assert len(result) == 1
    entry = result[0]
    assert entry["id"] == "skillssh/octo/skills/octo-react-helper"
    assert entry["skill"] == "React Helper"
    assert entry["name"] == "React Helper"
    assert entry["description"] == "Helps with React hooks"
    assert entry["repo"] == "octo/skills"
    assert entry["stars"] == 42
    assert entry["source"] == "skillssh"  # install routing stays on skillssh


def test_search_skillssh_kill_switch_falls_back_to_live(monkeypatch):
    """DULUS_ALGOLIA=0 → the original live path (skills.sh first) runs
    untouched."""
    monkeypatch.setenv("DULUS_ALGOLIA", "0")

    payload = {
        "skills": [{
            "id": "octo/skills/react-helper",
            "source": "octo/skills",
            "skillId": "react-helper",
            "installs": 1234,
        }]
    }

    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(getattr(req, "full_url", str(req)))
        return _Response(json.dumps(payload).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = clawhub.search_skillssh("react", limit=5)

    assert calls and "skills.sh" in calls[0]
    assert result[0]["id"] == "skillssh/octo/skills/react-helper"
    assert result[0]["installs"] == 1234
    assert result[0]["source"] == "skillssh"


def test_search_skillssh_algolia_down_falls_back_to_live(monkeypatch):
    """Algolia returning None (timeout/5xx) → live fallback still works."""
    monkeypatch.setattr(algolia_search, "search_index", lambda *a, **kw: None)

    payload = {
        "skills": [{
            "id": "octo/skills/react-helper",
            "source": "octo/skills",
            "skillId": "react-helper",
            "installs": 7,
        }]
    }

    def fake_urlopen(req, timeout=None):
        return _Response(json.dumps(payload).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = clawhub.search_skillssh("react", limit=5)

    assert result[0]["id"] == "skillssh/octo/skills/react-helper"
    assert result[0]["installs"] == 7
