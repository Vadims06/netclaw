#!/usr/bin/env python3
"""
worldlabs-marble-mcp — a thin, fully stateless proxy to three World Labs Marble REST endpoints.

See specs/122-worldlabs-topology-viz/contracts/worldlabs-marble-mcp.md for the full wire contract.
This server holds no state of its own between calls (Clarifications session 2026-09-03, Q1) and
reads exactly one credential, WLT_API_KEY, from the environment at call time — never logged, never
echoed in a tool result (FR-010).

Tools: generate_world (the one credit-spending operation — guarded by a required user_confirmed
argument, FR-016/research.md R8), check_generation_status, get_world.
"""

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("worldlabs-marble-mcp")

WORLD_LABS_API_BASE = "https://api.worldlabs.ai/marble/v1"

# contracts/worldlabs-marble-mcp.md's failure-category table (research.md R3). The 404 category is
# parameterized because check_generation_status and get_world want different wording for the same
# status code: an operation record can expire (research.md R4's whole reason get_world exists as a
# durable fallback), but a world itself is either found or it isn't.
_FIXED_MESSAGES = {
    "authentication_failure": "World Labs rejected the API key — check WLT_API_KEY.",
    "rate_limited": "World Labs rate limit hit — wait and retry; do not resubmit automatically.",
}


def _provider_message(body_text: str, fallback: str) -> str:
    """Best-effort extraction of the provider's own error message, passed through verbatim
    (research.md R3 — 402's exact wording is deliberately not re-worded). Never raises on
    malformed JSON; falls back to a fixed message instead of leaking a raw, possibly-huge body."""
    try:
        parsed = json.loads(body_text)
    except (json.JSONDecodeError, TypeError):
        return fallback
    if isinstance(parsed, dict):
        error_obj = parsed.get("error")
        if isinstance(error_obj, dict) and error_obj.get("message"):
            return str(error_obj["message"])
        if parsed.get("message"):
            return str(parsed["message"])
    return fallback


def _map_failure(status_code: int, body_text: str, not_found_category: str = "not_found_or_expired") -> dict:
    """Maps an HTTP failure response to one of the five (or six, including confirmation_required)
    normalized failure categories — never the raw provider error object, and never anything
    derived from the request (so the API key, which is only ever sent as a header, can never end
    up here). See contracts/worldlabs-marble-mcp.md's failure-category table."""
    if status_code == 401:
        return {"failure_category": "authentication_failure", "message": _FIXED_MESSAGES["authentication_failure"]}
    if status_code == 402:
        fallback = "Insufficient API credits to start this request. Add credits or enable auto-refill."
        return {"failure_category": "insufficient_credits", "message": _provider_message(body_text, fallback)}
    if status_code == 429:
        return {"failure_category": "rate_limited", "message": _FIXED_MESSAGES["rate_limited"]}
    if status_code == 404:
        fallback = "Not found."
        return {"failure_category": not_found_category, "message": _provider_message(body_text, fallback)}
    fallback = f"World Labs returned HTTP {status_code}."
    return {"failure_category": "generic_failure", "message": _provider_message(body_text, fallback)}


def _confirmation_required_error() -> dict:
    """FR-016 / research.md R8 — raised before any outbound HTTP call is made, so an unconfirmed
    call never reaches (and never risks) the provider at all."""
    return {
        "failure_category": "confirmation_required",
        "message": (
            "generate_world requires user_confirmed=true — this call was rejected before any "
            "request was sent to World Labs."
        ),
    }


def _headers() -> dict:
    """WLT_API_KEY is read fresh from the environment on every call (FR-010) — never cached at
    import time, never logged, never returned to a caller."""
    return {"WLT-Api-Key": os.environ.get("WLT_API_KEY", ""), "Content-Type": "application/json"}


def _http_post(path: str, json_body: dict) -> httpx.Response:
    return httpx.post(f"{WORLD_LABS_API_BASE}{path}", json=json_body, headers=_headers(), timeout=30.0)


def _http_get(path: str) -> httpx.Response:
    return httpx.get(f"{WORLD_LABS_API_BASE}{path}", headers=_headers(), timeout=30.0)


def generate_world_impl(
    text_prompt: str,
    display_name: str,
    user_confirmed: bool,
    image_base64: str | None = None,
    image_extension: str = "png",
    model: str = "marble-1.1",
) -> str:
    """The one credit-spending operation in this feature (contracts/worldlabs-marble-mcp.md).
    Raises RuntimeError(json string) on any failure — including confirmation_required, which is
    checked before anything else and before any HTTP call is made (FR-016, research.md R8).

    TEXT-ONLY BY DEFAULT (research.md R9/R10, corrected 2026-09-03 after live evidence): passing
    image_base64 is now opt-in, not the default path. Six real production generations showed
    image conditioning (1) treats the reference diagram as a literal photo and pastes it flat and
    unchanged into the scene rather than using it as structural guidance, and (2) is measurably
    less reliable (3 of 4 image-bearing attempts failed with a 500 or a timeout; 4 of 4 text-only
    attempts succeeded on the first try). Callers should build text_prompt with real device/link
    detail (see fantastical_prompt_builder.build_prompt) instead of relying on image_base64."""
    if user_confirmed is not True:
        raise RuntimeError(json.dumps(_confirmation_required_error()))

    if image_base64:
        world_prompt = {
            "type": "image",
            "image_prompt": {
                "source": "data_base64",
                "data_base64": image_base64,
                "extension": image_extension,
            },
            "text_prompt": text_prompt,
        }
    else:
        world_prompt = {"type": "text", "text_prompt": text_prompt}

    payload = {
        "display_name": display_name,
        "model": model,
        "world_prompt": world_prompt,
    }
    resp = _http_post("/worlds:generate", payload)
    if resp.status_code != 200:
        raise RuntimeError(json.dumps(_map_failure(resp.status_code, resp.text)))
    return json.dumps(resp.json())


def check_generation_status_impl(operation_id: str) -> str:
    """Read-only poll — no credentials, no confirmation gate needed (contracts/worldlabs-marble-mcp.md).
    A 404 here means the *operation record* expired or never existed, not necessarily that the
    generation failed (research.md R4) — hence not_found_or_expired rather than not_found."""
    resp = _http_get(f"/operations/{operation_id}")
    if resp.status_code != 200:
        raise RuntimeError(json.dumps(_map_failure(resp.status_code, resp.text, not_found_category="not_found_or_expired")))
    return json.dumps(resp.json())


def get_world_impl(world_id: str) -> str:
    """Durable, no-cost fallback lookup (research.md R4) — a 404 here means the world itself does
    not exist (or access is denied), which is a different, more final condition than an expired
    operation record."""
    resp = _http_get(f"/worlds/{world_id}")
    if resp.status_code != 200:
        raise RuntimeError(json.dumps(_map_failure(resp.status_code, resp.text, not_found_category="not_found")))
    return json.dumps(resp.json())


@mcp.tool()
async def generate_world(
    text_prompt: str,
    display_name: str,
    user_confirmed: bool,
    image_base64: str | None = None,
    image_extension: str = "png",
    model: str = "marble-1.1",
) -> str:
    """Start a Marble world generation from a composed text prompt. THIS IS THE ONE
    CREDIT-SPENDING OPERATION IN THIS FEATURE.

    TEXT-ONLY BY DEFAULT — do not pass image_base64 unless you have a specific reason to. Live
    evidence (2026-09-03, six real production generations) showed image conditioning pastes the
    reference diagram flat and unchanged into the scene instead of using it as structural
    guidance, and is measurably less reliable (3 of 4 image-bearing attempts failed vs. 4 of 4
    text-only successes). Build text_prompt with real device/link detail instead (see
    fantastical_prompt_builder.build_prompt) — describe each device and each real connection
    individually, not as an aggregate count, and never ask for legible inscribed text (text
    rendering is unreliable — a real attempt at "eth0/1" came back garbled).

    Args:
        text_prompt: the composed Fantastical Prompt
        display_name: max 64 chars
        user_confirmed: MUST be true — the caller MUST have already obtained explicit user
            confirmation before setting this; a missing or false value is rejected before any
            request is sent to World Labs (FR-016)
        image_base64: OPT-IN ONLY, default None — base64-encoded PNG (e.g.
            topology-diagram-mcp's image_base64 output). Known to produce a flat-pasted-diagram
            artifact; only pass this if you have already accepted that tradeoff.
        image_extension: file extension of image_base64's content, default "png" (ignored if
            image_base64 is not set)
        model: one of marble-1.0-draft|marble-1.0|marble-1.1|marble-1.1-plus, default "marble-1.1"
    """
    return generate_world_impl(text_prompt, display_name, user_confirmed, image_base64, image_extension, model)


@mcp.tool()
async def check_generation_status(operation_id: str) -> str:
    """Poll a previously started generation. Requires the caller to supply operation_id — this
    server keeps no record of any operation it has started (Clarifications session 2026-09-03, Q1).

    Args:
        operation_id: returned by a prior generate_world call
    """
    return check_generation_status_impl(operation_id)


@mcp.tool()
async def get_world(world_id: str) -> str:
    """Durable, no-cost, read-only lookup of a completed world by id — the fallback path when an
    operation record has expired but the world it produced has not (research.md R4).

    Args:
        world_id: observed in an earlier check_generation_status poll's metadata, or in a
            completed operation's response
    """
    return get_world_impl(world_id)


if __name__ == "__main__":
    mcp.run()
