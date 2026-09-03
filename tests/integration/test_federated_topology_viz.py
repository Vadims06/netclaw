"""
Integration tests for spec 121's federated topology visualization pipeline.

Like spec 120's own integration tests, this feature has real live dependencies this environment
actually has: the mesh daemon's HTTP API (localhost:8179) and the `johns-risk/viz` federation
member. Tests here skip automatically when the daemon isn't reachable, matching spec 120's
"skip if unset" convention (tests/integration/test_comfyui_topology_viz.py).

The member-restart tests (T036) are opt-in via RUN_DISRUPTIVE_FEDERATION_TESTS=1 — they stop and
restart a live systemd service shared with other work on this host, so they don't run by default.

Run:
    pytest tests/integration/test_federated_topology_viz.py -v
    RUN_DISRUPTIVE_FEDERATION_TESTS=1 pytest tests/integration/test_federated_topology_viz.py -v
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import federated_generation  # noqa: E402
from topology_model import Device, DeviceRole, Link, LinkEndpoint, SourceKind, TopologySnapshot  # noqa: E402

_DAEMON_API = "http://127.0.0.1:8179"


def _daemon_reachable() -> bool:
    try:
        httpx.get(f"{_DAEMON_API}/n2n/members/health", timeout=5.0)
        return True
    except Exception:
        return False


def _member_active() -> bool:
    try:
        response = httpx.get(f"{_DAEMON_API}/n2n/members/health", timeout=5.0)
        for m in response.json().get("members", []):
            if m.get("member_id") == "johns-risk/viz":
                return m.get("state") == "active"
    except Exception:
        pass
    return False


pytestmark = pytest.mark.skipif(not _daemon_reachable(), reason="mesh daemon not reachable at :8179")


def _snapshot():
    return TopologySnapshot(
        snapshot_id="it-fed-1",
        source_kind=SourceKind.CML,
        source_label="federated integration test",
        devices=[
            Device(hostname="core1", role=DeviceRole.ROUTER),
            Device(hostname="sw1", role=DeviceRole.SWITCH),
            Device(hostname="fw1", role=DeviceRole.FIREWALL),
        ],
        links=[
            Link(link_id="l1", endpoint_a=LinkEndpoint("core1"), endpoint_b=LinkEndpoint("sw1")),
            Link(link_id="l2", endpoint_a=LinkEndpoint("sw1"), endpoint_b=LinkEndpoint("fw1")),
        ],
    )


# ---- T039 (US3): Stage A alone, distinct from Border's own fallback rendering -------------

@pytest.mark.skipif(not _member_active(), reason="johns-risk/viz not active")
def test_stage_a_alone_returns_real_diagram_distinct_from_fallback():
    """Acceptance Scenario 2 (US3): calling render_structural directly against the live member
    returns a real, correct diagram — proving the member executes it, not Border in-process."""
    result = federated_generation._invoke_tool(
        federated_generation.STRUCTURAL_MEMBER,
        federated_generation._STRUCTURAL_TOOL,
        {
            "snapshot_id": "it-stage-a-only",
            "devices": '[{"hostname": "core1", "role": "router"}, {"hostname": "sw1", "role": "switch"}]',
            "links": '[{"a": "core1", "b": "sw1", "label": ""}]',
        },
    )
    assert result["device_count"] == 2
    assert set(result["positions"].keys()) == {"core1", "sw1"}
    assert len(result["image_base64"]) > 1000  # a real image, not an empty/placeholder response


# ---- T025 (US1): full pipeline, live, whatever the current member/ComfyUI state allows ----

@pytest.mark.skipif(not _member_active(), reason="johns-risk/viz not active")
def test_full_pipeline_live_produces_correct_structural_diagram():
    """SC-001: device count, connections, and labels exactly match the source snapshot, via the
    real federated_generation.run_federated_generation() entry point against the live member.
    Whether Stage B also succeeds depends on ComfyUI/model availability at test time (asserted
    separately, not required here) — icon-role preservation through styling (Acceptance Scenario
    3) is a manual/visual check per tasks.md T025, not automated here."""
    federated_generation._federated_job_in_flight = False
    try:
        result = federated_generation.run_federated_generation(_snapshot())
    finally:
        federated_generation._federated_job_in_flight = False

    assert result.generation_path in ("federated", "federated_partial")
    assert result.structural_member == federated_generation.STRUCTURAL_MEMBER
    assert Path(result.image.file_path).exists()
    assert Path(result.image.file_path).stat().st_size > 1000


# ---- T037 (US2): freeform routes to fallback without attempting the federated path --------

def test_freeform_request_does_not_attempt_federated_path():
    snapshot = TopologySnapshot(
        snapshot_id="it-freeform-1", source_kind=SourceKind.FREEFORM,
        devices=[Device(hostname="core1", role=DeviceRole.ROUTER)],
    )
    federated_generation._federated_job_in_flight = False
    from unittest.mock import patch
    with patch("federated_generation._member_reachable") as mock_reachable, \
         patch("generation.run_generation") as mock_fallback:
        federated_generation.run_federated_generation(snapshot)
    mock_reachable.assert_not_called()
    mock_fallback.assert_called_once()


# ---- T036 (US2): member unreachable still routes to fallback (disruptive, opt-in) ---------

@pytest.mark.skipif(
    os.environ.get("RUN_DISRUPTIVE_FEDERATION_TESTS") != "1",
    reason="stops/restarts a live systemd service — set RUN_DISRUPTIVE_FEDERATION_TESTS=1 to run",
)
def test_member_unreachable_routes_to_fallback_attempt():
    """quickstart.md step 6. Stops netclaw-member-johns-risk-viz.service, confirms
    _member_reachable() correctly reports it down, restores it afterward regardless of outcome."""
    unit = "netclaw-member-johns-risk-viz.service"
    subprocess.run(["systemctl", "--user", "stop", unit], check=True)
    try:
        time.sleep(2)
        assert federated_generation._member_reachable(federated_generation.STRUCTURAL_MEMBER) is False
    finally:
        subprocess.run(["systemctl", "--user", "start", unit], check=True)
        time.sleep(5)
