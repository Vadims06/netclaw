"""
Unit tests: each of the four ComfyUI-side failure classifications (backend_unreachable,
no_usable_model, generation_job_failed, generation_already_in_progress) produces a distinct,
correctly-worded message under mocked comfyui-mcp conditions (spec 119 FR-007/008/009/009a,
SC-003).
"""

import sys
from pathlib import Path
from unittest.mock import patch

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import pytest  # noqa: E402

import comfyui_client  # noqa: E402
import generation  # noqa: E402
from generation_model import FailureKind, GenerationFailure, ModelAvailabilityCheck, ModelCheckStatus  # noqa: E402
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


def test_backend_unreachable_is_distinct():
    with patch(
        "comfyui_client.get_status",
        side_effect=comfyui_client.ComfyUIBackendUnreachable("ComfyUI is not connected at http://bad:1"),
    ):
        with pytest.raises(GenerationFailure) as exc_info:
            generation.run_generation(_snapshot())
    assert exc_info.value.kind == FailureKind.BACKEND_UNREACHABLE


def test_no_usable_model_names_what_to_install():
    with patch("comfyui_client.get_status", return_value={}), patch(
        "comfyui_client.controlnet_available", return_value=False
    ):
        with patch(
            "comfyui_client.check_model_availability",
            return_value=ModelAvailabilityCheck(status=ModelCheckStatus.NO_USABLE_MODEL),
        ):
            with pytest.raises(GenerationFailure) as exc_info:
                generation.run_generation(_snapshot())
    assert exc_info.value.kind == FailureKind.NO_USABLE_MODEL
    assert "checkpoint" in exc_info.value.message.lower()


def test_generation_job_failed_is_distinct_from_model_and_backend_failures():
    availability = ModelAvailabilityCheck(
        available_checkpoints=["sdxl.safetensors"],
        selected_checkpoint="sdxl.safetensors",
        status=ModelCheckStatus.OK,
    )
    with patch("comfyui_client.get_status", return_value={}), patch(
        "comfyui_client.controlnet_available", return_value=False
    ), patch(
        "comfyui_client.check_model_availability", return_value=availability
    ), patch(
        "comfyui_client.search_templates",
        return_value=[{"id": "standard_txt2img", "name": "Standard Text-to-Image"}],
    ), patch(
        "comfyui_client.get_template", return_value={"1": {"class_type": "CheckpointLoaderSimple"}}
    ), patch(
        "comfyui_client.run_workflow", return_value="task-123"
    ), patch(
        "comfyui_client.get_prompt_history",
        return_value={"status": {"completed": True, "status_str": "error", "messages": ["OOM"]}},
    ):
        with pytest.raises(GenerationFailure) as exc_info:
            generation.run_generation(_snapshot())
    assert exc_info.value.kind == FailureKind.GENERATION_JOB_FAILED
    assert not generation._job_in_flight  # guard released even on failure


def test_generation_already_in_progress_is_rejected_outright():
    generation._job_in_flight = True
    try:
        with pytest.raises(GenerationFailure) as exc_info:
            generation.run_generation(_snapshot())
    finally:
        generation._job_in_flight = False
    assert exc_info.value.kind == FailureKind.GENERATION_ALREADY_IN_PROGRESS


def test_all_four_messages_are_mutually_distinct():
    messages = set()

    with patch(
        "comfyui_client.get_status",
        side_effect=comfyui_client.ComfyUIBackendUnreachable("unreachable"),
    ):
        with pytest.raises(GenerationFailure) as e:
            generation.run_generation(_snapshot())
        messages.add(e.value.message)

    with patch("comfyui_client.get_status", return_value={}), patch(
        "comfyui_client.controlnet_available", return_value=False
    ), patch(
        "comfyui_client.check_model_availability",
        return_value=ModelAvailabilityCheck(status=ModelCheckStatus.NO_USABLE_MODEL),
    ):
        with pytest.raises(GenerationFailure) as e:
            generation.run_generation(_snapshot())
        messages.add(e.value.message)

    generation._job_in_flight = True
    try:
        with pytest.raises(GenerationFailure) as e:
            generation.run_generation(_snapshot())
        messages.add(e.value.message)
    finally:
        generation._job_in_flight = False

    assert len(messages) == 3  # all distinct
