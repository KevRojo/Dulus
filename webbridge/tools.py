"""WebBridge tools registered in Dulus tool registry.

Provides 7 AI-callable tools for browser automation:
  WebBridgeNavigate  → open a URL
  WebBridgeClick     → click an element
  WebBridgeType      → type text into an input
  WebBridgeScreenshot→ capture a screenshot
  WebBridgeExtract   → extract page text or DOM structure
  WebBridgeScroll    → scroll up/down
  WebBridgeClose     → close the browser
"""
from __future__ import annotations

import json
from pathlib import Path

from tool_registry import ToolDef, register_tool

from .core import DulusWebBridge

_bridge = DulusWebBridge()

# ── Tool schemas (JSON format sent to the LLM) ───────────────────────────────

_TOOL_SCHEMAS = [
    {
        "name": "WebBridgeNavigate",
        "description": (
            "Open a URL in the user's VISIBLE browser tab. Returns the page title, "
            "URL, and HTTP status.\n\n"
            "✅ WHEN TO USE THIS (experiential / interactive):\n"
            "• User wants to SEE or HEAR something: 'play / pon / ponme / reproduce "
            "  X on YouTube', 'watch Y', 'listen to Z', 'open Spotify and play …'\n"
            "• User wants to INTERACT with a page: log into a site, fill a form, "
            "  navigate a SPA, scrape behind JS, click around.\n"
            "• User explicitly asked you to open a URL for them.\n\n"
            "⚠️ WHEN NOT TO USE THIS:\n"
            "• If the active tab is doing user-visible work (music/video playing, a "
            "  game, a logged-in session, a long-running app), DO NOT Navigate it — "
            "  you'll kill what the user is watching/listening to. Use WebBridgeNewTab.\n"
            "• Info lookups (weather, news, definitions, prices, plain docs) → use "
            "  WebSearch + WebFetch. Those are headless / text-only and don't disturb "
            "  the user's browser. Returning a search link when the user asked to "
            "  PLAY/WATCH something is the wrong tool — actually open it here.\n\n"
            "Rule of thumb: 'the user wants to experience this page' → WebBridge. "
            "'the user wants information from a page' → WebFetch/WebSearch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (e.g. https://example.com)",
                },
                "headless": {
                    "type": "boolean",
                    "description": "Run without visible window. Default false (window visible).",
                },
                "tab_id": {
                    "type": "string",
                    "description": "Optional tab ID to navigate in. Uses active tab if omitted.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "WebBridgeClick",
        "description": (
            "⚠️ FALLBACK ONLY — prefer WebBridgeEvaluate for clicks. Playwright's "
            "actionability checks regularly stall on SPAs, modals, and shadow-DOM "
            "widgets, eating turns. If you actually need a Playwright-mediated "
            "click (real input dispatch, hover side-effects, native file picker), "
            "use this; otherwise reach for WebBridgeEvaluate first with "
            "document.querySelector('<sel>').click(). Set force=true to bypass "
            "visibility checks on overlays. Use WebBridgeExtract mode='dom' to "
            "discover selectors before either approach."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the element to click (e.g. '#submit', 'button.primary')",
                },
                "force": {
                    "type": "boolean",
                    "description": "Bypass Playwright's actionability checks. Default false.",
                },
                "tab_id": {
                    "type": "string",
                    "description": "Optional tab ID to click in. Uses active tab if omitted.",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": "WebBridgeEvaluate",
        "description": (
            "✅ PREFERRED interaction primitive — execute raw JavaScript in the "
            "browser and return the result. Use this as the default for clicks, "
            "form fills, scroll-to-element, value reads, anything DOM. "
            "WebBridgeClick / WebBridgeType go through Playwright's actionability "
            "checks which routinely stall on SPAs and shadow-DOM widgets — "
            "evaluating JS bypasses all of that and is dramatically more reliable.\n\n"
            "Examples:\n"
            "  • Click:        document.querySelector('button[name=\"search\"]').click()\n"
            "  • Click by text: [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Battle!').click()\n"
            "  • Fill input:   const i = document.querySelector('input[name=username]'); i.value = 'foo'; i.dispatchEvent(new Event('input', {bubbles:true}))\n"
            "  • Read state:   document.querySelector('.score')?.textContent\n"
            "  • Submit form:  document.forms[0].submit()\n\n"
            "Returns the final expression's value (JSON-serialised). Wrap in an "
            "IIFE if you need multiple statements with a return."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "JavaScript code to execute in the browser context",
                },
                "tab_id": {
                    "type": "string",
                    "description": "Optional tab ID to execute in. Uses active tab if omitted.",
                },
            },
            "required": ["script"],
        },
    },
    {
        "name": "WebBridgeType",
        "description": (
            "Type text into an input field, textarea, or content-editable element "
            "on the current page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the input field",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type into the element",
                },
                "tab_id": {
                    "type": "string",
                    "description": "Optional tab ID to type in. Uses active tab if omitted.",
                },
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "WebBridgeScreenshot",
        "description": (
            "Take a screenshot of the current page. Always saves to disk and "
            "returns BOTH the saved path AND the OCR-extracted text from the "
            "image in one shot — no second tool call needed.\n\n"
            "Response shape:\n"
            "  { \"ok\": true, \"saved_to\": \"<absolute path>\", \"text\": \"<page text>\" }\n\n"
            "If `path` is omitted, the screenshot lands at "
            "`~/.dulus/outputs/screenshots/screenshot-<timestamp>.png`.\n\n"
            "The `text` field is populated by local OCR (pytesseract → "
            "easyocr fallback, no vision tokens). If no OCR engine is "
            "available on the host, `text` comes back empty and the user "
            "can install one via `pip install dulus[ocr]`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional file path. Omit to auto-save under ~/.dulus/outputs/screenshots/.",
                },
                "tab_id": {
                    "type": "string",
                    "description": "Optional tab ID to screenshot. Uses active tab if omitted.",
                },
            },
        },
    },
    {
        "name": "WebBridgeExtract",
        "description": (
            "Extract content from the current page. "
            "mode='text' returns visible text content. "
            "mode='dom' returns a list of interactive elements with selectors."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["text", "dom"],
                    "description": "Extraction mode: 'text' for page text, 'dom' for interactive elements",
                },
                "tab_id": {
                    "type": "string",
                    "description": "Optional tab ID to extract from. Uses active tab if omitted.",
                },
            },
        },
    },
    {
        "name": "WebBridgeScroll",
        "description": "Scroll the current page up or down by one viewport height.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Scroll direction",
                },
                "tab_id": {
                    "type": "string",
                    "description": "Optional tab ID to scroll. Uses active tab if omitted.",
                },
            },
        },
    },
    {
        "name": "WebBridgeClose",
        "description": "Close the browser and release all resources.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "WebBridgeNewTab",
        "description": "Open a new browser tab. Optionally navigate to a URL immediately.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Optional URL to open in the new tab. Defaults to about:blank.",
                },
            },
        },
    },
    {
        "name": "WebBridgeSwitchTab",
        "description": "Switch the active tab to a different tab by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tab_id": {
                    "type": "string",
                    "description": "Tab ID to switch to (e.g. 'tab_1', 'default')",
                },
            },
            "required": ["tab_id"],
        },
    },
    {
        "name": "WebBridgeCloseTab",
        "description": "Close a specific tab by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tab_id": {
                    "type": "string",
                    "description": "Tab ID to close (e.g. 'tab_1')",
                },
            },
            "required": ["tab_id"],
        },
    },
    {
        "name": "WebBridgeListTabs",
        "description": "List all open tabs with their IDs, URLs, and active status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ── Tool callbacks (sync, receive params+config dicts) ───────────────────────

def _webbridge_navigate(params: dict, config: dict) -> str:
    url = params.get("url", "")
    headless = params.get("headless", False)
    tab_id = params.get("tab_id")
    result = _bridge.navigate_sync(url, headless=headless, tab_id=tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_click(params: dict, config: dict) -> str:
    selector = params.get("selector", "")
    force = params.get("force", False)
    tab_id = params.get("tab_id")
    result = _bridge.click_sync(selector, force=force, tab_id=tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_evaluate(params: dict, config: dict) -> str:
    script = params.get("script", "")
    tab_id = params.get("tab_id")
    result = _bridge.evaluate_sync(script, tab_id=tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_type(params: dict, config: dict) -> str:
    selector = params.get("selector", "")
    text = params.get("text", "")
    tab_id = params.get("tab_id")
    result = _bridge.type_sync(selector, text, tab_id=tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_screenshot(params: dict, config: dict) -> str:
    path = params.get("path")
    tab_id = params.get("tab_id")

    # Auto-save default: ~/.dulus/outputs/screenshots/screenshot-<ts>.png
    # Two wins from forcing this: (a) the user always knows where the
    # captures land instead of digging in /tmp; (b) we can run local OCR
    # on the saved file and include the extracted text inline in the
    # response — the model gets PNG-path + readable text in a single
    # tool call instead of having to chain Screenshot → OCR.
    if not path:
        from pathlib import Path as _P
        import time as _t
        out_dir = _P.home() / ".dulus" / "outputs" / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = str(out_dir / f"screenshot-{int(_t.time())}.png")

    result = _bridge.screenshot_sync(path=path, tab_id=tab_id)
    if path:
        # Auto-OCR: bundle the textual content so the model doesn't have
        # to make a second tool call (and doesn't get tempted to Read the
        # raw PNG bytes). If OCR engines aren't installed we still return
        # the saved_to path — the model just doesn't get text this turn.
        text = ""
        try:
            from tools import _ocr_extract  # type: ignore
            raw = _ocr_extract(path, languages="en,es")
            # _ocr_extract returns either "[engine: …]\n\n<text>" on
            # success, or an "Error: …" string when no engine is wired
            # up. Strip the engine prefix line so the model gets clean
            # text, and treat any "Error:" prefix as "no text available".
            if raw and not raw.startswith("Error:"):
                # Drop the leading "[engine: …]\n\n" header if present.
                if raw.startswith("[engine:"):
                    nl = raw.find("\n\n")
                    text = raw[nl + 2:] if nl != -1 else raw
                else:
                    text = raw
                text = text.strip()
        except Exception:
            text = ""

        return json.dumps({
            "ok": True,
            "saved_to": path,
            "text": text,
        }, ensure_ascii=False)
    # Return base64 but truncate the data to avoid token bloat
    b64 = result.get("base64", "") if isinstance(result, dict) else ""
    if b64:
        preview = b64[:80] + "..." if len(b64) > 80 else b64
        return json.dumps(
            {"ok": True, "format": "png", "base64_preview": preview, "base64_length": len(b64)},
            ensure_ascii=False,
        )
    return json.dumps(result, ensure_ascii=False)


def _webbridge_extract(params: dict, config: dict) -> str:
    mode = params.get("mode", "text")
    tab_id = params.get("tab_id")
    if mode == "dom":
        result = _bridge.get_dom_sync(tab_id=tab_id)
    else:
        result = _bridge.get_text_sync(tab_id=tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_scroll(params: dict, config: dict) -> str:
    direction = params.get("direction", "down")
    tab_id = params.get("tab_id")
    result = _bridge.scroll_sync(direction=direction, tab_id=tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_close(params: dict, config: dict) -> str:
    result = _bridge.close_sync()
    return json.dumps(result, ensure_ascii=False)


def _webbridge_new_tab(params: dict, config: dict) -> str:
    url = params.get("url", "about:blank")
    result = _bridge.new_tab_sync(url)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_switch_tab(params: dict, config: dict) -> str:
    tab_id = params.get("tab_id", "")
    result = _bridge.switch_tab_sync(tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_close_tab(params: dict, config: dict) -> str:
    tab_id = params.get("tab_id", "")
    result = _bridge.close_tab_sync(tab_id)
    return json.dumps(result, ensure_ascii=False)


def _webbridge_list_tabs(params: dict, config: dict) -> str:
    result = _bridge.list_tabs_sync()
    return json.dumps(result, ensure_ascii=False)


# ── Registration ─────────────────────────────────────────────────────────────

_CALLBACK_MAP = {
    "WebBridgeNavigate": _webbridge_navigate,
    "WebBridgeClick": _webbridge_click,
    "WebBridgeEvaluate": _webbridge_evaluate,
    "WebBridgeType": _webbridge_type,
    "WebBridgeScreenshot": _webbridge_screenshot,
    "WebBridgeExtract": _webbridge_extract,
    "WebBridgeScroll": _webbridge_scroll,
    "WebBridgeClose": _webbridge_close,
    "WebBridgeNewTab": _webbridge_new_tab,
    "WebBridgeSwitchTab": _webbridge_switch_tab,
    "WebBridgeCloseTab": _webbridge_close_tab,
    "WebBridgeListTabs": _webbridge_list_tabs,
}


def register_webbridge_tools() -> None:
    """Register all WebBridge tools into the Dulus tool registry."""
    for schema in _TOOL_SCHEMAS:
        name = schema["name"]
        register_tool(ToolDef(
            name=name,
            schema=schema,
            func=_CALLBACK_MAP[name],
            read_only=False,
            concurrent_safe=False,
        ))


# Auto-register on import
register_webbridge_tools()
