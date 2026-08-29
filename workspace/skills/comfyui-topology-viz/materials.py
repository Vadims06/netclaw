"""
Device-role inference for the ComfyUI network topology visualization skill.

Ported from workspace/skills/threejs-network-viz/materials.py (spec 046), trimmed to just
`infer_device_role` — the role/state COLOR tables (`DEVICE_TYPE_COLORS`, etc.) are a 3D-rendering
concept this feature has no use for (prompt_builder.py describes roles in words, not colors). See
specs/120-comfyui-topology-viz/research.md §5.
"""

import re

from topology_model import DeviceRole

DEVICE_ROLE_PATTERNS: dict[DeviceRole, list[str]] = {
    DeviceRole.ROUTER: [
        "rtr", "router", "cr", "er", "br", "core", "edge", "border",
        "isr", "asr", "csr", "nexus", "nxos",
    ],
    DeviceRole.SWITCH: [
        "sw", "switch", "ds", "as", "access", "distribution", "tor",
        "leaf", "spine", "catalyst", "n3k", "n5k", "n7k", "n9k",
        "ap", "wap", "wireless", "wlc", "wifi", "aruba", "meraki-ap",
        "air", "aironet",
    ],
    DeviceRole.FIREWALL: [
        "fw", "firewall", "asa", "ftd", "palo", "fortigate", "checkpoint",
        "srx", "pfsense", "pan", "fmc",
    ],
    DeviceRole.LOAD_BALANCER: [
        "lb", "f5", "bigip", "netscaler", "haproxy", "alb", "elb", "nlb",
        "avi", "citrix", "a10",
    ],
    DeviceRole.CLIENT: [
        "pc", "host", "server", "vm", "workstation", "laptop", "desktop",
        "srv", "node", "instance", "client",
    ],
}


def infer_device_role(hostname: str, model: str = "") -> DeviceRole:
    """Infer a DeviceRole from hostname/model text; UNCLASSIFIED is the explicit,
    always-used fallback, never omitted.

    Matches against whole alphanumeric TOKENS (split on any non-alphanumeric character), not a
    raw substring search — a naive substring search on a short pattern like "er" false-positives
    inside unrelated words. A token counts as a match if it equals a pattern exactly or starts
    with it (so "rtr1", "sw12", "isr4321" still match "rtr"/"sw"/"isr" as a prefix)."""
    search_text = f"{hostname} {model}".lower()
    tokens = re.findall(r"[a-z0-9]+", search_text)
    for role, patterns in DEVICE_ROLE_PATTERNS.items():
        for pattern in patterns:
            if any(token == pattern or token.startswith(pattern) for token in tokens):
                return role
    return DeviceRole.UNCLASSIFIED
