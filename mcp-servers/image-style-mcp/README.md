# image-style-mcp

Stage B of spec 121's federated topology visualization pipeline: applies an image-edit diffusion
model to Stage A's already-correct structural diagram, restyling its appearance without altering
structure. See
[specs/121-federated-topology-viz/contracts/image-style-mcp.md](../../specs/121-federated-topology-viz/contracts/image-style-mcp.md)
for the wire contract, and
[specs/121-federated-topology-viz/research.md](../../specs/121-federated-topology-viz/research.md)
(R5, R9) for why this talks to ComfyUI directly rather than through `comfyui-mcp`.

## Tools

| Tool | Description |
|---|---|
| `style_image(image_base64, style_prompt, negative_prompt="")` | Restyles the given PNG via an image-edit (not txt2img) ComfyUI workflow. Returns `{styled_image_base64, format}`. |

## Model status

Targets Qwen-Image-Edit-2509 (GGUF-quantized) — the FR-015 research spike's primary candidate.
`build_image_edit_workflow()`'s node graph uses node class names confirmed live against this
ComfyUI instance during spec 120 (`TextEncodeQwenImageEdit`, `ReferenceLatent`, `UnetLoaderGGUF`,
`CLIPLoaderGGUF`), but the exact input parameter wiring has **not** been re-verified against this
instance's live `/object_info` — ComfyUI was unreachable at `COMFYUI_URL` during this feature's
implementation. See `specs/121-federated-topology-viz/spike-findings.md` for the spike's actual
result once it has run; `MODEL_FILENAMES` in `server.py` may need updating to match whatever the
spike actually downloads (or its FLUX.2 [klein] 4B fallback, research.md R9).

## Environment variables

| Variable | Description |
|---|---|
| `COMFYUI_URL` | Base URL of the ComfyUI instance (e.g. `http://127.0.0.1:8000`), same variable spec 120's `comfyui-topology-viz` skill already uses (`.env.example`) |

No device credentials or device-configuration access of any kind (FR-014) — this server only ever
transforms image bytes it is given.

## Transport

stdio, matching every other Python MCP server in this repo (FastMCP, `mcp.server.fastmcp`).

## Installation

```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
```

Registered in `config/openclaw.json` / `~/.openclaw/openclaw.json` as:
```json
{"command": "python3", "args": ["-u", "mcp-servers/image-style-mcp/server.py"], "cwd": "/home/johncapobianco/netclaw", "env": {"COMFYUI_URL": "${COMFYUI_URL}"}}
```
