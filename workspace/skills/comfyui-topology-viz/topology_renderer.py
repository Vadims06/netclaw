"""
Renders a TopologySnapshot as a deterministic, high-contrast black-on-white line diagram —
the "structure engine" step of the ControlNet pipeline. This is NOT AI-generated; it is a plain
geometric rendering (networkx for layout, Pillow for drawing) whose only job is to be clean
enough for ComfyUI's Canny node to extract sharp edges from. Flux+ControlNet then paints over
those edges, so structural accuracy (which device connects to which) comes from this renderer,
not from the diffusion model — the diffusion model no longer has to (and cannot be trusted to)
invent topology structure from a text description alone.

Deliberately draws NO hostname text (see label_overlay.py). Live-verified during implementation:
Canny edge detection on small in-box text is too lossy for Flux to reliably reconstruct exact
letters from — a real end-to-end run produced garbled nonsense ("fret", "svitch", "evrit")
instead of the actual hostnames. Real, legible labels are burned onto the FINAL generated image
deterministically instead, using the same positions this module computes (label_overlay.py).
"""

import io

import networkx as nx
from PIL import Image, ImageDraw

from topology_model import TopologySnapshot

CANVAS_SIZE = (1024, 1024)
BOX_WIDTH = 140
BOX_HEIGHT = 70

_MARGIN = 120
_LINE_WIDTH = 6
_BOX_LINE_WIDTH = 5


def _build_graph(snapshot: TopologySnapshot) -> nx.Graph:
    graph = nx.Graph()
    for device in snapshot.devices:
        graph.add_node(device.hostname, role=device.role.value)
    for link in snapshot.links:
        a, b = link.endpoint_a.hostname, link.endpoint_b.hostname
        if a in graph and b in graph:
            graph.add_edge(a, b)
    return graph


def _layout_positions(graph: nx.Graph) -> dict:
    """Kamada-Kawai spreads nodes more evenly than spring_layout for small topologies,
    minimizing edge crossings/overlaps — important since overlapping lines would confuse
    Canny edge detection into merging distinct connections."""
    if graph.number_of_nodes() <= 1:
        return {n: (0.5, 0.5) for n in graph.nodes}
    try:
        return nx.kamada_kawai_layout(graph)
    except Exception:
        return nx.spring_layout(graph, seed=42)


def _to_canvas_coords(pos: dict) -> dict:
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


def compute_positions(snapshot: TopologySnapshot) -> dict[str, tuple[float, float]]:
    """The same canvas-space (x, y) per hostname used by render_structure_image() below —
    exposed separately so label_overlay.py can place real text at matching coordinates on
    the final generated image without re-deriving the layout."""
    return _to_canvas_coords(_layout_positions(_build_graph(snapshot)))


def render_structure_image(snapshot: TopologySnapshot) -> bytes:
    """Returns PNG bytes: white background, black rectangles per device, black lines per
    link — a plain geometric diagram, not styled art, and deliberately textless (see module
    docstring)."""
    graph = _build_graph(snapshot)
    positions = compute_positions(snapshot)

    image = Image.new("RGB", CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(image)

    # Links first, so device boxes are drawn on top of any line endpoints touching them.
    for a, b in graph.edges:
        ax, ay = positions[a]
        bx, by = positions[b]
        draw.line([(ax, ay), (bx, by)], fill="black", width=_LINE_WIDTH)

    for x, y in positions.values():
        left, top = x - BOX_WIDTH / 2, y - BOX_HEIGHT / 2
        right, bottom = x + BOX_WIDTH / 2, y + BOX_HEIGHT / 2
        draw.rectangle([left, top, right, bottom], fill="white", outline="black", width=_BOX_LINE_WIDTH)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
