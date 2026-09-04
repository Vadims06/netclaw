# verdicts

Criterion -> evidence ledger. **Checker-written only** — the maker (loop/PROMPT.md) is
explicitly forbidden from writing here (loop/CHECK.md). harness/done_gate.sh parses this file
for FR-/SC- ids from specs/122-astra-live-digital-twin/spec.md; do not change that heading
format without updating done_gate.sh's parser.

## Iteration 0 — C1. GET /api/twin/snapshot in ui/netclaw-visual/server.js
Verdict: ACCEPT
Criteria evidenced:
  - FR-001: [ui/netclaw-visual/server.js] now defines `GET /api/twin/snapshot` and returns the `get_snapshot` payload via `res.json(snapshot)` (no server-side remapping of TwinSnapshot fields).
  - FR-003: `loop/runs/0/diff.patch` adds only read-path wiring (`get_snapshot` MCP call); grep of the patch shows no write-capable network tool calls or config verbs.
  - SC-002: Endpoint pass-through keeps `testbed_identity` in the returned object shape because the route returns the MCP payload object unchanged.
Criteria claimed but not evidenced:
  - none
Concerns: Local sandbox forbids opening localhost sockets (`curl: (7) failed to open socket: Operation not permitted`), so live HTTP execution of the new route could not be replayed here; verdict is based on direct code-path inspection and patch-scope validation.

## Iteration 1 — C2. WS /ws/twin in ui/netclaw-visual/server.js
Verdict: REJECT
Criteria evidenced:
  - FR-002: [ui/netclaw-visual/server.js] adds a dedicated `WebSocketServer` on `/ws/twin`, starts a polling loop, and forwards each returned delta object to connected clients.
  - FR-003: `loop/runs/1/diff.patch` adds only `callAstraTwinTool('get_deltas', ...)` read-path usage in this task scope; no write-capable device/config tool invocation was introduced in the patch.
Criteria claimed but not evidenced:
  - FR-002 / SC-001: Not independently verified at runtime in this checker pass (no direct observed evidence here that live deltas reach the HUD within the bounded window).
Concerns: Immediate policy violation: `loop/runs/1/diff.patch` modifies frozen path `loop/state/iterations.md`, which is explicitly disallowed for maker changes by checker rules (automatic reject).

## Iteration 2 — task.txt missing (no claimed task)
Verdict: REJECT
Criteria evidenced:
  - FR-003: `loop/runs/2/diff.patch` only appends one line in `loop/state/iterations.md`; inspection shows no device/config write-capable tool call introduced in this iteration patch.
Criteria claimed but not evidenced:
  - FR-001..FR-011 / SC-001..SC-006: `loop/runs/2/task.txt` is absent, so there is no claim to validate and no criterion-level implementation evidence to grade.
Concerns: Immediate policy violation: `loop/runs/2/diff.patch` modifies frozen path `loop/state/iterations.md` (checker rule: everything under `loop/` is frozen except `IMPLEMENTATION_PLAN.md`, `state/memory.md`, and `state/debt.md`), which requires rejection regardless of gate results.

## Iteration 3 — C3. Delta-application scene layer (ui/netclaw-visual/src/twin/)
Verdict: REJECT
Criteria evidenced:
  - FR-002: `ui/netclaw-visual/src/main.js` wires a live twin layer into boot (`createLiveTwinLayer(...); await start();`) and ticks it during animation (`state.liveTwin?.tick?.()`), which is the entry point for incremental update behavior.
  - FR-009: `ui/netclaw-visual/src/twin/live-twin.js` contains explicit change-highlighting behavior (`markChanged`, timed pulse/opacity in `tick`) for node/link deltas, indicating an attempt to visually distinguish recent changes.
Criteria claimed but not evidenced:
  - FR-002 / SC-001: Not independently verified at runtime in this checker pass; no direct observed evidence here that a real lab change appears in-scene within 30 seconds without reload.
  - FR-008: No independent verification that camera/view state is preserved across live updates.
Concerns: Immediate policy violation: `loop/runs/3/diff.patch` modifies frozen path `loop/state/iterations.md`, which is outside the allowed maker-write exceptions under `loop/`; additionally, `loop/runs/3/task.txt` is missing, so the claimed scope is not fully auditable from primary artifacts.

## Iteration 4 — C4. Freshness indicator (FR-010)
Verdict: REJECT
Criteria evidenced:
  - FR-010: [ui/netclaw-visual/server.js] adds `GET /api/twin/status` calling `callAstraTwinTool('get_status', {}, 60)` and returning JSON status directly; [ui/netclaw-visual/src/twin/live-twin.js] polls that endpoint every 10s and renders a fixed `#astra-twin-freshness` badge with explicit `LIVE`/`STALE` text.
  - FR-010: Independent runtime probe executed from `ui/netclaw-visual` via `node --input-type=module` with mocked `fetch` responses showed operator-visible staleness transitions at source: `fresh: Twin data LIVE | 0s ago (threshold 45s)`, `waiting: Twin data STALE | waiting for first successful poll (stale threshold 45s)`, `failure_count: Twin data STALE | 0s ago (threshold 45s), 2 failed poll(s)`, `fetch_error: Twin data STALE | status unavailable (boom)`.
  - SC-005: The badge is fixed-position (`position:fixed;top:10px;right:10px`) and continuously visible, so current-vs-stale state is immediately legible without opening panels.
  - FR-003: `loop/runs/4/diff.patch` introduces no network configuration-write tool invocations; additions are limited to `get_status` read path plus UI rendering logic.
Criteria claimed but not evidenced:
  - SC-005: Not independently timed with a real operator or full browser session in this environment; evidence is code-path + runtime harness output.
Concerns: Immediate policy violation: `loop/runs/4/diff.patch` modifies frozen paths `loop/runs/4/task.txt` and `loop/state/iterations.md` (checker rule says everything under `loop/` is frozen except `IMPLEMENTATION_PLAN.md`, `loop/state/memory.md`, and `loop/state/debt.md`), requiring rejection regardless of functional correctness.

## Iteration 5 — C5. Delta highlighting (FR-009)
Verdict: REJECT
Criteria evidenced:
  - FR-009: [ui/netclaw-visual/src/twin/live-twin.js] adds a dedicated `#astra-twin-last-change` overlay and routes every recognized `TwinDelta.kind` through `showChange(delta)` after `applyDelta`, including removals. Independent runtime probe executed from `ui/netclaw-visual` (`node --input-type=module`) with a mocked WebSocket drove all six delta kinds and produced visible HUD text per event: `node_added: Twin change | Node added: R1`, `node_removed: Twin change | Node removed: R1`, `link_added: Twin change | Link added: r1-r2`, `link_removed: Twin change | Link removed: r1-r2`, `node_status_changed: Twin change | Node status: R2 -> down`, `link_state_changed: Twin change | Link state: l1 -> down`; overlay auto-faded to `opacity=0` after ~3.2s.
  - FR-003: `loop/runs/5/diff.patch` introduces no write-capable network tool usage; changes are UI-only plus loop state/documentation files.
Criteria claimed but not evidenced:
  - none
Concerns: Immediate policy violation: `loop/runs/5/diff.patch` modifies frozen path `loop/state/iterations.md` (driver-owned under `loop/`; only `loop/IMPLEMENTATION_PLAN.md`, `loop/state/memory.md`, and `loop/state/debt.md` are maker-writable), so this iteration must be rejected regardless of functional FR-009 behavior.

## Iteration 6 — C6. Camera-state preservation (FR-008)
Verdict: REJECT
Criteria evidenced:
  - FR-008: [ui/netclaw-visual/src/main.js] now passes `camera` and `controls` into `createLiveTwinLayer(...)`; [ui/netclaw-visual/src/twin/live-twin.js] wraps both `applyDelta` and `reconcileSnapshot` in `withPreservedView(...)`, which captures and restores camera position/zoom plus controls target around every live twin update path.
  - FR-008: Independent runtime probe executed from `ui/netclaw-visual` via `node --input-type=module` with mocked `fetch` + `WebSocket` and a deliberately camera-mutating `makeLabel` (to simulate accidental view mutation inside update paths) produced `snapshot_preserved true` and `delta_preserved true` after `start()` (snapshot reconcile) and a pushed `node_added` delta, confirming pose preservation across both update classes.
Criteria claimed but not evidenced:
  - none
Concerns: Immediate policy violation: `loop/runs/6/diff.patch` modifies frozen path `loop/state/iterations.md` (outside the allowed `loop/` exceptions), requiring rejection per checker rules regardless of FR-008 behavior.

## Iteration 7 — D1. Enroll Astra Twin as a real iN2N member
Verdict: REJECT
Criteria evidenced:
  - FR-006: Independent DB check on `~/.openclaw/n2n/federation.db` shows no enrolled `astra-twin` member row (`SELECT member_id,node_type,state,updated_at FROM member WHERE member_id='astra-twin';` returned zero rows).
  - FR-007: Independent DB schema check shows the required `model_provider` attribute is not present on `member` in this environment (`.schema member` contains no `model_provider`; direct `SELECT ... model_provider ...` fails with `no such column: model_provider`).
Criteria claimed but not evidenced:
  - SC-004: No primary evidence demonstrates Astra Twin is discoverable as a distinct mesh member with provider attribution; `loop/runs/7/diff.patch` contains only documentation/debt notes and no successful enrollment artifact.
Concerns: Immediate policy violation: `loop/runs/7/diff.patch` modifies frozen path `loop/state/iterations.md` (driver-owned under `loop/`; not in allowed maker-write exceptions), which is an automatic reject independent of functional status.

## Iteration 8 — D2. Full Artifact Coherence Checklist (constitution.md Principle XI)
Verdict: REJECT
Criteria evidenced:
  - FR-003: `loop/runs/8/diff.patch` adds Astra Twin wiring/docs (`config/openclaw.json`, installer/catalog/docs) and introduces no new write-capable network action in patch scope; grep found no added `pyats_configure_device`/config-push call patterns.
Criteria claimed but not evidenced:
  - FR-006 / FR-007 / SC-004: No mesh enrollment/member-record change or lookup evidence is present in this iteration; provider-attributed Astra Twin membership is not independently evidenced here.
  - FR-011 / SC-006: Runtime AI-independence is described in docs, but this iteration provides no independent runtime verification evidence.
Concerns: Immediate policy violation: `loop/runs/8/diff.patch` modifies frozen path `loop/state/iterations.md` (driver-owned under `loop/`; only `loop/IMPLEMENTATION_PLAN.md`, `loop/state/memory.md`, and `loop/state/debt.md` are maker-writable). Additional checker note: `specs/122-astra-live-digital-twin/contracts/data-model.md` referenced by checker instructions is absent in this worktree, limiting contract-level shape validation to `contracts/astra-twin-mcp.md`.

## Iteration 9 — D1. Enroll Astra Twin as a real iN2N member
Verdict: REJECT
Criteria evidenced:
  - FR-006: `loop/runs/9/diff.patch` contains only documentation/state updates (`loop/IMPLEMENTATION_PLAN.md`, `loop/state/debt.md`, `loop/state/iterations.md`, `loop/state/memory.md`) and no enrollment artifact; independent DB query on `~/.openclaw/n2n/federation.db` (`SELECT member_id,node_type,state,updated_at FROM member WHERE member_id='astra-twin';`) returned no row.
  - FR-007: Independent schema inspection on `~/.openclaw/n2n/federation.db` (`PRAGMA table_info(member);` and `.schema member`) shows no `model_provider` column, so provider attribution for Astra Twin is not representable/evidenced in this iteration.
Criteria claimed but not evidenced:
  - SC-004: No primary evidence shows Astra Twin as a distinct, correctly AI-provider-attributed member in admin lookups.
Concerns: Immediate policy violation: `loop/runs/9/diff.patch` modifies frozen path `loop/state/iterations.md` (outside allowed `loop/` exceptions), and this is out of task scope for D1 implementation.

## Iteration 10 — D1. Enroll Astra Twin as a real iN2N member
Verdict: REJECT
Criteria evidenced:
  - FR-006: Independent member lookup on `~/.openclaw/n2n/federation.db` found no Astra Twin enrollment record (`SELECT member_id,display_name,node_type,state FROM member WHERE lower(member_id) LIKE '%astra%' OR lower(display_name) LIKE '%astra%';` returned zero rows).
  - FR-007: Independent schema check confirms `member.model_provider` still does not exist (`PRAGMA table_info(member);` lists 26 columns and none named `model_provider`), so OpenAI provider attribution cannot be stored or shown.
  - SC-004: Independent reproduction of the enrollment write path fails before token issuance: `sqlite3 ~/.openclaw/n2n/federation.db "update risk set role='border' where id=1;"` returns `attempt to write a readonly database`; direct module-path reproduction (`RiskManager.set_role('border')`) returns `OperationalError attempt to write a readonly database`.
Criteria claimed but not evidenced:
  - none
Concerns: `loop/runs/10/diff.patch` only updates loop planning/debt/memory notes and does not implement or land any enrollment/migration artifact, so the claimed D1 outcome is not completed.

## Iteration 11 — D1. Enroll Astra Twin as a real iN2N member
Verdict: REJECT
Criteria evidenced:
  - FR-006: Independent lookup found no Astra Twin member row (`sqlite3 ~/.openclaw/n2n/federation.db "SELECT member_id, display_name FROM member WHERE lower(display_name) LIKE '%astra twin%' OR lower(member_id) LIKE '%astra%';"` returned no rows).
  - FR-007: Independent schema check shows `model_provider` still absent (`sqlite3 ~/.openclaw/n2n/federation.db "PRAGMA table_info(member);"` lists 26 columns; `SELECT ... model_provider ...` fails with `no such column: model_provider`).
  - SC-004: Independent write-path probe still fails at first mutation (`sqlite3 ~/.openclaw/n2n/federation.db "UPDATE risk SET role='border' WHERE id=1;"` => `attempt to write a readonly database`), so enrollment/provider-attribution cannot be completed in this run.
Criteria claimed but not evidenced:
  - SC-004: No evidence that Astra Twin is discoverable as a distinct, correctly provider-attributed mesh member in any admin lookup.
Concerns: Immediate policy violation: `loop/runs/11/diff.patch` modifies frozen path `loop/state/iterations.md`; for this checker workflow that is an automatic reject independent of gates.

## Iteration 12 — D1. Enroll Astra Twin as a real iN2N member
Verdict: REJECT
Criteria evidenced:
  - FR-006: Independent member lookup on `~/.openclaw/n2n/federation.db` found no Astra Twin enrollment row (`SELECT member_id,display_name,node_type,state FROM member WHERE member_id='astra-twin' OR member_id LIKE '%/astra-twin%' OR lower(display_name) LIKE '%astra twin%';` returned zero rows).
  - FR-007: Independent schema inspection shows provider attribution is not representable in the live DB here (`PRAGMA table_info(member);` lists 26 columns and no `model_provider`; selecting that column errors with `no such column: model_provider`).
  - SC-004: Independent write-path checks fail before enrollment/token flow can run: direct SQL `UPDATE risk SET role='border' WHERE id=1` returns `attempt to write a readonly database`, and real module-path execution (`FederationManager` + `RiskManager.set_role('border')`) raises `sqlite3.OperationalError: attempt to write a readonly database` at `mcp-servers/protocol-mcp/bgp/federation/risk.py:339`.
Criteria claimed but not evidenced:
  - FR-006 / FR-007 / SC-004: The iteration does not produce a successful, queryable Astra Twin member record with correct provider attribution.
Concerns: Immediate policy violation: `loop/runs/12/diff.patch` modifies frozen path `loop/state/iterations.md` (outside allowed maker-write exceptions under `loop/`), which is an automatic reject regardless of gate pass output.

## Iteration 0 — C1. GET /api/twin/snapshot in ui/netclaw-visual/server.js
Verdict: REJECT
Criteria evidenced:
  - FR-003: `loop/runs/0/diff.patch` (current artifact) introduces no new write-capable device/config tool invocations; inspected patch content shows loop-plan/state edits only.
Criteria claimed but not evidenced:
  - FR-001: The run-0 primary artifact does not evidence the claimed C1 route implementation; `loop/runs/0/diff.patch` currently shows edits to loop artifacts rather than the `ui/netclaw-visual/server.js` change it claims.
  - SC-001: Not independently verifiable in this environment for run 0; localhost socket access is denied by sandbox (`curl: (7) failed to open socket: Operation not permitted`), so live endpoint behavior cannot be replayed here.
Concerns: Immediate checker-policy violation: the run artifact itself modifies frozen path `loop/runs/0/diff.patch` (everything under `loop/` is frozen except `IMPLEMENTATION_PLAN.md`, `loop/state/memory.md`, `loop/state/debt.md`), which is an automatic reject.
