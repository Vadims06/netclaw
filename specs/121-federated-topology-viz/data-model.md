# Phase 1 Data Model: Federated AI-Augmented Network Topology Visualization

**Feature**: 121-federated-topology-viz | **Date**: 2026-08-30

This feature adds no new persistent storage (no database, no new files that must survive a
restart) — every entity below is an in-memory/on-the-wire shape passed between Border and the
`johns-risk/viz` member for the lifetime of one request, or a file written to the existing
`workspace/output/comfyui-topology-viz/` directory spec 120 already owns.

## Reused, unchanged (from spec 120 / spec 046)

- **`TopologySnapshot`** (`workspace/skills/comfyui-topology-viz/topology_model.py`): the input to
  the whole pipeline. Not modified — `federated_generation.py` (R8) consumes it exactly as
  `generation.run_generation()` already does.
- **`Device`, `Interface`, `Link`, `DeviceRole`, `OperationalState`, `SourceKind`**: unchanged.
- **`sanitize_metadata()` / `FORBIDDEN_METADATA_KEYS`**: unchanged — the new
  `render_structural` tool receives only the same sanitized snapshot shape spec 120 already
  produces; no new metadata path is introduced that could bypass this.

## New entities

### `StructuralRenderRequest` (Border → `topology-diagram-mcp/render_structural`, tool arguments)

| Field | Type | Notes |
|---|---|---|
| `snapshot_id` | string | From `TopologySnapshot.snapshot_id`, carried through for audit correlation |
| `devices` | list of `{hostname, role, state}` | Flattened from `TopologySnapshot.devices` |
| `links` | list of `{a, b, label}` | Flattened from `TopologySnapshot.links`, hostnames only (no interface config, no credentials — same sanitize boundary as spec 120) |

### `StructuralRenderResult` (`topology-diagram-mcp/render_structural` tool result → Border)

| Field | Type | Notes |
|---|---|---|
| `image_base64` | string | PNG bytes, base64-encoded (R6: inline transport) |
| `format` | string | Always `"png"` for v1 |
| `positions` | dict `{hostname: [x, y]}` | Canvas-space coordinates, so a future consumer (or a diagnostic) can correlate a label back to its device without re-deriving layout |
| `device_count` | int | Used by FR-002/SC-001 verification — must equal `len(snapshot.devices)` |

### `StyleRequest` (Border → `image-style-mcp/style_image`, tool arguments)

| Field | Type | Notes |
|---|---|---|
| `image_base64` | string | Stage A's `image_base64`, passed through unmodified |
| `style_prompt` | string | Built by the *existing* `prompt_builder.build_prompt()` / `_STYLE_SUFFIX` (spec 120, reused, not duplicated) — style-only language, never structural language (FR-003) |
| `negative_prompt` | string | The *existing* `prompt_builder.NEGATIVE_PROMPT` constant (spec 120, reused) |

### `StyleResult` (`image-style-mcp/style_image` tool result → Border)

| Field | Type | Notes |
|---|---|---|
| `styled_image_base64` | string | Final image bytes |
| `format` | string | `"png"` |

### `GenerationPath` (Key Entity from spec.md — response metadata, not a stored record)

| Field | Type | Values / Notes |
|---|---|---|
| `path` | enum | `"federated"` \| `"fallback"` \| `"federated_partial"` (Stage A succeeded, Stage B failed — FR-010's "offer the unstyled diagram" case) |
| `reason` | string, optional | Populated on `"fallback"`/`"federated_partial"`: e.g. `"johns-risk/viz unreachable"`, `"styling stage timeout"`, `"freeform request"` |
| `structural_member` | string, optional | `"johns-risk/viz"` when the federated path was attempted, absent on pure fallback |
| `styling_member` | string, optional | Same member as `structural_member` per R5, present under the same conditions |

This is attached to the existing sidecar JSON that spec 120's `output.py` already writes per
generated image (an additive field on the object `federated_generation.py` returns, not a schema
change inside `output.py` itself — see R8: `output.py` is not modified).

## Validation rules

- `StructuralRenderResult.device_count` MUST equal the count of devices in the request; a mismatch
  is treated as a Stage A failure (falls back per FR-009), never silently accepted (SC-001's "zero
  phantom devices").
- `StructuralRenderResult.image_base64` (decoded) size MUST be checked against a size ceiling before
  being handed to Stage B (transport bound, research.md R6); exceeding it is reported plainly, not
  silently truncated. This is distinct from the next rule — a small topology could still fail it if
  something else inflated the payload, and a large topology could pass it while still failing the
  next rule.
- **Separately**, `render_structural` MUST check `device_count` against a fixed density ceiling for
  the working canvas resolution (1024×1024, matching spec 120's proven working size) *before*
  rendering — this is the Edge Cases bullet on "a topology so large it exceeds what the styling stage
  can process at its working resolution": a topology can be well under the transport size cap and
  still be too visually dense (icons/labels too small/overlapping) for Stage B to preserve legibly.
  Exceeding this ceiling is reported plainly by `render_structural` itself (contracts/topology-diagram-mcp.md
  failure shape), before any Stage B call is attempted — not discovered downstream as a styling
  failure.
- `GenerationPath.path == "federated"` is only ever set when *both* stages completed successfully
  end to end — never inferred from "the member was reachable" alone (SC-003 requires this to be
  accurate per completed request, not per attempted request).

## State transitions (per request)

```
freeform request? ──yes──> fallback (spec 120, unchanged)
       │no
       ▼
johns-risk/viz reachable (n2n_member_health)? ──no──> fallback, reason="structural member unreachable"
       │yes
       ▼
render_structural succeeds? ──no──> fallback, reason="structural stage failed"
       │yes
       ▼
style_image succeeds? ──no──> federated_partial: return Stage A's unstyled diagram,
       │yes                    reason="styling stage failed/unreachable"
       ▼
federated: return styled image
```
