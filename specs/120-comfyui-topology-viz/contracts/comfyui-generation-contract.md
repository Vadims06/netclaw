# Contract: TopologySnapshot → Generated Image (via `comfyui-mcp`)

This is the interface contract between `generation.py` (this skill's orchestration module) and the
vendored `comfyui-mcp` MCP server. It defines the required call sequence, the shape each call must
produce, and which failure at which step maps to which spec requirement. See data-model.md for the
entity shapes referenced here and research.md §4 for the rationale behind this sequence.

## Preconditions

- Exactly one `TopologySnapshot` (per data-model.md) is available as input, produced by the
  conversational orchestration layer exactly as it is for spec 046 (research.md §5).
- No other `Generation Request` for this skill's process is currently in `submitted` state
  (FR-009a) — checked before step 1 below runs at all.
- The input `TopologySnapshot` has at least one device (FR-013 `empty_topology`), and, if it came
  from a named live source, that source was actually reachable (FR-012 `source_unreachable`) — both
  checked before step 1 below runs at all, so an unreachable source or an empty topology never
  results in any call to `comfyui-mcp`.

## Call sequence

| Step | Call | Required on success | Failure → |
|---|---|---|---|
| 1 | `get_status` against the configured `COMFYUI_URL`, verifying the response's `comfyuiUrl`/`discoverySource` actually match what was configured (research.md §8 — `comfyui-mcp` silently port-scans past a misconfigured URL rather than failing) | Backend confirmed reachable AND confirmed to be the configured instance | `backend_unreachable` (FR-007) — stop, no further calls made, whether the failure is outright unreachability or a config-fidelity mismatch |
| 2 | `list_models` | At least one checkpoint-type entry usable for image generation | `no_usable_model` (FR-008) — stop, report what to install, no further calls made |
| 2a | (internal) deterministic selection over step 2's result | Exactly one `selected_checkpoint` chosen (FR-006a) | N/A — step 2 already guarantees non-empty input here |
| 3 | `search_templates(taskType: "txt2img", modelType: <family of selected_checkpoint>)` | At least one matching built-in template id | If none match a known family, treat as `no_usable_model` — the checkpoint exists but this feature cannot drive it |
| 4 | `get_template(templateId, parameters: {prompt: <prompt_text>, model: <selected_checkpoint>, ...})` | A populated, valid ComfyUI workflow JSON object | Malformed/rejected template response → `generation_job_failed` (treated as a ComfyUI-side failure, not a NetClaw bug, since the template is ComfyUI/`comfyui-mcp`-owned) |
| 5 | `run_workflow(workflow, sync: false, outputMode: "file", name: <request_id>)` | A `comfyui_task_id` returned immediately (this ID equals ComfyUI's own `promptId`, confirmed live) | Submission itself rejected → `generation_job_failed` (FR-009) |
| 6 | Poll ComfyUI's own `GET /history/{comfyui_task_id}` REST endpoint directly (`comfyui_client.get_prompt_history()`) at a short, fixed interval **with no maximum attempt count or wall-clock cutoff** — **not** `comfyui-mcp`'s `get_task_result`/`get_task`/`list_tasks`, which was live-verified to get permanently stuck reporting `"working"` for jobs ComfyUI itself had already completed (research.md §9) | The history entry is present with `status.completed: true` and `status.status_str: "success"`, carrying the output image's `filename`/`subfolder`/`type` | `status.status_str` present but not `"success"` → `generation_job_failed` (FR-009); this step never itself times out (Clarification session 2026-08-26) |
| 7 | `comfyui_client.download_image()` fetches the finished image directly from ComfyUI's own `GET /view` endpoint using the `filename`/`subfolder`/`type` from step 6 (not any path `comfyui-mcp` reports); `output.py` writes it to `workspace/output/comfyui-topology-viz/` plus a sidecar JSON (prompt, model, source) | New `Generated Image` record, distinct `file_path` (FR-003/FR-004) | Local write failure is a NetClaw-side I/O error, out of this contract's scope (same as any other file-write failure elsewhere in the repo) |

## Postconditions

- On any stop at steps 1–2, **no** `Generation Request` record ever reaches `pending`/`submitted` —
  the failure is reported directly (FR-007/FR-008), with zero ComfyUI-side job created.
- On success, exactly one new `Generated Image` file exists, and the engineer is told its path
  (FR-003) and which checkpoint was used (FR-006a).
- The single-in-flight guard (FR-009a) is released as soon as step 6 reaches any terminal state
  (completed or failed) — not before.

## Non-goals of this contract

- It does not define how `prompt_text` is composed (see research.md §6 / `prompt_builder.py`) —
  only that it is the `prompt` parameter passed at step 4.
- It does not cover video, multi-image, or any output type beyond one still image per request
  (out of scope per FR-016).
- It does not define retry behavior beyond the polling in step 6 — a `failed` terminal result is
  reported once and the engineer re-asks if they want another attempt, consistent with FR-009a
  never auto-queuing a second attempt.
