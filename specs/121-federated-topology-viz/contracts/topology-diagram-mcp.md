# Contract: `topology-diagram-mcp` (Stage A)

**New MCP server** registered as `topology-diagram-mcp` in `~/.openclaw/openclaw.json` and
`config/openclaw.json`, deployed so it is spawnable via stdio by both Border and any member sharing
this host (per research.md R2/R3). Invoked over the federation channel via `n2n/tools/call` with
`tool = "topology-diagram-mcp/render_structural"`, executed by whichever process receives the call
— in this feature, always the `johns-risk/viz` member (FR-005: Border never runs this in-process).

## Tool: `render_structural`

**Purpose**: Deterministically render a Topology Snapshot as a correct, role-iconed, labeled network
diagram — no diffusion model involved (FR-001).

### Arguments

```json
{
  "snapshot_id": "string",
  "devices": [{"hostname": "string", "role": "router|switch|firewall|load_balancer|client|unclassified", "state": "healthy|degraded|down|unknown|null"}],
  "links": [{"a": "hostname", "b": "hostname", "label": "string"}]
}
```

### Result (MCP `tools/call` result, `content[0].text` is this JSON)

Success:
```json
{
  "image_base64": "iVBORw0KG...",
  "format": "png",
  "positions": {"core1": [412.0, 300.0], "sw1": [612.0, 300.0]},
  "device_count": 2
}
```

Failure (oversized topology, N2G/CLI error, etc.) — returned as an MCP `isError: true` result so the
caller's existing `_call_tool_async`-style error handling (already proven in `comfyui_client.py`)
applies unchanged:
```json
{"content": [{"type": "text", "text": "{\"error\": \"...\"}"}], "isError": true}
```

### Failure modes (two distinct ceilings — data-model.md validation rules)

1. **Transport size**: the encoded PNG would exceed the federation channel's message cap
   (research.md R6). Checked after rendering.
2. **Working-resolution density**: `device_count` exceeds what the fixed 1024×1024 canvas can render
   legibly (Edge Cases: "a topology so large it exceeds what the styling stage can process at its
   working resolution"). Checked *before* rendering, independent of (1) — a topology can pass one
   check and fail the other.

Both fail the same way (an `isError: true` result), but the caller-side reason string reported to the
engineer (FR-010's spirit applied to Stage A) MUST distinguish which ceiling was hit.

### Guarantees (FR-002, FR-003 upstream requirement)

- Every device in `devices` appears exactly once, with role-appropriate iconography (N2G / draw.io
  `mxgraph.networks` stencil keyed off `role` — `unclassified` gets a generic-but-labeled box, never
  an unlabeled shape).
- Every link in `links` is rendered as a visible connection between its two endpoints.
- Every device's hostname is rendered as legible text (Pillow's native text rendering, not
  AI-reconstructed — this is the entire reason Stage A exists instead of spec 120's Canny approach;
  no Canny edge detection touches this image at any point, so spec 120's label-legibility workaround
  is not needed here).
- `device_count` in the result always equals `len(devices)` in the request, or the call fails
  outright rather than silently under-rendering (data-model.md validation rule).

### Non-goals

- No styling, coloring, or "cyberpunk" treatment of any kind — that is Stage B's job exclusively
  (`image-style-mcp`), enforced by keeping this tool's only inputs as structural data.
- No network device access of any kind (FR-014) — this tool only ever touches the snapshot already
  handed to it in the request; it makes no outbound calls to any live network device.
