# Contract: `astra-twin-mcp` MCP tools

FastMCP server, stdio transport (matching NetClaw MCP convention). All tools are read-only; there is
no write-capable tool defined anywhere in this contract, by design (FR-003/FR-005).

## `get_snapshot()`

Returns a `TwinSnapshot` (see data-model.md) — full current node/link state and the sequence number
it is current as of.

- **Preconditions**: Collector has completed at least one successful poll cycle since startup.
- **Postconditions**: None (read-only).
- **Failure mode**: If the collector has never successfully polled the lab (e.g., testbed unreachable
  since startup), returns an empty `nodes`/`links` list with `seq: 0` rather than an error — the HUD
  must be able to render "no data yet, waiting" (FR-010) rather than fail to load.

## `get_deltas(since_seq: int)`

Returns `TwinDelta[]` with `seq > since_seq`, ordered by `seq` ascending.

- **Preconditions**: `since_seq >= 0`.
- **Postconditions**: None.
- **Failure mode**: If `since_seq` is older than the oldest delta still in the ring buffer (buffer
  overflow — client fell too far behind), returns a sentinel indicating the caller must call
  `get_snapshot()` instead, rather than silently returning a truncated/incorrect delta list.

## `get_status()`

Returns collector health: `{ "last_successful_poll": <ISO 8601 | null>, "testbed_identity": <string>,
"poll_interval_seconds": <int>, "consecutive_failures": <int> }`.

- Backs FR-010 (freshness indicator) directly — the HUD computes staleness from
  `last_successful_poll`, it does not infer freshness from whether the WebSocket connection is open.

## Required environment

- `PYATS_TESTBED` — same variable the loop's `harness/assert_lab_only.py` gate validates; the running
  `astra-twin-mcp` server performs the identical lab-allowlist check at its own startup (FR-004),
  independent of the loop — the deployed twin must refuse to run against a non-lab testbed even
  outside the build loop's lifetime. Note: the existing `pyATS_MCP` server (which `astra-twin-mcp`
  subprocesses as an MCP client) reads its testbed path from a differently-named variable,
  `PYATS_TESTBED_PATH` — `astra-twin-mcp` translates `PYATS_TESTBED` into `PYATS_TESTBED_PATH` only
  in the environment it hands to that subprocess, so the existing server's contract is untouched.
- No credential environment variables of its own — device access happens entirely through the
  already-configured pyATS/CML MCP servers it calls as a client.

---

# Contract: HUD twin endpoints (`ui/netclaw-visual/server.js`)

## `GET /api/twin/snapshot`

Returns the `TwinSnapshot` from `astra-twin-mcp`'s `get_snapshot()`, JSON, unmodified shape.

## `WS /ws/twin`

On connect: no initial payload is pushed (client is expected to call `/api/twin/snapshot` first, then
connect here for the tail). Server pushes one JSON-encoded `TwinDelta` message per delta as it
receives one from `astra-twin-mcp`'s `get_deltas` polling loop. Message shape is exactly `TwinDelta`
from data-model.md — no server-side envelope/wrapper field, so the frontend's delta-application code
and `harness/visual_verify.py`'s assertions consume the identical shape.

- **Reconnect contract**: On reconnect, the client MUST re-fetch `/api/twin/snapshot` and only apply
  subsequently-received deltas with `seq > snapshot.seq` — the server does not replay missed deltas
  over a freshly (re)opened WS connection.
