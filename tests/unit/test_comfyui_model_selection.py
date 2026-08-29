"""
Unit tests for comfyui_client.check_model_availability()'s deterministic selection (spec 119
FR-006a) over zero/one/multiple mocked checkpoint lists. comfyui_client._call_tool is mocked so
these are independent of any real ComfyUI instance's actual installed models.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import comfyui_client  # noqa: E402
from generation_model import ModelCheckStatus  # noqa: E402


def _mock_list_models(checkpoints: list[str]):
    return (False, json.dumps({"checkpoints": checkpoints}))


def test_zero_checkpoints_reports_no_usable_model():
    with patch("comfyui_client._call_tool", return_value=_mock_list_models([])):
        result = comfyui_client.check_model_availability()
    assert result.status == ModelCheckStatus.NO_USABLE_MODEL
    assert result.selected_checkpoint is None
    assert result.available_checkpoints == []


def test_one_checkpoint_is_selected():
    with patch("comfyui_client._call_tool", return_value=_mock_list_models(["sd_xl_base_1.0.safetensors"])):
        result = comfyui_client.check_model_availability()
    assert result.status == ModelCheckStatus.OK
    assert result.selected_checkpoint == "sd_xl_base_1.0.safetensors"


def test_multiple_checkpoints_select_deterministically():
    checkpoints = ["zzz_model.safetensors", "aaa_model.safetensors", "mmm_model.safetensors"]
    with patch("comfyui_client._call_tool", return_value=_mock_list_models(checkpoints)):
        result_a = comfyui_client.check_model_availability()
    with patch("comfyui_client._call_tool", return_value=_mock_list_models(checkpoints)):
        result_b = comfyui_client.check_model_availability()

    assert result_a.status == ModelCheckStatus.OK
    assert result_a.selected_checkpoint == result_b.selected_checkpoint
    assert result_a.selected_checkpoint == "aaa_model.safetensors"
    assert set(result_a.available_checkpoints) == set(checkpoints)
