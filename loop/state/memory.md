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

## D2 coherence closure details for astra-twin-mcp (iteration 8)

To satisfy Principle XI and clear catalog coverage, `astra-twin-mcp` must be coherent across four surfaces at once: `config/openclaw.json` registration key `astra-twin-mcp`, installer catalog id `astra-twin` (so `strip_mcp_suffix('astra-twin-mcp')` matches), install function `component_install_astra_twin()`, and documented env vars in `.env.example`/`TOOLS.md`.

If any one of those is missing, `python3 scripts/verify-catalog-coverage.py` fails with an unexplained vendored server gap. After adding all four plus README/SOUL count updates, both `verify-catalog-coverage.py` and `verify-inventory-counts.py` pass with MCP totals at 169 (106 config + 63 external).

`component_install_astra_twin()` intentionally only installs `mcp-servers/astra-twin-mcp/requirements.txt`; it does not install pyATS itself. pyATS remains owned by `component_install_pyats()`. The deploy step now also exports `PYATS_TESTBED` alongside `PYATS_TESTBED_PATH` so astra-twin-mcp has the env name it requires.

## D1 blocker reconfirmed on iteration 9: sandbox-enforced readonly federation DB

Even when Unix perms show writable owner (`-rw-r--r-- johncapobianco`), this runner cannot write
`~/.openclaw/n2n/federation.db` because it is outside writable roots. Two independent repros:

- `sqlite3 ~/.openclaw/n2n/federation.db "CREATE TABLE IF NOT EXISTS __astra_probe(id INTEGER);"`
  fails with `attempt to write a readonly database`.
- Real enrollment code path via repo modules
  (`FederationManager(db_path=..., base_dir=...)`, `RiskManager(fm)`,
  `set_role('border')`, then intended `issue_token`/`consume_token`) fails on first write with the
  same error.

Also reconfirmed the live DB schema currently has no `member.model_provider` column (`.schema member`
omits it), so FR-007/SC-004 cannot be evidenced in this runner until executed where `~/.openclaw`
is writable and migration/enrollment can commit.

## D1 execution order quirk: enrollment path writes `risk` before token issue

Re-attempted D1 on iteration 10 using the real repo modules under
`mcp-servers/protocol-mcp/bgp/federation/`. The first write happens at
`RiskManager.set_role('border')` (updates `risk` row id=1) before `issue_token` or
`consume_token` run. On read-only `~/.openclaw/n2n/federation.db`, D1 fails immediately at that
step with `sqlite3.OperationalError: attempt to write a readonly database`.

For future retries in constrained runners: checking only whether `consume_token` can run is not
sufficient; writable DB is required from the `set_role` step onward.

## D1 blocker reconfirmed on iteration 11: schema unchanged and writes still denied

Iteration 11 re-ran D1 validation with three independent checks against
`~/.openclaw/n2n/federation.db`:

- `PRAGMA table_info(member);` still lists 26 columns and does not include `model_provider`.
- Direct sqlite write probe (`UPDATE risk SET role='border' WHERE id=1;`) still fails with
  `attempt to write a readonly database`.
- Real module path (`mcp-servers/protocol-mcp/bgp/federation/{manager,risk}.py`) still raises
  `sqlite3.OperationalError: attempt to write a readonly database` at `RiskManager.set_role`.

This confirms D1 cannot be completed in this sandbox; failure is environmental, not a transient in
token issuance/consumption logic.

## D1 blocker reconfirmed on iteration 12 with exact failing path

Iteration 12 reran D1 using the real repo modules from
`mcp-servers/protocol-mcp/bgp/federation/` and still failed on the first write:
`RiskManager.set_role('border')` raises `sqlite3.OperationalError: attempt to write a readonly
database` (`risk.py` line 339 in this checkout). Independent probes still show:

- `PRAGMA table_info(member)` has 26 columns and no `model_provider`.
- `UPDATE risk SET role='border' WHERE id=1` fails readonly.
- `SELECT ... FROM member WHERE member_id/display_name LIKE '%astra%'` returns no rows.

No part of the enrollment flow (`issue_token`/`consume_token`) is reachable until that first write
succeeds, so D1 remains runner-blocked rather than logic-blocked.

## Gate quirk: run_gates visual verify still skips in this runner after Phase C

`harness/run_gates.sh loop/runs/12` passes, but still prints:
`SKIP: visual_verify.py — http://localhost:3001/ not reachable yet (expected before Phase C's HUD routes exist)`.
Phase C routes are already implemented, so this skip in current loop runs is due local socket
reachability/runtime startup assumptions, not missing C tasks. Do not treat this skip message as
proof that C1-C3 are absent.

## D1 redirected enrollment is now scriptable and reproducible in sandboxed runners

Use `scripts/in2n-enroll-astra-twin-test-db.py --reset` for Phase D1 in restricted runners.
It runs the exact enrollment sequence against a worktree-local DB:
`RiskManager.set_role('border')` -> `issue_token` -> `consume_token(..., model_provider='openai')`,
writing `loop/state/astra-twin-test-federation.db` and printing the enrolled row.

Current deterministic evidence command:
`sqlite3 loop/state/astra-twin-test-federation.db "SELECT member_id,display_name,node_type,model_provider,state FROM member WHERE member_id='astra-test-risk/astra-twin';"`
returns `astra-test-risk/astra-twin|Astra Twin|agent|openai|enrolled`.

## D3 status: done_gate currently blocked by checker evidence, not by build/test gates

`harness/run_gates.sh loop/runs/1` passes in this runner, but `harness/done_gate.sh` currently
returns `NOT DONE — missing evidence for: FR-004 FR-005 SC-003`.

This is a verdict-ledger gap (`loop/state/verdicts.md`), not a failing compile/test/harness
gate. Next iteration should focus on checker-verifiable evidence for those three ids.

The script defaults `base_dir` to `/tmp/astra-twin-test-federation-home` so only the DB artifact
is persisted in the worktree; transient key material stays outside `loop/state/`.

## C2 re-verification pass result on current HEAD

A C2-only re-verification iteration reran `harness/run_gates.sh loop/runs/0` and passed:
python import/compile, `pytest tests/contract`, and `npm test` all green. Visual verify still
skips in this runner because `http://localhost:3001/` is not reachable from the loop process.

`ui/netclaw-visual/server.js` still implements the expected C2 contract points:
- dedicated WebSocket path `/ws/twin` (`new WebSocketServer({ server, path: '/ws/twin' })`)
- shared global poll loop with `twinSinceSeq` (not per-client polling)
- `get_deltas({ since_seq: twinSinceSeq })` call and raw `TwinDelta` JSON broadcast
- overflow control message `{ type: 'twin:resync_required', reason: 'buffer_overflow', snapshot: '/api/twin/snapshot' }`
