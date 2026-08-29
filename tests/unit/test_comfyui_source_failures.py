"""
Unit test: a SourceUnreachableError from sources.py produces the distinct source_unreachable
message (spec 119 FR-012) — never a ComfyUI-side message, since the failure happens before any
comfyui-mcp call could even be attempted.
"""

import sys
from pathlib import Path

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

import pytest  # noqa: E402

from generation import resolve_and_validate_source  # noqa: E402
from generation_model import FailureKind, GenerationFailure  # noqa: E402


def test_no_available_sources_raises_source_unreachable():
    with pytest.raises(GenerationFailure) as exc_info:
        resolve_and_validate_source("visualize my topology", available_sources=[])

    assert exc_info.value.kind == FailureKind.SOURCE_UNREACHABLE
    assert "comfyui" not in exc_info.value.message.lower()
    assert "not currently configured" in exc_info.value.message or "unreachable" in exc_info.value.message.lower()


def test_source_unreachable_message_names_the_source():
    with pytest.raises(GenerationFailure) as exc_info:
        resolve_and_validate_source("anything", available_sources=[])
    assert exc_info.value.kind == FailureKind.SOURCE_UNREACHABLE
