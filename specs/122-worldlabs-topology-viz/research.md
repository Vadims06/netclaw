# Phase 0 Research: World Labs Fantastical Topology Visualization

## R1: Image input — `data_base64` replaces the assumed upload-then-generate flow

**Decision**: `worldlabs-marble-mcp`'s `generate_world` tool passes the reference PNG directly as
`world_prompt.image_prompt = {"source": "data_base64", "data_base64": "<...>", "extension": "png"}`
in the single `POST /marble/v1/worlds:generate` call. No `media-assets:prepare_upload` call is made.

**Rationale**: The feature description (and this session's first working draft) assumed World
Labs' documented "upload a local image" quickstart flow — `media-assets:prepare_upload` returning a
signed upload URL, a `PUT` of the raw bytes, then referencing the resulting `media_asset_id` in
`worlds:generate`. Fetching the endpoint's own reference schema
(`/api/reference/worlds/generate`) during planning showed image/video references support three
source types: `uri`, `media_asset`, and `data_base64`. Since the reference diagram is already
in-process as PNG bytes (from `topology-diagram-mcp/render_structural`'s `image_base64` field,
already base64-encoded), `data_base64` needs zero extra round trips, introduces no orphaned-asset
failure mode (an uploaded asset left behind by a generation that then fails), and needs no second
tool (`upload_reference_image`) on the new MCP server at all.

**Alternatives considered**:
- Two-step upload-then-generate (the originally assumed flow) — rejected: strictly more failure
  surface (a successful upload followed by a failed generate leaves a billed-for-nothing orphaned
  asset) and one more tool to build, test, and document for no functional benefit, since the image
  never needs to be independently addressable by URL for this feature's purposes.
- `uri` source (host the PNG somewhere public first) — rejected: NetClaw has no existing
  public-image-hosting capability, and inventing one purely to satisfy this would be far more
  machinery than the feature needs.

## R2: Live authentication verification (satisfies FR-014/SC-006)

**Decision**: FR-014/SC-006's "minimal, low/no-cost round trip" requirement is already satisfied as
of this planning session, not deferred to implementation.

**Rationale**: During the conversation that produced this spec, a freshly rotated `WLT_API_KEY` was
tested directly against `POST /marble/v1/worlds:generate` using World Labs' own quickstart text
prompt ("Mystical Forest"). Result: HTTP 200, a real `operation_id`
(`8c874c13-9094-4084-a9c9-0124b0e5caaa`), `expires_at` one hour out. This is real evidence the
credential and basic connectivity work end-to-end against the production API — not a mock, not a
docs-only claim. (An earlier, differently-sourced key returned HTTP 401 on the identical request,
which is what motivated key rotation in the first place; that failure was platform-side, not a
client-side defect — see the session's diagnostic steps: clean key encoding, exact documented
request shape, still 401.) The one caveat: this verification call was a **text**-only generation
(no image), since it predates this plan's design. A first real call using the actual
`generate_world` tool with an image reference (once implemented) is still the first true end-to-end
exercise of this feature's exact request shape — tracked as an implementation-time task, not a
re-run of basic auth verification.

**Alternatives considered**: Treating FR-014 as still-open until implementation — rejected: the
evidence already exists and re-spending credits purely to re-prove a fact already proven would
contradict the credit-consciousness this same spec requires.

## R3: HTTP status → failure-category mapping (satisfies FR-011)

**Decision**: `generate_world`'s error handling maps:

| HTTP status | Category | User-facing guidance |
|---|---|---|
| 401 | `authentication_failure` | Check `WLT_API_KEY` — never echo the key itself |
| 402 | `insufficient_credits` | Add credits or enable auto-refill (this is the API's own documented message text) |
| 429 | `rate_limited` | Wait and retry — do not re-attempt automatically |
| 400 / 422 / 500 / anything else | `generic_failure` | Pass through the provider's own error message (it carries no credential) |

`check_generation_status` and `get_world` map 404 to a fifth category, `not_found_or_expired`,
distinct from the four above (an expired *operation* is not the same class of problem as a failed
*generation* — research.md R4 covers the durable fallback for this case).

**Rationale**: Confirmed against `/api/reference/worlds/generate`'s documented error table (400,
402, 422, 500) plus this session's own empirical 401 (bad key) and the operations/worlds reference
pages' documented 404s. 402's exact message text was specified in World Labs' own reference doc
("Insufficient API credits to start this request. Add credits or enable auto-refill") — that natural
text is reused verbatim rather than re-worded, since it is already the clearest possible instruction
and re-wording it risks losing the "enable auto-refill" detail. 429 is not explicitly documented on
this endpoint, but the World Labs dashboard's own "Rate limits" page (seen directly in this session)
describes "default request limits, higher-throughput options, and retry guidance for world
generation starts" — standard HTTP convention (429 Too Many Requests) is assumed for this in the
absence of a documented alternative status code, and is treated as its own category per
Clarifications Q3.

**Alternatives considered**: Folding 429 into `generic_failure` — rejected per Clarifications
session 2026-09-03 Q3 (explicit user decision: rate-limiting needs its own "wait and retry" guidance,
distinct from a failure that might need credentials or billing checked).

## R4: Operation expiry vs. world durability (informs `get_world`'s role)

**Decision**: `worldlabs-marble-mcp` exposes `get_world(world_id)` (`GET /marble/v1/worlds/{id}`) as
a durable fallback lookup, separate from `check_generation_status(operation_id)`
(`GET /marble/v1/operations/{id}`).

**Rationale**: World Labs' own docs state operations carry an `expires_at` and that polling an
expired operation returns 404 (confirmed empirically: this session's own test operation carries
`expires_at` one hour after creation). `check_generation_status`'s `metadata` field is documented to
include a `world_id` even before the operation completes. Once a `world_id` is known, the `World`
object it identifies is retrievable via `worlds/get`, whose documentation does not mention any
expiry behavior of its own (unlike operations) — treating it as durable for the life of the world is
the more conservative, more useful assumption, and does not require re-confirming anything since
`get_world` costs no credits (it's a read).

**Alternatives considered**: Only exposing `check_generation_status` and accepting that a caller who
does not poll within the operation's expiry window loses access to a world they already paid for —
rejected: this is a real, easily-hit failure mode (a five-minute generation plus normal
human-response-time delay could plausibly exceed a short expiry window), and a second read-only,
no-cost tool call is a small addition compared to that risk.

## R5: Prompt-composition technique (satisfies FR-002/FR-003)

**Decision**: `fantastical_prompt_builder.py` reuses the exact structural pattern already proven in
spec 120's `workspace/skills/comfyui-topology-viz/prompt_builder.py`: a role-count summary (e.g. "2
routers, 2 switches") plus a connectivity-density summary (sparse / typical hierarchical / densely
meshed, based on link-to-device ratio), composed into one bounded-length descriptive string, with a
theme-specific suffix swapped in for spec 120's fixed cyberpunk style suffix.

**Rationale**: This is a solved problem in this exact codebase — spec 120 already had to answer "how
do you describe an arbitrarily-sized real topology as one coherent natural-language prompt without
enumerating every device" (its own research.md documents why summarization beats exhaustive
enumeration for prompt quality). Re-deriving that from scratch would be needless duplication of a
decision already made and validated; porting the technique (not the file) keeps this feature's
scope to what's actually new (the thematic language, not the summarization algorithm).

**Alternatives considered**: Letting an LLM freely improvise the prompt from the raw topology data on
each call — rejected: FR-002/FR-003 require the preview to be deterministic and instant (no external
call, no variable-latency generation step), and an LLM call would also reintroduce a place where raw
device data (potentially including sanitizer-relevant fields) could leak into a third-party-bound
string without the same denylist discipline spec 120's `sanitize_metadata` already enforces.

## R6: Credential isolation — why the skill never sees `WLT_API_KEY`

**Decision**: Only `worldlabs-marble-mcp` reads `WLT_API_KEY`. The skill (`worldlabs-topology-viz`)
never receives, handles, or passes the key — it only calls the MCP server's tools, exactly as it
calls `topology-diagram-mcp`'s tools without ever touching that server's (nonexistent) credentials.

**Rationale**: Direct lesson from this session's own incident — a key was pasted into a chat
transcript. Keeping the credential inside the one process whose job is to make the HTTP call (never
inside the orchestration/skill layer, which is exactly the layer most likely to end up in a
conversational transcript or log) minimizes the blast radius of a future accidental exposure to
exactly the same class of mistake.

**Alternatives considered**: Having the skill build the full HTTP request and hand it to a
generic/shared HTTP-calling tool — rejected: that would mean the key has to pass through the skill
layer (or a shared generic tool with much broader reach) to reach the HTTP client, widening exposure
for no benefit over a dedicated, narrow-purpose MCP server.

## R7: GAIT audit logging is required, not optional (correction from `/speckit.analyze`, finding C1)

**Decision**: Every confirmed `generate_world` attempt (success or failure) MUST produce a
`gait_record_turn` entry — topology snapshot identity/theme, operation id, cost once known, and
outcome. This uses the existing GAIT mechanism already registered in this repo
(`mcp-servers/gait_mcp/`, the same `gait_record_turn`/`gait_branch`/`gait_log` pattern documented in
`workspace/skills/atlassian-itsm/SKILL.md`) — not a new database, not a new file store.

**Rationale**: The spec's original Clarifications session (Q2) chose "no audit logging at all,"
reasoning that World Labs' own billing history was sufficient. Running `/speckit.analyze` against
the finished `spec.md`/`plan.md`/`tasks.md` set surfaced a direct conflict with Constitution
Principle IV ("No operation MAY execute silently — all actions MUST produce an audit record") and
the Forbidden Operations list ("Silent operations without GAIT logging"). Per this repo's own
analysis discipline, a constitution conflict is resolved by adjusting the spec/plan/tasks, never by
diluting or reinterpreting the principle. Using the *existing* GAIT trail (rather than inventing a
new logging mechanism) satisfies the principle without contradicting FR-013's "no new persistent
storage" — the two requirements were never actually in tension; the original Q2 answer just went
further than FR-013 required by ruling out *reusing an existing* mechanism too.

**Alternatives considered**: Keeping "no audit logging at all" and recording the conflict as a
justified constitutional exception in Complexity Tracking — rejected: Principle IV is not marked
NON-NEGOTIABLE in the same explicit way Principles I and XI are, but "MUST" language throughout it
and its presence on the Forbidden Operations list make it binding by the constitution's own
Governance section ("supersedes all other development practices"); there was also no compelling
reason *not* to use the already-existing, zero-new-infrastructure GAIT mechanism, so an exception
would have traded principle compliance for no actual benefit.

## R8: Code-level confirmation guard on `generate_world` (correction from `/speckit.analyze`, finding E1)

**Decision**: `generate_world` takes a required `user_confirmed: bool` argument. A missing or
`false` value is rejected with `failure_category: "confirmation_required"` before any HTTP call to
World Labs is attempted.

**Rationale**: The original design (contracts/worldlabs-marble-mcp.md's first draft) made this tool
a fully unconditional executor, with FR-004/FR-005's confirmation gate enforced *only* by the
orchestrating skill's documented workflow and the calling agent's conversational judgment — the same
pattern Constitution Principle XIV already establishes for Slack/ServiceNow/GitHub actions. Running
`/speckit.analyze` flagged this as a gap specifically because SC-002 claims the guarantee is
"verified by inspection of every code path" — a claim that implies a testable, code-level property,
which did not actually exist. Adding a required, explicitly-named argument closes that gap cheaply:
it does not change who makes the real judgment call (the orchestrating skill still decides when to
set it), but it does make an accidental or careless call fail by construction rather than by
convention, and it is now something `tests/unit/test_worldlabs_marble_mcp.py` can actually assert.

**Alternatives considered**: Leaving SC-002's wording as purely aspirational/convention-based (the
Constitution Principle XIV precedent) — rejected in favor of the cheap code-level guard, since the
cost (one required boolean argument) is far lower than the cost of continuing to claim a stronger
guarantee than the design actually provided.

## R9: Image conditioning disabled by default — per-device/per-edge prompt replaces aggregate summary

**Decision**: `generate_world`'s `image_base64` argument is now optional and defaults to unset;
`fantastical_prompt_builder.build_prompt` no longer summarizes the topology as aggregate role
counts and connectivity density ("2 routers, 2 switches... connected in a typical hierarchical
pattern"). It now emits one clause per device (naming its real hostname and a role-appropriate
shape/tier) and one clause per real link (naming both real endpoint hostnames), composed into
prose Marble is conditioned on as text only.

**Rationale**: Both changes are the direct, verified result of six real production generations run
this session (real credits spent, real outputs inspected — not simulated). Three separate findings
forced this correction:

1. **Image conditioning pastes the input flat, it does not use it as a blueprint.** A generation
   using the reference diagram as `image_base64` produced a result that was, visually inspected,
   the flat 2D diagram unchanged and floating in the middle of the scene, with generic hallucinated
   surroundings on either side bearing no structural relationship to the real topology. A control
   generation with no image input at all (same session) produced one single, fully coherent 3D
   room instead — proving the image is what caused the defect, not the theme or wording.
2. **Aggregate counts give the model nothing to anchor to.** A themed, structurally-worded
   text-only prompt using "2 routers, 2 switches, 4 client endpoints" produced a visually striking,
   fully coherent cyberpunk scene — genuinely fixing the flat-image defect — but with zero
   traceable connection to the real topology; it was, in the user's own words after inspecting it,
   "just another fantasy world." A follow-up generation describing each device individually by its
   real hostname and each real link explicitly by its endpoints, in otherwise identical style
   language, produced a result whose own Marble-generated caption correctly named every one of the
   8 real hostnames and described the exact real hierarchy — proof the model responds to named,
   individual, per-edge description in a way it does not respond to an aggregate summary.
3. **Image-conditioned calls were also measurably less reliable.** Across this session, 4 of 4
   text-only `worlds:generate` calls succeeded on the first attempt; image-bearing calls failed 3
   of 4 times (a schema-validation rejection, a 30-second read timeout, and a bare HTTP 500),
   succeeding only once on a manual retry. This was investigated as a possible DefenseClaw
   interception issue and ruled out with direct evidence: DefenseClaw's fetch-interceptor patches
   Node's own `fetch` inside the gateway process, `worldlabs-marble-mcp` is a separate Python
   process making its own `httpx` calls in a different runtime entirely, no `HTTP_PROXY`/
   `HTTPS_PROXY` variable was present in that process's actual live environment, and DefenseClaw's
   own path/body-shape heuristics do not match this request's path or top-level body keys. The
   likelier explanation is that image-bearing requests exercise a different, currently-flakier code
   path on World Labs' own backend — but regardless of root cause, dropping image conditioning
   removes the correlation entirely, since it was never required for a good result in the first
   place.

**Alternatives considered**: Keeping image conditioning as the default and trying to fix the
flat-paste defect with a different image (e.g. a pre-stylized "concept art" image rendered through
an additional diffusion pass first, mirroring spec 121's two-stage Stage A/Stage B pattern) —
rejected for now as out of scope for this correction: it would add a whole new rendering stage and
dependency for a payoff (image conditioning) that has not demonstrated any advantage over
per-device/per-edge text alone, and carries a proven reliability cost. Worth revisiting only if a
future need specifically requires image-level fidelity that text cannot express.

## R10: Legible text/sigils requested in-scene are unreliable — never ask for them

**Decision**: `fantastical_prompt_builder.build_prompt`'s composed prompt explicitly instructs "no
readable text or writing anywhere in the scene." Real hostnames appear only in the prompt's own
language (which shapes structure and is reflected in Marble's own caption), never as an instruction
to paint words into the rendered pixels.

**Rationale**: A generation that explicitly asked for each device's hostname to be rendered as a
glowing inscribed sigil (e.g. "a monolith inscribed with the sigil 'R1'") did produce a visible
attempt at real alphanumeric text in the output — but garbled ("eth0/1" rendered as something close
to "Fco/1"). This is consistent with a well-known, model-class-wide limitation of current
generative image/video/3D models — exact text rendering is unreliable across nearly all of
them — not something specific to Marble or fixable by rewording the request. Asking for it anyway
produces visual noise (garbled scribbles) for no reliable payoff, so the corrected prompt avoids
requesting it entirely while keeping the same named-entity, per-edge structural approach that
demonstrably does work (R9).

**Alternatives considered**: Continuing to request inscribed sigils since the attempt was partially
recognizable — rejected: "partially recognizable if you already know what it's supposed to say" is
not a usable bar for a real feature, and the garbled text made the affected structures look like a
rendering error rather than a deliberate design choice.
