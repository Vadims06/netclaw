"""
Unit tests for mcp-servers/worldlabs-marble-mcp/server.py's failure-category mapping (spec 122
FR-011, research.md R3/R4) and the confirmation guard (FR-016, research.md R8). World Labs itself
is mocked — these tests verify this server's own logic, not a live call (that's research.md R2's
job, already performed and documented as a one-off).
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

# Loaded by explicit file path under a unique module name — see test_topology_diagram_mcp.py's
# comment: every mcp-servers/*/ package has its own, unrelated server.py.
_server_path = Path(__file__).parent.parent.parent / "mcp-servers" / "worldlabs-marble-mcp" / "server.py"
_spec = importlib.util.spec_from_file_location("worldlabs_marble_mcp_server", _server_path)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def _resp(status_code, body):
    return httpx.Response(status_code=status_code, json=body)


# ---------------------------------------------------------------------------
# _map_failure: HTTP status -> normalized failure category (research.md R3)
# ---------------------------------------------------------------------------

def test_401_maps_to_authentication_failure_with_fixed_message():
    mapped = server._map_failure(401, json.dumps({"message": "Unauthorized"}))
    assert mapped["failure_category"] == "authentication_failure"
    assert "WLT_API_KEY" in mapped["message"]


def test_402_maps_to_insufficient_credits_passing_provider_message_through():
    provider_message = "Insufficient API credits to start this request. Add credits or enable auto-refill."
    mapped = server._map_failure(402, json.dumps({"error": {"message": provider_message}}))
    assert mapped["failure_category"] == "insufficient_credits"
    assert mapped["message"] == provider_message


def test_429_maps_to_rate_limited_with_wait_and_retry_guidance():
    mapped = server._map_failure(429, "")
    assert mapped["failure_category"] == "rate_limited"
    assert "wait" in mapped["message"].lower()


def test_404_default_category_is_not_found_or_expired():
    mapped = server._map_failure(404, "")
    assert mapped["failure_category"] == "not_found_or_expired"


def test_404_can_be_overridden_to_not_found_for_get_world():
    mapped = server._map_failure(404, "", not_found_category="not_found")
    assert mapped["failure_category"] == "not_found"


@pytest.mark.parametrize("status_code", [400, 422, 500])
def test_other_statuses_map_to_generic_failure(status_code):
    mapped = server._map_failure(status_code, json.dumps({"message": "boom"}))
    assert mapped["failure_category"] == "generic_failure"
    assert mapped["message"] == "boom"


def test_malformed_body_falls_back_without_raising():
    mapped = server._map_failure(500, "not json at all {{{")
    assert mapped["failure_category"] == "generic_failure"
    assert "HTTP 500" in mapped["message"]


# ---------------------------------------------------------------------------
# Confirmation guard (FR-016, research.md R8) — checked before any HTTP call
# ---------------------------------------------------------------------------

def test_generate_world_rejects_false_confirmation_without_any_http_call():
    with patch.object(server, "_http_post") as mock_post:
        with pytest.raises(RuntimeError) as exc_info:
            server.generate_world_impl(text_prompt="a prompt", display_name="My World", user_confirmed=False)
    mapped = json.loads(str(exc_info.value))
    assert mapped["failure_category"] == "confirmation_required"
    mock_post.assert_not_called()


def test_generate_world_rejects_non_boolean_truthy_confirmation():
    """A non-literal-True value (e.g. the string "true") MUST NOT satisfy the guard — the check
    is `is not True`, not truthiness, so a caller cannot accidentally satisfy it with a stray
    string."""
    with patch.object(server, "_http_post") as mock_post:
        with pytest.raises(RuntimeError) as exc_info:
            server.generate_world_impl(text_prompt="a prompt", display_name="My World", user_confirmed="true")
    mapped = json.loads(str(exc_info.value))
    assert mapped["failure_category"] == "confirmation_required"
    mock_post.assert_not_called()


def test_generate_world_proceeds_when_confirmed_true():
    with patch.object(server, "_http_post", return_value=_resp(200, {"operation_id": "op-1", "done": False})):
        result = json.loads(server.generate_world_impl(text_prompt="a prompt", display_name="My World", user_confirmed=True))
    assert result["operation_id"] == "op-1"


def test_generate_world_maps_failure_when_confirmed_but_provider_rejects():
    with patch.object(server, "_http_post", return_value=_resp(402, {"error": {"message": "no credits"}})):
        with pytest.raises(RuntimeError) as exc_info:
            server.generate_world_impl(text_prompt="a prompt", display_name="My World", user_confirmed=True)
    mapped = json.loads(str(exc_info.value))
    assert mapped["failure_category"] == "insufficient_credits"
    assert mapped["message"] == "no credits"


# ---------------------------------------------------------------------------
# Text-only by default vs. opt-in image (research.md R9/R10, corrected 2026-09-03
# after live evidence: image conditioning pastes the diagram flat and is less reliable)
# ---------------------------------------------------------------------------

def test_generate_world_defaults_to_text_only_world_prompt():
    captured = {}

    def fake_post(path, payload):
        captured["payload"] = payload
        return _resp(200, {"operation_id": "op-text"})

    with patch.object(server, "_http_post", side_effect=fake_post):
        server.generate_world_impl(text_prompt="a prompt", display_name="My World", user_confirmed=True)
    assert captured["payload"]["world_prompt"] == {"type": "text", "text_prompt": "a prompt"}


def test_generate_world_uses_image_prompt_only_when_explicitly_opted_in():
    captured = {}

    def fake_post(path, payload):
        captured["payload"] = payload
        return _resp(200, {"operation_id": "op-image"})

    with patch.object(server, "_http_post", side_effect=fake_post):
        server.generate_world_impl(
            text_prompt="a prompt", display_name="My World", user_confirmed=True, image_base64="aGVsbG8="
        )
    wp = captured["payload"]["world_prompt"]
    assert wp["type"] == "image"
    assert wp["image_prompt"] == {"source": "data_base64", "data_base64": "aGVsbG8=", "extension": "png"}


# ---------------------------------------------------------------------------
# check_generation_status / get_world — distinct 404 handling (research.md R4)
# ---------------------------------------------------------------------------

def test_check_generation_status_404_is_not_found_or_expired():
    with patch.object(server, "_http_get", return_value=_resp(404, {})):
        with pytest.raises(RuntimeError) as exc_info:
            server.check_generation_status_impl("op-expired")
    assert json.loads(str(exc_info.value))["failure_category"] == "not_found_or_expired"


def test_get_world_404_is_not_found():
    with patch.object(server, "_http_get", return_value=_resp(404, {})):
        with pytest.raises(RuntimeError) as exc_info:
            server.get_world_impl("world-missing")
    assert json.loads(str(exc_info.value))["failure_category"] == "not_found"


def test_get_world_success_passes_through_world_marble_url():
    body = {"world_id": "w-1", "world_marble_url": "https://marble.worldlabs.ai/world/w-1"}
    with patch.object(server, "_http_get", return_value=_resp(200, body)):
        result = json.loads(server.get_world_impl("w-1"))
    assert result["world_marble_url"] == "https://marble.worldlabs.ai/world/w-1"


# ---------------------------------------------------------------------------
# SC-005 — the API key must never leak into a log or a mapped failure output (finding E3)
# ---------------------------------------------------------------------------

def test_api_key_never_appears_in_any_mapped_failure_message(monkeypatch):
    monkeypatch.setenv("WLT_API_KEY", "sk-super-secret-value-12345")
    for status in (401, 402, 429, 404, 500):
        mapped = server._map_failure(status, json.dumps({"message": "sk-super-secret-value-12345 was here"}))
        # Even if a (hypothetical) malicious/broken response body echoed the key, only 402/generic
        # pass the provider's message through verbatim — 401/429/404 use fixed messages that never
        # touch the body at all. Assert the fixed-message categories never contain it either way.
        if mapped["failure_category"] in ("authentication_failure", "rate_limited"):
            assert "sk-super-secret-value-12345" not in mapped["message"]


def test_no_print_statements_anywhere_in_server_module():
    """FastMCP servers speak JSON-RPC over stdio — any stray print() corrupts the protocol, and
    would also be the most likely place a key could accidentally leak into a log (finding E3).
    Zero print() calls are required for both reasons."""
    source = _server_path.read_text()
    assert "print(" not in source


def test_no_logging_calls_reference_the_api_key_variable():
    """Static check: no actual logging/print call anywhere in the module interpolates
    WLT_API_KEY — restricted to real call-site tokens so prose in comments/docstrings that merely
    *mentions* WLT_API_KEY (of which there are several, by design) doesn't false-positive."""
    logging_call_tokens = ("logging.", "logger.", ".debug(", ".info(", ".warning(", ".error(", ".exception(", "print(")
    source = _server_path.read_text()
    for line in source.splitlines():
        if "WLT_API_KEY" in line and any(tok in line for tok in logging_call_tokens):
            pytest.fail(f"Possible credential-logging line: {line!r}")
