#!/usr/bin/env python3
"""
visual_verify.py — automated headless-browser verification of the live HUD (research.md R2).

Frozen (see specs/122-astra-live-digital-twin/plan.md, loop.md). This exists because specs
101/102 relied on a human manually taking and comparing screenshots — there is no human in an
unattended loop iteration, so this is the only way the gate step can independently confirm the
twin scene actually rendered, not merely that the server process didn't crash.

Contract this file depends on (owned by Phase C's HUD work, NOT this frozen file): the page at
$ASTRA_TWIN_HUD_URL must set `window.__astraTwinDebug = { nodeCount: <int>, linkCount: <int>,
lastError: <string|null> }` once the twin scene has rendered at least one frame, and must keep
it current as deltas are applied. This is a debug hook, not a public API — the maker is free to
name internal variables anything it wants; `window.__astraTwinDebug` is the one stable name this
harness (frozen) reads, so it may not be renamed by any loop iteration.

Usage:
    python3 harness/visual_verify.py --out-dir loop/runs/<iteration>
Exit 0 = screenshot captured, non-blank, element counts present and > 0, no console errors.
Exit 1 = any of those failed; a written reason and the screenshot (if captured) land in --out-dir.

Requires Playwright with a Chromium browser installed. On hosts where the default `python3` on
PATH is newer than what Playwright's wheels support, set PLAYWRIGHT_PYTHON to an interpreter
that has it (this host: python3.13 — see loop/state/memory.md for why).
"""

import argparse
import json
import os
import sys
import time

DEFAULT_HUD_URL = os.environ.get("ASTRA_TWIN_HUD_URL", f"http://localhost:{os.environ.get('HUD_PORT', 3001)}/")
DEBUG_HOOK_WAIT_SECONDS = 20
DEBUG_HOOK_POLL_INTERVAL = 0.5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--url", default=DEFAULT_HUD_URL)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    screenshot_path = os.path.join(args.out_dir, "twin_screenshot.png")
    result_path = os.path.join(args.out_dir, "visual_verify_result.json")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _fail(result_path, "playwright not importable — see this file's docstring re: PLAYWRIGHT_PYTHON")

    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        try:
            page.goto(args.url, wait_until="networkidle", timeout=30000)
        except Exception as exc:
            browser.close()
            return _fail(result_path, f"failed to load {args.url}: {exc}")

        debug = None
        deadline = time.time() + DEBUG_HOOK_WAIT_SECONDS
        while time.time() < deadline:
            debug = page.evaluate("window.__astraTwinDebug || null")
            if debug and debug.get("nodeCount", 0) > 0:
                break
            time.sleep(DEBUG_HOOK_POLL_INTERVAL)

        page.screenshot(path=screenshot_path)
        browser.close()

    if debug is None:
        return _fail(result_path, "window.__astraTwinDebug never appeared — scene did not signal it rendered")

    if debug.get("lastError"):
        return _fail(result_path, f"HUD reported lastError: {debug['lastError']}")

    if console_errors:
        return _fail(result_path, f"browser console errors: {console_errors}", screenshot_path)

    node_count = debug.get("nodeCount", 0)
    link_count = debug.get("linkCount", 0)
    if node_count <= 0:
        return _fail(result_path, f"nodeCount is {node_count} — scene appears empty", screenshot_path)

    if _screenshot_is_blank(screenshot_path):
        return _fail(result_path, "screenshot is blank (uniform color) despite nonzero element counts", screenshot_path)

    _write_result(result_path, {
        "status": "pass",
        "url": args.url,
        "node_count": node_count,
        "link_count": link_count,
        "screenshot": screenshot_path,
    })
    print(f"OK: {node_count} nodes, {link_count} links, screenshot at {screenshot_path}")
    return 0


def _screenshot_is_blank(path: str, sample_stride: int = 17) -> bool:
    """Cheap non-blank check: sample pixels and confirm not all identical. Avoids a heavy
    imaging dependency — PNG chunk-level sampling via Pillow if available, else a raw byte
    variance check on the file itself as a last resort."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        pixels = list(img.getdata())[::sample_stride]
        return len(set(pixels)) <= 1
    except ImportError:
        with open(path, "rb") as fh:
            data = fh.read()
        sample = data[::sample_stride]
        return len(set(sample)) <= 2  # PNG framing bytes alone won't vary much; content will


def _fail(result_path: str, reason: str, screenshot_path: str | None = None) -> int:
    _write_result(result_path, {"status": "fail", "reason": reason, "screenshot": screenshot_path})
    print(f"FAIL: {reason}", file=sys.stderr)
    return 1


def _write_result(result_path: str, payload: dict) -> None:
    with open(result_path, "w") as fh:
        json.dump(payload, fh, indent=2)


if __name__ == "__main__":
    sys.exit(main())
