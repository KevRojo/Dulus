# -*- coding: utf-8 -*-
"""
algolia_search.py — cliente Algolia mínimo (stdlib puro) para búsqueda de
skills y MCPs del ecosistema Dulus.

SEGURIDAD / PORT AL PÚBLICO:
  - ALGOLIA_APP_ID y ALGOLIA_SEARCH_KEY son PÚBLICOS por diseño: la search key
    tiene ACL search-only (solo buscar; no escribe, no borra, no lista settings)
    y el App ID va en el hostname de la API. Es el mismo modelo que cualquier
    website con Algolia (la key viaja en el JS del browser). Este archivo ES
    safe para el repo público.
  - JAMÁS meter aquí la Admin key ni la Write key. Esas viven SOLO en env vars
    de sesión para reindex (scripts/algolia_reindex.py) y se rotan.
  - Override por env: ALGOLIA_APP_ID / ALGOLIA_SEARCH_KEY (p.ej. staging).
  - Kill-switch: DULUS_ALGOLIA=0 desactiva y los callers caen a su path live.

Índices (app 6B4COE0NPM):
  - dulus_skills : ~97k skills (skillsdirectory + awesome + anthropic + local)
  - dulus_mcps   : ~3.1k MCP servers (official registry + awesome + composio)
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

# ── constantes PÚBLICAS (search-only, ver docstring) ───────────────────────
ALGOLIA_APP_ID = os.environ.get("ALGOLIA_APP_ID", "6B4COE0NPM")
ALGOLIA_SEARCH_KEY = os.environ.get(
    "ALGOLIA_SEARCH_KEY", "4be7a622637fca58881ee8c3ef50885a")

INDEX_SKILLS = "dulus_skills"
INDEX_MCPS = "dulus_mcps"

_TIMEOUT = 8
_BASE = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net"


def algolia_enabled() -> bool:
    """Kill-switch global: DULUS_ALGOLIA=0 apaga la integración."""
    return os.environ.get("DULUS_ALGOLIA", "1").strip() not in {"0", "false", "off"}


def search_index(
    index: str,
    query: str = "",
    *,
    page: int = 0,
    hits_per_page: int = 30,
    filters: str | None = None,
    facets: list[str] | None = None,
) -> dict | None:
    """Query un índice Algolia. Returns dict normalizado o None si falla.

    Normalizado: {hits, total, page, pages, has_more, hits_per_page, facets}
    - page es 0-based (convención Algolia).
    - filters: sintaxis Algolia, p.ej. "source:composio AND verified:true".
    - facets: atributos de faceting a contar, p.ej. ["source"] → counts por
      valor en la MISMA query (para badges de tabs sin requests extra).
    """
    if not algolia_enabled():
        return None
    payload: dict = {
        "query": query or "",
        "page": max(int(page), 0),
        "hitsPerPage": min(max(int(hits_per_page), 1), 100),
    }
    if filters:
        payload["filters"] = filters
    if facets:
        payload["facets"] = list(facets)
    try:
        req = urllib.request.Request(
            f"{_BASE}/1/indexes/{index}/query",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "X-Algolia-Application-Id": ALGOLIA_APP_ID,
                "X-Algolia-API-Key": ALGOLIA_SEARCH_KEY,
                "Content-Type": "application/json",
                "User-Agent": "dulus-algolia-search/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            d = json.loads(r.read().decode("utf-8"))
        return {
            "hits": d.get("hits", []),
            "total": int(d.get("nbHits", 0)),
            "page": int(d.get("page", 0)),
            "pages": int(d.get("nbPages", 0)),
            "has_more": int(d.get("page", 0)) + 1 < int(d.get("nbPages", 0)),
            "hits_per_page": payload["hitsPerPage"],
            "facets": d.get("facets", {}),
        }
    except Exception:
        return None  # caller cae a su path live — Algolia nunca rompe el flujo
