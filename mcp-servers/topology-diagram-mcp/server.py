#!/usr/bin/env python3
"""
topology-diagram-mcp — Stage A of spec 121's federated topology visualization pipeline.

Deterministically renders a Topology Snapshot (devices + links) as a correct, role-iconed,
legibly-labeled network diagram. No diffusion model involved anywhere in this server — this is
the entire point of Stage A (see specs/121-federated-topology-viz/research.md R1-R3): structural
correctness comes from this deterministic renderer, never from a diffusion model reconstructing
structure from an edge map (the failure class spec 120's Canny+ControlNet pipeline had to work
around after the fact).

Rendering stack: networkx (Kamada-Kawai layout, same approach as spec 120's
workspace/skills/comfyui-topology-viz/topology_renderer.py) + Pillow (drawing). The original design
(research.md's now-superseded R3) called for N2G -> draw.io XML -> the draw.io desktop CLI for PNG
export; that path does not work headlessly on this host (no drawio CLI anywhere, N2G's
drawio_diagram class has no rasterizer of its own, and installing the graphviz system package needs
interactive sudo this session doesn't have). research.md R3a documents the correction: procedural
per-role icon shapes drawn directly with Pillow, reusing the exact dependency-free stack spec 120
already proved works in this environment.

Exposes exactly one tool: render_structural. See
specs/121-federated-topology-viz/contracts/topology-diagram-mcp.md for the wire contract.
"""

import base64
import io
import json
import math
from typing import Optional

import networkx as nx
from mcp.server.fastmcp import FastMCP
from PIL import Image, ImageDraw, ImageFont

mcp = FastMCP("topology-diagram-mcp")

CANVAS_SIZE = (1024, 1024)
_MARGIN = 120
_ICON_SIZE = 90
_LINE_WIDTH = 5
_LINE_FILL = (40, 40, 40)
_TEXT_FILL = (20, 20, 20)
_ICON_OUTLINE = (30, 30, 30)
_ICON_FILL = (255, 255, 255)

# Density ceiling (data-model.md rule 2 / Edge Cases: "a topology so large it exceeds what the
# styling stage can process at its working resolution"). At CANVAS_SIZE with _ICON_SIZE icons plus
# label text, more than this many devices on a Kamada-Kawai layout produces icon/label overlap
# severe enough that Stage B's edit pass cannot be expected to preserve individual devices legibly.
# Checked BEFORE rendering, independent of the transport-size check below (a topology can be well
# under one ceiling and still fail the other).
MAX_DEVICES_FOR_LEGIBILITY = 60

# Transport-size ceiling (data-model.md rule 1 / research.md R6). NCFED_MAX_MESSAGE is a 16 MB
# aggregate cap on the reassembled federation-channel message; base64 inflates raw bytes by ~33%,
# and the result JSON carries other fields too, so this leaves real headroom rather than cutting it
# close to the wire-level cap.
MAX_ENCODED_BYTES = 10 * 1024 * 1024

_VALID_ROLES = {"router", "switch", "firewall", "load_balancer", "client", "unclassified"}


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _build_graph(devices: list[dict], links: list[dict]) -> nx.Graph:
    graph = nx.Graph()
    for device in devices:
        graph.add_node(device["hostname"], role=device.get("role") or "unclassified")
    for link in links:
        a, b = link["a"], link["b"]
        if a in graph and b in graph:
            graph.add_edge(a, b)
    return graph


def _layout_positions(graph: nx.Graph) -> dict:
    """Same approach as spec 120's topology_renderer.py: Kamada-Kawai minimizes edge crossings
    for small topologies; spring_layout as a fallback if KK fails to converge."""
    if graph.number_of_nodes() <= 1:
        return {n: (0.5, 0.5) for n in graph.nodes}
    try:
        return nx.kamada_kawai_layout(graph)
    except Exception:
        return nx.spring_layout(graph, seed=42)


def _to_canvas_coords(pos: dict) -> dict[str, tuple[float, float]]:
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = (max_x - min_x) or 1.0
    span_y = (max_y - min_y) or 1.0
    usable_w = CANVAS_SIZE[0] - 2 * _MARGIN
    usable_h = CANVAS_SIZE[1] - 2 * _MARGIN
    canvas = {}
    for node, (x, y) in pos.items():
        cx = _MARGIN + (x - min_x) / span_x * usable_w
        cy = _MARGIN + (y - min_y) / span_y * usable_h
        canvas[node] = (cx, cy)
    return canvas


def _draw_router(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_ICON_FILL, outline=_ICON_OUTLINE, width=3)
    # Two crossing arrows inside — the conventional "router" glyph.
    draw.line([(cx - r * 0.5, cy - r * 0.5), (cx + r * 0.5, cy + r * 0.5)], fill=_ICON_OUTLINE, width=3)
    draw.line([(cx - r * 0.5, cy + r * 0.5), (cx + r * 0.5, cy - r * 0.5)], fill=_ICON_OUTLINE, width=3)


def _draw_switch(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    left, top, right, bottom = cx - r, cy - r * 0.6, cx + r, cy + r * 0.6
    draw.rounded_rectangle([left, top, right, bottom], radius=8, fill=_ICON_FILL, outline=_ICON_OUTLINE, width=3)
    # Port tick marks along the bottom edge — the conventional "switch" glyph.
    port_count = 6
    for i in range(port_count):
        px = left + (right - left) * (i + 0.5) / port_count
        draw.line([(px, bottom - 10), (px, bottom - 2)], fill=_ICON_OUTLINE, width=2)


def _draw_firewall(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    left, top, right, bottom = cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8
    draw.rectangle([left, top, right, bottom], fill=_ICON_FILL, outline=_ICON_OUTLINE, width=3)
    # Brick hatch fill — the conventional "firewall" glyph.
    row_h = (bottom - top) / 4
    for row in range(4):
        y = top + row * row_h
        offset = (row % 2) * (r * 0.4)
        x = left + offset
        while x < right:
            draw.line([(x, y), (x, y + row_h)], fill=_ICON_OUTLINE, width=1)
            x += r * 0.4
        draw.line([(left, y), (right, y)], fill=_ICON_OUTLINE, width=1)


def _draw_load_balancer(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(points, fill=_ICON_FILL, outline=_ICON_OUTLINE, width=3)


def _draw_client(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    screen_left, screen_top = cx - r * 0.8, cy - r * 0.7
    screen_right, screen_bottom = cx + r * 0.8, cy + r * 0.25
    draw.rectangle([screen_left, screen_top, screen_right, screen_bottom],
                    fill=_ICON_FILL, outline=_ICON_OUTLINE, width=3)
    stand_w = r * 0.3
    draw.rectangle([cx - stand_w / 2, screen_bottom, cx + stand_w / 2, screen_bottom + r * 0.25],
                    fill=_ICON_FILL, outline=_ICON_OUTLINE, width=2)
    base_w = r * 0.7
    draw.line([(cx - base_w / 2, screen_bottom + r * 0.25), (cx + base_w / 2, screen_bottom + r * 0.25)],
              fill=_ICON_OUTLINE, width=3)


def _draw_unclassified(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    draw.rounded_rectangle([cx - r * 0.8, cy - r * 0.5, cx + r * 0.8, cy + r * 0.5],
                            radius=6, fill=_ICON_FILL, outline=_ICON_OUTLINE, width=3)


_ROLE_DRAWERS = {
    "router": _draw_router,
    "switch": _draw_switch,
    "firewall": _draw_firewall,
    "load_balancer": _draw_load_balancer,
    "client": _draw_client,
    "unclassified": _draw_unclassified,
}


def render_diagram(devices: list[dict], links: list[dict]) -> tuple[bytes, dict[str, tuple[float, float]]]:
    """Returns (png_bytes, positions). Raises ValueError on the density ceiling (checked before any
    drawing happens, per data-model.md rule 2 / contracts/topology-diagram-mcp.md failure mode 2)."""
    if len(devices) > MAX_DEVICES_FOR_LEGIBILITY:
        raise ValueError(
            f"topology has {len(devices)} devices, exceeding the working-resolution density ceiling "
            f"of {MAX_DEVICES_FOR_LEGIBILITY} — too large to render legibly at {CANVAS_SIZE[0]}x"
            f"{CANVAS_SIZE[1]}"
        )

    graph = _build_graph(devices, links)
    positions = _to_canvas_coords(_layout_positions(graph))

    image = Image.new("RGB", CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(image)
    font = _load_font(18)

    for a, b in graph.edges:
        ax, ay = positions[a]
        bx, by = positions[b]
        draw.line([(ax, ay), (bx, by)], fill=_LINE_FILL, width=_LINE_WIDTH)

    r = _ICON_SIZE / 2
    for device in devices:
        hostname = device["hostname"]
        role = device.get("role") or "unclassified"
        if role not in _VALID_ROLES:
            role = "unclassified"
        cx, cy = positions[hostname]
        _ROLE_DRAWERS[role](draw, cx, cy, r)

        text_bbox = draw.textbbox((0, 0), hostname, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        label_y = cy + r + 8
        pad = 4
        draw.rectangle(
            [cx - text_w / 2 - pad, label_y - pad, cx + text_w / 2 + pad, label_y + text_h + pad],
            fill=(255, 255, 255, 220),
        )
        draw.text((cx - text_w / 2, label_y), hostname, fill=_TEXT_FILL, font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), positions


@mcp.tool()
async def render_structural(snapshot_id: str, devices: str, links: str) -> str:
    """Deterministically render a topology snapshot as a correct, role-iconed, labeled diagram.
    No diffusion model involved (spec 121 FR-001).

    Args:
        snapshot_id: identifier carried through for audit correlation
        devices: JSON string, list of {"hostname": str, "role": str, "state": str|null}
        links: JSON string, list of {"a": hostname, "b": hostname, "label": str}
    """
    device_list = json.loads(devices) if isinstance(devices, str) else devices
    link_list = json.loads(links) if isinstance(links, str) else links

    if not device_list:
        raise ValueError("devices list is empty — nothing to render")

    hostnames = {d["hostname"] for d in device_list}
    dup_check = [d["hostname"] for d in device_list]
    if len(dup_check) != len(set(dup_check)):
        raise ValueError("duplicate hostnames in devices list")
    for link in link_list:
        if link["a"] not in hostnames or link["b"] not in hostnames:
            raise ValueError(f"link references unknown device: {link}")

    png_bytes, positions = render_diagram(device_list, link_list)

    encoded = base64.b64encode(png_bytes).decode("ascii")
    if len(encoded) > MAX_ENCODED_BYTES:
        raise ValueError(
            f"rendered image ({len(encoded)} base64 bytes) exceeds the transport-size ceiling of "
            f"{MAX_ENCODED_BYTES} bytes — topology too large to hand off over the federation channel"
        )

    result = {
        "image_base64": encoded,
        "format": "png",
        "positions": {k: [v[0], v[1]] for k, v in positions.items()},
        "device_count": len(device_list),
    }
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run()
