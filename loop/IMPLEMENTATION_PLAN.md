# IMPLEMENTATION_PLAN — Astra Live Digital Twin build loop

Derived from `specs/122-astra-live-digital-twin/tasks.md` and `plan.md`'s Pass Schedule
(Phase C, then Phase D — Phase A/B are already built and frozen; see `loop.md`). This is the
maker's work queue. The maker updates this file (marking tasks done, adding discovered tasks);
it must never touch `IMPLEMENTATION_PLAN.md`'s ordering rule (Phase C before Phase D) or the
frozen-path list this file references.

Format: one task per `##` heading, in priority order within its phase. A rejected task returns
here with the checker's reason appended under it, sorted above new work in the same phase per
`loop.md`'s Select step.

## Phase C — Live HUD integration

### C1. `GET /api/twin/snapshot` in `ui/netclaw-visual/server.js`

Add a route that calls `astra-twin-mcp`'s `get_snapshot()` tool (spawn it as an MCP client over
stdio, matching how `astra-twin-mcp/collector.py` itself talks to `pyATS_MCP` — same pattern,
one level up) and returns the `TwinSnapshot` JSON unmodified, per
`specs/122-astra-live-digital-twin/contracts/astra-twin-mcp.md`.
Done (iteration 0): `server.js` now exposes `GET /api/twin/snapshot`, calling `get_snapshot()`
through `scripts/mcp-call.py` over stdio and returning the payload shape unchanged.

### C2. `WS /ws/twin` in `ui/netclaw-visual/server.js`

New WebSocket endpoint using the already-present `ws` dependency (research.md R3). On a fixed
interval, calls `astra-twin-mcp`'s `get_deltas(since_seq)` and forwards each new `TwinDelta` as
its own JSON message to every connected client — no envelope/wrapper, exact `TwinDelta` shape
per data-model.md. Handle the `{"buffer_overflow": true}` response by telling connected clients
to re-fetch `/api/twin/snapshot` (see contracts/astra-twin-mcp.md's reconnect contract).
Done (iteration 1): `server.js` now exposes `WS /ws/twin` with shared polling against
`get_deltas(since_seq)` and broadcasts each delta as a raw `TwinDelta` JSON message (no
wrapper). On `{"buffer_overflow": true}`, it sends a `twin:resync_required` control message
pointing clients at `/api/twin/snapshot`.

### C3. Delta-application scene layer (`ui/netclaw-visual/src/twin/`)

New module that: (a) on load, fetches `/api/twin/snapshot`, renders it using the existing
Three.js node/link primitives from specs 101/102 (reuse, do not fork); (b) opens `/ws/twin` and
applies each incoming delta incrementally — add/remove/update the specific node or link, never a
full scene rebuild (FR-002, SC-001's 30-second-visible requirement depends on this being cheap).
Sets and keeps current `window.__astraTwinDebug = { nodeCount, linkCount, lastError }` once the
first frame has rendered — this is `harness/visual_verify.py`'s frozen contract (see
`loop/state/memory.md`); the gate cannot pass without this exact global.
Done (iteration 4): added `src/twin/live-twin.js` and wired it in `src/main.js`. On boot it
fetches `/api/twin/snapshot`, renders twin nodes/links into a persistent scene group, then
subscribes to `/ws/twin` and applies `TwinDelta` messages incrementally by kind
(`node_added/node_removed/node_status_changed/link_added/link_removed/link_state_changed`)
without scene rebuild. Overflow control (`twin:resync_required`) re-fetches snapshot. The module
maintains `window.__astraTwinDebug = { nodeCount, linkCount, lastError }` and keeps counts
current as deltas apply.

### C4. Freshness indicator (FR-010)

Poll `astra-twin-mcp`'s `get_status()` (via a small server.js route, e.g.
`GET /api/twin/status`) and render a visible staleness indicator in the HUD once
`last_successful_poll` falls outside a reasonable window. Must go visibly stale, not silently
keep showing last-known state as current.
Done (iteration 4): `server.js` now exposes `GET /api/twin/status` via `get_status()`, and
`src/twin/live-twin.js` now polls that endpoint every 10s and renders a fixed HUD badge
(`Twin data LIVE|STALE`) that computes staleness from `last_successful_poll` against a dynamic
threshold (`max(45s, poll_interval_seconds*3+5)`). Null/invalid timestamps, status-fetch
failures, and nonzero `consecutive_failures` all force a visible STALE state.

### C5. Delta highlighting (FR-009)

When a delta lands, visually distinguish the affected node/link from stable state for a short
window (e.g., a brief highlight/pulse) so an operator can tell "just changed" from "steady."
Done (iteration 5): `src/twin/live-twin.js` now surfaces every incoming `TwinDelta` as a
transient fixed HUD notice (`#astra-twin-last-change`, 3s visibility) with explicit change text
for all delta kinds, including removals (`node_removed`, `link_removed`). Existing geometry-level
flash behavior remains for node/link add or state-change deltas, so both in-scene emphasis and
operator-visible textual "just changed" context are present.

### C6. Camera-state preservation (FR-008)

Confirm — and if needed, wire — that applying a delta never resets camera position/orientation
or any manual zoom/grouping already established by specs 101/102's camera-pose persistence.
This should mostly fall out of C3 doing incremental updates rather than scene rebuilds; treat
any camera reset on delta application as a bug to fix, not an acceptable side effect.
Done (iteration 6): `src/twin/live-twin.js` now enforces camera/target preservation around both
delta application and snapshot reconciliation (`withPreservedView`), using explicit
capture/restore helpers that reset camera position/zoom + controls target if any twin update path
mutates them. `src/main.js` now passes the live chart `camera` and `controls` into the twin layer.
Added `src/twin/live-twin.test.js` coverage for capture/restore behavior, including mutation-then-
restore with projection/control update callbacks invoked once.

### C7. `harness/run_gates.sh`'s visual_verify step becomes mandatory

Once C1-C3 exist and the HUD is reachable at `$ASTRA_TWIN_HUD_URL` (or the default
`http://localhost:$HUD_PORT/`), `run_gates.sh`'s current SKIP for `visual_verify.py` (see its
own comment) starts actually running and must pass — this is not a separate task, just a note
that C1-C3 change the shape of every gate run after them.

## Phase D — Astra Twin enrollment & constitution coherence

*Depends on Phase C being done and gated green — do not start Phase D early just because a task
looks easier; the pass schedule order in plan.md is deliberate (a human checkpoint sits between
these phases).*

### D1. Enroll Astra Twin as a real iN2N member (REDIRECTED — read this before touching D1 again)

Iterations 7, 9, 10, 11, 12 all correctly diagnosed the same root cause and correctly stopped
short of forcing a write — this was not a bug in enrollment logic and does not need re-diagnosing
again: `~/.openclaw/n2n/federation.db` is the **real, live, shared iN2N mesh database** that the
actual running mesh reads and acts on. codex's own sandbox (`--sandbox workspace-write`, writable
roots: the worktree, `/tmp`, `$TMPDIR`, `$CODEX_HOME/memories`) correctly refuses to write outside
those roots, and `~/.openclaw/` is outside all of them. That refusal is doing its job — an
unattended loop enrolling a permanent row into the production mesh database is exactly the kind
of live-system side effect this loop should never cause, sandbox or no sandbox.

**Corrected task**: enroll Astra Twin against a worktree-local *test* federation database
instead, not the live one. `FederationManager.__init__` already accepts an explicit `db_path`
(`mcp-servers/protocol-mcp/bgp/federation/manager.py`) — construct it with
`db_path="loop/state/astra-twin-test-federation.db"` (relative to the worktree root, so it's
inside the sandbox's writable root), let it create/migrate that file fresh, then run the same
`RiskManager.set_role('border')` → `issue_token` → `consume_token(model_provider="openai")` flow
against *that* file. Confirm the resulting row has `model_provider='openai'` there. This is what
now stands in for `spec.md`'s SC-004 and `quickstart.md`'s Phase D checkpoint in this loop-run
context — evidence lives at `loop/state/astra-twin-test-federation.db`, not
`~/.openclaw/n2n/federation.db`. Note this substitution explicitly in `verdicts.md` (the checker
should record that SC-004 was evidenced against a test-scoped DB, not the production one, and why
— see this task's own reasoning above) so a human reviewing the loop's output later understands
real enrollment into the live mesh is a separate, deliberate, human-run step, not something this
loop did or was ever meant to do unattended.

### D2. Full Artifact Coherence Checklist (constitution.md Principle XI)

For `astra-twin-mcp` and the HUD's twin routes, walk every item and make it real, not a
box-check:
- `README.md` — capability description, architecture note, updated tool/MCP-server count
- `scripts/lib/catalog.sh` — one catalog entry for `astra-twin-mcp`
- `scripts/lib/install-steps.sh` — one `component_install_astra_twin_mcp()` function
- `scripts/verify-catalog-coverage.py` — run it; it must pass with zero unexplained gaps
- `ui/netclaw-visual/` — already touched in Phase C; confirm it counts as "HUD nodes for new
  integrations" per the checklist, don't add a second redundant panel
- `SOUL.md` — skill/capability summary entry, including that Astra Twin is a distinct,
  OpenAI-backed mesh identity (spec.md User Story 3 — this must not be buried)
- `workspace/skills/` — only if this feature adds an operator-facing skill surface; if it
  doesn't (the twin is a HUD extension, not a new skill), record that explicitly in `debt.md`
  as "not applicable" rather than silently skipping the checklist item
- `.env.example` — `OPENAI_API_KEY` (description only, already confirmed present but
  undocumented in `.env.example` — see `research.md`), plus any new `astra-twin-mcp`/HUD
  variables from Phase C (`ASTRA_TWIN_POLL_INTERVAL_SECONDS`, `ASTRA_TWIN_HUD_URL`, etc.)
- `TOOLS.md` — infrastructure reference entry
- `config/openclaw.json` — register `astra-twin-mcp` as an MCP server entry
Done (iteration 8): added `astra-twin` catalog component to `scripts/lib/catalog.sh`,
added `component_install_astra_twin()` and `PYATS_TESTBED` environment export in
`scripts/lib/install-steps.sh`, registered `astra-twin-mcp` in `config/openclaw.json`,
updated `.env.example` with Astra Twin/OpenAI env vars, updated README/SOUL MCP counts
and Astra Twin capability text, and added Astra Twin entries in `TOOLS.md`.
`python3 scripts/verify-catalog-coverage.py` now passes with zero vendored-state gaps.

### D3. `harness/done_gate.sh` passes

Once D1/D2 are done and the checker has written evidence for every FR-001..FR-011/SC-001..SC-006
in `loop/state/verdicts.md`, `harness/done_gate.sh` should pass — this is the loop's own exit
condition, not a task to "do" separately from D1/D2 actually being complete and evidenced.
