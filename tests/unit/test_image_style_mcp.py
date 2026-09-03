"""
Unit tests for mcp-servers/image-style-mcp/server.py's REST plumbing and workflow construction
(spec 121 FR-003, contracts/image-style-mcp.md). ComfyUI itself is mocked — these tests verify
this server's own logic (request/response shape, polling loop, error propagation), not a live
diffusion run (that's the FR-015 spike / live integration test's job).
"""

import base64
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

# Loaded by explicit file path under a unique module name — see test_topology_diagram_mcp.py's
# comment: mcp-servers/topology-diagram-mcp/ has its own, unrelated server.py.
_server_path = Path(__file__).parent.parent.parent / "mcp-servers" / "image-style-mcp" / "server.py"
_spec = importlib.util.spec_from_file_location("image_style_mcp_server", _server_path)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def test_build_image_edit_workflow_is_structure_preserving_not_txt2img():
    """The workflow must start from the source image (VAEEncode of the uploaded image feeds
    KSampler's latent_image), never an EmptySD3LatentImage/fresh-generation start — that
    distinction is the entire reason Stage B can restyle without risking structural drift."""
    workflow = server.build_image_edit_workflow({"name": "src.png"}, "cyberpunk style", "garbled text")
    latent_source_node = workflow["3"]["inputs"]["latent_image"][0]
    assert workflow[latent_source_node]["class_type"] == "VAEEncode"
    assert workflow["79"]["inputs"]["pixels"] == ["78", 0]
    assert workflow["78"]["inputs"]["image"] == "src.png"


def test_build_image_edit_workflow_passes_prompts_through():
    workflow = server.build_image_edit_workflow({"name": "src.png"}, "positive style text", "negative text")
    assert workflow["76"]["inputs"]["prompt"] == "positive style text"
    assert workflow["77"]["inputs"]["prompt"] == "negative text"


def test_extract_image_ref_finds_first_image_output():
    entry = {"outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}}}
    ref = server.extract_image_ref(entry)
    assert ref["filename"] == "out.png"


def test_extract_image_ref_returns_none_when_no_images():
    assert server.extract_image_ref({"outputs": {}}) is None


def test_submit_and_poll_returns_bytes_on_completion(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:8000")
    with patch.object(server, "submit_prompt", return_value="prompt-123"), \
         patch.object(server, "get_prompt_history", return_value={
             "status": {"completed": True},
             "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
         }), \
         patch.object(server, "download_image", return_value=b"PNGDATA"):
        result = server._submit_and_poll({"dummy": "workflow"}, timeout_s=5.0)
    assert result == b"PNGDATA"


def test_submit_and_poll_raises_on_comfyui_error_status(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:8000")
    with patch.object(server, "submit_prompt", return_value="prompt-123"), \
         patch.object(server, "get_prompt_history", return_value={"status": {"status_str": "error"}}):
        with pytest.raises(server.ComfyUIBackendUnreachable):
            server._submit_and_poll({"dummy": "workflow"}, timeout_s=5.0)


def test_configured_url_raises_when_unset(monkeypatch):
    monkeypatch.delenv("COMFYUI_URL", raising=False)
    with pytest.raises(server.ComfyUIConfigError):
        server._configured_url()
