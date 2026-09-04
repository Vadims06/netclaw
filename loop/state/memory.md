# memory

Durable findings across loop iterations. Append, do not delete past entries (they may matter
again). Read this file before assuming anything about the environment.

## Host quirk: Playwright is on python3.13, not python3

This host's `python3` on PATH is 3.14.4. Playwright (1.55.0, with Chromium already downloaded
under `~/.cache/ms-playwright/`) is installed for `python3.13`'s site-packages
(`~/.local/lib/python3.13/site-packages/playwright/`), not importable from `python3`.
`harness/run_gates.sh` already handles this (`PLAYWRIGHT_PYTHON` env var, auto-detects
`python3.13` if it can import playwright, falls back to `python3`) — don't rediscover this,
don't hardcode `python3` for anything Playwright-related, and don't "fix" `run_gates.sh` to
stop doing the detection.

## harness/visual_verify.py's debug-hook contract (Phase C dependency)

`harness/visual_verify.py` is frozen and expects the HUD page to set
`window.__astraTwinDebug = { nodeCount: <int>, linkCount: <int>, lastError: <string|null> }`
once the twin scene has rendered at least one frame, kept current as deltas apply. This is the
one stable name the frozen harness reads — Phase C's HUD integration task MUST expose exactly
this global, under exactly this name, or the visual-verify gate can never pass once a HUD is
running. Confirmed working end-to-end against a synthetic page during Phase B's self-test
(below) — the mechanics are proven, only the real HUD side (Phase C) is still owed.

## Phase B self-test (T013) — harness proven to catch injected regressions, then reverted

Two independent checks proven on 2026-09-04, no permanent changes left behind:

1. **pytest gate**: temporarily changed a correct assertion in
   `tests/contract/test_twin_schema.py` (`test_link_state_never_asserted_when_both_endpoints_unreachable`)
   to assert the wrong value. `harness/run_gates.sh` correctly failed (exit 1, pytest gate
   reported FAIL). Reverted; suite back to 10/10 passing.
2. **visual_verify.py blank-screenshot check**: pointed it at a synthetic local HTML page
   with `window.__astraTwinDebug` set but a collapsed-height body (effectively blank white
   viewport). It correctly failed with "screenshot is blank (uniform color) despite nonzero
   element counts." Pointed at the same page with a full-viewport gradient background, it
   correctly passed.

Both `run_gates.sh` and `harness/visual_verify.py` are confirmed to actually catch what they
claim to catch — this is the evidence the quickstart.md Phase B human checkpoint (and loop.md's
"prove the gates catch things" requirement after iteration 0) can point to. `visual_verify.py`
skips (does not fail) when no HUD is reachable yet — that's intentional (Phase A/B iterations
have nothing to screenshot), not a gap; it becomes a mandatory failure-capable gate the moment
`ASTRA_TWIN_HUD_URL` (or the default `http://localhost:$HUD_PORT/`) answers.

## pyATS_MCP subprocess details (for whoever builds/touches collector.py's polling path)

- pyATS_MCP is NOT currently installed on this host (`~/.openclaw/pyats-venv` doesn't exist,
  `import pyats` fails on system Python). `collector.py`'s `PYATS_MCP_PYTHON` env var and its
  fallback-to-`~/.openclaw/pyats-venv/bin/python3` default exist for exactly this reason —
  don't assume pyats is importable from whatever interpreter is running astra-twin-mcp itself.
- pyATS_MCP reads its testbed path from `PYATS_TESTBED_PATH`, a *different* name than the
  `PYATS_TESTBED` this loop's own safety envelope uses. `collector.py`'s `_pyats_subprocess_env`
  already translates one to the other at the subprocess boundary — don't rename either side to
  "fix" the mismatch; it's intentional (see contracts/astra-twin-mcp.md).
- Only `pyats_list_devices` and `pyats_run_show_command` are ever called by collector.py.
  `pyats_configure_device` exists on that server and must never be referenced from this
  codebase, even in a test double.

## Lab allowlist is intentionally empty by default

`harness/lab_allowlist.yaml` ships empty and `harness/assert_lab_only.py` fails closed on an
empty allowlist. This is deliberate — none of the existing `testbed/*.yaml` files in this repo
were independently confirmed to be a real, human-controlled CML lab (one points at a shared
external DevNet sandbox host, not a lab under local control). Do not populate the allowlist
with a guess at which existing testbed is "probably fine" — that decision belongs to the human
running the loop, not to a build iteration.

## C1 wiring detail: server.js uses mcp-call.py to reach astra-twin-mcp

`ui/netclaw-visual/server.js` now implements `GET /api/twin/snapshot` via
`scripts/mcp-call.py` and `get_snapshot()` (stdio MCP call), matching the one-shot tool-call
pattern already used for `rag-mcp`. Useful overrides for later Phase C work:
- `ASTRA_TWIN_MCP_SERVER_CMD` to set a full custom server command
- `ASTRA_TWIN_MCP_PYTHON` and `ASTRA_TWIN_MCP_SERVER_PATH` to compose that command from parts

The route returns the MCP payload shape as-is (`structuredContent` preferred, then JSON text
content fallback), so frontend contracts should consume the `TwinSnapshot` schema directly.

## C2 wiring detail: WS /ws/twin polling and overflow behavior

`ui/netclaw-visual/server.js` now hosts a second WebSocket path, `/ws/twin`, separate from the
existing `/ws` graph/rag stream. Implementation details that matter for later Phase C tasks:
- Delta polling is shared across all twin clients (single timer), not per-socket; this avoids
  duplicate `get_deltas` MCP calls when multiple browser tabs are open.
- The server tracks a process-level `twinSinceSeq` and calls `get_deltas({ since_seq })` on a
  fixed interval (`ASTRA_TWIN_WS_POLL_INTERVAL_MS`, default 5000ms, floor 1000ms).
- Each delta is sent as the raw `TwinDelta` object JSON (no envelope), per contract.
- On `{"buffer_overflow": true}`, the server sends a control message
  `{ "type": "twin:resync_required", "reason": "buffer_overflow", "snapshot": "/api/twin/snapshot" }`
  so clients can re-fetch a snapshot and resume from `snapshot.seq`.

## C3 client contract: live twin module wiring and debug global

`ui/netclaw-visual/src/twin/live-twin.js` is now the frontend twin consumer. It is mounted from
`src/main.js` during boot (`createLiveTwinLayer(...); await start();`) and does:
- initial `GET /api/twin/snapshot` reconciliation into a persistent scene group
  (`astra-twin-live` with separate node/link subgroups)
- continuous `/ws/twin` consumption with per-delta incremental mutation only (no full rebuild on
  normal deltas)
- overflow handling via `twin:resync_required` -> re-fetch snapshot
- runtime debug hook maintenance: `window.__astraTwinDebug = { nodeCount, linkCount, lastError }`
  after first load and after every delta/error path

The module stores `lastSeq` locally and ignores stale/replayed deltas (`seq <= lastSeq`) so a
reconnect cannot double-apply old updates.

## Sandbox quirk during maker runs: git write operations can fail on worktree index.lock

In this environment, git commands that write index state (for example `git restore`) can fail with:
`Unable to create .../.git/worktrees/<branch>/index.lock: Permission denied`. File edits and test
commands still work. If this appears again, avoid relying on git-mutating commands inside the
iteration and use normal file edits/gates flow.

## C4 wiring detail: freshness status API + HUD staleness badge

- `ui/netclaw-visual/server.js` now exposes `GET /api/twin/status`, a direct MCP pass-through to
  `get_status()` (`last_successful_poll`, `testbed_identity`, `poll_interval_seconds`,
  `consecutive_failures`).
- `ui/netclaw-visual/src/twin/live-twin.js` polls `/api/twin/status` every 10s and renders a
  fixed badge (`#astra-twin-freshness`) at top-right so freshness is always visible without opening
  any panel.
- Staleness rule is intentionally explicit in the client: stale when
  `now - last_successful_poll > max(45s, poll_interval_seconds*3 + 5)`. Also forced stale on null
  or unparseable timestamps, status endpoint errors, or `consecutive_failures > 0`.

## C5 wiring detail: delta highlighting includes removal events via HUD notice

`ui/netclaw-visual/src/twin/live-twin.js` now has two distinct "recent change" channels:
- existing in-scene flash/pulse (`flashes` map in `tick()`) for node/link add + state-change deltas
- a new fixed overlay `#astra-twin-last-change` that displays `Twin change | ...` for 3 seconds
  on *every* recognized `TwinDelta` kind, including removals (`node_removed`, `link_removed`)

This avoids the removals blind spot where an object disappears with no remaining geometry to pulse.
If this element's id or text contract is changed later, update any visual checks that assert FR-009.

## C6 guardrail: twin updates now hard-preserve camera/view pose

FR-008 is now enforced directly in `ui/netclaw-visual/src/twin/live-twin.js`, not left as an
implicit side effect of incremental rendering. The module captures `{camera.position, camera.zoom,
controls.target}` before both `applyDelta` and `reconcileSnapshot`, then restores it if changed.
This means any future twin code path that accidentally calls camera-framing logic during delta
handling is automatically neutralized.

`createLiveTwinLayer` now accepts `{ camera, controls }` (wired from `src/main.js`). If either is
not passed, the preservation helper safely no-ops and behavior is unchanged.

Regression coverage lives in `ui/netclaw-visual/src/twin/live-twin.test.js` against exported
`captureTwinViewState` / `restoreTwinViewState`, including a mutation-then-restore assertion that
also checks `updateProjectionMatrix()` and `controls.update()` are triggered exactly once on
restore.

## Sandbox quirk: D1 cannot write `~/.openclaw/n2n/federation.db` in this runner

Iteration 7 attempted Phase D task D1 by importing repo-local
`mcp-servers/protocol-mcp/bgp/federation/{manager,risk}.py` and running the real enrollment path
(`issue_token` -> `consume_token(member_id='astra-twin', model_provider='openai', node_type='agent')`)
against `~/.openclaw/n2n/federation.db`. It failed with
`sqlite3.OperationalError: attempt to write a readonly database`.

Important details for next run:
- `bgp/federation/` does not exist at repo root; the canonical path here is
  `mcp-servers/protocol-mcp/bgp/federation/`.
- The migration that adds `member.model_provider` runs when `FederationManager(...)` initializes,
  but that migration also needs DB write permission.
- D1 must be executed on a runner where `~/.openclaw` is writable; otherwise any token issue/enroll
  attempt fails before evidence can be produced for SC-004.
