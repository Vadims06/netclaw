"""
Unit tests for federated_generation.py's routing matrix (spec 121 FR-009/FR-010/FR-011/FR-013,
data-model.md's state-transition diagram). generation.run_generation() and the federation HTTP
calls are mocked — this tests routing logic only; tests/integration/test_federated_topology_viz.py
covers the real live path.
"""

import sys
from pathlib import Path
from unittest.mock import patch

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import pytest

import federated_generation  # noqa: E402
from generation_model import FailureKind, GeneratedImage, GenerationFailure  # noqa: E402
from topology_model import (  # noqa: E402
    Device,
    DeviceRole,
    Link,
    LinkEndpoint,
    SourceKind,
    TopologySnapshot,
)


def _snapshot(source_kind=SourceKind.CML, with_devices=True):
    devices = [Device(hostname="core1", role=DeviceRole.ROUTER)] if with_devices else []
    return TopologySnapshot(snapshot_id="snap1", source_kind=source_kind, devices=devices)


def _fake_fallback_image():
    return GeneratedImage(
        file_path="/tmp/fallback.png", generation_request_id="r1",
        model_used="flux1-schnell-fp8", snapshot_source=SourceKind.CML,
    )


@pytest.fixture(autouse=True)
def _reset_in_flight_guard():
    federated_generation._federated_job_in_flight = False
    yield
    federated_generation._federated_job_in_flight = False


def test_empty_topology_raises():
    with pytest.raises(GenerationFailure) as exc_info:
        federated_generation.run_federated_generation(_snapshot(with_devices=False))
    assert exc_info.value.kind == FailureKind.EMPTY_TOPOLOGY


def test_freeform_routes_directly_to_fallback_without_attempting_federated_path():
    """FR-011."""
    with patch("federated_generation._member_reachable") as mock_reachable, \
         patch("generation.run_generation", return_value=_fake_fallback_image()) as mock_fallback:
        result = federated_generation.run_federated_generation(_snapshot(source_kind=SourceKind.FREEFORM))
    mock_reachable.assert_not_called()
    mock_fallback.assert_called_once()
    assert result.generation_path == "fallback"
    assert result.reason == "freeform request"


def test_structural_member_unreachable_routes_to_fallback():
    """FR-009."""
    with patch("federated_generation._member_reachable", return_value=False), \
         patch("generation.run_generation", return_value=_fake_fallback_image()) as mock_fallback:
        result = federated_generation.run_federated_generation(_snapshot())
    mock_fallback.assert_called_once()
    assert result.generation_path == "fallback"
    assert "unreachable" in result.reason
    assert result.structural_member == federated_generation.STRUCTURAL_MEMBER


def test_structural_stage_call_failure_routes_to_fallback():
    with patch("federated_generation._member_reachable", return_value=True), \
         patch("federated_generation._run_stage_a", side_effect=federated_generation._FederationCallError("boom")), \
         patch("generation.run_generation", return_value=_fake_fallback_image()) as mock_fallback:
        result = federated_generation.run_federated_generation(_snapshot())
    mock_fallback.assert_called_once()
    assert result.generation_path == "fallback"
    assert "structural stage failed" in result.reason


def test_styling_member_unreachable_after_stage_a_success_returns_federated_partial():
    """FR-010: distinct reason from a structural-member failure, unstyled diagram still offered."""
    stage_a_result = {"image_base64": "aGVsbG8=", "format": "png", "positions": {}, "device_count": 1}

    with patch("federated_generation._member_reachable", side_effect=[True, False]), \
         patch("federated_generation._run_stage_a", return_value=stage_a_result), \
         patch("federated_generation._write_federated_image", return_value=_fake_fallback_image()) as mock_write, \
         patch("generation.run_generation") as mock_fallback:
        result = federated_generation.run_federated_generation(_snapshot())
    mock_fallback.assert_not_called()
    mock_write.assert_called_once()
    assert result.generation_path == "federated_partial"
    assert "unreachable" in result.reason
    assert result.structural_member == federated_generation.STRUCTURAL_MEMBER


def test_stage_b_call_failure_returns_federated_partial_not_fallback():
    """FR-010: a Stage B call failure (not just unreachability) is also federated_partial,
    never a full fallback — Stage A's correct diagram is still offered."""
    stage_a_result = {"image_base64": "aGVsbG8=", "format": "png", "positions": {}, "device_count": 1}

    with patch("federated_generation._member_reachable", return_value=True), \
         patch("federated_generation._run_stage_a", return_value=stage_a_result), \
         patch("federated_generation._run_stage_b", side_effect=federated_generation._FederationCallError("styling died")), \
         patch("federated_generation._write_federated_image", return_value=_fake_fallback_image()) as mock_write, \
         patch("generation.run_generation") as mock_fallback:
        result = federated_generation.run_federated_generation(_snapshot())
    mock_fallback.assert_not_called()
    mock_write.assert_called_once()
    assert result.generation_path == "federated_partial"
    assert "styling stage failed" in result.reason


def test_full_success_returns_federated_path_with_both_members_set():
    stage_a_result = {"image_base64": "aGVsbG8=", "format": "png", "positions": {}, "device_count": 1}
    stage_b_result = {"styled_image_base64": "d29ybGQ=", "format": "png"}

    with patch("federated_generation._member_reachable", return_value=True), \
         patch("federated_generation._run_stage_a", return_value=stage_a_result), \
         patch("federated_generation._run_stage_b", return_value=stage_b_result), \
         patch("federated_generation._write_federated_image", return_value=_fake_fallback_image()) as mock_write, \
         patch("generation.run_generation") as mock_fallback:
        result = federated_generation.run_federated_generation(_snapshot())
    mock_fallback.assert_not_called()
    mock_write.assert_called_once()
    assert result.generation_path == "federated"
    assert result.structural_member == federated_generation.STRUCTURAL_MEMBER
    assert result.styling_member == federated_generation.STYLING_MEMBER


def test_device_count_mismatch_routes_to_fallback():
    """SC-001's 'zero phantom devices' guarantee — a Stage A result whose device_count doesn't
    match the request is treated as a failure, not silently trusted."""
    stage_a_result = {"image_base64": "aGVsbG8=", "format": "png", "positions": {}, "device_count": 999}

    with patch("federated_generation._member_reachable", return_value=True), \
         patch("federated_generation._run_stage_a", return_value=stage_a_result), \
         patch("generation.run_generation", return_value=_fake_fallback_image()) as mock_fallback:
        result = federated_generation.run_federated_generation(_snapshot())
    mock_fallback.assert_called_once()
    assert result.generation_path == "fallback"
    assert "device count mismatch" in result.reason


def test_concurrent_request_raises_generation_already_in_progress():
    """FR-013: single in-flight guard extends to the federated path."""
    federated_generation._federated_job_in_flight = True
    with pytest.raises(GenerationFailure) as exc_info:
        federated_generation.run_federated_generation(_snapshot())
    assert exc_info.value.kind == FailureKind.GENERATION_ALREADY_IN_PROGRESS
