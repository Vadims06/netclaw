#!/usr/bin/env python3
"""
astra-twin-mcp — Astra Live Digital Twin collector (spec 122-astra-live-digital-twin).

Exposes 3 read-only tools via FastMCP/stdio:
  get_snapshot   — full current twin state (nodes, links, seq, testbed_identity)
  get_deltas     — deltas observed since a given sequence number
  get_status     — collector health / freshness (FR-010)

No write-capable tool is defined anywhere in this server — not merely unused, but absent
(FR-005). See specs/122-astra-live-digital-twin/contracts/astra-twin-mcp.md for the full
contract, and collector.py for how device state is actually read (always through the existing
pyATS MCP server, never directly).

Frozen (see specs/122-astra-live-digital-twin/plan.md, loop.md).
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from collector import DEFAULT_POLL_INTERVAL_SECONDS, Collector  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("astra-twin-mcp")

PYATS_TESTBED = os.environ.get("PYATS_TESTBED")
POLL_INTERVAL = int(os.environ.get("ASTRA_TWIN_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS))

HERE = os.path.dirname(os.path.abspath(__file__))
ASSERT_LAB_ONLY = os.path.join(HERE, "..", "..", "harness", "assert_lab_only.py")

if not PYATS_TESTBED or not os.path.isfile(PYATS_TESTBED):
    logger.critical("PYATS_TESTBED not set or file not found: %s", PYATS_TESTBED)
    print(f"ERROR: PYATS_TESTBED not set or file not found: {PYATS_TESTBED}", file=sys.stderr)
    sys.exit(1)

# FR-004: refuse to serve against anything but an explicitly allowlisted lab testbed, even
# outside the build loop's lifetime — this check is independent of loop/ralph.sh's own.
import subprocess  # noqa: E402

_check = subprocess.run(
    [sys.executable, ASSERT_LAB_ONLY, PYATS_TESTBED],
    capture_output=True,
    text=True,
)
if _check.returncode != 0:
    logger.critical("lab-only check failed:\n%s", _check.stderr)
    print(_check.stderr, file=sys.stderr)
    sys.exit(1)
logger.info(_check.stdout.strip())

collector = Collector(pyats_testbed=PYATS_TESTBED, poll_interval_seconds=POLL_INTERVAL)

mcp = FastMCP("astra-twin-mcp")

# --- persistent-process cache -------------------------------------------------------------
#
# ui/netclaw-visual/server.js's twin routes (and every other MCP integration in this repo)
# call MCP tools via scripts/mcp-call.py, which spawns a FRESH server process per call. That
# is fine for stateless queries, but astra-twin-mcp's whole point is a continuously-running
# collector accumulating state across polls — a fresh process per HTTP request would restart
# the collector from empty state every single time and pay a full pyATS/SSH round trip on
# every request. So this server, when run as a long-lived process (a systemd service, not
# spawned per-call), also writes its current state to a small cache file on a fixed interval.
# ui/netclaw-visual/server.js reads that file directly (no subprocess, no MCP round trip) for
# its own twin routes; the MCP tools below remain fully available for an AI agent to query
# this server directly via mcp-call.py exactly as before — the two paths are independent.
CACHE_DIR = os.path.expanduser(os.environ.get("ASTRA_TWIN_CACHE_DIR", "~/.openclaw/astra-twin"))
CACHE_PATH = os.path.join(CACHE_DIR, "twin_cache.json")
CACHE_WRITE_INTERVAL_SECONDS = float(os.environ.get("ASTRA_TWIN_CACHE_WRITE_INTERVAL_SECONDS", "2"))


async def _cache_writer() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    while True:
        snap = await collector.snapshot()
        all_deltas = await collector.all_buffered_deltas()
        payload = {
            "snapshot": snap.to_dict(),
            "deltas": [d.to_dict() for d in (all_deltas or [])],
            "status": collector.status(),
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = CACHE_PATH + f".tmp.{os.getpid()}"
        with open(tmp_path, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp_path, CACHE_PATH)  # atomic on the same filesystem — no partial reads
        await asyncio.sleep(CACHE_WRITE_INTERVAL_SECONDS)


@mcp.tool()
async def get_snapshot() -> str:
    """Full current twin state: nodes, links, the sequence number this snapshot is current
    as of, and which lab testbed it came from. Returns an empty nodes/links list with seq: 0
    if the collector has not yet completed a successful poll since startup — this is not an
    error condition, the HUD renders it as 'no data yet, waiting'."""
    snap = await collector.snapshot()
    return json.dumps(snap.to_dict(), indent=2)


@mcp.tool()
async def get_deltas(since_seq: int) -> str:
    """Deltas observed since sequence number since_seq, ordered oldest to newest. If since_seq
    is older than the oldest delta still buffered, returns {"buffer_overflow": true} — the
    caller must call get_snapshot() instead of trusting a truncated delta list."""
    result = await collector.deltas_since(since_seq)
    if result is None:
        return json.dumps({"buffer_overflow": True})
    return json.dumps([d.to_dict() for d in result], indent=2)


@mcp.tool()
async def get_status() -> str:
    """Collector health: last_successful_poll, testbed_identity, poll_interval_seconds,
    consecutive_failures. This is what the HUD's freshness indicator (FR-010) reads — the HUD
    must not infer freshness merely from whether its own WebSocket connection is open."""
    return json.dumps(collector.status(), indent=2)


async def _run() -> None:
    poll_task = asyncio.create_task(collector.run_forever())
    cache_task = asyncio.create_task(_cache_writer())
    try:
        await mcp.run_stdio_async()
    finally:
        poll_task.cancel()
        cache_task.cancel()


async def _run_headless() -> None:
    """Run the collector + cache writer without the MCP stdio transport — for use as a
    persistent background service (e.g. a systemd unit) where nothing is piping stdio into
    this process. The MCP tools (get_snapshot/get_deltas/get_status) remain available whenever
    this same script is invoked normally (spawned per-call via mcp-call.py, per this server's
    original design) — that path is untouched; this is an additional way to run it."""
    poll_task = asyncio.create_task(collector.run_forever())
    cache_task = asyncio.create_task(_cache_writer())
    try:
        await asyncio.gather(poll_task, cache_task)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    logger.info(
        "Starting astra-twin-mcp — testbed=%s poll_interval=%ds",
        PYATS_TESTBED,
        POLL_INTERVAL,
    )
    if "--headless" in sys.argv:
        asyncio.run(_run_headless())
    else:
        asyncio.run(_run())
