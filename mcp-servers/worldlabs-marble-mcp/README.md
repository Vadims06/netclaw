# worldlabs-marble-mcp

A thin, fully stateless proxy to three World Labs Marble REST endpoints, built for spec 122's
AI-augmented fantastical topology visualization feature. See
[specs/122-worldlabs-topology-viz/contracts/worldlabs-marble-mcp.md](../../specs/122-worldlabs-topology-viz/contracts/worldlabs-marble-mcp.md)
for the full wire contract, and
[specs/122-worldlabs-topology-viz/research.md](../../specs/122-worldlabs-topology-viz/research.md)
for why this design looks the way it does (R1: no upload step needed; R3: the failure-category
table; R4: why `get_world` exists as a durable fallback; R8: the confirmation guard).

This server holds no state of its own between calls (Clarifications session 2026-09-03, Q1) — the
caller (the `worldlabs-topology-viz` skill) is responsible for retaining any `operation_id`/
`world_id` it needs to check later.

## Tools

| Tool | Description |
|---|---|
| `generate_world(image_base64, text_prompt, display_name, user_confirmed, image_extension="png", model="marble-1.1")` | **The one credit-spending operation in this server.** Starts an image-conditioned Marble world generation. Requires `user_confirmed=true` — a missing or `false` value is rejected with `confirmation_required` before any request is sent to World Labs (FR-016). Returns the operation object (`operation_id`, `done`, `expires_at`, `cost`) as JSON text. |
| `check_generation_status(operation_id)` | Polls a previously started generation. A 404 maps to `not_found_or_expired` — the operation record itself may have expired (they carry roughly a one-hour `expires_at`), which does not necessarily mean the generation failed. |
| `get_world(world_id)` | Durable, no-cost, read-only lookup of a completed world by id — the fallback path when an operation record has expired but the world it produced has not. A 404 here maps to `not_found`. |

## Failure categories

Every non-200 response is normalized into one of five categories (never the raw provider error
object, and never anything derived from the API key):

| Category | Meaning |
|---|---|
| `authentication_failure` | The API key was rejected (HTTP 401) — check `WLT_API_KEY`, never logged |
| `insufficient_credits` | HTTP 402 — the provider's own message is passed through verbatim |
| `rate_limited` | HTTP 429 — wait and retry, do not resubmit automatically |
| `not_found_or_expired` / `not_found` | HTTP 404 — worded differently for `check_generation_status` vs. `get_world` (research.md R4) |
| `generic_failure` | Any other non-200 status |
| `confirmation_required` | `generate_world` only — `user_confirmed` was missing or not literally `true`; no HTTP call was made |

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `WLT_API_KEY` | Yes | World Labs API key (`platform.worldlabs.ai/api-keys`), with a funded account. Read fresh from the environment on every call — never cached at import time, never logged, never returned to a caller. |

## Transport

stdio, matching every other Python MCP server in this repo (FastMCP, `mcp.server.fastmcp`).

## Installation

```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
```

Registered in `config/openclaw.json` / `~/.openclaw/openclaw.json` as:
```json
{
  "command": "python3",
  "args": ["-u", "mcp-servers/worldlabs-marble-mcp/server.py"],
  "env": {"WLT_API_KEY": "${WLT_API_KEY}"},
  "cwd": "/home/johncapobianco/netclaw"
}
```
