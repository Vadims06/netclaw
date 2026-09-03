"""
Federated generation orchestrator (spec 121). Routes each request between the federated path
(Stage A + Stage B, invoked via n2n/tools/call on the johns-risk/viz member) and spec 120's
existing fallback pipeline (generation.run_generation(), reused UNCHANGED — FR-012). This module
is the only new call site into spec 120's code (research.md R8); generation.py itself is never
modified.

Talks to the mesh daemon's HTTP API directly (not through the n2n-mcp MCP-stdio hop — research.md
R4a found a real client-side argument-coercion bug there during implementation).
"""

import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

import generation
import output
import prompt_builder
from generation_model import (
    FailureKind,
    GeneratedImage,
    GenerationFailure,
    GenerationRequest,
    GenerationStatus,
)
from topology_model import SourceKind, TopologySnapshot

logger = logging.getLogger("comfyui-topology-viz.federated_generation")

# Matches mcp-servers/n2n-mcp/server.py's BGP_DAEMON_API default exactly (research.md R4a).
_DAEMON_API = "http://127.0.0.1:8179"

# research.md R5: both stages run on the same, already-live member.
STRUCTURAL_MEMBER = "johns-risk/viz"
STYLING_MEMBER = "johns-risk/viz"

_STRUCTURAL_TOOL = "topology-diagram-mcp/render_structural"
_STYLING_TOOL = "image-style-mcp/style_image"

# A single in-flight guard for the FEDERATED path specifically (T035/FR-013) — separate variable
# from generation.py's own _job_in_flight (spec 120's, untouched) so the two guards compose:
# whichever path (federated or fallback) is running blocks the other, without either module
# reaching into the other's internals.
_federated_job_in_flight = False


@dataclass
class FederatedResult:
    """Wraps spec 120's GeneratedImage with the routing metadata FR-004/FR-004a require —
    additive, not a modification of GeneratedImage itself."""

    image: GeneratedImage
    generation_path: str  # "federated" | "fallback" | "federated_partial"
    reason: Optional[str] = None
    structural_member: Optional[str] = None
    styling_member: Optional[str] = None


class _FederationCallError(RuntimeError):
    pass


def _member_reachable(member_id: str) -> bool:
    """FR-009/FR-011 routing check — same reachability surface the HUD/CLI already use
    (research.md R4), just called from Python instead of an operator command."""
    try:
        response = httpx.get(f"{_DAEMON_API}/n2n/members/health", timeout=15.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("member health check failed for %s: %s", member_id, exc)
        return False
    for member in data.get("members", []):
        if member.get("member_id") == member_id:
            return member.get("state") == "active"
    return False


def _invoke_tool(peer: str, target_name: str, arguments: dict) -> dict:
    """POSTs directly to the daemon's /n2n/invoke (research.md R4a) — the same n2n/tools/call
    wire method FR-006 requires, just without the MCP-stdio hop's argument-coercion bug."""
    body = {
        "peer": peer,
        "target_type": "tool",
        "target_name": target_name,
        "arguments": arguments,
    }
    try:
        # 1830s to outlast N2N_TOOL_TIMEOUT_S=1800 (research.md R7, raised live during the FR-015
        # spike after a cold GGUF model load + real diffusion pass genuinely exceeded 600s) — the
        # client must never give up before the daemon's own timeout could.
        response = httpx.post(f"{_DAEMON_API}/n2n/invoke", json=body, timeout=1830.0)
        response.raise_for_status()
        envelope = response.json()
    except Exception as exc:
        raise _FederationCallError(f"{target_name} call to {peer} failed: {exc}") from exc

    if "error" in envelope:
        raise _FederationCallError(f"{target_name} on {peer} returned an error: {envelope['error']}")

    result = envelope.get("result", {})
    if result.get("isError"):
        raise _FederationCallError(f"{target_name} on {peer} reported isError: {result}")

    content = result.get("content", [])
    if not content:
        raise _FederationCallError(f"{target_name} on {peer} returned no content: {result}")

    try:
        return json.loads(content[0].get("text", "{}"))
    except (json.JSONDecodeError, TypeError) as exc:
        raise _FederationCallError(f"{target_name} on {peer} returned unparseable content: {exc}") from exc


def _snapshot_to_devices_links(snapshot: TopologySnapshot) -> tuple[str, str]:
    devices = [
        {"hostname": d.hostname, "role": d.role.value, "state": d.state.value if d.state else None}
        for d in snapshot.devices
    ]
    links = [
        {"a": link.endpoint_a.hostname, "b": link.endpoint_b.hostname, "label": link.label}
        for link in snapshot.links
    ]
    return json.dumps(devices), json.dumps(links)


def _run_stage_a(snapshot: TopologySnapshot) -> dict:
    devices_json, links_json = _snapshot_to_devices_links(snapshot)
    return _invoke_tool(
        STRUCTURAL_MEMBER,
        _STRUCTURAL_TOOL,
        {"snapshot_id": snapshot.snapshot_id, "devices": devices_json, "links": links_json},
    )


def _run_stage_b(image_base64: str, style_prompt: str, negative_prompt: str) -> dict:
    return _invoke_tool(
        STYLING_MEMBER,
        _STYLING_TOOL,
        {
            "image_base64": image_base64,
            "style_prompt": style_prompt,
            "negative_prompt": negative_prompt,
        },
    )


def _write_federated_image(
    snapshot: TopologySnapshot, image_bytes: bytes, model_used: str, request_id: str
) -> GeneratedImage:
    """Writes to spec 120's exact OUTPUT_DIR / sidecar convention (output.py's own directory and
    naming scheme), without calling into output.write_image() (which is ComfyUI-history-shaped,
    not bytes-shaped) — a small, additive writer matching the same conventions."""
    import json as _json
    from datetime import datetime, timezone
    from pathlib import Path

    output.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in request_id)
    dest_path = output.OUTPUT_DIR / f"federated-{timestamp}-{safe_id}.png"
    if dest_path.exists():
        raise GenerationFailure(
            FailureKind.GENERATION_JOB_FAILED, f"Refusing to overwrite an existing output file: {dest_path}"
        )
    dest_path.write_bytes(image_bytes)

    sidecar = {
        "request_id": request_id,
        "snapshot_source": snapshot.source_kind.value,
        "model_used": model_used,
        "generation_path": "federated",
        "structural_member": STRUCTURAL_MEMBER,
        "styling_member": STYLING_MEMBER,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    dest_path.with_suffix(dest_path.suffix + ".json").write_text(
        _json.dumps(sidecar, indent=2), encoding="utf-8"
    )

    return GeneratedImage(
        file_path=str(dest_path),
        generation_request_id=request_id,
        model_used=model_used,
        snapshot_source=snapshot.source_kind,
    )


def run_federated_generation(snapshot: TopologySnapshot) -> FederatedResult:
    """FR-001..FR-013: the routing decision matrix in data-model.md's state-transition diagram.

    Raises GenerationFailure only for conditions spec 120's own taxonomy already covers (empty
    topology, concurrency); every federation-specific failure degrades to the fallback path or
    federated_partial rather than raising, per Story 2's "still get a real image back" guarantee.
    """
    global _federated_job_in_flight

    if snapshot.is_empty():
        raise GenerationFailure(FailureKind.EMPTY_TOPOLOGY, "Topology snapshot has zero devices")

    if _federated_job_in_flight or generation._job_in_flight:
        raise GenerationFailure(
            FailureKind.GENERATION_ALREADY_IN_PROGRESS,
            "A generation request (federated or fallback) is already in progress",
        )

    request_id = f"fed-{snapshot.snapshot_id}"

    # FR-011: freeform has no real device data for Stage A to work from — route directly.
    if snapshot.source_kind == SourceKind.FREEFORM:
        image = generation.run_generation(snapshot)
        return FederatedResult(image=image, generation_path="fallback", reason="freeform request")

    # FR-009: structural member unreachable — fall back rather than attempt and fail.
    if not _member_reachable(STRUCTURAL_MEMBER):
        image = generation.run_generation(snapshot)
        return FederatedResult(
            image=image, generation_path="fallback",
            reason=f"{STRUCTURAL_MEMBER} unreachable", structural_member=STRUCTURAL_MEMBER,
        )

    _federated_job_in_flight = True
    try:
        try:
            stage_a_result = _run_stage_a(snapshot)
        except _FederationCallError as exc:
            logger.warning("Stage A failed on %s: %s", STRUCTURAL_MEMBER, exc)
            image = generation.run_generation(snapshot)
            return FederatedResult(
                image=image, generation_path="fallback",
                reason=f"structural stage failed: {exc}", structural_member=STRUCTURAL_MEMBER,
            )

        if stage_a_result.get("device_count") != len(snapshot.devices):
            image = generation.run_generation(snapshot)
            return FederatedResult(
                image=image, generation_path="fallback",
                reason="structural stage device count mismatch", structural_member=STRUCTURAL_MEMBER,
            )

        structural_image_b64 = stage_a_result["image_base64"]

        # FR-010: styling member unreachable — offer the correct unstyled Stage A diagram
        # rather than nothing (Edge Cases), distinct from a structural-member failure.
        if not _member_reachable(STYLING_MEMBER):
            image = _write_federated_image(
                snapshot, base64.b64decode(structural_image_b64), "topology-diagram-mcp (unstyled)", request_id
            )
            return FederatedResult(
                image=image, generation_path="federated_partial",
                reason=f"{STYLING_MEMBER} unreachable — delivering the unstyled structural diagram",
                structural_member=STRUCTURAL_MEMBER,
            )

        style_prompt = prompt_builder.build_prompt(snapshot)
        try:
            stage_b_result = _run_stage_b(structural_image_b64, style_prompt, prompt_builder.NEGATIVE_PROMPT)
        except _FederationCallError as exc:
            logger.warning("Stage B failed on %s: %s", STYLING_MEMBER, exc)
            image = _write_federated_image(
                snapshot, base64.b64decode(structural_image_b64), "topology-diagram-mcp (unstyled)", request_id
            )
            return FederatedResult(
                image=image, generation_path="federated_partial",
                reason=f"styling stage failed: {exc} — delivering the unstyled structural diagram",
                structural_member=STRUCTURAL_MEMBER,
            )

        styled_bytes = base64.b64decode(stage_b_result["styled_image_base64"])
        image = _write_federated_image(
            snapshot, styled_bytes, "topology-diagram-mcp + image-style-mcp", request_id
        )
        return FederatedResult(
            image=image, generation_path="federated",
            structural_member=STRUCTURAL_MEMBER, styling_member=STYLING_MEMBER,
        )
    finally:
        _federated_job_in_flight = False
