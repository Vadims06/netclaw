"""T031: authorization — default-deny, grants, rate limits, budgets, approvals."""

import os

import pytest

from bgp.federation.authorization import Authorizer
from bgp.federation.manager import peer_identity


def _federated(manager, peer_as=65007, rid="7.7.7.7"):
    manager.local_consent(peer_as, rid)
    manager.remote_consent(peer_as, rid)
    return peer_identity(peer_as, rid)


def test_default_deny(manager):
    ident = _federated(manager)
    authz = Authorizer(manager)
    d = authz.authorize(ident, "tool", "cml-mcp/list_labs")
    assert not d.allowed and d.code == "not_allowlisted"


def test_non_federated_peer_denied_by_default(manager):
    """A peer_identity with no federation_peer row at all (e.g. an iN2N
    member's self-referential identity on its own channel to Border, which
    has no eN2N federation_peer row) is denied via the is_federated() gate
    when already_trusted is not set (spec 121 research.md R10)."""
    authz = Authorizer(manager)
    d = authz.authorize("johns-risk/viz", "tool", "topology-diagram-mcp/render_structural")
    assert not d.allowed and d.code == "severed"


def test_already_trusted_bypasses_is_federated_gate_but_still_requires_grant(manager):
    """spec 121 research.md R10: an internal (iN2N) channel's self-referential
    peer_identity has no federation_peer row, but is_federated() must not be
    the only gate — already_trusted skips ONLY that eN2N-specific check, the
    grant check below it still runs and still denies with no grant."""
    authz = Authorizer(manager)
    d = authz.authorize("johns-risk/viz", "tool", "topology-diagram-mcp/render_structural",
                        already_trusted=True)
    assert not d.allowed and d.code == "not_allowlisted"

    authz.grant("johns-risk/viz", "tool", "topology-diagram-mcp/render_structural")
    d2 = authz.authorize("johns-risk/viz", "tool", "topology-diagram-mcp/render_structural",
                         already_trusted=True)
    assert d2.allowed and d2.code == "allowlisted"


def test_grant_allows(manager):
    ident = _federated(manager)
    authz = Authorizer(manager)
    authz.grant(ident, "tool", "cml-mcp/list_labs")
    d = authz.authorize(ident, "tool", "cml-mcp/list_labs")
    assert d.allowed and d.code == "allowlisted"


def test_approval_required(manager):
    ident = _federated(manager)
    authz = Authorizer(manager)
    authz.grant(ident, "skill", "reboot-router", requires_approval=True)
    d = authz.authorize(ident, "skill", "reboot-router")
    assert not d.allowed and d.code == "approval_required"


def test_rate_limit(manager, monkeypatch):
    monkeypatch.setenv("N2N_RATE_PER_MIN", "2")
    ident = _federated(manager)
    authz = Authorizer(manager)
    authz.grant(ident, "tool", "t/x")
    assert authz.authorize(ident, "tool", "t/x").allowed
    assert authz.authorize(ident, "tool", "t/x").allowed
    assert authz.authorize(ident, "tool", "t/x").code == "rate_limited"


def test_budget_exhaustion_and_reset(manager, monkeypatch):
    monkeypatch.setenv("N2N_DAILY_REQUESTS", "1")
    ident = _federated(manager)
    authz = Authorizer(manager)
    authz.grant(ident, "tool", "t/x")
    assert authz.authorize(ident, "tool", "t/x").allowed
    authz.debit(ident, requests=1)
    assert authz.authorize(ident, "tool", "t/x").code == "budget_exhausted"


def test_approval_lifecycle(manager):
    ident = _federated(manager)
    authz = Authorizer(manager)
    # Need an invocation row to reference
    inv_id = manager._conn.execute(
        "INSERT INTO remote_invocation_record (direction, peer_identity, decision, outcome) "
        "VALUES ('inbound', ?, 'approval_required', 'pending')", (ident,)).lastrowid
    manager._conn.commit()
    appr = authz.create_approval(inv_id)
    assert authz.approval_status(appr["approval_id"]) == "pending"
    authz.resolve_approval(appr["approval_id"], "approve")
    assert authz.approval_status(appr["approval_id"]) == "approved"
    assert len(authz.pending_approvals()) == 0
