"""Core WebBridge implementation using Playwright."""
from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import os
import threading
from pathlib import Path
from typing import Any, Optional

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

# Cache the import check so we don't retry every call
_playwright_available: Optional[bool] = None
_playwright_import_error: Optional[str] = None


def _check_playwright() -> bool:
    """Check if Playwright is installed. Cached."""
    global _playwright_available, _playwright_import_error
    if _playwright_available is not None:
        return _playwright_available
    try:
        import playwright  # noqa: F401
        _playwright_available = True
        return True
    except ImportError as exc:
        _playwright_available = False
        _playwright_import_error = str(exc)
        return False


class DulusWebBridge:
    """Singleton browser automation controller using Playwright.

    Uses a dedicated background worker thread so the browser stays alive
    across multiple tool calls.  Playwright objects are bound to the event
    loop that created them; by always running Playwright code in the same
    thread we avoid "browser has been closed" errors.

    Usage:
        bridge = DulusWebBridge()
        result = bridge.navigate_sync("https://example.com")
        result = bridge.click_sync("button#submit")
        result = bridge.screenshot_sync()
        bridge.close_sync()
    """

    _instance: Optional["DulusWebBridge"] = None
    _lock = threading.Lock()

    # Playwright objects — owned by the worker thread
    _playwright: Any = None
    _context: Any = None   # BrowserContext from launch_persistent_context
    _browser: Any = None

    # Multi-tab support
    _tabs: dict[str, Any] = {}
    _active_tab_id: str = "default"

    # Dedicated worker thread + event loop
    _worker_thread: Optional[threading.Thread] = None
    _worker_loop: Optional[asyncio.AbstractEventLoop] = None
    _worker_ready = threading.Event()

    def __new__(cls) -> "DulusWebBridge":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_playwright(self) -> None:
        """Raise a clear error if Playwright is not installed."""
        if not _check_playwright():
            raise RuntimeError(
                "Playwright is not installed. "
                "Install with: pip install playwright && playwright install chromium"
            )

    @property
    def _active_page(self) -> Any:
        """Return the currently active page/tab."""
        return self._tabs.get(self._active_tab_id)

    def _is_browser_alive(self) -> bool:
        """Check if the browser process is still responsive."""
        if self._browser is None or not self._tabs:
            return False
        try:
            page = self._active_page
            if page is None:
                return False
            # Quick health check — run in the worker thread so we don't
            # create a foreign event loop that confuses Playwright.
            async def _check():
                await page.evaluate("1 + 1")
                return True
            return self._sync(_check())
        except Exception:
            # Browser is dead — clean up stale references
            self._context = None
            self._browser = None
            self._tabs.clear()
            self._active_tab_id = "default"
            self._playwright = None
            return False

    def _get_profile_dir(self) -> Path:
        """Return the persistent profile directory for cookies/state."""
        profile_dir = Path.home() / ".dulus" / "webbridge_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    def _get_lock_file(self) -> Path:
        """Return the lock file path for cross-process browser detection."""
        return self._get_profile_dir() / ".dulus_bridge_lock"

    def _read_lock_info(self) -> dict | None:
        """Read lock file to find existing browser's CDP endpoint."""
        lock_file = self._get_lock_file()
        if not lock_file.exists():
            return None
        try:
            import json
            data = json.loads(lock_file.read_text())
            # Verify PID is still alive
            pid = data.get("pid")
            if pid and os.name == "nt":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(1, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return data
                else:
                    # Process dead, stale lock
                    lock_file.unlink(missing_ok=True)
                    return None
            return data
        except Exception:
            return None

    def _write_lock_info(self, cdp_endpoint: str | None = None) -> None:
        """Write lock file with current browser info."""
        import json
        lock_file = self._get_lock_file()
        data = {
            "pid": os.getpid(),
            "cdp_endpoint": cdp_endpoint,
        }
        lock_file.write_text(json.dumps(data))

    def _clear_lock(self) -> None:
        """Remove lock file on clean shutdown."""
        self._get_lock_file().unlink(missing_ok=True)

    async def _ensure_browser(self, headless: bool = False) -> None:
        """Launch browser + page if not already open.
        
        Uses persistent context so cookies, localStorage, and session
        data survive across tool calls and Dulus restarts.
        
        Strategy:
        1. Check if WE already have a live browser (same process)
        2. Check if ANOTHER process has a browser running (cross-process)
        3. Launch new browser if none exists
        """
        # 1. Same-process singleton check
        if self._browser is not None and self._tabs:
            try:
                page = self._active_page
                if page:
                    await page.evaluate("1 + 1")
                    return
            except Exception:
                self._context = None
                self._browser = None
                self._tabs.clear()
                self._active_tab_id = "default"
                self._playwright = None

        self._ensure_playwright()
        from playwright.async_api import async_playwright

        # 2. Cross-process check: is another Dulus tool call holding the browser?
        lock_info = self._read_lock_info()
        if lock_info and lock_info.get("pid") != os.getpid():
            # Another process has the browser. We can't share via CDP easily
            # without knowing the WS endpoint, so for now we launch a new one
            # with a SEPARATE profile directory to avoid "profile in use" crash.
            # TODO: Use CDP to connect to existing browser for true sharing.
            pass  # Fall through to launch with unique profile

        self._playwright = await async_playwright().start()
        
        profile_dir = self._get_profile_dir()
        
        # If another process might be using the profile, use a unique subdir
        if lock_info and lock_info.get("pid") != os.getpid():
            import time
            profile_dir = profile_dir / f"instance_{os.getpid()}_{int(time.time())}"
            profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Use persistent context for cookies + localStorage survival
        context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        
        self._context = context
        self._browser = context.browser
        pages = context.pages
        default_page = pages[0] if pages else await context.new_page()
        self._tabs["default"] = default_page
        self._active_tab_id = "default"
        
        # Write lock so other processes know we're running
        self._write_lock_info()

    # ── Worker thread management ──────────────────────────────────────────────

    def _ensure_worker(self) -> None:
        """Start the background worker thread if it isn't running."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._worker_ready.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop_target, daemon=True)
        self._worker_thread.start()
        # Wait until the loop is actually spinning
        if not self._worker_ready.wait(timeout=15):
            raise RuntimeError("WebBridge worker thread failed to start")

    def _worker_loop_target(self) -> None:
        """Target for the background thread — creates and runs an event loop forever."""
        loop = asyncio.new_event_loop()
        self._worker_loop = loop
        self._worker_ready.set()
        loop.run_forever()

    def _sync(self, coro):
        """Run an async coroutine in the dedicated worker thread.

        Playwright objects are bound to the event loop that created them.
        By always submitting coroutines to the same background thread we
        keep the browser alive across tool calls.
        """
        self._ensure_worker()
        future = asyncio.run_coroutine_threadsafe(coro, self._worker_loop)
        return future.result(timeout=120)

    # ── Public async API ──────────────────────────────────────────────────────

    async def navigate(self, url: str, headless: bool = False, tab_id: Optional[str] = None) -> dict[str, Any]:
        """Navigate to *url* and return page metadata."""
        try:
            await self._ensure_browser(headless=headless)
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(0.5)  # Wait for JS hydration
            return {
                "ok": True,
                "url": page.url,
                "title": await page.title(),
                "status": response.status if response else None,
                "tab_id": tab_id or self._active_tab_id,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def click(self, selector: str, force: bool = False, tab_id: Optional[str] = None) -> dict[str, Any]:
        """Click element matching *selector*.

        Set *force=True* to bypass Playwright's actionability checks
        (useful for overlays or elements reported as "not visible").
        """
        try:
            await self._ensure_browser()
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}
            await page.click(selector, timeout=10000, force=force)
            await asyncio.sleep(0.3)
            return {
                "ok": True,
                "clicked": selector,
                "url": page.url,
                "tab_id": tab_id or self._active_tab_id,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def type_text(self, selector: str, text: str, tab_id: Optional[str] = None) -> dict[str, Any]:
        """Type *text* into input matching *selector*."""
        try:
            await self._ensure_browser()
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}
            await page.fill(selector, text, timeout=10000)
            return {
                "ok": True,
                "typed": text,
                "into": selector,
                "tab_id": tab_id or self._active_tab_id,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def screenshot(self, path: Optional[str] = None, full_page: bool = True, tab_id: Optional[str] = None) -> dict[str, Any]:
        """Capture screenshot. Returns base64 or saves to *path*."""
        try:
            await self._ensure_browser()
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}
            if path:
                await page.screenshot(path=path, full_page=full_page)
                return {"ok": True, "saved_to": path, "tab_id": tab_id or self._active_tab_id}
            else:
                data = await page.screenshot(full_page=full_page)
                b64 = base64.b64encode(data).decode("ascii")
                return {"ok": True, "base64": b64, "format": "png", "tab_id": tab_id or self._active_tab_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def get_text(self, tab_id: Optional[str] = None) -> dict[str, Any]:
        """Extract visible text from the page body."""
        try:
            await self._ensure_browser()
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}
            text = await page.inner_text("body")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            cleaned = "\n".join(lines[:500])
            return {
                "ok": True,
                "text": cleaned,
                "url": page.url,
                "title": await page.title(),
                "tab_id": tab_id or self._active_tab_id,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # Classes that are framework noise — skip them when building selectors
    _JUNK_CLASSES = frozenset({
        "style-scope", "yt-simple-endpoint", "yt-spec-button-shape-next",
        "yt-spec-button-shape-next--tonal", "yt-spec-button-shape-next--text",
        "yt-spec-button-shape-next--mono", "yt-spec-button-shape-next--size-m",
        "yt-spec-button-shape-next--icon-only-default",
        "yt-spec-button-shape-next--enable-backdrop-filter-experiment",
        "yt-icon-button", "yt-formatted-string", "metadata-snippet-timestamp",
        "inline-block", "ytd-topbar-logo-renderer", "ytd-mini-guide-entry-renderer",
        "ytd-topbar-menu-button-renderer", "ytd-video-renderer",
        "ytd-video-owner-renderer", "ytd-video-primary-info-renderer",
        "ytd-thumbnail", "ytd-video-preview", "ytd-channel-renderer",
    })

    async def get_dom(self, tab_id: Optional[str] = None) -> dict[str, Any]:
        """Extract simplified DOM with interactive elements using BeautifulSoup.

        Returns at most 30 relevant elements with clean CSS selectors that
        Playwright can actually click.
        """
        try:
            await self._ensure_browser()
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}

            if not _BS4_AVAILABLE:
                # Fallback to the JS evaluator if bs4 is missing
                return await self._get_dom_js(page)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            elements: list[dict] = []

            # Tags we actually care about
            for tag in soup.find_all(["a", "button", "input", "textarea", "select"]):
                if len(elements) >= 30:
                    break

                tag_name = tag.name or ""
                text = (
                    tag.get_text(strip=True)
                    or tag.get("value", "")
                    or tag.get("placeholder", "")
                    or tag.get("aria-label", "")
                    or tag.get("title", "")
                )[:60]

                selector = self._build_selector(tag, soup, tag_name)
                if not selector:
                    continue

                elements.append({
                    "tag": tag_name,
                    "type": tag.get("type", ""),
                    "text": text,
                    "selector": selector,
                    "href": tag.get("href", ""),
                })

            return {
                "ok": True,
                "elements": elements,
                "url": page.url,
                "title": await page.title(),
                "tab_id": tab_id or self._active_tab_id,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _build_selector(self, tag, soup, tag_name: str) -> str | None:
        """Build a concise unique-ish CSS selector for *tag*."""
        # 1. ID is gold
        tid = tag.get("id")
        if tid:
            return f"#{tid}"

        # 2. Name attribute (great for inputs)
        name = tag.get("name")
        if name:
            return f'{tag_name}[name="{name}"]'

        # 3. Classes — filter out junk, keep meaningful ones
        classes = tag.get("class", [])
        if classes:
            meaningful = [c for c in classes if c not in self._JUNK_CLASSES]
            if meaningful:
                # Try with one class first
                sel = f"{tag_name}.{meaningful[0]}"
                if len(soup.select(sel)) <= 3:
                    return sel
                # Add second class if needed for disambiguation
                if len(meaningful) > 1:
                    sel = f"{tag_name}.{'.'.join(meaningful[:2])}"
                    if len(soup.select(sel)) <= 3:
                        return sel

        # 4. Playwright :has-text() for links/buttons with visible text
        text = tag.get_text(strip=True)
        if text and len(text) <= 40 and "\"" not in text:
            return f'{tag_name}:has-text("{text}")'

        # Too generic — skip it so we don't pollute the list
        return None

    async def _get_dom_js(self, page: Any) -> dict[str, Any]:
        """Fallback DOM extraction using browser JS (no BS4)."""
        elements = await page.evaluate("""
            () => {
                const interactive = document.querySelectorAll(
                    'a, button, input, textarea, select, [role="button"], [onclick]'
                );
                return Array.from(interactive).map((el, i) => ({
                    index: i,
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    text: (el.textContent || el.value || el.placeholder || '').trim().slice(0, 120),
                    id: el.id || '',
                    class: el.className || '',
                    name: el.name || '',
                    href: el.href || '',
                    selector: el.id ? '#' + el.id :
                              el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] :
                              el.tagName.toLowerCase(),
                }));
            }
        """)
        return {
            "ok": True,
            "elements": elements[:30],
            "url": page.url,
            "title": await page.title(),
        }

    async def scroll(self, direction: str = "down", tab_id: Optional[str] = None) -> dict[str, Any]:
        """Scroll page up or down by one viewport."""
        try:
            await self._ensure_browser()
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}
            amount = 800 if direction == "down" else -800
            await page.evaluate(f"window.scrollBy(0, {amount})")
            return {"ok": True, "scrolled": direction, "tab_id": tab_id or self._active_tab_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def close(self) -> dict[str, Any]:
        """Close browser and clean up."""
        try:
            self._tabs.clear()
            self._active_tab_id = "default"
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass  # Already dead, ignore
                self._context = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass  # Already dead, ignore
                self._playwright = None
            self._browser = None
            self._clear_lock()
            return {"ok": True, "status": "closed"}
        except Exception as exc:
            # Force reset even on unexpected errors
            self._context = None
            self._browser = None
            self._playwright = None
            self._tabs.clear()
            self._active_tab_id = "default"
            self._clear_lock()
            return {"ok": True, "status": "closed_forced", "note": str(exc)}

    async def evaluate(self, script: str, tab_id: Optional[str] = None) -> dict[str, Any]:
        """Execute raw JavaScript in the browser and return the result."""
        try:
            await self._ensure_browser()
            page = self._tabs.get(tab_id) if tab_id else self._active_page
            if page is None:
                return {"ok": False, "error": f"Tab '{tab_id}' not found"}
            result = await page.evaluate(script)
            return {"ok": True, "result": result, "tab_id": tab_id or self._active_tab_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def status(self) -> dict[str, Any]:
        """Return current browser status (sync, safe to call anytime)."""
        active_page = self._active_page
        tabs_info = {
            tab_id: {"url": page.url}
            for tab_id, page in self._tabs.items()
        }
        return {
            "browser_open": self._browser is not None,
            "active_tab": self._active_tab_id,
            "url": active_page.url if active_page else None,
            "tabs": tabs_info,
            "tab_count": len(self._tabs),
        }

    # ── Tab management ────────────────────────────────────────────────────────

    async def new_tab(self, url: str = "about:blank") -> dict[str, Any]:
        """Open a new browser tab and navigate to *url*."""
        try:
            await self._ensure_browser()
            page = await self._context.new_page()
            tab_id = f"tab_{len(self._tabs) + 1}"
            self._tabs[tab_id] = page
            self._active_tab_id = tab_id
            if url and url != "about:blank":
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(0.5)
            return {
                "ok": True,
                "tab_id": tab_id,
                "url": page.url,
                "title": await page.title(),
                "active": True,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def switch_tab(self, tab_id: str) -> dict[str, Any]:
        """Switch the active tab to *tab_id*."""
        if tab_id not in self._tabs:
            return {"ok": False, "error": f"Tab '{tab_id}' not found"}
        self._active_tab_id = tab_id
        page = self._tabs[tab_id]
        return {
            "ok": True,
            "tab_id": tab_id,
            "url": page.url,
            "title": await page.title(),
        }

    async def close_tab(self, tab_id: str) -> dict[str, Any]:
        """Close tab *tab_id* and remove it from the tab list."""
        if tab_id not in self._tabs:
            return {"ok": False, "error": f"Tab '{tab_id}' not found"}
        page = self._tabs.pop(tab_id)
        try:
            await page.close()
        except Exception:
            pass
        # If we closed the active tab, switch to another one
        if self._active_tab_id == tab_id:
            if self._tabs:
                self._active_tab_id = next(iter(self._tabs.keys()))
            else:
                self._active_tab_id = "default"
                # Create a default tab so the browser doesn't break
                try:
                    new_page = await self._context.new_page()
                    self._tabs["default"] = new_page
                except Exception:
                    pass
        return {
            "ok": True,
            "closed": tab_id,
            "active_tab": self._active_tab_id,
            "remaining_tabs": list(self._tabs.keys()),
        }

    async def list_tabs(self) -> dict[str, Any]:
        """List all open tabs with their IDs and URLs."""
        tabs = []
        for tab_id, page in self._tabs.items():
            try:
                tabs.append({
                    "tab_id": tab_id,
                    "url": page.url,
                    "title": await page.title(),
                    "active": tab_id == self._active_tab_id,
                })
            except Exception:
                tabs.append({
                    "tab_id": tab_id,
                    "url": "(unavailable)",
                    "title": "(unavailable)",
                    "active": tab_id == self._active_tab_id,
                })
        return {
            "ok": True,
            "tabs": tabs,
            "active_tab": self._active_tab_id,
        }

    # ── Sync wrappers for tool callbacks ──────────────────────────────────────

    def navigate_sync(self, url: str, headless: bool = False, tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.navigate(url, headless=headless, tab_id=tab_id))

    def click_sync(self, selector: str, force: bool = False, tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.click(selector, force=force, tab_id=tab_id))

    def evaluate_sync(self, script: str, tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.evaluate(script, tab_id=tab_id))

    def type_sync(self, selector: str, text: str, tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.type_text(selector, text, tab_id=tab_id))

    def screenshot_sync(self, path: Optional[str] = None, tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.screenshot(path=path, tab_id=tab_id))

    def get_text_sync(self, tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.get_text(tab_id=tab_id))

    def get_dom_sync(self, tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.get_dom(tab_id=tab_id))

    def scroll_sync(self, direction: str = "down", tab_id: Optional[str] = None) -> dict[str, Any]:
        return self._sync(self.scroll(direction, tab_id=tab_id))

    def close_sync(self) -> dict[str, Any]:
        return self._sync(self.close())

    def new_tab_sync(self, url: str = "about:blank") -> dict[str, Any]:
        return self._sync(self.new_tab(url))

    def switch_tab_sync(self, tab_id: str) -> dict[str, Any]:
        return self._sync(self.switch_tab(tab_id))

    def close_tab_sync(self, tab_id: str) -> dict[str, Any]:
        return self._sync(self.close_tab(tab_id))

    def list_tabs_sync(self) -> dict[str, Any]:
        return self._sync(self.list_tabs())
