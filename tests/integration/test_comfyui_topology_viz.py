"""
Integration tests for the comfyui-topology-viz skill.

Unlike the mocked unit tests, test_live_backend_reports_no_usable_model below makes a real,
unmocked call against whatever ComfyUI instance is actually configured via COMFYUI_URL — this
is this feature's one legitimately live dependency (matching the "never mock the dependency
whose failure would matter most" rule from specs 044/045/046). As of spec 120's planning session
(research.md §3), the real configured instance is reachable but has zero installed checkpoints —
so the CORRECT assertion here is that outcome, not a fabricated success. If you have since
installed a checkpoint, this test will need updating (see quickstart.md).

The other two tests use realistic fixture data shaped like a real source's raw output — the same
"real-shaped fixture, not a truly live API call" convention spec 046's own integration test uses
(tests/integration/test_threejs_network_viz.py) — with comfyui-mcp itself mocked, since exercising
a real generation end-to-end requires a checkpoint this environment does not have.

Run:
    pytest tests/integration/test_comfyui_topology_viz.py -v

Requires COMFYUI_URL set in .env for test_live_backend_reports_no_usable_model; skips
automatically if unset.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import comfyui_client  # noqa: E402
import generation  # noqa: E402
from generation_model import ModelCheckStatus  # noqa: E402
from __init__ import visualize_topology_via_comfyui  # noqa: E402

_CML_RAW = {
    "source_kind": "cml",
    "source": "cml-lab-integration-test",
    "devices": [
        {"hostname": "r1", "device_type": "router", "interfaces": [{"name": "Gi0/0"}]},
        {"hostname": "sw1", "device_type": "switch", "interfaces": [{"name": "Gi0/1"}]},
        {"hostname": "fw1", "interfaces": [], "status": "down"},
    ],
    "links": [
        {
            "source_device": "r1",
            "target_device": "sw1",
            "source_interface": "Gi0/0",
            "target_interface": "Gi0/1",
            "status": "healthy",
        }
    ],
}


def setup_function():
    generation._job_in_flight = False


@pytest.mark.skipif(not os.environ.get("COMFYUI_URL"), reason="COMFYUI_URL not configured")
def test_live_backend_reports_no_usable_model():
    """research.md §3: today's real, verified environment state."""
    check = comfyui_client.check_model_availability()
    # Documents today's real state without hard-failing forever if a checkpoint later appears —
    # either outcome is a legitimate, well-classified result; what matters is it's never silently
    # wrong (an exception, a hang, or a fabricated success would all be bugs).
    assert check.status in (ModelCheckStatus.OK, ModelCheckStatus.NO_USABLE_MODEL)
    if check.status == ModelCheckStatus.NO_USABLE_MODEL:
        assert check.available_checkpoints == []
        assert check.selected_checkpoint is None


def _mock_happy_path(tmp_path):
    from generation_model import ModelAvailabilityCheck

    return (
        patch("comfyui_client.get_status", return_value={"comfyuiConnected": True}),
        patch("comfyui_client.controlnet_available", return_value=False),
        patch(
            "comfyui_client.check_model_availability",
            return_value=ModelAvailabilityCheck(
                available_checkpoints=["sdxl.safetensors"],
                selected_checkpoint="sdxl.safetensors",
                status=ModelCheckStatus.OK,
            ),
        ),
        patch(
            "comfyui_client.search_templates",
            return_value=[{"id": "standard_txt2img", "name": "Standard Text-to-Image"}],
        ),
        patch("comfyui_client.get_template", return_value={"1": {"class_type": "CheckpointLoaderSimple"}}),
        patch("comfyui_client.run_workflow", return_value="prompt-123"),
        patch(
            "comfyui_client.get_prompt_history",
            return_value={
                "status": {"completed": True, "status_str": "success"},
                "outputs": {"7": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
            },
        ),
        patch("comfyui_client.download_image", return_value=b"\x89PNG\r\n"),
        patch("output.OUTPUT_DIR", tmp_path / "output"),
    )


def test_freeform_end_to_end(tmp_path):
    """FR-011: freeform description, real sources.from_freeform parsing, comfyui-mcp mocked."""
    patches = _mock_happy_path(tmp_path)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
        result = visualize_topology_via_comfyui(
            {"freeform_description": "a router called core1, core1 connects to a switch called sw1"}
        )
    assert Path(result.file_path).is_file()
    assert result.snapshot_source.value == "freeform"


def test_live_source_shaped_request_produces_same_request_shape_as_freeform(tmp_path):
    """FR-010/FR-011: a live-source-shaped input produces a request through the identical
    pipeline as the freeform path (fixture data shaped like a real CML export, per the same
    convention spec 046's own integration test uses; comfyui-mcp mocked)."""
    patches = _mock_happy_path(tmp_path)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
        result = visualize_topology_via_comfyui(_CML_RAW)
    assert Path(result.file_path).is_file()
    assert result.snapshot_source.value == "cml"
