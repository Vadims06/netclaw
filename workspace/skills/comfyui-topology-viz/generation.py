"""
Orchestrates one ComfyUI generation request end-to-end: model discovery -> deterministic
selection -> template/workflow composition -> async submission -> no-timeout polling to a
ComfyUI-reported terminal state -> image delivery. Implements the full call sequence in
contracts/comfyui-generation-contract.md and every FailureKind in generation_model.py's taxonomy.

FR-009a's single-in-flight-job guard is a module-level flag scoped to this process's lifetime
(research.md §7) — no persistent store is needed since an orphaned ComfyUI job on a NetClaw
restart could not be recovered by a durable lock either way.
"""

import uuid
from datetime import datetime, timezone

import httpx

import comfyui_client
import output
import prompt_builder
import sources
import topology_renderer
from generation_model import (
    FailureKind,
    GeneratedImage,
    GenerationFailure,
    GenerationRequest,
    GenerationStatus,
    ModelCheckStatus,
)
from topology_model import TopologySnapshot

_MODEL_INSTALL_ADVICE = (
    "install at least one Stable Diffusion 1.5, SDXL, or Flux checkpoint into ComfyUI's "
    "models/checkpoints directory (via ComfyUI Manager or a manual download), then ask again"
)

# FR-009a: at most one generation job in flight at a time for this skill's process.
_job_in_flight = False


def _new_request_id() -> str:
    return f"req-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}"


def resolve_and_validate_source(request_text: str, available_sources: list[str]) -> str:
    """FR-012: reclassify sources.py's SourceUnreachableError into the distinct,
    ComfyUI-independent source_unreachable failure. Called by __init__.py before this
    module's snapshot-consuming run_generation() — a snapshot cannot exist yet if source
    resolution itself failed."""
    try:
        return sources.resolve_source(request_text, available_sources)
    except sources.SourceUnreachableError as exc:
        raise GenerationFailure(
            FailureKind.SOURCE_UNREACHABLE,
            f"Topology source {exc.source_kind!r} is unreachable or returned an error: {exc.detail}",
        ) from exc


def _submit_and_poll(request: GenerationRequest) -> dict:
    """FR-009: no NetClaw-imposed timeout — loops until ComfyUI's OWN /history endpoint (not
    comfyui-mcp's task tracker) reports the job present with a terminal status.

    Live-verified during implementation: comfyui-mcp's get_task_result got permanently stuck
    reporting {"status": "working"} for a job ComfyUI itself had already completed successfully
    ~19 seconds earlier — its WebSocket completion listener never fired. Polling comfyui-mcp's
    own tracker (as originally designed) would have looped forever past a real, silent hang.
    ComfyUI's /history/{promptId} is the verified-reliable source of truth instead (research.md
    §9); comfyui-mcp's run_workflow taskId IS ComfyUI's own promptId (confirmed live)."""
    import time

    request.comfyui_task_id = comfyui_client.run_workflow(request.workflow, request.request_id)
    request.status = GenerationStatus.SUBMITTED

    while True:
        history_entry = comfyui_client.get_prompt_history(request.comfyui_task_id)
        if history_entry is not None:
            status = history_entry.get("status", {})
            if status.get("completed"):
                if status.get("status_str") == "success":
                    return history_entry
                raise GenerationFailure(
                    FailureKind.GENERATION_JOB_FAILED,
                    f"ComfyUI reported generation job {request.comfyui_task_id!r} failed: "
                    f"{status.get('status_str')!r} — {status.get('messages')}",
                )
        time.sleep(3)


def run_generation(snapshot: TopologySnapshot) -> GeneratedImage:
    """FR-001/FR-002: the happy-path orchestrator. Raises GenerationFailure with a distinct
    FailureKind for every failure condition (FR-007/008/009/009a/013)."""
    global _job_in_flight

    # FR-013: nothing to visualize — stop before any comfyui-mcp call is made.
    if snapshot.is_empty():
        raise GenerationFailure(
            FailureKind.EMPTY_TOPOLOGY,
            f"The {snapshot.source_kind.value} topology has zero devices — nothing to visualize.",
        )

    # FR-009a: reject a second request outright rather than queuing or running concurrently.
    if _job_in_flight:
        raise GenerationFailure(
            FailureKind.GENERATION_ALREADY_IN_PROGRESS,
            "A ComfyUI generation is already in progress — wait for it to finish (or fail) and ask again.",
        )

    # FR-007 (incl. research.md §8's config-fidelity check).
    try:
        comfyui_client.get_status()
    except comfyui_client.ComfyUIBackendUnreachable as exc:
        raise GenerationFailure(FailureKind.BACKEND_UNREACHABLE, str(exc)) from exc
    except comfyui_client.ComfyUIConfigError as exc:
        raise GenerationFailure(FailureKind.BACKEND_UNREACHABLE, str(exc)) from exc

    # research.md §11: prefer the structural (accurate-topology) ControlNet+Flux pipeline
    # whenever every required model is installed — plain txt2img (below) free-associates a
    # picture from the prompt text and cannot be trusted to render the actual topology
    # structure. Falls back to the simple path only when the ControlNet pipeline's models
    # aren't all present, preserving FR-008's graceful-degradation behavior.
    label_positions = None
    if comfyui_client.controlnet_available():
        request = GenerationRequest(
            request_id=_new_request_id(),
            snapshot_source=snapshot.source_kind,
            prompt_text=prompt_builder.build_prompt(snapshot),
            model_used="flux1-schnell-fp8.safetensors + ControlNet (structural)",
        )
        label_positions = topology_renderer.compute_positions(snapshot)
        structure_png = topology_renderer.render_structure_image(snapshot)
        uploaded = comfyui_client.upload_image(structure_png, f"{request.request_id}-structure.png")
        request.template_id = "controlnet_structural"
        request.workflow = comfyui_client.build_controlnet_workflow(
            request.prompt_text, uploaded, negative_text=prompt_builder.NEGATIVE_PROMPT
        )
    else:
        # FR-006/FR-006a/FR-008.
        availability = comfyui_client.check_model_availability()
        if availability.status != ModelCheckStatus.OK:
            raise GenerationFailure(
                FailureKind.NO_USABLE_MODEL,
                f"No usable image-generation checkpoint found on the configured ComfyUI instance — "
                f"{_MODEL_INSTALL_ADVICE}.",
            )

        request = GenerationRequest(
            request_id=_new_request_id(),
            snapshot_source=snapshot.source_kind,
            prompt_text=prompt_builder.build_prompt(snapshot),
            model_used=availability.selected_checkpoint,
        )

        templates = comfyui_client.search_templates(model_type="any", task_type="txt2img")
        if not templates:
            raise GenerationFailure(
                FailureKind.NO_USABLE_MODEL,
                f"ComfyUI has checkpoint {availability.selected_checkpoint!r} installed, but no "
                f"compatible text-to-image template is available — {_MODEL_INSTALL_ADVICE}.",
            )
        request.template_id = templates[0]["id"]
        request.workflow = comfyui_client.get_template(
            request.template_id,
            {"prompt": request.prompt_text, "checkpoint": availability.selected_checkpoint},
        )

    _job_in_flight = True
    try:
        history_entry = _submit_and_poll(request)
    except (comfyui_client.ComfyUIToolError, httpx.HTTPError) as exc:
        raise GenerationFailure(FailureKind.GENERATION_JOB_FAILED, str(exc)) from exc
    finally:
        _job_in_flight = False

    request.status = GenerationStatus.COMPLETED
    request.resolved_at = datetime.now(timezone.utc)
    return output.write_image(history_entry, request, label_positions=label_positions)
