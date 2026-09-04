# Contract: `worldlabs-marble-mcp`

**New MCP server** registered as `worldlabs-marble-mcp` in `~/.openclaw/openclaw.json` and
`config/openclaw.json`. Stdio transport, FastMCP (Python), matching every other NetClaw MCP server.
A fully stateless proxy to three World Labs Marble REST endpoints — it holds no state of its own
between calls (Clarifications session 2026-09-03, Q1) and reads exactly one credential,
`WLT_API_KEY`, from the environment at call time (never logged, never echoed — FR-010).

The real confirmation judgment is still made by the calling skill (`worldlabs-topology-viz`) and the
orchestrating conversation, exactly as every other MCP server in this repo is a thin executor of what
it is asked to do — but `generate_world` is **not** fully unconditional: it requires an explicit
`user_confirmed: true` argument and rejects the call outright if it is missing or `false`, before any
outbound HTTP request is made (FR-016, research.md R8 — added during `/speckit.analyze` after
finding SC-002's "verified by inspection" claim had no code-level backing).

## Tool: `generate_world`

**Purpose**: Start a Marble world generation from a composed text prompt (FR-006). **This is the
one credit-spending operation in this feature.**

**Text-only by default (corrected 2026-09-03, research.md R9/R10, after six real production
generations with real credits spent)**: `image_base64` is optional and unset by default. Passing
it opts into image-conditioned generation, which is known to paste the reference diagram flat and
unchanged into the scene instead of using it as structural guidance, and is also measurably less
reliable (3 of 4 image-bearing attempts failed this session vs. 4 of 4 text-only successes). The
recommended path is text-only, with the prompt describing each real device and each real link
individually (`fantastical_prompt_builder.build_prompt`) — that is what actually carries real data
into the result.

### Arguments

```json
{
  "text_prompt": "string — the composed Fantastical Prompt",
  "display_name": "string, max 64 chars",
  "user_confirmed": "boolean, REQUIRED, must be true — see 'Confirmation guard' below",
  "image_base64": "string, OPTIONAL, default unset — base64-encoded PNG. Opt-in only; known tradeoffs above.",
  "image_extension": "string, optional, default 'png' — ignored if image_base64 is not set",
  "model": "string, optional, default 'marble-1.1' — one of marble-1.0-draft|marble-1.0|marble-1.1|marble-1.1-plus"
}
```

### Confirmation guard (FR-016, research.md R8)

If `user_confirmed` is missing, `false`, or not literally `true`, this tool MUST return
`isError: true` with `failure_category: "confirmation_required"` and MUST NOT make any outbound
HTTP request to World Labs. This check happens before argument validation of anything else
credit-relevant, so an unconfirmed call never reaches — and never risks — the provider at all.

### Result (MCP `tools/call` result, `content[0].text` is this JSON)

Success (HTTP 200 from `POST /marble/v1/worlds:generate`):
```json
{
  "operation_id": "8c874c13-9094-4084-a9c9-0124b0e5caaa",
  "done": false,
  "expires_at": "2026-09-03T17:46:51Z",
  "cost": null
}
```

Failure — returned as an MCP `isError: true` result with a normalized failure category (never the
raw provider error object, and never the API key):
```json
{"content": [{"type": "text", "text": "{\"failure_category\": \"insufficient_credits\", \"message\": \"Insufficient API credits to start this request. Add credits or enable auto-refill.\"}"}], "isError": true}
```

### Failure category mapping (research.md R3 — FR-011)

| HTTP status | `failure_category` | Message source |
|---|---|---|
| 401 | `authentication_failure` | Fixed message: "World Labs rejected the API key — check WLT_API_KEY." Never includes the key value. |
| 402 | `insufficient_credits` | Provider's own message, passed through verbatim |
| 429 | `rate_limited` | Fixed message: "World Labs rate limit hit — wait and retry; do not resubmit automatically." |
| 400 / 422 / 500 / other | `generic_failure` | Provider's own message, passed through verbatim |
| *(no HTTP call made)* | `confirmation_required` | Fixed message: "generate_world requires user_confirmed=true — this call was rejected before any request was sent to World Labs." |

### Non-goals

- No upload step — the image travels inline via `world_prompt.image_prompt.source = "data_base64"`
  (research.md R1). This tool never calls `media-assets:prepare_upload`.
- No credit-balance pre-check (none exists — research.md), no retry — a single attempt per call once
  `user_confirmed` is satisfied. The confirmation *judgment* (when it is appropriate to set
  `user_confirmed=true`) still lives one layer up, in the skill — this tool only enforces that the
  flag was set, it does not decide whether it should have been.
- No persistence of the returned `operation_id` anywhere — the caller must retain it.

## Tool: `check_generation_status`

**Purpose**: Poll a previously started generation (FR-007). Requires the caller to supply the
`operation_id` — this server keeps no record of any operation it has started.

### Arguments

```json
{"operation_id": "string"}
```

### Result

While in progress:
```json
{"operation_id": "...", "done": false, "metadata": {"world_id": "...", "progress": "..."}}
```

On completion:
```json
{
  "operation_id": "...",
  "done": true,
  "cost": {"total_credits": 42, "line_items": [...]},
  "response": {
    "world_id": "...",
    "display_name": "...",
    "world_marble_url": "https://marble.worldlabs.ai/world/...",
    "assets": {"thumbnail_url": "...", "splats": {"spz_urls": {...}}, "mesh": {...}, "imagery": {"pano_url": "..."}}
  }
}
```

On failure (generation itself failed, not a transport error):
```json
{"operation_id": "...", "done": true, "error": {"code": "...", "message": "..."}}
```

Transport-level failure (`isError: true`), same five-category mapping as `generate_world`, plus:

| HTTP status | `failure_category` |
|---|---|
| 404 | `not_found_or_expired` — the operation record itself expired or never existed; if a `world_id` was previously observed in an earlier poll's `metadata`, call `get_world` instead (research.md R4) |

## Tool: `get_world`

**Purpose**: Durable, no-cost, read-only lookup of a completed world by id — the fallback path when
an operation record has expired (research.md R4) but the world it produced has not.

### Arguments

```json
{"world_id": "string"}
```

### Result

Same `response` shape as `check_generation_status`'s completed-operation case
(`world_id`, `display_name`, `world_marble_url`, `assets`), or `isError: true` with
`failure_category: "not_found"` on a 404.

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `WLT_API_KEY` | Yes | World Labs API key. Read at call time from the environment only — never from a config file, never logged, never included in any tool result (FR-010). |

## Transport

stdio, matching every other Python MCP server in this repo (FastMCP, `mcp.server.fastmcp`).
