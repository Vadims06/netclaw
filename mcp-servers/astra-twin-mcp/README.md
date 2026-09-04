# astra-twin-mcp

Read-only collector for the Astra Live Digital Twin (spec [122-astra-live-digital-twin](../../specs/122-astra-live-digital-twin/)).

Continuously polls the *existing* [pyATS MCP server](../pyATS_MCP/) — never a device directly —
and maintains an in-memory current-state snapshot plus a bounded ring buffer of deltas, which
[`ui/netclaw-visual/server.js`](../../ui/netclaw-visual/) streams to the browser HUD.

## Privilege level

**Read-only. Holds no device credential, session, or write-capable MCP tool call anywhere in
this codebase — not merely unused, but absent.** It only ever calls two tools on the pyATS MCP
server: `pyats_list_devices` and `pyats_run_show_command` with fixed observation commands
(`show cdp neighbors detail`, `show interfaces description`). It never calls
`pyats_configure_device`, `pyats_run_linux_command`, or `pyats_run_dynamic_test`.

It also independently enforces [`harness/assert_lab_only.py`](../../harness/assert_lab_only.py)
at its own startup, refusing to serve at all against a testbed that isn't on the lab allowlist
— this holds even when the server is run outside the build loop entirely.

## Tools

| Tool | Description |
|---|---|
| `get_snapshot()` | Full current twin state: nodes, links, sequence number, testbed identity. |
| `get_deltas(since_seq: int)` | Deltas observed since `since_seq`. Returns `{"buffer_overflow": true}` if `since_seq` has fallen out of the retained window — caller must re-fetch `get_snapshot()`. |
| `get_status()` | Collector health: `last_successful_poll`, `testbed_identity`, `poll_interval_seconds`, `consecutive_failures`. Backs the HUD's freshness indicator (FR-010). |

Full contract: [`specs/122-astra-live-digital-twin/contracts/astra-twin-mcp.md`](../../specs/122-astra-live-digital-twin/contracts/astra-twin-mcp.md).

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `PYATS_TESTBED` | Yes | Path to the pyATS testbed YAML. Must resolve entirely within `harness/lab_allowlist.yaml` or the server refuses to start. |
| `PYATS_MCP_PYTHON` | No | Interpreter used to launch the pyATS MCP subprocess. Defaults to `~/.openclaw/pyats-venv/bin/python3` if present, else the interpreter running `astra-twin-mcp` itself. pyATS needs its own venv on hosts where system Python is newer than 3.13. |
| `PYATS_MCP_SERVER_PATH` | No | Path to `pyats_mcp_server.py`. Defaults to the sibling `../pyATS_MCP/pyats_mcp_server.py`. |
| `ASTRA_TWIN_POLL_INTERVAL_SECONDS` | No | Poll interval in seconds. Default `10`. |
| `LAB_ALLOWLIST` | No | Override path for `harness/assert_lab_only.py`'s allowlist file. Defaults to `harness/lab_allowlist.yaml`. |

## Transport

stdio (FastMCP), matching every other NetClaw MCP server.

## Installation

```bash
pip install -r requirements.txt
```

pyATS itself is *not* a dependency of this server — it is a dependency of the pyATS MCP server
this one subprocesses. See `scripts/lib/install-steps.sh`'s `component_install_pyats` for that
server's own (venv-based) install path.

## Why this exists instead of astra-twin-mcp talking to devices directly

Constitution Principle VI (Multi-Vendor Neutrality) already assigns vendor-specific device
logic to vendor-specific MCP servers. Re-implementing device polling here would duplicate that
logic and give vendor bugs a second place to live. It also makes the read-only guarantee
structural: this server simply has no code path that can issue a write, because it never holds
a device credential or session at all — only MCP tool-call results from a server that does.
