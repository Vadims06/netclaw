# Phase 1 Data Model: World Labs Fantastical Topology Visualization

No new persistent storage (spec FR-013/FR-015). Every entity below exists only for the duration of a
single request/response cycle, held in the calling conversation's own context — not written to any
database, file, or in-memory server-side cache.

## Topology Snapshot *(consumed, not owned by this feature)*

Reused as-is from the existing spec 120/121 shape. Trimmed copy of spec 120's
`topology_model.py` ported into this feature's skill directory (same technique spec 120 itself used
when porting from spec 046 — copy and trim, not cross-skill import).

| Field | Type | Notes |
|---|---|---|
| `devices` | list of `Device` | `hostname` (str), `role` (`DeviceRole` enum: router/switch/firewall/load_balancer/client/unclassified), `state` (`OperationalState` enum: healthy/degraded/down/unknown, optional) |
| `links` | list of `Link` | `a`, `b` (hostnames), `label` (str, optional) |

**Validation rules** (enforced by the existing `topology-diagram-mcp/render_structural`, unmodified
— FR-012):
- No duplicate hostnames.
- Every link's endpoints must reference a declared device.
- Device count over 60 fails with a distinct, reportable error (the working-resolution density
  ceiling) — checked before any World Labs call is possible, since no Reference Diagram means no
  image input exists yet.

**Sanitization**: `sanitize_metadata` (ported unchanged from spec 120's `topology_model.py`) strips
any credential-shaped key (password, secret, token, api_key, etc.) from device/link metadata before
it can reach `fantastical_prompt_builder.py`. This matters more here than in spec 120, since the
composed prompt is sent to a third-party (World Labs), not just to a locally-hosted ComfyUI
instance.

## Reference Diagram *(produced by the existing spec 121 pipeline, consumed here)*

| Field | Type | Notes |
|---|---|---|
| `image_base64` | str | PNG bytes, base64-encoded — capable of being passed into `generate_world`'s optional `data_base64` image reference (research.md R1), but not part of the default generation path as of research.md R9/R10; never written to disk by this feature |
| `format` | str | Always `"png"` |
| `positions` | dict[str, [float, float]] | Canvas coordinates per hostname — not used by this feature, but part of the existing tool's result shape |
| `device_count` | int | Used to select connectivity-density language in the Fantastical Prompt |

## Fantastical Prompt *(new — produced by `fantastical_prompt_builder.py`)*

| Field | Type | Notes |
|---|---|---|
| `theme` | str | User-selected or defaulted (e.g. "floating islands", "underwater city"); free text, bounded length |
| `role_summary` | str | e.g. "2 routers, 2 switches" — same technique as spec 120's `prompt_builder.py` |
| `connectivity_summary` | str | sparse / typical hierarchical / densely meshed, from link-to-device ratio |
| `text_prompt` | str | The final composed string sent as `world_prompt.text_prompt`; bounded length (mirrors spec 120's 900-char bound as a reasonable default, since World Labs documents no explicit maximum — research.md) |

**Lifecycle**: Built fresh on every preview request (FR-003 — a new theme produces a new prompt from
the same snapshot); never persisted; identical in shape whether used for a free preview or an actual
paid generation (FR-006's requirement that the same reference image + prompt pairing drives both).

## Generation Request *(new — the credit-spending call's input, never persisted)*

| Field | Type | Notes |
|---|---|---|
| `text_prompt` | str | From the Fantastical Prompt — per-device and per-real-link description (research.md R9), not an aggregate summary |
| `image_base64` / `image_extension` | str, optional | **Opt-in only, unset by default** (corrected 2026-09-03, research.md R9/R10) — not populated from the Reference Diagram in the default path. Passing it pastes the diagram flat into the scene and is measurably less reliable; not recommended |
| `display_name` | str | Derived from the topology snapshot's identity (e.g. lab/session name), max 64 chars per the provider's documented limit |
| `model` | str | Defaults to `marble-1.1`; not user-configurable in v1 (Assumptions — no reasonable case for exposing `marble-1.0-draft`/`marble-1.0-plus` selection yet) |
| `user_confirmed` | bool | **Required, must be `true`.** Added during `/speckit.analyze` (finding E1) as a code-level safeguard: the tool rejects the call with `confirmation_required` before making any outbound HTTP request if this is missing or `false` — the conversational confirmation (FR-004) and this argument are two independent layers, not one. |

## Generation Operation *(provider-owned, referenced not stored)*

| Field | Type | Notes |
|---|---|---|
| `operation_id` | str | The caller's only handle to check status later (Clarifications Q1 — no server-side tracking) |
| `done` | bool | |
| `expires_at` | ISO 8601 datetime | Operation record expires; poll before this or fall back to `get_world` once `world_id` is known (research.md R4) |
| `error` | object, optional | `{code, message}` — mapped to one of five failure categories (research.md R3) before ever reaching the user |
| `cost` | object, optional | `{total_credits, line_items}` — surfaced to the user once known; never estimated in advance (no such endpoint exists) |
| `metadata` | object, optional | May include `world_id` before `done=true` — the fallback lookup key |

## Generated World *(provider-owned, referenced not stored — FR-013)*

| Field | Type | Notes |
|---|---|---|
| `world_id` | str | Durable identifier — usable with `get_world` independent of operation expiry (research.md R4) |
| `world_marble_url` | str | The viewer link surfaced to the user (FR-008) — `marble.worldlabs.ai/world/{world_id}` |
| `assets` | object | `imagery.pano_url`, `mesh.*`, `splats.spz_urls`, `thumbnail_url` — surfaced as-is, not re-hosted or downloaded by this feature |
| `display_name` | str | Echoed back from the request |

**Every result carrying any of the above MUST also carry the FR-009 decorative-interpretation
statement and a reference to (or copy of) the Reference Diagram it was generated from.**

## GAIT Audit Entry *(new — added during `/speckit.analyze`, finding C1)*

Not owned by this feature — written via the existing, repo-wide `gait_record_turn` mechanism
(Constitution Principle IV). Not a new store; this table documents only which fields this feature
contributes to that existing mechanism.

| Field | Type | Notes |
|---|---|---|
| `user_text` | str | The topology snapshot's identity/theme and the fact that the user explicitly confirmed generation |
| `assistant_text` | str | The outcome: `operation_id`, `world_id`/`world_marble_url` once known, `cost.total_credits` once known, or the failure category |
| `artifacts` | list | Empty, or a reference to the Reference Diagram's identity — never the raw base64 PNG bytes, never the API key, never raw device metadata beyond hostname/role identity |

**Written once per confirmed `generate_world` call** (success or failure) — not per preview (previews
spend nothing and are explicitly free/repeatable, FR-002/FR-003), and not per status-check poll
(polling is a read, not an operational decision).

## State Transitions

```text
Topology Snapshot (existing, given)
        │
        ▼
Reference Diagram  ──(render_structural, spec 121, unmodified)
        │
        ▼
Fantastical Prompt ──(fantastical_prompt_builder.py, this feature)
        │
        │  ◄── FREE, repeatable with a different theme — no state change, no external call (FR-002/003)
        │
        │  ════ explicit user confirmation, conversational (FR-004/005) ════
        ▼
Generation Request (user_confirmed=true) ──(generate_world)
        │
        │  ── generate_world rejects with `confirmation_required` if user_confirmed is missing/false,
        │     BEFORE any outbound HTTP call (FR-016, code-level guard, not just convention)
        ▼
[HTTP call to World Labs — the ONLY credit-spending step]
        │
        ▼
GAIT Audit Entry written (gait_record_turn — FR-015, Constitution Principle IV; NOT a new store)
        │
        ▼
Generation Operation ──poll── check_generation_status ──┐
        │                                                │ (expires; if world_id already
        │ done=true                                      │  known, fall back here instead)
        ▼                                                ▼
Generated World  ◄──────────────────────────────── get_world(world_id)
```

No transition in this diagram writes to any *new* NetClaw-controlled store. The one write shown
(the GAIT Audit Entry) goes to the pre-existing, repo-wide GAIT audit trail — every other arrow is
either a pure-Python transformation (no external call) or a stateless HTTP round trip to World Labs.
