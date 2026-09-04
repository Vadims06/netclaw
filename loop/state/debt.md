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
