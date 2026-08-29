"""
ComfyUI network topology visualization skill (spec 119).

Top-level entry point: visualize_topology_via_comfyui(). Accepts the same normalized
{"devices": [...], "links": [...]} shape spec 046's threejs-network-viz skill already consumes
from NetClaw's conversational orchestration layer, tagged with either a "source_kind" (one of
sources.SourceKind's live-source values) or a "freeform_description" string (FR-010, FR-011).
"""

import generation
import sources
from generation_model import FailureKind, GeneratedImage, GenerationFailure
from topology_model import SourceKind


def visualize_topology_via_comfyui(topology_input: dict) -> GeneratedImage:
    """Raises GenerationFailure (generation_model.py) with a distinct FailureKind for every
    failure condition this feature defines — callers should catch it and report
    `exc.kind`/`exc.message` to the engineer rather than a generic error."""
    freeform_description = topology_input.get("freeform_description")
    if freeform_description:
        snapshot = sources.from_freeform(freeform_description)
    else:
        source_kind = topology_input.get("source_kind")
        adapter = sources._SOURCE_KIND_ADAPTERS.get(source_kind)
        if adapter is None:
            raise GenerationFailure(
                FailureKind.SOURCE_UNREACHABLE,
                f"Unrecognized or missing topology source_kind: {source_kind!r}",
            )
        try:
            snapshot = adapter(topology_input)
        except sources.SourceUnreachableError as exc:
            raise GenerationFailure(
                FailureKind.SOURCE_UNREACHABLE,
                f"Topology source {exc.source_kind!r} is unreachable or returned an error: {exc.detail}",
            ) from exc

    return generation.run_generation(snapshot)
