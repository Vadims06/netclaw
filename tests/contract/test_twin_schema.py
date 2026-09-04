"""
Contract tests for models/twin_schema.py (spec 122-astra-live-digital-twin).

Frozen alongside models/twin_schema.py — see specs/122-astra-live-digital-twin/loop.md.
These tests exist to keep the build loop honest: they assert the state-transition rules
from data-model.md are actually enforced in code, not merely that the dataclasses accept
well-formed input.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from models.twin_schema import (
    DeltaKind,
    LinkState,
    NodeStatus,
    TwinDelta,
    TwinLink,
    TwinNode,
    TwinSnapshot,
    next_link_state,
    next_node_status,
)


def make_node(node_id="r1", status=NodeStatus.UP):
    return TwinNode(id=node_id, label=node_id, vendor_platform="iosxe", status=status)


def make_link(a="r1", b="r2", state=LinkState.UP):
    return TwinLink(
        id=TwinLink.make_id(a, "Gi0/0", b, "Gi0/1"),
        source_node_id=a,
        target_node_id=b,
        source_interface="Gi0/0",
        target_interface="Gi0/1",
        state=state,
    )


def test_link_id_is_order_independent():
    id_ab = TwinLink.make_id("r1", "Gi0/0", "r2", "Gi0/1")
    id_ba = TwinLink.make_id("r2", "Gi0/1", "r1", "Gi0/0")
    assert id_ab == id_ba


def test_node_delta_requires_node():
    with pytest.raises(ValueError):
        TwinDelta(seq=1, kind=DeltaKind.NODE_ADDED, node=None)


def test_link_delta_requires_link():
    with pytest.raises(ValueError):
        TwinDelta(seq=1, kind=DeltaKind.LINK_ADDED, link=None)


def test_valid_node_delta_round_trips_to_dict():
    delta = TwinDelta(seq=5, kind=DeltaKind.NODE_STATUS_CHANGED, node=make_node())
    d = delta.to_dict()
    assert d["seq"] == 5
    assert d["kind"] == "node_status_changed"
    assert d["node"]["id"] == "r1"
    assert d["link"] is None


def test_snapshot_serializes_nodes_and_links():
    snap = TwinSnapshot(nodes=[make_node()], links=[make_link()], seq=1, testbed_identity="lab-cml-01")
    d = snap.to_dict()
    assert len(d["nodes"]) == 1
    assert len(d["links"]) == 1
    assert d["testbed_identity"] == "lab-cml-01"


def test_next_node_status_unreachable_on_failed_poll():
    assert next_node_status(poll_succeeded=False, reported_admin_down=False) == NodeStatus.UNREACHABLE


def test_next_node_status_down_only_on_confirmed_admin_down():
    assert next_node_status(poll_succeeded=True, reported_admin_down=True) == NodeStatus.DOWN
    assert next_node_status(poll_succeeded=True, reported_admin_down=False) == NodeStatus.UP


def test_link_state_never_asserted_when_both_endpoints_unreachable():
    """The core safety rule: no guessing when neither endpoint can be reached."""
    result = next_link_state(
        current=LinkState.UP,
        endpoint_a_reachable=False,
        endpoint_b_reachable=False,
        observed_state=LinkState.DOWN,
    )
    assert result is None


def test_link_state_updates_when_one_endpoint_reachable():
    result = next_link_state(
        current=LinkState.UP,
        endpoint_a_reachable=True,
        endpoint_b_reachable=False,
        observed_state=LinkState.DOWN,
    )
    assert result == LinkState.DOWN


def test_link_state_no_change_without_an_observation():
    result = next_link_state(
        current=LinkState.UP,
        endpoint_a_reachable=True,
        endpoint_b_reachable=True,
        observed_state=None,
    )
    assert result is None
