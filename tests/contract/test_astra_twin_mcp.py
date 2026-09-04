"""
Contract tests for mcp-servers/astra-twin-mcp/collector.py's state machine
(spec 122-astra-live-digital-twin).

Frozen alongside collector.py — see specs/122-astra-live-digital-twin/loop.md.

These exercise Collector._reconcile()/deltas_since()/snapshot() directly against synthetic
observed state, rather than a live pyATS MCP subprocess — the collector's polling I/O (over
stdio to the existing pyATS MCP server) requires a real lab testbed to integration-test, which
is exactly what specs/122-astra-live-digital-twin/quickstart.md's Phase A checkpoint is for.
What belongs in an automated, loop-graded contract test is the part that doesn't need a live
lab: that reconciliation never fabricates state and that the documented failure modes
(buffer_overflow, empty-before-first-poll) actually happen.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-servers", "astra-twin-mcp"))

import pytest

from collector import DELTA_BUFFER_SIZE, Collector
from models.twin_schema import DeltaKind, LinkState, NodeStatus, TwinLink, TwinNode


def run(coro):
    return asyncio.run(coro)


def test_snapshot_before_any_poll_is_empty_not_error():
    c = Collector(pyats_testbed="unused.yaml")
    snap = run(c.snapshot())
    assert snap.nodes == []
    assert snap.links == []
    assert snap.seq == 0


def test_reconcile_first_poll_emits_node_added_for_each_node():
    c = Collector(pyats_testbed="unused.yaml")
    nodes = {"r1": TwinNode(id="r1", label="r1", vendor_platform="iosxe", status=NodeStatus.UP)}
    c._reconcile(nodes, {})
    deltas = run(c.deltas_since(0))
    assert len(deltas) == 1
    assert deltas[0].kind == DeltaKind.NODE_ADDED
    assert deltas[0].node.id == "r1"


def test_reconcile_no_change_emits_no_delta():
    c = Collector(pyats_testbed="unused.yaml")
    nodes = {"r1": TwinNode(id="r1", label="r1", vendor_platform="iosxe", status=NodeStatus.UP)}
    c._reconcile(nodes, {})
    c._reconcile(dict(nodes), {})  # identical second poll
    deltas = run(c.deltas_since(0))
    assert len(deltas) == 1  # only the original node_added — no phantom second delta


def test_reconcile_status_change_emits_delta():
    c = Collector(pyats_testbed="unused.yaml")
    up = {"r1": TwinNode(id="r1", label="r1", vendor_platform="iosxe", status=NodeStatus.UP)}
    down = {"r1": TwinNode(id="r1", label="r1", vendor_platform="iosxe", status=NodeStatus.UNREACHABLE)}
    c._reconcile(up, {})
    c._reconcile(down, {})
    deltas = run(c.deltas_since(1))
    assert len(deltas) == 1
    assert deltas[0].kind == DeltaKind.NODE_STATUS_CHANGED
    assert deltas[0].node.status == NodeStatus.UNREACHABLE


def test_reconcile_node_removed_when_absent_from_next_poll():
    c = Collector(pyats_testbed="unused.yaml")
    nodes = {"r1": TwinNode(id="r1", label="r1", vendor_platform="iosxe", status=NodeStatus.UP)}
    c._reconcile(nodes, {})
    c._reconcile({}, {})
    deltas = run(c.deltas_since(1))
    assert len(deltas) == 1
    assert deltas[0].kind == DeltaKind.NODE_REMOVED


def test_link_not_asserted_down_when_both_endpoints_unreachable():
    """Mirrors test_twin_schema.py's rule at the collector's reconciliation layer: a link must
    never flip state purely because both its endpoints dropped off this poll."""
    c = Collector(pyats_testbed="unused.yaml")
    nodes_up = {
        "r1": TwinNode(id="r1", label="r1", vendor_platform="iosxe", status=NodeStatus.UP),
        "r2": TwinNode(id="r2", label="r2", vendor_platform="iosxe", status=NodeStatus.UP),
    }
    link = TwinLink(
        id=TwinLink.make_id("r1", "Gi0/0", "r2", "Gi0/1"),
        source_node_id="r1",
        target_node_id="r2",
        source_interface="Gi0/0",
        target_interface="Gi0/1",
        state=LinkState.UP,
    )
    c._reconcile(nodes_up, {link.id: link})

    nodes_both_unreachable = {
        "r1": TwinNode(id="r1", label="r1", vendor_platform="iosxe", status=NodeStatus.UNREACHABLE),
        "r2": TwinNode(id="r2", label="r2", vendor_platform="iosxe", status=NodeStatus.UNREACHABLE),
    }
    # Both endpoints unreachable this poll means no fresh link observation is even possible —
    # the collector wouldn't observe this link at all, so it stays at last-known state.
    c._reconcile(nodes_both_unreachable, {})

    snap = run(c.snapshot())
    surviving_link = next(l for l in snap.links if l.id == link.id)
    assert surviving_link.state == LinkState.UP  # unchanged, not guessed down


def test_deltas_since_reports_buffer_overflow_when_seq_too_old():
    c = Collector(pyats_testbed="unused.yaml", poll_interval_seconds=1)
    for i in range(DELTA_BUFFER_SIZE + 5):
        c._reconcile({f"r{i}": TwinNode(id=f"r{i}", label=f"r{i}", vendor_platform="x", status=NodeStatus.UP)}, {})
    result = run(c.deltas_since(0))
    assert result is None  # since_seq=0 is older than the retained window


def test_status_reflects_no_successful_poll_initially():
    c = Collector(pyats_testbed="unused.yaml")
    status = c.status()
    assert status["last_successful_poll"] is None
    assert status["consecutive_failures"] == 0
