#!/usr/bin/env python3
"""
image-style-mcp — Stage B of spec 121's federated topology visualization pipeline.

Applies a true image-editing diffusion model to Stage A's already-correct structural diagram,
restyling its visual appearance (color, texture, lighting, background) without adding, removing,
or relabeling a device or connection (FR-003). Talks to ComfyUI directly over REST — NOT through
the vendored `comfyui-mcp` Node server — because spec 120's research (research.md §9 there) found
comfyui-mcp's own task tracker permanently stuck reporting "working" for jobs ComfyUI itself had
already completed; this server ports the same direct-REST approach spec 120's
comfyui_client.py already proved reliable (submit /prompt, poll /history/{id} directly, fetch
/view, upload /upload/image), rather than reintroducing a known-broken dependency (research.md R5).

Exposes exactly one tool: style_image. See
specs/121-federated-topology-viz/contracts/image-style-mcp.md for the wire contract.

MODEL STATUS: the workflow graph built by build_image_edit_workflow() below targets
Qwen-Image-Edit-2509 (GGUF-quantized) — the FR-015 research spike's primary candidate — using node
names confirmed live against this ComfyUI instance in spec 120's own research
(TextEncodeQwenImageEdit, ReferenceLatent, UnetLoaderGGUF, CLIPLoaderGGUF: all present per spec 120
research.md's object_info query). The exact node INPUT PARAMETER NAMES below are the well-documented
public ComfyUI Qwen-Image-Edit workflow shape, but have NOT been re-verified against this specific
instance's live /object_info (ComfyUI was unreachable at COMFYUI_URL during this implementation
session — see specs/121-federated-topology-viz/spike-findings.md). Re-verify the node inputs live
before trusting T018's spike result, and swap MODEL_FILENAMES if the actual downloaded GGUF
quantization uses different filenames.
"""

import base64
import json
import os
import random
import time
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("image-style-mcp")

_ENV_VAR = "COMFYUI_URL"

# FR-015 spike's primary candidate (research.md R9). Verified live against the real
# QuantStack/Qwen-Image-Edit-2509-GGUF and Comfy-Org/Qwen-Image_ComfyUI HuggingFace repos before
# downloading (FR-016) — real sizes: unet 13,065,746,976 B, clip 9,384,670,680 B,
# vae 253,806,246 B, both repos ungated, Apache-2.0. The text encoder is the standard safetensors
# file (loaded via CLIPLoader below), NOT a GGUF clip — this is the well-tested, documented
# community pattern (only the large diffusion unet benefits enough from GGUF quantization to be
# worth it; CLIPLoaderGGUF's own dropdown had zero Qwen-compatible files installed, confirming
# GGUF-clip isn't the standard path here). Update if the spike selects FLUX.2 [klein] 4B instead
# (R9 fallback).
MODEL_FILENAMES = {
    "unet": "Qwen-Image-Edit-2509-Q4_K_M.gguf",
    "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
    "vae": "qwen_image_vae.safetensors",
}

_POLL_INTERVAL_S = 2.0


class ComfyUIConfigError(RuntimeError):
    pass


class ComfyUIBackendUnreachable(RuntimeError):
    pass


def _configured_url() -> str:
    url = os.environ.get(_ENV_VAR, "").strip()
    if not url:
        raise ComfyUIConfigError(f"{_ENV_VAR} is not set — required external configuration")
    return url


def upload_image(image_bytes: bytes, filename: str) -> dict:
    """Ported from workspace/skills/comfyui-topology-viz/comfyui_client.py's proven direct
    /upload/image call."""
    configured_url = _configured_url()
    response = httpx.post(
        f"{configured_url}/upload/image",
        files={"image": (filename, image_bytes, "image/png")},
        data={"type": "input", "overwrite": "true"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def submit_prompt(workflow: dict) -> str:
    """POSTs directly to ComfyUI's own /prompt endpoint (not comfyui-mcp's run_workflow tool —
    research.md R5). Returns the prompt_id."""
    configured_url = _configured_url()
    client_id = f"image-style-mcp-{random.randint(0, 2**32 - 1)}"
    response = httpx.post(
        f"{configured_url}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30.0,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("node_errors"):
        raise ComfyUIBackendUnreachable(f"ComfyUI rejected the workflow: {body['node_errors']}")
    prompt_id = body.get("prompt_id")
    if not prompt_id:
        raise ComfyUIBackendUnreachable(f"/prompt did not return a prompt_id: {body}")
    return str(prompt_id)


def get_prompt_history(prompt_id: str) -> Optional[dict]:
    """Ported from comfyui_client.py's get_prompt_history — the authoritative completion check,
    queried directly against ComfyUI, never through comfyui-mcp's known-broken task tracker."""
    configured_url = _configured_url()
    response = httpx.get(f"{configured_url}/history/{prompt_id}", timeout=10.0)
    response.raise_for_status()
    history = response.json()
    return history.get(prompt_id)


def extract_image_ref(history_entry: dict) -> Optional[dict]:
    for node_output in history_entry.get("outputs", {}).values():
        images = node_output.get("images")
        if images:
            return images[0]
    return None


def download_image(filename: str, subfolder: str, image_type: str) -> bytes:
    configured_url = _configured_url()
    response = httpx.get(
        f"{configured_url}/view",
        params={"filename": filename, "subfolder": subfolder, "type": image_type},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.content


def _submit_and_poll(workflow: dict, timeout_s: float = 1700.0) -> bytes:
    """No fixed generation timeout beyond this generous outer bound (spec's own Assumption: no
    fixed timeout at either stage — this bound exists only to keep a truly wedged ComfyUI job from
    hanging the MCP call forever, well above any real generation time spec 120 observed)."""
    prompt_id = submit_prompt(workflow)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        entry = get_prompt_history(prompt_id)
        if entry is not None:
            status = entry.get("status", {})
            if status.get("completed") is True or extract_image_ref(entry):
                image_ref = extract_image_ref(entry)
                if image_ref is None:
                    raise ComfyUIBackendUnreachable(f"job {prompt_id} completed with no image output")
                return download_image(image_ref["filename"], image_ref.get("subfolder", ""), image_ref["type"])
            if status.get("status_str") == "error":
                raise ComfyUIBackendUnreachable(f"job {prompt_id} failed: {status}")
        time.sleep(_POLL_INTERVAL_S)
    raise ComfyUIBackendUnreachable(f"job {prompt_id} did not complete within {timeout_s}s")


def build_image_edit_workflow(uploaded_image: dict, style_prompt: str, negative_prompt: str) -> dict:
    """Qwen-Image-Edit-2509 GGUF image-to-image workflow — see the MODEL STATUS docstring at the
    top of this file. Structure-preserving: the source image is the diffusion starting point
    (via the reference-conditioning path), never a fresh txt2img generation, which is the entire
    reason Stage B can restyle without risking structural drift (FR-003)."""
    return {
        "37": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": MODEL_FILENAMES["unet"]}},
        "38": {"class_type": "CLIPLoader", "inputs": {"clip_name": MODEL_FILENAMES["clip"], "type": "qwen_image"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": MODEL_FILENAMES["vae"]}},
        "78": {"class_type": "LoadImage", "inputs": {"image": uploaded_image["name"], "upload": "image"}},
        "76": {
            "class_type": "TextEncodeQwenImageEdit",
            "inputs": {"clip": ["38", 0], "vae": ["39", 0], "image": ["78", 0], "prompt": style_prompt},
        },
        "77": {
            "class_type": "TextEncodeQwenImageEdit",
            "inputs": {"clip": ["38", 0], "vae": ["39", 0], "image": ["78", 0], "prompt": negative_prompt},
        },
        "79": {"class_type": "VAEEncode", "inputs": {"pixels": ["78", 0], "vae": ["39", 0]}},
        "80": {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": ["76", 0], "latent": ["79", 0]},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": random.randint(0, 2**32 - 1),
                "steps": 20,
                "cfg": 2.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                # Partial denoise preserves the source image's structure — this is an edit, not a
                # fresh generation (FR-003). research.md R9 spike note: 0.5 on a mostly-white,
                # sparse source image produced almost no visible stylization at all (labels/lines
                # perfectly preserved, but the style prompt had essentially no effect) — raised to
                # 0.75 to give the model enough room to actually apply style while ReferenceLatent
                # still anchors structure; re-verify against the spike's fidelity bar after this
                # change, don't assume it's still 100% at the higher value.
                "denoise": 0.75,
                "model": ["37", 0],
                "positive": ["80", 0],
                "negative": ["77", 0],
                "latent_image": ["79", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "image-style-mcp_styled", "images": ["8", 0]}},
    }


@mcp.tool()
async def style_image(image_base64: str, style_prompt: str, negative_prompt: str = "") -> str:
    """Restyle an already-correct structural diagram without altering its structure (spec 121
    FR-003). Never a fresh txt2img/Canny-reconstruction — always an image-edit pass starting from
    the given image.

    Args:
        image_base64: Stage A's rendered PNG, base64-encoded
        style_prompt: style-only language (color/texture/lighting/background) — built by the
            caller's existing prompt_builder.build_prompt(), never structural language
        negative_prompt: built by the caller's existing prompt_builder.NEGATIVE_PROMPT
    """
    image_bytes = base64.b64decode(image_base64)
    uploaded = upload_image(image_bytes, "stage_a_structural.png")
    workflow = build_image_edit_workflow(uploaded, style_prompt, negative_prompt)
    styled_bytes = _submit_and_poll(workflow)
    return json.dumps({"styled_image_base64": base64.b64encode(styled_bytes).decode("ascii"), "format": "png"})


if __name__ == "__main__":
    mcp.run()
