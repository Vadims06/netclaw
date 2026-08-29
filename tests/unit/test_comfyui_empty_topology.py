"""
Unit test: a zero-device TopologySnapshot produces FailureKind.EMPTY_TOPOLOGY (spec 120 FR-013)
and comfyui_client is never invoked — checked before any comfyui-mcp call is made.
"""

import sys
from pathlib import Path
from unittest.mock import patch

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import pytest  # noqa: E402

import generation  # noqa: E402
from generation_model import FailureKind, GenerationFailure  # noqa: E402
from topology_model import SourceKind, TopologySnapshot  # noqa: E402


def test_empty_topology_stops_before_any_comfyui_call():
    snapshot = TopologySnapshot(snapshot_id="empty-1", source_kind=SourceKind.CML, devices=[], links=[])

    with patch("comfyui_client.get_status") as mock_get_status:
        with pytest.raises(GenerationFailure) as exc_info:
            generation.run_generation(snapshot)

    assert exc_info.value.kind == FailureKind.EMPTY_TOPOLOGY
    mock_get_status.assert_not_called()
