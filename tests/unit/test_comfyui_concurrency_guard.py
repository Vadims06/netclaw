"""
Unit test: the single-in-flight-job guard (spec 119 FR-009a) — a second call to
run_generation() while the first is still `submitted` is rejected without ever calling
comfyui_client again.
"""

import sys
from pathlib import Path
from unittest.mock import patch

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import pytest  # noqa: E402

import generation  # noqa: E402
from generation_model import FailureKind, GenerationFailure  # noqa: E402
from topology_model import Device, DeviceRole, SourceKind, TopologySnapshot  # noqa: E402


def _snapshot():
    return TopologySnapshot(
        snapshot_id="snap-1",
        source_kind=SourceKind.CML,
        devices=[Device(hostname="r1", role=DeviceRole.ROUTER)],
        links=[],
    )


def setup_function():
    generation._job_in_flight = False


def teardown_function():
    generation._job_in_flight = False


def test_second_request_rejected_without_touching_comfyui_client():
    generation._job_in_flight = True

    with patch("comfyui_client.get_status") as mock_get_status:
        with pytest.raises(GenerationFailure) as exc_info:
            generation.run_generation(_snapshot())

    assert exc_info.value.kind == FailureKind.GENERATION_ALREADY_IN_PROGRESS
    mock_get_status.assert_not_called()


def test_guard_is_released_after_job_resolves(monkeypatch):
    """Guard state doesn't leak: once a (mocked) prior job has resolved, the next request
    proceeds past the guard check (and only fails later, on backend reachability)."""
    generation._job_in_flight = False

    with patch(
        "comfyui_client.get_status",
        side_effect=RuntimeError("boom - proves we got past the guard"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            generation.run_generation(_snapshot())
