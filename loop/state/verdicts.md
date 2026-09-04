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
