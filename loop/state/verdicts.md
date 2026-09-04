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
