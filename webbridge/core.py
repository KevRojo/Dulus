"""Core WebBridge implementation using Playwright."""
from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import os
import socket
import subprocess
import threading
import time
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

    # Detached browser process we launched ourselves (survives Dulus Ctrl+C)
    _browser_process: Optional[subprocess.Popen] = None
    _cdp_port: int = 0
    _owns_browser_process: bool = False

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

    @staticmethod
    def _pid_exists(pid: int | None) -> bool:
        """Return True when *pid* appears to be alive."""
        if not pid:
            return False
        try:
            if os.name == "nt":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(1, False, int(pid))
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            os.kill(int(pid), 0)
            return True
        except Exception:
            return False

    @staticmethod
    def _cdp_port_open(cdp_endpoint: str | None) -> bool:
        """Return True if a saved CDP endpoint is accepting connections."""
        if not cdp_endpoint:
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(cdp_endpoint)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port
            if not port:
                return False
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except Exception:
            return False

    def _read_lock_info(self) -> dict | None:
        """Read lock file to find an existing browser's CDP endpoint."""
        lock_file = self._get_lock_file()
        if not lock_file.exists():
            return None
        try:
            import json
            data = json.loads(lock_file.read_text())

            # New locks store the real Chromium PID. Older locks stored the
            # Dulus PID, so prefer browser_pid but tolerate pid for migration.
            browser_pid = data.get("browser_pid") or data.get("pid")
            cdp_endpoint = data.get("cdp_endpoint")
            if self._pid_exists(browser_pid) and self._cdp_port_open(cdp_endpoint):
                return data

            # Process or debug endpoint is gone: remove the stale lock so the
            # next call can start a fresh browser/profile cleanly.
            lock_file.unlink(missing_ok=True)
            return None
        except Exception:
            return None

    def _write_lock_info(
        self,
        cdp_endpoint: str | None = None,
        browser_pid: int | None = None,
    ) -> None:
        """Write lock file with current browser info."""
        import json
        lock_file = self._get_lock_file()
        data = {
            "pid": browser_pid,
            "browser_pid": browser_pid,
            "dulus_pid": os.getpid(),
            "cdp_endpoint": cdp_endpoint,
        }
        lock_file.write_text(json.dumps(data))

    def _clear_lock(self) -> None:
        """Remove lock file on clean shutdown."""
        self._get_lock_file().unlink(missing_ok=True)

    @staticmethod
    def _find_free_port() -> int:
        """Return an available TCP port on localhost."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    async def _launch_detached_browser(
        self, profile_dir: Path, headless: bool = False
    ) -> None:
        """Launch Chrome in its own process group and connect via CDP.

        Detaching the browser process keeps it alive when the user presses
        Ctrl+C in Dulus's terminal, because SIGINT is not propagated to a
        different Windows process group / POSIX session.
        """
        port = self._find_free_port()
        exe = self._playwright.chromium.executable_path
        if not exe or not Path(exe).exists():
            raise RuntimeError(f"Chromium executable not found: {exe}")

        cmd = [
            str(exe),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--start-maximized",        # open fullscreen
            "--window-size=1920,1080",  # fallback for monitors that need explicit size
        ]
        if headless:
            cmd.append("--headless=new")

        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        breakaway_flag = 0
        if os.name == "nt":
            creationflags = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
            # If Dulus is running inside a parent job object, Ctrl+C/cancel can
            # tear down children in that job. Break away when Windows allows it
            # so the visible browser is not part of the terminal's lifecycle.
            breakaway_flag = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
            creationflags |= breakaway_flag
            popen_kwargs["creationflags"] = creationflags
        else:
            popen_kwargs["start_new_session"] = True
        popen_kwargs["close_fds"] = True

        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
        except OSError:
            if os.name != "nt" or not breakaway_flag:
                raise
            popen_kwargs["creationflags"] = (
                popen_kwargs["creationflags"] & ~breakaway_flag
            )
            proc = subprocess.Popen(cmd, **popen_kwargs)
        self._browser_process = proc
        self._cdp_port = port
        self._owns_browser_process = True

        # Wait for the debug port to accept connections
        deadline = time.time() + 20
        reached = False
        last_err: Optional[Exception] = None
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"Chromium exited early (code {proc.returncode})"
                )
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    reached = True
                    break
            except Exception as exc:
                last_err = exc
                await asyncio.sleep(0.2)

        if not reached:
            raise RuntimeError(
                f"Chromium debug port {port} did not open: {last_err}"
            )

        browser = await self._playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{port}"
        )
        self._browser = browser

        # Reuse the default persistent context created by Chrome
        context = (
            browser.contexts[0]
            if browser.contexts
            else await browser.new_context(no_viewport=True)
        )
        self._context = context

        pages = context.pages
        default_page = pages[0] if pages else await context.new_page()
        # Don't force a fixed viewport — let the window use its maximized size
        self._tabs["default"] = default_page
        self._active_tab_id = "default"

        self._write_lock_info(
            cdp_endpoint=f"http://127.0.0.1:{port}",
            browser_pid=proc.pid,
        )

    async def _connect_existing_browser(self, cdp_endpoint: str) -> bool:
        """Connect to an already-running detached Chromium instance."""
        try:
            browser = await self._playwright.chromium.connect_over_cdp(cdp_endpoint)
            self._browser = browser
            context = (
                browser.contexts[0]
                if browser.contexts
                else await browser.new_context(no_viewport=True)
            )
            self._context = context

            pages = context.pages
            default_page = pages[0] if pages else await context.new_page()
            self._tabs.clear()
            self._tabs["default"] = default_page
            for idx, page in enumerate(pages[1:], 1):
                self._tabs[f"tab_{idx}"] = page
            self._active_tab_id = "default"
            self._browser_process = None
            self._cdp_port = 0
            self._owns_browser_process = False
            return True
        except Exception:
            self._context = None
            self._browser = None
            self._tabs.clear()
            self._active_tab_id = "default"
            return False

    async def _ensure_browser(self, headless: bool = False) -> None:
        """Launch browser + page if not already open.

        Uses a detached Chrome process so the browser survives Dulus Ctrl+C.
        Cookies / localStorage survive because we reuse the same profile dir.
        """
        # 1. Same-process singleton check
        if self._browser is not None and self._tabs:
            try:
                page = self._active_page
                if page and self._browser.is_connected():
                    await page.evaluate("1 + 1")
                    return
            except Exception:
                pass
            self._context = None
            self._browser = None
            self._browser_process = None
            self._cdp_port = 0
            self._owns_browser_process = False
            self._tabs.clear()
            self._active_tab_id = "default"
            self._playwright = None

        self._ensure_playwright()
        from playwright.async_api import async_playwright

        # 2. Cross-process check: reuse a detached browser if it survived a
        # prior Ctrl+C/process restart.
        lock_info = self._read_lock_info()

        self._playwright = await async_playwright().start()

        if lock_info and lock_info.get("cdp_endpoint"):
            if await self._connect_existing_browser(lock_info["cdp_endpoint"]):
                return
            self._clear_lock()

        profile_dir = self._get_profile_dir()

        # If another process might be using the profile, use a unique subdir
        lock_owner = lock_info.get("dulus_pid") if lock_info else None
        if lock_owner and lock_owner != os.getpid():
            profile_dir = profile_dir / f"instance_{os.getpid()}_{int(time.time())}"
            profile_dir.mkdir(parents=True, exist_ok=True)

        await self._launch_detached_browser(profile_dir, headless=headless)

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
        future = asyncio.run_coroutine_threadsafe(coro, self._worker_loop)  # type: ignore[arg-type,index]
        return future.result(timeout=120)

    # ── Public async API ──────────────────────────────────────────────────────

    async def navigate(self, url: str, headless: bool = False, tab_id: Optional[str] = None) -> dict[str, Any]:  # type: ignore[arg-type,index]
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
                )[:60]  # type: ignore[arg-type,index]

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
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass  # Already dead, ignore
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass  # Already dead, ignore
                self._playwright = None
            if self._browser_process and self._owns_browser_process:
                try:
                    self._browser_process.terminate()
                    self._browser_process.wait(timeout=5)
                except Exception:
                    try:
                        self._browser_process.kill()
                    except Exception:
                        pass
                self._browser_process = None
                self._cdp_port = 0
                self._owns_browser_process = False
            self._clear_lock()
            return {"ok": True, "status": "closed"}
        except Exception as exc:
            # Force reset even on unexpected errors
            self._context = None
            self._browser = None
            self._playwright = None
            self._tabs.clear()
            self._active_tab_id = "default"
            if self._browser_process and self._owns_browser_process:
                try:
                    self._browser_process.kill()
                except Exception:
                    pass
            self._browser_process = None
            self._cdp_port = 0
            self._owns_browser_process = False
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

    def _prune_closed_tabs(self) -> None:
        """Remove closed Playwright pages from the logical tab registry."""
        for tab_id, page in list(self._tabs.items()):
            try:
                closed = page.is_closed()
            except Exception:
                closed = True
            if closed:
                self._tabs.pop(tab_id, None)
        if self._active_tab_id not in self._tabs:
            self._active_tab_id = next(reversed(self._tabs), "default")

    def _next_tab_id(self) -> str:
        """Return a collision-free tab id even after tabs have been closed."""
        index = 1
        while f"tab_{index}" in self._tabs:
            index += 1
        return f"tab_{index}"

    async def _activate_tab(self, tab_id: str) -> dict[str, Any]:
        """Bring a tab visibly to the foreground, then commit logical state."""
        self._prune_closed_tabs()
        page = self._tabs.get(tab_id)
        if page is None:
            return {"ok": False, "error": f"Tab '{tab_id}' not found"}

        previous_tab_id = self._active_tab_id
        try:
            await page.bring_to_front()
            await asyncio.sleep(0)
            if page.is_closed():
                raise RuntimeError(f"Tab '{tab_id}' closed while being activated")
            self._active_tab_id = tab_id
            return {
                "ok": True,
                "tab_id": tab_id,
                "url": page.url,
                "title": await page.title(),
                "active": True,
                "foregrounded": True,
            }
        except Exception as exc:
            if previous_tab_id in self._tabs:
                self._active_tab_id = previous_tab_id
            return {
                "ok": False,
                "error": f"Could not foreground tab '{tab_id}': {exc}",
                "active_tab": self._active_tab_id,
            }

    async def new_tab(self, url: str = "about:blank") -> dict[str, Any]:
        """Open a new browser tab, navigate, and visibly focus it."""
        page = None
        tab_id = None
        try:
            await self._ensure_browser()
            self._prune_closed_tabs()
            page = await self._context.new_page()
            tab_id = self._next_tab_id()
            self._tabs[tab_id] = page
            if url and url != "about:blank":
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(0.5)
            result = await self._activate_tab(tab_id)
            if not result.get("ok"):
                self._tabs.pop(tab_id, None)
                try:
                    await page.close()
                except Exception:
                    pass
            return result
        except Exception as exc:
            if tab_id:
                self._tabs.pop(tab_id, None)
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
            return {"ok": False, "error": str(exc)}

    async def switch_tab(self, tab_id: str) -> dict[str, Any]:
        """Switch both logical state and the visible Chromium tab."""
        return await self._activate_tab(tab_id)

    async def close_tab(self, tab_id: str) -> dict[str, Any]:
        """Close a tab and visibly focus a deterministic survivor."""
        self._prune_closed_tabs()
        if tab_id not in self._tabs:
            return {"ok": False, "error": f"Tab '{tab_id}' not found"}
        was_active = self._active_tab_id == tab_id
        page = self._tabs.pop(tab_id)
        try:
            await page.close()
        except Exception:
            pass

        foregrounded = False
        if was_active and self._tabs:
            fallback_tab_id = next(reversed(self._tabs))
            activation = await self._activate_tab(fallback_tab_id)
            if not activation.get("ok"):
                return {
                    "ok": False,
                    "error": activation["error"],
                    "closed_tab": tab_id,
                    "active_tab": self._active_tab_id,
                }
            foregrounded = True
        elif not self._tabs:
            self._active_tab_id = "default"

        return {
            "ok": True,
            "closed_tab": tab_id,
            "active_tab": self._active_tab_id,
            "foregrounded": foregrounded,
        }

    async def list_tabs(self) -> dict[str, Any]:
        """List all open tabs after pruning stale Playwright pages."""
        await self._ensure_browser()
        self._prune_closed_tabs()
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
