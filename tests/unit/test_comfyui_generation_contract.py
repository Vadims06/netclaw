"""
Contract test: with every comfyui-mcp/ComfyUI call mocked, assert generation.py's happy-path
call order matches contracts/comfyui-generation-contract.md steps 1-7 exactly:
get_status -> list_models (via check_model_availability) -> search_templates -> get_template ->
run_workflow(sync=False) -> get_prompt_history (polled against ComfyUI's own /history, not
comfyui-mcp's task tracker — research.md §9) -> download_image -> local write.
"""

import sys
from pathlib import Path
from unittest.mock import patch

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import generation  # noqa: E402
from generation_model import ModelAvailabilityCheck, ModelCheckStatus  # noqa: E402
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


def test_happy_path_call_order_matches_contract(tmp_path):
    call_order = []

    def _get_status():
        call_order.append("get_status")
        return {"comfyuiConnected": True}

    def _check_model_availability():
        call_order.append("list_models")
        return ModelAvailabilityCheck(
            available_checkpoints=["sdxl.safetensors"],
            selected_checkpoint="sdxl.safetensors",
            status=ModelCheckStatus.OK,
        )

    def _search_templates(model_type, task_type):
        call_order.append("search_templates")
        return [{"id": "standard_txt2img", "name": "Standard Text-to-Image"}]

    def _get_template(template_id, parameters):
        call_order.append("get_template")
        return {"1": {"class_type": "CheckpointLoaderSimple"}}

    def _run_workflow(workflow, name):
        call_order.append("run_workflow")
        return "prompt-123"

    def _get_prompt_history(prompt_id):
        call_order.append("get_prompt_history")
        return {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"7": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        }

    def _download_image(filename, subfolder, image_type):
        call_order.append("download_image")
        return b"\x89PNG\r\n"

    with patch("comfyui_client.get_status", side_effect=_get_status), patch(
        "comfyui_client.controlnet_available", return_value=False
    ), patch(
        "comfyui_client.check_model_availability", side_effect=_check_model_availability
    ), patch("comfyui_client.search_templates", side_effect=_search_templates), patch(
        "comfyui_client.get_template", side_effect=_get_template
    ), patch("comfyui_client.run_workflow", side_effect=_run_workflow), patch(
        "comfyui_client.get_prompt_history", side_effect=_get_prompt_history
    ), patch("comfyui_client.download_image", side_effect=_download_image), patch(
        "output.OUTPUT_DIR", tmp_path / "output"
    ):
        result = generation.run_generation(_snapshot())

    assert call_order == [
        "get_status",
        "list_models",
        "search_templates",
        "get_template",
        "run_workflow",
        "get_prompt_history",
        "download_image",
    ]
    assert Path(result.file_path).is_file()
    assert result.model_used == "sdxl.safetensors"
    assert not generation._job_in_flight


def test_stuck_comfyui_mcp_task_tracker_does_not_block_completion_detection(tmp_path):
    """Regression test for the real bug found live during implementation: comfyui-mcp's own
    task tracker can get permanently stuck reporting "working" for a job ComfyUI itself already
    completed. Completion detection must never depend on comfyui-mcp's get_task_result/get_task
    — only on ComfyUI's own /history via get_prompt_history."""
    with patch("comfyui_client.get_status", return_value={"comfyuiConnected": True}), patch(
        "comfyui_client.controlnet_available", return_value=False
    ), patch(
        "comfyui_client.check_model_availability",
        return_value=ModelAvailabilityCheck(
            available_checkpoints=["sdxl.safetensors"], selected_checkpoint="sdxl.safetensors",
            status=ModelCheckStatus.OK,
        ),
    ), patch(
        "comfyui_client.search_templates",
        return_value=[{"id": "standard_txt2img", "name": "Standard Text-to-Image"}],
    ), patch(
        "comfyui_client.get_template", return_value={"1": {"class_type": "CheckpointLoaderSimple"}}
    ), patch("comfyui_client.run_workflow", return_value="prompt-456"), patch(
        "comfyui_client.get_task_result",
        return_value={"status": "working", "statusMessage": "Queued for generation"},
    ), patch(
        "comfyui_client.get_prompt_history",
        return_value={
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"7": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        },
    ), patch("comfyui_client.download_image", return_value=b"\x89PNG\r\n"), patch(
        "output.OUTPUT_DIR", tmp_path / "output"
    ):
        result = generation.run_generation(_snapshot())

    assert Path(result.file_path).is_file()
