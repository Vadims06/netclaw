# Phase 1 Data Model: ComfyUI Network Topology Visualization

Entities marked **(ported from 046)** are copied, unmodified in shape, from
`workspace/skills/threejs-network-viz/topology_model.py` — see research.md §5 for why this is a
port rather than a cross-package import. Entities marked **NEW** are introduced by this feature.

## TopologySnapshot **(ported from 046)**

The complete set of devices, roles, and connections assembled for a single visualization request,
regardless of whether it came from a live source or a freeform description. Fields: `source_kind`
(`SourceKind`), `devices: list[Device]`, `links: list[Link]`, `retrieved_at`. This feature consumes
the same `TopologySnapshot` spec 046 already defines — it is this feature's sole input, produced by
the conversational orchestration layer exactly as it is for 046 (research.md §5).

## Device / Interface / Link / SourceKind / OperationalState **(ported from 046)**

Unchanged from 046's canonical types. This feature trims the *asset-resolution* concepts 046 needs
for 3D rendering (`AssetKind`, `ProceduralShape`, `ModelSource`, `Device Asset`) since a still image
has no equivalent per-device asset-selection step — the whole snapshot is summarized into one prompt
(see `Generation Request` below), not rendered device-by-device.

## Generation Request — NEW

The composed description and parameters sent to `comfyui-mcp` for one visualization ask, derived
from exactly one `TopologySnapshot`.

| Field | Type | Notes |
|---|---|---|
| `request_id` | string | Generated per request; used for the output filename and sidecar JSON |
| `snapshot_source` | `SourceKind` | Carried through from the input `TopologySnapshot` (FR-002) |
| `prompt_text` | string | Bounded-length natural-language description built by `prompt_builder.py` (research.md §6) |
| `model_used` | string | The checkpoint name selected by the Model Availability Check (FR-006a) |
| `template_id` | string | The `comfyui-mcp` built-in template id chosen by `search_templates` (research.md §4) |
| `workflow` | object (opaque) | The populated ComfyUI workflow JSON returned by `get_template`, passed to `run_workflow` unmodified |
| `comfyui_task_id` | string \| null | Set once `run_workflow(..., sync: false)` returns; equals ComfyUI's own `promptId` (confirmed live) — used to poll `GET /history/{id}` directly, not `comfyui-mcp`'s task tracker (research.md §9) |
| `status` | enum: `pending` \| `submitted` \| `completed` \| `failed` | Tracked via polling `get_task_result` against ComfyUI's own status (FR-009) — never a NetClaw-imposed timeout state |
| `submitted_at` / `resolved_at` | timestamp | For the sidecar JSON and any future troubleshooting |

**Lifecycle**: `pending` (composed, not yet submitted) → `submitted` (task id received) →
`completed` | `failed` (terminal, as reported by ComfyUI). No NetClaw-side timeout transition exists
in this state machine, per Clarification session 2026-08-26.

**Invariant (FR-009a)**: At most one `Generation Request` may be in `submitted` state at a time for
this skill's process. A new request arriving while one is `submitted` is rejected before it is ever
composed into a `pending` record — it never enters this state machine at all.

## Model Availability Check — NEW

The result of querying the ComfyUI backend for installed checkpoints/models before generation is
attempted (FR-006).

| Field | Type | Notes |
|---|---|---|
| `checked_at` | timestamp | |
| `available_checkpoints` | list[string] | Raw result of `list_models` filtered to checkpoint-type entries |
| `selected_checkpoint` | string \| null | Deterministically chosen when `available_checkpoints` is non-empty (FR-006a); `null` when empty |
| `status` | enum: `ok` \| `backend_unreachable` \| `no_usable_model` | Drives which of FR-007/FR-008 fires, if any |

**Note**: As of this planning session's live verification (research.md §3), `status` for the
currently-configured ComfyUI instance evaluates to `no_usable_model` — `available_checkpoints` is
empty. This is expected, real, current behavior, not a bug to fix in this feature.

## Generated Image — NEW

The completed still image returned by ComfyUI for one `Generation Request`.

| Field | Type | Notes |
|---|---|---|
| `file_path` | path | Under `workspace/output/comfyui-topology-viz/`, timestamped and uniquely named (FR-003) |
| `generation_request_id` | string | Foreign key to the `Generation Request` that produced it |
| `model_used` | string | Copied from the `Generation Request` for standalone traceability of the sidecar JSON |
| `snapshot_source` | `SourceKind` | Copied from the `Generation Request` |
| `created_at` | timestamp | |

**Invariant (FR-003/FR-004)**: Every completed `Generation Request` produces exactly one new
`Generated Image` record with a distinct `file_path`; an existing file at that path is never
overwritten, and no two requests ever share a `file_path`.

## Generation Failure — NEW (typed error taxonomy)

Not a persisted entity — the return/exception shape `generation.py` uses to give the engineer the
distinct, specific messages FR-007/FR-008/FR-009/FR-009a/FR-012/FR-013 each require.

| `kind` | Fires when | Required spec FR |
|---|---|---|
| `backend_unreachable` | ComfyUI endpoint cannot be reached | FR-007 |
| `no_usable_model` | Reachable, but `Model Availability Check.status == no_usable_model` | FR-008 |
| `generation_job_failed` | ComfyUI itself reports the submitted job errored | FR-009 |
| `generation_already_in_progress` | A `Generation Request` is already `submitted` | FR-009a |
| `source_unreachable` | The named live topology source is unreachable or errors | FR-012 |
| `empty_topology` | The input `TopologySnapshot` has zero devices | FR-013 |

Each `kind` maps to a distinct, human-readable message — never a generic "something went wrong,"
satisfying SC-003's "100% of ... conditions produce a specific, distinguishable message."
