# Contract: `image-style-mcp` (Stage B)

**New MCP server** registered as `image-style-mcp`, deployed identically to
`topology-diagram-mcp` (research.md R2/R3/R5) — also executed by the `johns-risk/viz` member in this
feature's design (FR-008 decision, same member as Stage A). Invoked via `n2n/tools/call` with
`tool = "image-style-mcp/style_image"`.

## Tool: `style_image`

**Purpose**: Apply visual/stylistic restyling to an already-correct structural diagram, without ever
adding, removing, or relabeling a device or connection (FR-003).

### Arguments

```json
{
  "image_base64": "iVBORw0KG...",
  "style_prompt": "neon cyan and magenta color palette, holographic glow, circuit-board grid background...",
  "negative_prompt": "gauge, meter, dashboard UI, garbled text, ..."
}
```

`style_prompt`/`negative_prompt` are built Border-side by the existing, unmodified
`prompt_builder.build_prompt()` / `prompt_builder.NEGATIVE_PROMPT` (spec 120) and passed through —
this tool does not compose its own prompt language, keeping "what the image should look like" logic
in one place.

### Result

Success:
```json
{"styled_image_base64": "iVBORw0KG...", "format": "png"}
```

Failure (ComfyUI unreachable from this member, model not loaded, generation error, timeout within
the tool's own bound):
```json
{"content": [{"type": "text", "text": "{\"error\": \"...\"}"}], "isError": true}
```
A failure here is handled Border-side as the `"federated_partial"` path (data-model.md) — Stage A's
already-correct diagram is still offered to the engineer (FR-010), never discarded.

### Implementation notes (not part of the wire contract, recorded for the tasks phase)

- Talks to ComfyUI directly over REST (`/prompt`, `/history/{id}`, `/view`, `/upload/image`) from
  `COMFYUI_URL` in this member's own environment — ports spec 120's already-proven direct-REST
  approach (`comfyui_client.py`'s `get_prompt_history`/`download_image`/`upload_image`), not the
  `comfyui-mcp` Node server's task tracker (research.md R5: that tracker is known-broken).
- Uses the model selected by the FR-015 research spike (Qwen-Image-Edit-2509 GGUF, or FLUX.2
  [klein] 4B if the spike finds the first candidate fails the fidelity bar) as an image-edit
  workflow (image-to-image, preserving input structure) — never a fresh txt2img/Canny-reconstruction
  workflow, which is precisely the failure class this feature exists to remove.

### Non-goals

- No structural interpretation of the input image (no re-deriving device positions, no re-labeling)
  — it is treated as opaque pixels to restyle, trusting Stage A's correctness entirely (FR-003).
- No network device access of any kind (FR-014).
