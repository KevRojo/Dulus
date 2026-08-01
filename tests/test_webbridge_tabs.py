"""Regression tests for logical and visible WebBridge tab synchronization."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from webbridge.core import DulusWebBridge


class FakePage:
    def __init__(self, url: str, title: str, *, focus_error: Exception | None = None):
        self.url = url
        self._title = title
        self._closed = False
        self._focus_error = focus_error
        self.calls: list[str] = []

    def is_closed(self) -> bool:
        return self._closed

    async def bring_to_front(self) -> None:
        self.calls.append("bring_to_front")
        if self._focus_error:
            raise self._focus_error

    async def title(self) -> str:
        self.calls.append("title")
        return self._title

    async def goto(self, url: str, **_kwargs) -> None:
        self.calls.append("goto")
        self.url = url

    async def close(self) -> None:
        self.calls.append("close")
        self._closed = True


@pytest.fixture
def bridge() -> DulusWebBridge:
    # Bypass the singleton so every test owns isolated mutable tab state.
    instance = object.__new__(DulusWebBridge)
    instance._tabs = {}
    instance._active_tab_id = "default"
    instance._context = None
    return instance


@pytest.mark.asyncio
async def test_switch_tab_foregrounds_before_committing_state(bridge):
    first = FakePage("https://one.test", "One")
    second = FakePage("https://two.test", "Two")
    bridge._tabs = {"default": first, "tab_2": second}
    bridge._active_tab_id = "default"

    result = await bridge.switch_tab("tab_2")

    assert result["ok"] is True
    assert result["foregrounded"] is True
    assert bridge._active_tab_id == "tab_2"
    assert second.calls[:2] == ["bring_to_front", "title"]


@pytest.mark.asyncio
async def test_switch_failure_preserves_previous_active_tab(bridge):
    first = FakePage("https://one.test", "One")
    broken = FakePage("https://broken.test", "Broken", focus_error=RuntimeError("focus failed"))
    bridge._tabs = {"default": first, "tab_2": broken}
    bridge._active_tab_id = "default"

    result = await bridge.switch_tab("tab_2")

    assert result["ok"] is False
    assert "focus failed" in result["error"]
    assert bridge._active_tab_id == "default"


@pytest.mark.asyncio
async def test_unknown_or_closed_tab_is_rejected_and_pruned(bridge):
    open_page = FakePage("https://one.test", "One")
    closed_page = FakePage("https://closed.test", "Closed")
    closed_page._closed = True
    bridge._tabs = {"default": open_page, "tab_2": closed_page}
    bridge._active_tab_id = "default"

    result = await bridge.switch_tab("tab_2")

    assert result == {"ok": False, "error": "Tab 'tab_2' not found"}
    assert "tab_2" not in bridge._tabs


@pytest.mark.asyncio
async def test_new_tab_navigates_and_explicitly_foregrounds(bridge, monkeypatch):
    first = FakePage("https://one.test", "One")
    created = FakePage("about:blank", "Created")
    context = Mock()
    context.new_page = AsyncMock(return_value=created)
    bridge._tabs = {"default": first}
    bridge._active_tab_id = "default"
    bridge._context = context
    monkeypatch.setattr(bridge, "_ensure_browser", AsyncMock())
    monkeypatch.setattr("webbridge.core.asyncio.sleep", AsyncMock())

    result = await bridge.new_tab("https://new.test")

    assert result["ok"] is True
    assert result["tab_id"] == "tab_1"
    assert bridge._active_tab_id == "tab_1"
    assert created.calls == ["goto", "bring_to_front", "title"]


@pytest.mark.asyncio
async def test_close_active_tab_foregrounds_latest_survivor(bridge):
    first = FakePage("https://one.test", "One")
    second = FakePage("https://two.test", "Two")
    third = FakePage("https://three.test", "Three")
    bridge._tabs = {"default": first, "tab_2": second, "tab_3": third}
    bridge._active_tab_id = "tab_3"

    result = await bridge.close_tab("tab_3")

    assert result == {
        "ok": True,
        "closed_tab": "tab_3",
        "active_tab": "tab_2",
        "foregrounded": True,
    }
    assert third._closed is True
    assert second.calls[:2] == ["bring_to_front", "title"]


@pytest.mark.asyncio
async def test_list_tabs_prunes_stale_pages(bridge, monkeypatch):
    first = FakePage("https://one.test", "One")
    stale = FakePage("https://stale.test", "Stale")
    stale._closed = True
    bridge._tabs = {"default": first, "tab_2": stale}
    bridge._active_tab_id = "tab_2"
    monkeypatch.setattr(bridge, "_ensure_browser", AsyncMock())

    result = await bridge.list_tabs()

    assert result["active_tab"] == "default"
    assert [tab["tab_id"] for tab in result["tabs"]] == ["default"]
    assert result["tabs"][0]["active"] is True
