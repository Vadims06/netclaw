"""
Client wrapper around the vendored `comfyui-mcp` server (mcp-servers/comfyui-mcp/, registered as
`comfyui-mcp` in config/openclaw.json). Same MCP-stdio-client pattern
workspace/skills/threejs-network-viz/assets.py already uses for `sketchfab-mcp-server` (`mcp`
SDK's ClientSession/stdio_client/StdioServerParameters), each call a short-lived subprocess —
correctness and testability over connection pooling, matching the established, working precedent.

Implements the call sequence in contracts/comfyui-generation-contract.md. See
specs/119-comfyui-topology-viz/research.md §4 and §8.
"""

import asyncio
import json
import logging
import os
import random
from pathlib import Path
from typing import Optional

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from generation_model import ModelAvailabilityCheck, ModelCheckStatus

logging.getLogger("mcp.client.stdio").setLevel(logging.CRITICAL)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SERVER_SCRIPT = _REPO_ROOT / "mcp-servers" / "comfyui-mcp" / "dist" / "index.js"

# comfyui-mcp's own built-in fallback defaults (8000 for ComfyUI Desktop, 8188 for a manual
# install) — never used here. FR-005 requires COMFYUI_URL be treated as required external
# configuration, not silently assumed.
_ENV_VAR = "COMFYUI_URL"

# The three checkpoint families comfyui-mcp's built-in templates recognize (research.md §3's
# "what to install" message, and search_templates' modelType enum).
_KNOWN_MODEL_FAMILIES = ("sd15", "sdxl", "flux")


class ComfyUIConfigError(RuntimeError):
    """Raised when COMFYUI_URL is unset — a NetClaw configuration error, not a runtime failure."""


class ComfyUIBackendUnreachable(RuntimeError):
    """FR-007: the configured COMFYUI_URL could not be reached, OR comfyui-mcp silently
    substituted a different instance than the one configured (research.md §8)."""


class ComfyUIToolError(RuntimeError):
    """A comfyui-mcp tool call itself reported isError=True."""


def _configured_url() -> str:
    url = os.environ.get(_ENV_VAR, "").strip()
    if not url:
        raise ComfyUIConfigError(
            f"{_ENV_VAR} is not set — required external configuration (FR-005), see .env.example"
        )
    return url


def _server_env(configured_url: str) -> dict:
    env = dict(os.environ)
    env[_ENV_VAR] = configured_url
    return env


async def _call_tool_async(tool_name: str, arguments: dict, configured_url: str):
    """Live-verified during implementation: comfyui-mcp sends trailing stdio traffic after a
    tool's JSON-RPC response (observed specifically after run_workflow — plausibly async-job
    progress/logging notifications on the same stdio channel). Returning from inside the nested
    `async with` blocks races that trailing traffic against session teardown, raising a spurious
    anyio.BrokenResourceError (wrapped in a BaseExceptionGroup) even though the real tool result
    was already received successfully — confirmed live: ComfyUI's own /history showed the
    submitted job completed successfully every time this was hit. So the result is captured
    BEFORE the `async with` blocks close, and a teardown-phase exception is only re-raised if we
    never actually got a result (research.md §9)."""
    params = StdioServerParameters(
        command="node", args=[str(_SERVER_SCRIPT)], env=_server_env(configured_url)
    )
    captured: dict = {}
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
                captured["value"] = (getattr(result, "isError", False), text)
    except* Exception:
        if "value" not in captured:
            raise
    return captured["value"]


def _call_tool(tool_name: str, arguments: dict) -> tuple[bool, str]:
    """Sync wrapper — this skill's callers are synchronous, matching the rest of the repo's
    non-async skill architecture (threejs-network-viz/assets.py)."""
    return asyncio.run(_call_tool_async(tool_name, arguments, _configured_url()))


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def get_status() -> dict:
    """FR-007: confirm the backend is reachable AND that it is actually the configured
    instance — comfyui-mcp was found to silently port-scan past a misconfigured COMFYUI_URL
    and connect to a different local ComfyUI instance instead of failing (research.md §8), so
    `comfyuiConnected: true` alone is not sufficient.

    Raises ComfyUIBackendUnreachable on any failure to confirm the configured endpoint."""
    configured_url = _configured_url()
    is_error, text = _call_tool("get_status", {})
    if is_error:
        raise ComfyUIBackendUnreachable(f"comfyui-mcp reported an error calling get_status: {text}")
    status = _parse_json(text)
    if not status.get("comfyuiConnected"):
        raise ComfyUIBackendUnreachable(f"ComfyUI is not connected at {configured_url}")
    reported_url = status.get("comfyuiUrl")
    discovery_source = status.get("discoverySource")
    if reported_url != configured_url or discovery_source != "environment":
        raise ComfyUIBackendUnreachable(
            f"Configured COMFYUI_URL ({configured_url}) was not reachable; comfyui-mcp instead "
            f"connected to a different instance ({reported_url!r}, discovered via "
            f"{discovery_source!r}) rather than the one configured. Treating this as unreachable "
            f"rather than silently generating against the wrong ComfyUI instance."
        )
    return status


def list_models(model_type: str = "checkpoints") -> list[str]:
    """Raw checkpoint-name list for the given comfyui-mcp model type filter."""
    is_error, text = _call_tool("list_models", {"type": model_type})
    if is_error:
        raise ComfyUIToolError(f"list_models failed: {text}")
    parsed = _parse_json(text)
    names = parsed.get(model_type, [])
    return [str(n) for n in names] if isinstance(names, list) else []


def check_model_availability() -> ModelAvailabilityCheck:
    """FR-006: query installed checkpoints before generation is ever attempted. FR-006a:
    select one deterministically when more than one is usable (lexicographically first,
    so selection is stable and reproducible across runs)."""
    checkpoints = sorted(list_models("checkpoints"))
    if not checkpoints:
        return ModelAvailabilityCheck(
            available_checkpoints=[], selected_checkpoint=None, status=ModelCheckStatus.NO_USABLE_MODEL
        )
    return ModelAvailabilityCheck(
        available_checkpoints=checkpoints,
        selected_checkpoint=checkpoints[0],
        status=ModelCheckStatus.OK,
    )


def search_templates(model_type: str = "any", task_type: str = "txt2img") -> list[dict]:
    is_error, text = _call_tool(
        "search_templates", {"modelType": model_type, "taskType": task_type}
    )
    if is_error:
        raise ComfyUIToolError(f"search_templates failed: {text}")
    return _parse_json(text).get("results", [])


def get_template(template_id: str, parameters: dict) -> dict:
    is_error, text = _call_tool(
        "get_template", {"templateId": template_id, "parameters": parameters}
    )
    if is_error:
        raise ComfyUIToolError(f"get_template({template_id!r}) failed: {text}")
    parsed = _parse_json(text)
    workflow = parsed.get("workflow")
    if not workflow:
        raise ComfyUIToolError(f"get_template({template_id!r}) returned no workflow: {text}")
    return workflow


def run_workflow(workflow: dict, name: str) -> str:
    """Submits async (sync=False) — returns a task id immediately rather than blocking on
    GPU-bound generation time (FR-009's no-fixed-timeout requirement is only honest if the
    submission itself never blocks; see research.md §4)."""
    is_error, text = _call_tool(
        "run_workflow",
        {
            "workflow": workflow,
            "sync": False,
            "outputMode": "file",
            "imageFormat": "png",
            "name": name,
        },
    )
    if is_error:
        raise ComfyUIToolError(f"run_workflow submission failed: {text}")
    parsed = _parse_json(text)
    task_id = parsed.get("taskId") or parsed.get("id")
    if not task_id:
        raise ComfyUIToolError(f"run_workflow did not return a task id: {text}")
    return str(task_id)


def get_task_result(task_id: str) -> dict:
    """One poll attempt against comfyui-mcp's OWN task tracker. Retained for diagnostics only
    — DO NOT poll completion off this alone. Live-verified during implementation: comfyui-mcp's
    task tracker got permanently stuck reporting {"status": "working"} for a real job that had
    already completed successfully in ComfyUI itself ~19 seconds earlier (research.md §9). Its
    WebSocket completion listener silently failed to update the task record. See
    get_prompt_history() below for the actual polling source of truth."""
    is_error, text = _call_tool("get_task_result", {"taskId": task_id})
    if is_error:
        return {"status": "pending", "raw_error": text}
    return _parse_json(text)


def get_prompt_history(prompt_id: str) -> Optional[dict]:
    """Queries ComfyUI's OWN /history/{prompt_id} REST endpoint directly — bypassing
    comfyui-mcp's task tracker entirely, since that tracker was found live to get stuck
    reporting "working" forever for jobs ComfyUI itself had already completed (research.md §9).
    comfyui-mcp's own run_workflow returns a taskId that IS ComfyUI's promptId (confirmed live:
    get_task's response includes "promptId" equal to the taskId passed in), so this is a valid,
    authoritative completion check for a job submitted via run_workflow.

    Returns the history entry dict ({"prompt": [...], "outputs": {...}, "status": {...}}) once
    ComfyUI has it recorded, or None while the job is still queued/running (a not-yet-present
    prompt_id returns {} from ComfyUI, confirmed live — HTTP 200, not 404)."""
    configured_url = _configured_url()
    response = httpx.get(f"{configured_url}/history/{prompt_id}", timeout=10.0)
    response.raise_for_status()
    history = response.json()
    return history.get(prompt_id)


def extract_image_ref(history_entry: dict) -> Optional[dict]:
    """Walks a completed history entry's `outputs` for the first node that produced images
    (ComfyUI's real, live-verified shape: outputs.<node_id>.images[].{filename,subfolder,type})."""
    for node_output in history_entry.get("outputs", {}).values():
        images = node_output.get("images")
        if images:
            return images[0]
    return None


def download_image(filename: str, subfolder: str, image_type: str) -> bytes:
    """Downloads the finished image straight from ComfyUI's own /view endpoint — bypassing
    comfyui-mcp's outputMode/file-path reporting entirely, which this feature no longer relies
    on for delivery (research.md §9)."""
    configured_url = _configured_url()
    response = httpx.get(
        f"{configured_url}/view",
        params={"filename": filename, "subfolder": subfolder, "type": image_type},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.content


def upload_image(image_bytes: bytes, filename: str) -> dict:
    """Uploads an image directly to ComfyUI's own /upload/image endpoint (bypassing
    comfyui-mcp, which has no image-upload tool) — used to feed the structure renderer's
    output (topology_renderer.py) into a ControlNet workflow as the LoadImage/Canny source.
    Returns {"name": ..., "subfolder": ..., "type": ...} — the same shape a LoadImage node's
    `image` input expects."""
    configured_url = _configured_url()
    response = httpx.post(
        f"{configured_url}/upload/image",
        files={"image": (filename, image_bytes, "image/png")},
        data={"type": "input", "overwrite": "true"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def controlnet_available() -> bool:
    """Whether a Flux base model, its text encoders/VAE, and a ControlNet are all installed —
    the structural (accurate-topology) generation path (research.md §10) is only used when
    every piece is present; otherwise generation.py falls back to the plain SDXL/txt2img path."""
    unet = set(list_models("unet"))
    clip = set(list_models("clip"))
    vae = set(list_models("vae"))
    controlnet = set(list_models("controlnet"))
    return bool(
        {"flux1-schnell-fp8.safetensors", "flux1-dev-fp8.safetensors"} & unet
        and {"t5xxl_fp8_e4m3fn.safetensors", "t5xxl_fp16.safetensors"} & clip
        and "clip_l.safetensors" in clip
        and "ae.safetensors" in vae
        and controlnet
    )


def build_controlnet_workflow(prompt_text: str, uploaded_image: dict, negative_text: str = "") -> dict:
    """Adapts comfyui-mcp's own verified "Flux ControlNet (Community)" example workflow
    (research.md §4) — swapping its single-file CheckpointLoaderSimple for the split
    UNETLoader/DualCLIPLoader/VAELoader nodes matching the files this feature actually
    installs, and its static LoadImage source for the freshly-uploaded structure render.

    `negative_text` (prompt_builder.NEGATIVE_PROMPT) suppresses the decorative dashboard/gauge
    hallucination clutter found live when this was left empty (research.md §11)."""
    controlnet_name = next(iter(set(list_models("controlnet"))), "instantx_flux_canny.safetensors")
    return {
        "20u": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-schnell-fp8.safetensors", "weight_dtype": "default"}},
        "20c": {
            "class_type": "DualCLIPLoader",
            "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"},
        },
        "20v": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "17": {
            "class_type": "LoadImage",
            "inputs": {"image": uploaded_image["name"], "upload": "image"},
        },
        "18": {
            "class_type": "Canny",
            "inputs": {"low_threshold": 0.2, "high_threshold": 0.3, "image": ["17", 0]},
        },
        "15": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": controlnet_name}},
        "23": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["20c", 0]},
        },
        "26": {
            "class_type": "FluxGuidance",
            "inputs": {"guidance": 3.5, "conditioning": ["23", 0]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_text, "clip": ["20c", 0]},
        },
        "14": {
            "class_type": "ControlNetApplySD3",
            "inputs": {
                "strength": 0.65,
                "start_percent": 0,
                "end_percent": 1,
                "positive": ["26", 0],
                "negative": ["7", 0],
                "control_net": ["15", 0],
                "vae": ["20v", 0],
                "image": ["18", 0],
            },
        },
        "28": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": random.randint(0, 2**32 - 1),
                "steps": 4,
                "cfg": 1,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1,
                "model": ["20u", 0],
                "positive": ["14", 0],
                "negative": ["14", 1],
                "latent_image": ["28", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["20v", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ComfyUI_MCP_structural", "images": ["8", 0]}},
    }
