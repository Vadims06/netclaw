"""
File delivery for the ComfyUI network topology visualization skill.

Downloads the completed image directly from ComfyUI's own /view endpoint (via
comfyui_client.download_image()), using the image reference from ComfyUI's own /history entry —
not comfyui-mcp's reported file path, which this feature no longer relies on for delivery
(research.md §9: comfyui-mcp's own task/file-path reporting proved unreliable in practice).
Writes NetClaw's own persistent, timestamped copy (FR-003), never overwriting a prior result
(FR-004), plus a small sidecar JSON recording the prompt and checkpoint used, mirroring
workspace/skills/threejs-network-viz/output.py's write_scene() pattern.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import comfyui_client
import label_overlay
from generation_model import FailureKind, GenerationFailure, GenerationRequest, GeneratedImage

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "comfyui-topology-viz"

_EXTENSION_BY_TYPE = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "webp": ".webp"}


def write_image(
    history_entry: dict,
    request: GenerationRequest,
    label_positions: Optional[dict[str, tuple[float, float]]] = None,
) -> GeneratedImage:
    """FR-003/FR-004: write a distinctly-named, timestamped copy of the completed image
    (never overwriting an existing file) plus a sidecar JSON, and return a GeneratedImage.

    `history_entry` is ComfyUI's own /history/{promptId} entry (live-verified shape:
    outputs.<node_id>.images[].{filename,subfolder,type}), not anything comfyui-mcp reports.

    `label_positions` (topology_renderer.compute_positions()'s output) is passed only by the
    structural ControlNet path — when present, real hostname labels are burned onto the image
    deterministically via label_overlay.py rather than trusting the diffusion model to have
    rendered legible text (research.md §11 — it doesn't, reliably)."""
    image_ref = comfyui_client.extract_image_ref(history_entry)
    if image_ref is None:
        raise GenerationFailure(
            FailureKind.GENERATION_JOB_FAILED,
            f"ComfyUI reported the job complete, but its history entry has no image output: "
            f"{history_entry!r}",
        )

    image_bytes = comfyui_client.download_image(
        filename=image_ref["filename"],
        subfolder=image_ref.get("subfolder", ""),
        image_type=image_ref.get("type", "output"),
    )
    if label_positions:
        image_bytes = label_overlay.overlay_labels(image_bytes, label_positions)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.request_id)
    suffix = Path(image_ref["filename"]).suffix or ".png"
    dest_path = OUTPUT_DIR / f"comfyui-{timestamp}-{safe_id}{suffix}"

    if dest_path.exists():
        raise GenerationFailure(
            FailureKind.GENERATION_JOB_FAILED,
            f"Refusing to overwrite an existing output file: {dest_path}",
        )
    dest_path.write_bytes(image_bytes)

    sidecar = {
        "request_id": request.request_id,
        "snapshot_source": request.snapshot_source.value,
        "prompt_text": request.prompt_text,
        "model_used": request.model_used,
        "template_id": request.template_id,
        "comfyui_prompt_id": request.comfyui_task_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    dest_path.with_suffix(dest_path.suffix + ".json").write_text(
        json.dumps(sidecar, indent=2), encoding="utf-8"
    )

    return GeneratedImage(
        file_path=str(dest_path),
        generation_request_id=request.request_id,
        model_used=request.model_used,
        snapshot_source=request.snapshot_source,
    )
