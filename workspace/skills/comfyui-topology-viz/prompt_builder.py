"""
Composes a bounded-length ComfyUI generation prompt from a TopologySnapshot.

Unlike spec 046's 3D scene (which can render arbitrarily many labeled objects), a ComfyUI text
prompt is a natural-language string with practical length and usefulness limits — an image model
cannot meaningfully render hundreds of individually-labeled interfaces, and an overlong prompt
degrades generation quality more than it improves fidelity. So this summarizes (device-role
counts, notable role diversity, connectivity density) rather than exhaustively enumerating every
device/interface (FR-002, Edge Cases, research.md §6).

Relies entirely on topology_model.py's `sanitize_metadata` having already stripped
credentials/secrets/config content from every Device/Interface before this module ever sees them
(FR-015) — this module does not re-sanitize, it only describes role/hostname/state/connectivity.
"""

from collections import Counter

from topology_model import TopologySnapshot

# A prompt this long stops helping an image model and starts hurting it — bounded per
# research.md §6, not an arbitrary style preference.
_MAX_PROMPT_CHARS = 900

_ROLE_LABELS = {
    "router": "router",
    "switch": "switch",
    "firewall": "firewall",
    "load_balancer": "load balancer",
    "client": "client endpoint",
    "unclassified": "network device",
}

_STYLE_SUFFIX = (
    ", cyberpunk network diagram art style, neon cyan and magenta color palette, holographic glow, "
    "circuit-board grid background, futuristic HUD aesthetic, glowing data streams along "
    "connection lines, dramatic rim lighting, high contrast, ultra detailed digital art"
)

# Threaded through comfyui_client.build_controlnet_workflow's negative-conditioning node.
# Live-verified need (research.md §11): with no negative prompt at all, Flux hallucinated
# decorative dashboard clutter (fake gauge bars, garbled pseudo-text, random numerals) into the
# background — none of it requested, all of it noise competing with the actual topology.
NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, watermark, fake UI elements, gauges, meters, progress bars, "
    "dashboard widgets, illegible text, gibberish text, random numbers, extra unrelated icons, "
    "jpeg artifacts, oversaturated, washed out"
)


def _role_summary(snapshot: TopologySnapshot) -> str:
    counts = Counter(d.role.value for d in snapshot.devices)
    parts = []
    for role_value, count in counts.most_common():
        label = _ROLE_LABELS.get(role_value, role_value)
        noun = label if count == 1 else f"{label}s"
        parts.append(f"{count} {noun}")
    return ", ".join(parts)


def _connectivity_summary(snapshot: TopologySnapshot) -> str:
    device_count = len(snapshot.devices)
    link_count = len(snapshot.links)
    if link_count == 0:
        return "shown as standalone, unconnected devices"
    if device_count <= 1:
        return f"with {link_count} connection(s)"
    density = link_count / device_count
    if density < 0.8:
        return "sparsely interconnected"
    if density < 2.0:
        return "connected in a typical hierarchical network topology"
    return "densely interconnected, a highly meshed network topology"


def build_prompt(snapshot: TopologySnapshot) -> str:
    """FR-002: compose a generation input from the topology's actual devices, roles, and
    connections, so the resulting image is recognizably driven by that specific topology
    rather than a generic placeholder description."""
    role_summary = _role_summary(snapshot)
    connectivity = _connectivity_summary(snapshot)
    source_label = snapshot.source_label or snapshot.source_kind.value

    prompt = (
        f"A stylized visualization of a network topology from {source_label}, "
        f"consisting of {role_summary}, {connectivity}"
        f"{_STYLE_SUFFIX}"
    )

    if len(prompt) > _MAX_PROMPT_CHARS:
        prompt = prompt[: _MAX_PROMPT_CHARS - 1].rstrip() + "…"

    return prompt
