# topology-diagram-mcp

Stage A of spec 121's federated topology visualization pipeline: deterministically renders a
Topology Snapshot (devices + links) as a correct, role-iconed, legibly-labeled network diagram —
no diffusion model involved. See
[specs/121-federated-topology-viz/contracts/topology-diagram-mcp.md](../../specs/121-federated-topology-viz/contracts/topology-diagram-mcp.md)
for the full wire contract, and
[specs/121-federated-topology-viz/research.md](../../specs/121-federated-topology-viz/research.md)
(R1-R3a) for why this exists as a separate MCP server rather than reusing the `drawio-diagram`
skill directly.

## Tools

| Tool | Description |
|---|---|
| `render_structural(snapshot_id, devices, links)` | Renders devices/links (JSON strings) to a PNG. Returns `{image_base64, format, positions, device_count}`. Raises on an empty/invalid topology, a device count over the working-resolution density ceiling (60), or an encoded size over the transport ceiling (10 MB). |

## Rendering approach

networkx (Kamada-Kawai layout) + Pillow (drawing) — the same dependency-free stack spec 120's
`workspace/skills/comfyui-topology-viz/topology_renderer.py` already uses in this environment. Each
device role gets a distinct, procedurally-drawn icon shape (circle=router, port-ticked rounded
rectangle=switch, brick-hatched rectangle=firewall, diamond=load_balancer, monitor glyph=client,
plain rounded rectangle=unclassified) rather than a generic unlabeled box. Hostnames are drawn as
real, legible text directly — no Canny edge detection is involved anywhere in this feature, so
spec 120's label-legibility workaround (burning labels onto the image *after* generation) does not
apply here; text can be drawn once, correctly, and stays that way.

research.md R3a documents why this is Pillow-based rather than N2G/draw.io-XML + the draw.io desktop
CLI as originally planned: the CLI isn't installed anywhere on this host and isn't installable
without interactive `sudo`, and N2G's `drawio_diagram` class has no rasterizer of its own.

## Environment variables

None. This server touches only the topology data it is given and produces image bytes — no network
device access, no credentials, no external service calls (FR-014).

## Transport

stdio, matching every other Python MCP server in this repo (FastMCP, `mcp.server.fastmcp`).

## Installation

```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
```

Registered in `config/openclaw.json` / `~/.openclaw/openclaw.json` as:
```json
{"command": "python3", "args": ["-u", "mcp-servers/topology-diagram-mcp/server.py"], "cwd": "/home/johncapobianco/netclaw"}
```
