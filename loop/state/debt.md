# debt

Things deliberately deferred, with reasons. Appended by the maker when a task cannot be
completed as scoped, and by ralph.sh on a stall halt.

## Pre-existing, deferred by /speckit.implement (not the loop) before iteration 0 ever ran

- **Real-lab integration verification of `astra-twin-mcp`'s collector polling path** — quickstart.md's
  Phase A checkpoint ("cross-check against a direct pyATS query") requires a real, running CML
  lab testbed and an installed pyATS MCP server (`~/.openclaw/pyats-venv`), neither of which
  exists in the environment this scaffold was generated in. The collector's reconciliation
  logic (state machine: node/link add/remove/status-change, the "never guess when unreachable"
  rule) is contract-tested directly (`tests/contract/test_astra_twin_mcp.py`) and passes; the
  actual stdio round-trip to a live `pyats_list_devices`/`pyats_run_show_command` call has not
  been exercised end-to-end. This is exactly the human checkpoint quickstart.md's Phase A
  section exists for — not a task for the loop to silently mark done from unit tests alone.
- **`harness/lab_allowlist.yaml` is empty** — by design (see loop/state/memory.md); a human must
  populate it with real lab device hosts/CIDRs before `loop/ralph.sh` can pass preflight at all.

- **C3 frontend bundle compile check (`npm run build`) not executable in this iteration environment** —
  `vite` is missing on PATH (`sh: 1: vite: not found`) despite unit tests and loop gates passing.
  The task implementation was validated by `npm test` and `harness/run_gates.sh`; full Vite bundle
  verification remains deferred until dependencies are installed in the runtime used for loop runs.

- **D1 Astra Twin enrollment into `~/.openclaw/n2n/federation.db` blocked by sandbox write policy** —
  iteration 7 ran the real `RiskManager.issue_token` + `consume_token(..., model_provider='openai')`
  enrollment path, but sqlite failed with `attempt to write a readonly database`. This runner can
  read that DB but cannot modify it. Deferred until run on a host/worktree context where
  `~/.openclaw` is writable.

- **D2 workspace/skills checklist item is not applicable for spec 122** — this feature adds a HUD extension and one MCP server (`astra-twin-mcp`), but no new operator-facing skill surface under `workspace/skills/`. Recorded explicitly per D2 instructions so the checklist item is not silently skipped.

- **D1 remains deferred after iteration 9 due sandbox write boundary on `~/.openclaw`** — this run re-attempted the real enrollment path (`mcp-servers/protocol-mcp/bgp/federation/{manager,risk}.py`) and an independent sqlite write probe; both fail with `sqlite3.OperationalError: attempt to write a readonly database` when targeting `~/.openclaw/n2n/federation.db`. Because the same DB still lacks `member.model_provider`, FR-007/SC-004 evidence remains blocked until D1 is run on a loop worker with writable `~/.openclaw`.

- **D1 still deferred after iteration 10: first write is `RiskManager.set_role('border')`** — reran the real enrollment path and confirmed the flow cannot even reach token issue in this runner: `set_role` updates table `risk` first, which fails on `~/.openclaw/n2n/federation.db` with `sqlite3.OperationalError: attempt to write a readonly database`. D1 cannot complete or produce SC-004 evidence until the loop runs where `~/.openclaw` is writable.

- **D1 still deferred after iteration 11: sandbox remains read-only for `~/.openclaw/n2n/federation.db`** — reconfirmed no `member.model_provider` column via `PRAGMA table_info(member)`, direct sqlite update (`UPDATE risk SET role='border' WHERE id=1`) still fails readonly, and the real `FederationManager`/`RiskManager` enrollment path still fails at first write. Task remains blocked until loop execution in a runner where `~/.openclaw` is writable.
