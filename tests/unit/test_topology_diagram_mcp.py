"""
Unit tests for mcp-servers/topology-diagram-mcp/server.py's render_diagram() (spec 121 FR-002,
data-model.md validation rules, research.md R3a).
"""

import importlib.util
import io
from pathlib import Path

import pytest
from PIL import Image

# Loaded by explicit file path under a unique module name (not sys.path + `import server`) —
# mcp-servers/image-style-mcp/ has its own, unrelated server.py, and a bare `import server` after
# a sys.path.insert collides between the two when both test modules are collected in one session.
_server_path = Path(__file__).parent.parent.parent / "mcp-servers" / "topology-diagram-mcp" / "server.py"
_spec = importlib.util.spec_from_file_location("topology_diagram_mcp_server", _server_path)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)

render_diagram = server.render_diagram
MAX_DEVICES_FOR_LEGIBILITY = server.MAX_DEVICES_FOR_LEGIBILITY


def _devices(n, role="router"):
    return [{"hostname": f"d{i}", "role": role} for i in range(n)]


def test_render_diagram_correct_device_count():
    devices = [
        {"hostname": "core1", "role": "router"},
        {"hostname": "sw1", "role": "switch"},
    ]
    links = [{"a": "core1", "b": "sw1", "label": ""}]
    png_bytes, positions = render_diagram(devices, links)
    assert len(positions) == 2
    assert set(positions.keys()) == {"core1", "sw1"}
    img = Image.open(io.BytesIO(png_bytes))
    assert img.format == "PNG"


def test_render_diagram_every_link_rendered_between_correct_endpoints():
    devices = [
        {"hostname": "core1", "role": "router"},
        {"hostname": "sw1", "role": "switch"},
        {"hostname": "fw1", "role": "firewall"},
    ]
    links = [
        {"a": "core1", "b": "sw1", "label": ""},
        {"a": "sw1", "b": "fw1", "label": ""},
    ]
    png_bytes, positions = render_diagram(devices, links)
    # Positions returned for every device that participates in a link, and every link's two
    # endpoints are both present — a link to a missing endpoint would KeyError in render_diagram.
    for link in links:
        assert link["a"] in positions
        assert link["b"] in positions


def test_render_diagram_role_to_icon_mapping_covers_every_role():
    for role in ("router", "switch", "firewall", "load_balancer", "client", "unclassified"):
        assert role in server._ROLE_DRAWERS


def test_render_diagram_unknown_role_does_not_crash():
    devices = [{"hostname": "mystery1", "role": "not_a_real_role"}]
    png_bytes, positions = render_diagram(devices, [])
    assert "mystery1" in positions


def test_render_diagram_density_ceiling_raises():
    devices = _devices(MAX_DEVICES_FOR_LEGIBILITY + 1)
    with pytest.raises(ValueError, match="density ceiling"):
        render_diagram(devices, [])


def test_render_diagram_at_density_ceiling_succeeds():
    devices = _devices(MAX_DEVICES_FOR_LEGIBILITY)
    png_bytes, positions = render_diagram(devices, [])
    assert len(positions) == MAX_DEVICES_FOR_LEGIBILITY
