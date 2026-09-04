#!/usr/bin/env python3
"""
Astra Live Digital Twin — shared data model (spec 122-astra-live-digital-twin).

Frozen once written (see specs/122-astra-live-digital-twin/plan.md's Project Structure and
loop.md's Safety Envelope): both mcp-servers/astra-twin-mcp/ and ui/netclaw-visual/server.js's
twin routes treat this file's shapes as the single source of truth for the wire format. The
build loop may read it but must never modify it.

Entity definitions and state-transition rules come from
specs/122-astra-live-digital-twin/data-model.md — keep this file and that document in sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    UNREACHABLE = "unreachable"


class LinkState(str, Enum):
    UP = "up"
    DOWN = "down"


class DeltaKind(str, Enum):
    NODE_ADDED = "node_added"
    NODE_REMOVED = "node_removed"
    NODE_STATUS_CHANGED = "node_status_changed"
    LINK_ADDED = "link_added"
    LINK_REMOVED = "link_removed"
    LINK_STATE_CHANGED = "link_state_changed"


@dataclass
class TwinNode:
    id: str
    label: str
    vendor_platform: str
    status: NodeStatus
    last_seen: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "vendor_platform": self.vendor_platform,
            "status": self.status.value,
            "last_seen": self.last_seen,
        }


@dataclass
class TwinLink:
    id: str
    source_node_id: str
    target_node_id: str
    source_interface: str
    target_interface: str
    state: LinkState
    last_seen: str = field(default_factory=utcnow_iso)

    @staticmethod
    def make_id(node_a: str, iface_a: str, node_b: str, iface_b: str) -> str:
        """Deterministic id from an *unordered* endpoint pair, so the same physical link
        always diffs to the same id regardless of which side was polled/observed first."""
        a = f"{node_a}:{iface_a}"
        b = f"{node_b}:{iface_b}"
        first, second = sorted([a, b])
        return f"{first}__{second}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "source_interface": self.source_interface,
            "target_interface": self.target_interface,
            "state": self.state.value,
            "last_seen": self.last_seen,
        }


@dataclass
class TwinDelta:
    seq: int
    kind: DeltaKind
    node: Optional[TwinNode] = None
    link: Optional[TwinLink] = None
    observed_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self) -> None:
        node_kinds = {DeltaKind.NODE_ADDED, DeltaKind.NODE_REMOVED, DeltaKind.NODE_STATUS_CHANGED}
        link_kinds = {DeltaKind.LINK_ADDED, DeltaKind.LINK_REMOVED, DeltaKind.LINK_STATE_CHANGED}
        if self.kind in node_kinds and self.node is None:
            raise ValueError(f"TwinDelta of kind {self.kind} requires a node")
        if self.kind in link_kinds and self.link is None:
            raise ValueError(f"TwinDelta of kind {self.kind} requires a link")

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "kind": self.kind.value,
            "node": self.node.to_dict() if self.node else None,
            "link": self.link.to_dict() if self.link else None,
            "observed_at": self.observed_at,
        }


@dataclass
class TwinSnapshot:
    nodes: list[TwinNode]
    links: list[TwinLink]
    seq: int
    testbed_identity: str

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "links": [l.to_dict() for l in self.links],
            "seq": self.seq,
            "testbed_identity": self.testbed_identity,
        }


def next_link_state(
    current: Optional[LinkState],
    endpoint_a_reachable: bool,
    endpoint_b_reachable: bool,
    observed_state: Optional[LinkState],
) -> Optional[LinkState]:
    """Enforce data-model.md's transition rule: a link is only ever asserted up/down from
    confirmed state reported by at least one *reachable* endpoint. If both endpoints are
    unreachable, the link state is left unchanged (None means "no change") rather than
    guessed — this is Constitution Principle I: "Device state MUST NOT be assumed or guessed."
    """
    if not endpoint_a_reachable and not endpoint_b_reachable:
        return None
    if observed_state is None:
        return None
    return observed_state


def next_node_status(poll_succeeded: bool, reported_admin_down: bool) -> NodeStatus:
    """Enforce data-model.md's node-status distinction: "down" is reserved for a device the
    collector can positively confirm is operationally down via a *successful* poll of it (or
    of a reachable neighbor reporting it); "unreachable" means the collector itself could not
    get a read. The two are never conflated.
    """
    if not poll_succeeded:
        return NodeStatus.UNREACHABLE
    if reported_admin_down:
        return NodeStatus.DOWN
    return NodeStatus.UP
